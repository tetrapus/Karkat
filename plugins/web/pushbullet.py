import socket
import json
import time
import threading
import ssl
import requests
from functools import partial

from bot.events import Callback, command, msghandler
from util.text import Buffer, pretty_date, ircstrip
from util.files import Config
from util.services import url
from util.images import image_search
from util.irc import Address

# TODO:
# digests
# highlight notifications
# self-awareness
# server accounts

ACTIVITY_TIMEOUT = 60*5

HEADERS = ("GET /websocket/%(key)s HTTP/1.1\r\n"
          "Host: stream.pushbullet.com\r\n"
          "User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:34.0) Gecko/20100101 Firefox/34.0\r\n"
          "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n"
          "Accept-Language: en-US,en;q=0.5\r\n"
          "Accept-Encoding: gzip, deflate\r\n"
          "Sec-WebSocket-Version: 13\r\n"
          "Sec-WebSocket-Key: VwQcElXiDe4ZsgAPdAur0g==\r\n"
          "Connection: keep-alive, Upgrade\r\n"
          "Pragma: no-cache\r\n"
          "Cache-Control: no-cache\r\n"
          "Upgrade: websocket\r\n"
          "\r\n")

def cstrip(text):
    if text.startswith(":"): return text[1:]
    return text

class WebSocket(object):
    def __init__(self, sock, buff=b''):
        self.buff = buff
        self.sock = sock

    def __iter__(self):
        return self

    def read(self, bytes):
        while len(self.buff) < bytes:
            data = self.sock.recv(1024)
            if not data:
                raise StopIteration
            self.buff += data
        ret, self.buff = self.buff[:bytes], self.buff[bytes:]
        return ret

    def __next__(self):
        self.read(1) # throw away first byte
        length = ord(self.read(1)) # assume mask bit is zero
        return json.loads(self.read(length).decode("utf-8"))

class PushListener(threading.Thread):
    def __init__(self, token, update_hook):
        self.sock = ssl.wrap_socket(socket.socket())
        self.listening = True
        self.last = time.time()
        self.token = token
        self.update = update_hook
        self.buffer = Buffer()
        self.ws = None
        self.retries = 0
        self.connect()
        self.decapitate()
        super().__init__()

    def connect(self):
        self.sock.connect(("stream.pushbullet.com", 443))
        self.sock.send((HEADERS % {"key": self.token}).encode("ascii"))

    def decapitate(self):
        while self.buffer.append(self.sock.recv(4096)):
            for line in self.buffer:
                if not line:
                    self.ws = WebSocket(self.sock, self.buffer.buffer)
                    return

    def run(self):
        try:
            for evt in self.ws:
                if not self.listening:
                    break
                self.dispatch(evt)
        except:
            # exponential backoff
            time.sleep(2**self.retries)
            self.retries += 1
            self.sock = ssl.wrap_socket(socket.socket())
            self.connect()
            self.decapitate()
            self.run()

    def dispatch(self, evt):
        if evt["type"] == "tickle":
            self.update()
        self.last = time.time()
                    
def push_bounce(push, sender, email):
    new_push = dict([(k,v) for k, v in push.items() if k in ["file_name", "file_type", "file_url", "title", "body", "type"]])
    body = []
    if new_push["type"] == "file":
        if "title" in new_push:
            new_push["title"] = "%s via PushBullet: %s" % (sender, new_push["title"])
        else:
            new_push["title"] = "%s via PushBullet" % sender

    if "title" in new_push: body.append(new_push["title"])
    if "body" in new_push: body.append(new_push["body"])

    if new_push["type"] != "file":
        new_push["title"] = "%s via PushBullet" % sender
    if body: new_push["body"] = "\n\n".join(body) 
    new_push["email"] = email
    return new_push


def push_text(push):
    fields = []
    if push["type"] in ["note", "link", "file"]:
        message_field = []
        if "file_url" in push:
            fields.append(url.format(url.shorten(push["file_url"])))
        if "title" in push:
            message_field.append("\x0303%s\x03" % push["title"])
        if "body" in push:
            message_field.append(push["body"].replace("\n", " · ")) # TODO: temporary
        if message_field:
            fields.append(" ".join(message_field))
        if "url" in push:
            try:
                fields.append(url.format(url.shorten(push["url"])))
            except:
                fields.append(url.format(push["url"]))
    elif push["type"] == "address":
        if "name" in push:
            fields.append("\x0303 📍 %s\x03" % push["name"])
        if "address" in push:
            fields.append(push["address"])
    return " · ".join(fields)

def push_format(push, sent, users):
    fields = []
    body = push_text(push)
    if body: fields.append(body)

    if push["iden"] in sent:
        sent.remove(push["iden"])
        tag, email = "to", push["receiver_email"]
    else:
        tag, email = "from", push["sender_email"]
    if email.lower() in users:
        user = users[email.lower()]
    else:
        user = "\x0303" + email + "\x03"

    fields.append(tag + " " + user)
    timedelta = pretty_date(time.time() - push["modified"])
    if timedelta != "just now":
        fields.append("\u231a " + timedelta)
    
    return "03│ ⁍ │ " + " · ".join(fields)

class PushBullet(Callback):
    def __init__(self, server):
        self.server = server
        self.configf = server.get_config_dir("pushbullet.json")
        self.config = Config(self.configf, default={"accounts":{}, "users":{}})
        self.usersettingsf = server.get_config_dir("pushbullet_settings.json")
        self.usersettings = Config(self.usersettingsf, default={})
        self.bouncefmt = "\x0303· \x02%(nick)s\x0f\x0f: %(body)s \x0315· via mobile"
        self.listeners = []
        self.skip = set()
        self.sent = set()
        self.pushlock = threading.Lock()
        self.watchers = {}
        self.channels = {}
        self.active = {}
        self.rejoin_ignore = {}
        self.lower = server.lower
        self.listen()
        for channel, account in self.config["accounts"].items():
            try:
                self.channels[channel] = requests.get("https://api.pushbullet.com/v2/users/me", headers={"Authorization": "Bearer " + account["token"]}).json()
            except:
                pass
        super().__init__(server)

    def listen(self):
        for channel, account in self.config["accounts"].items():
            self.listeners.append(PushListener(account["token"], partial(self.update, channel)))
        for listener in self.listeners:
            listener.start()

    def update(self, account):
        acc = self.config["accounts"][account]
        params = {"modified_after": acc["last"]}
        headers = {"Authorization": "Bearer " + acc["token"]}
        watchers = self.watchers.setdefault(self.lower(account), set())
        req = requests.get("https://api.pushbullet.com/v2/pushes", params=params, headers=headers)
        pushes = req.json()["pushes"]
        if not pushes:
            return
        for push in pushes:
            sender_email = push["sender_email"].lower()
            with self.pushlock:
                if push["iden"] in self.skip:
                    self.skip.remove(push["iden"])
                elif push.get("body", "").startswith(".highlight"):
                    if sender_email in self.config["users"]:
                        nick = self.config["users"][sender_email]
                        settings = self.usersettings.get(self.lower(account), [])
                        if " " in push["body"]: word = push["body"].split(" ", 1)[-1]
                        else: word = nick
                        pattern = [word, sender_email]
                        if pattern in settings:
                            settings.remove(pattern)
                            hlconfirm = {"type": "note", "email": sender_email, "title": "* %r removed from alerts." % word}
                            self.skip.add(self.push(hlconfirm, acc["token"]))
                        else:
                            settings.append(pattern)
                            hlconfirm = {"type": "note", "email": sender_email, "title": "* %r added to alerts." % word}
                            self.skip.add(self.push(hlconfirm, acc["token"]))
                        self.usersettings[self.lower(account)] = settings
                # Handle user joins
                elif push.get("body", "") == ".join":
                    if sender_email in self.config["users"]:
                        nick = self.config["users"][sender_email]
                        self.server.message("03│ ⁍ │ %s has joined the conversation via pushbullet." % nick, account)
                        watchers.add(sender_email)
                        push_join = {"type": "note", "title": "* %s has joined via PushBullet" % nick}
                        actives = {"type": "note", "email": push["sender_email"], "title": "* Now listening to %s" % account}
                        ausers = [k for k, v in self.active.setdefault(self.lower(account), {}).items() if time.time() - v < ACTIVITY_TIMEOUT]
                        if ausers:
                            actives["body"] = "Active users:\n%s" % (", ".join(ausers))
                        for email in watchers:
                            if email.lower() != sender_email:
                                push_join["email"] = email
                                self.skip.add(self.push(push_join, acc["token"]))
                        self.skip.add(self.push(actives, acc["token"]))
                elif push.get("body", "") == ".part":
                    if sender_email in watchers:
                        nick = self.config["users"][sender_email]
                        self.server.message("03│ ⁍ │ %s has stopped listening to the conversation." % nick, account)
                        watchers.remove(sender_email)
                        push_part = {"type": "note", "title": "* %s is no longer receiving updates via PushBullet" % nick}
                        partconfirm = {"type": "note", "email": push["sender_email"], "title": "* No longer listening to %s" % account}
                        for email in watchers:
                            if email.lower() != sender_email:
                                push_part["email"] = email
                                self.skip.add(self.push(push_part, acc["token"]))
                        self.skip.add(self.push(partconfirm, acc["token"]))
                else:
                    display_sender = self.config["users"].get(sender_email, push["sender_email"])
                    for email in watchers:
                        if email.lower() != sender_email:
                            self.skip.add(self.push(push_bounce(push, display_sender, email), acc["token"]))
                    if push["iden"] not in self.sent:
                        @command("reply", r"(?:(https?://\S+|:.+?:))?\s*(.*)")
                        def pushreply(server, message, link, text, push=push):
                            user = push["sender_email"]
                            return self.send_push.funct(self, server, message, user, link, text)
                        self.server.reply_hook = pushreply
                    if sender_email in watchers:
                        self.server.message(self.bouncefmt % {"nick": display_sender, "body": push_text(push)}, account)
                    else:
                        self.server.message(push_format(push, self.sent, self.config["users"]), account)

            acc["last"] = max(push["modified"], acc["last"])
        self.save(account, acc)


    def save(self, channel, account):
        with self.config as conf:
            conf["accounts"][channel] = account

    def queue(self, push):
        pass

    @command("setpush", "(.+@.+)")
    def set_push(self, server, msg, email):
        with self.config as conf:
            conf["users"][email.lower()] = msg.address.nick
        return "03│ ⁍ │ Associated %s with pushbullet account %s." % (msg.address.nick, email)

    @command("pushassoc", r"(#\S+)\s+(\S+)", admin=True)
    def add_channel(self, server, msg, channel, token):
        account = {"token": token, "last": time.time()}
        with self.config as conf:
            conf["accounts"][server.lower(channel)] = account
        listener = PushListener(account["token"], partial(self.update, channel))
        self.listeners.append(listener)
        listener.start()
        self.channels[channel] = requests.get("https://api.pushbullet.com/v2/users/me", headers={"Authorization": "Bearer " + token}).json()
        return "03│ ⁍ │ Done."

    @command("help", r"(?:(\S+)\s+)?pushbullet")
    def pushbullet_info(self, server, msg, user):
        try:
            acc = self.config["accounts"][self.lower(msg.context)]
            email = self.channels[self.lower(msg.context)]["email"]
        except KeyError:
            return "04│ ⁍ │ This channel has no associated pushbullet."

        steps = ["Go to https://www.pushbullet.com/add-friend", 
                 "Add %s (%s) as a friend" % (msg.context, email), 
                 "Visit https://www.pushbullet.com/?email=%s and send your first push to the channel!" % email]
        if user:
            user_email = self.get_user(user)
            if user not in self.config["users"]:
                steps = ["If you don't have an account: Set up an account at http://www.pushbullet.com/ and install pushbullet on your devices", "Type /msg %s .setpush EMAIL_ADDRESS" % server.nick] + steps
        else:
            return "03│ ⁍ │ Type .setpush \x02email\x02, then go to 12https://www.pushbullet.com/add-friend\x0f and add \x0303%s\x03 as a friend." % email            
        if user_email is None:
            return "03│ ⁍ │ %s: type .setpush \x02email\x02, then go to 12https://www.pushbullet.com/add-friend\x0f and add \x0303%s\x03 as a friend." % (user, email)
        else:
            with self.pushlock:
                self.sent.add(self.push({"type" : "link", 
                           "title": "Add %s on PushBullet" % msg.context,
                           "body" : "\r\n".join("%d) %s" % (i+1, s) for i, s in enumerate(steps)),
                           "link" : "https://www.pushbullet.com/add-friend",
                           "email": user_email}, 
                          acc["token"]))
            return "03│ ⁍ │ I've sent instructions to %s's pushbullet address." % user
        
        
    @command("send", r"(\S+(?:,\s*\S+)*)(?:\s+(https?://\S+|:.+?:))?(?:\s+(.+))?")
    def send_push(self, server, msg, user, link, text):
        try:
            acc = self.config["accounts"][server.lower(msg.context)]
        except KeyError:
            return

        push = {}

        user = self.get_user(user)
        if user is None:
            return "03│ ⁍ │ %s has not associated their pushbullet." % user

        push["title"] = msg.address.nick + ":"

        if link:
            if link.startswith(":"):
                link = image_search(link[1:-1])[0]["url"] 
            push["url"] = link
            push["type"] = "link"
        else:
            push["type"] = "note"
        if text:
            push["body"] = text
        push["email"] = user
        with self.pushlock:
            self.sent.add(self.push(push, acc["token"]))

    @msghandler
    def update_watchers(self, server, msg):
        ctx = server.lower(msg.context)
        # update 
        user = server.lower(msg.address.nick)
        self.active.setdefault(ctx, {})[user] = time.time()
        highlighted = []
        if ctx not in self.config["accounts"]: return
        acc = self.config["accounts"][ctx]
        if ctx in self.watchers:
            watchers = self.watchers[ctx]
            push = {"type": "note"}
            if msg.text.startswith("\x01ACTION ") and msg.text.endswith("\x01"):
                push["body"] = "* %s %s" % (msg.address.nick, ircstrip(msg.text[8:-1]))
            else:
                push["body"], push["title"] = ircstrip(msg.text), msg.address.nick
            for email in watchers:
                if any(email == target and word.lower() in ircstrip(msg.text)
                       for word, target in self.usersettings.get(ctx, [])):
                    hlpush = {"type": "note", "email": email, "body": push["body"]}
                    if "title" in push:
                        hlpush["title"] = "🔔 " + push["title"]
                    else:
                        hlpush["title"] = "🔔 Highlight from " + msg.address.nick
                    with self.pushlock:
                        self.skip.add(self.push(hlpush, acc["token"]))
                    highlighted.append(email)
                else:
                    push["email"] = email
                    with self.pushlock:
                        self.skip.add(self.push(push, acc["token"]))
        for word, email in self.usersettings.get(ctx, []):
            if email not in highlighted and word.lower() in ircstrip(msg.text):
                push = {"type": "note", "title": "🔔 Highlight from %s" % msg.address.nick, "body": ircstrip(msg.text), "email":email}
                with self.pushlock:
                    self.skip.add(self.push(push, acc["token"]))

    ## Channel state tracking

    def update_active_quit(self, server, line) -> "quit":
        words = line.split(" ", 2)
        nick = Address(words[0]).nick
        lnick = server.lower(nick)
        requires_updates = []
        for channel in self.active:
            if lnick in self.active[channel]:
                if time.time() - self.active[channel][lnick] < ACTIVITY_TIMEOUT:
                    requires_updates.append(channel)
                else:
                    self.rejoin_ignore.setdefault(channel, {})[lnick] = time.time()
                del self.active[channel][lnick]
        # Update watchers
        push = {"type": "note", "title": "* %s has disconnected" % nick, "body": cstrip(words[-1])}
        for channel in requires_updates:
            ctx = server.lower(channel)
            if ctx in self.watchers and ctx in self.config["accounts"]:
                acc = self.config["accounts"][ctx]
                watchers = self.watchers[ctx]
                for email in watchers:
                    push["email"] = email
                    with self.pushlock:
                        self.skip.add(self.push(push, acc["token"]))


    def update_active_part(self, server, line) -> "part":
        words = line.split(" ", 3)
        nick = Address(words[0]).nick
        lnick = server.lower(nick)
        channel = server.lower(words[2])
        push = {"type": "note", "title": "* %s has left the channel" % nick, "body": cstrip(words[-1])}
        if lnick in self.active[channel]:
            if (time.time() - self.active[channel][lnick] < ACTIVITY_TIMEOUT
                and channel in self.watchers 
                and channel in self.config["accounts"]):
                # Update watchers
                acc = self.config["accounts"][channel]
                watchers = self.watchers[channel]
                for email in watchers:
                    push["email"] = email
                    with self.pushlock:
                        self.skip.add(self.push(push, acc["token"]))
            del self.active[channel][lnick]

    def update_active_nick(self, server, line) -> "nick":
        words = line.split(" ", 2)
        nick = Address(words[0]).nick
        lnick = server.lower(nick)
        newnick = words[2]
        requires_updates = []
        for channel in self.active:
            if lnick in self.active[channel]:
                if time.time() - self.active[channel][lnick] < ACTIVITY_TIMEOUT:
                    requires_updates.append(channel)
                del self.active[channel][lnick]
                self.active[channel][server.lower(newnick)] = time.time()
        # Update watchers
        push = {"type": "note", "title": "* %s is now known as %s" % (nick, newnick)}
        for channel in requires_updates:
            ctx = server.lower(channel)
            if ctx in self.watchers and ctx in self.config["accounts"]:
                acc = self.config["accounts"][ctx]
                watchers = self.watchers[ctx]
                for email in watchers:
                    push["email"] = email
                    with self.pushlock:
                        self.skip.add(self.push(push, acc["token"]))

    def update_active_join(self, server, line) -> "join":
        words = line.split(" ", 3)
        nick = Address(words[0]).nick
        lnick = server.lower(nick)
        channel = server.lower(cstrip(words[2]))
        push = {"type": "note", "title": "* %s has joined the channel" % nick}
        if ((lnick not in self.rejoin_ignore.setdefault(channel, {})
            or (time.time() - self.rejoin_ignore[channel][lnick]) > ACTIVITY_TIMEOUT)
            and channel in self.watchers 
            and channel in self.config["accounts"]):
            # Update watchers
            acc = self.config["accounts"][channel]
            watchers = self.watchers[channel]
            for email in watchers:
                push["email"] = email
                with self.pushlock:
                    self.skip.add(self.push(push, acc["token"]))
        if lnick in self.rejoin_ignore[channel]:
            del self.rejoin_ignore[channel][lnick]
        self.active.setdefault(channel, {})[lnick] = time.time()

    def update_active_kick(self, server, line) -> "kick":
        words = line.split(" ", 4)
        kicker = Address(words[0]).nick
        nick = words[3]
        lnick = server.lower(nick)
        channel = server.lower(words[2])
        push = {"type": "note", "title": "* %s has kicked %s from %s" % (kicker, nick, words[2]), "body": cstrip(words[-1])}
        if (channel in self.watchers 
            and channel in self.config["accounts"]):
            # Update watchers
            acc = self.config["accounts"][channel]
            watchers = self.watchers[channel]
            for email in watchers:
                push["email"] = email
                with self.pushlock:
                    self.skip.add(self.push(push, acc["token"]))
        if lnick in self.active[channel]:
            del self.active[channel][lnick]


    def push(self, push, token):
        headers = {"Authorization": "Bearer " + token}
        response = requests.post("https://api.pushbullet.com/v2/pushes", headers=headers, data=push).json()
        return response["iden"]

    def get_user(self, user):
        if "@" not in user:
            users = self.config["users"]
            users = [i for i in users if self.lower(user) == self.lower(users[i])]
            if not users:
                return
            else:
                user = users[0]
        return user

    def __destroy__(self, server):
        for listener in self.listeners:
            listener.listening = False

    @command("pbflush", admin=True)
    def pbflush(self, server, msg):
        for channel, account in self.config["accounts"].items():
            self.update(channel)
        return "03│ ⁍ │ Manually tickled all pushbullet connections."        

    @command("pbrestart", admin=True)
    def pbrestart(self, server, msg):
        for listener in self.listeners:
            listener.listening = False     
        self.listen()
        return "03│ ⁍ │ Restarted all tickle threads."

__initialise__ = PushBullet
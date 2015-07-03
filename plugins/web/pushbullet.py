import socket
import json
import time
import threading
import ssl
import requests
from functools import partial

from bot.events import Callback, command
from util.text import Buffer, pretty_date
from util.files import Config
from util.services import url
from util.images import image_search

HEADERS = """GET /websocket/%(key)s HTTP/1.1\r\nHost: stream.pushbullet.com\r\nUser-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:34.0) Gecko/20100101 Firefox/34.0\r\nAccept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\nAccept-Language: en-US,en;q=0.5\r\nAccept-Encoding: gzip, deflate\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: VwQcElXiDe4ZsgAPdAur0g==\r\nConnection: keep-alive, Upgrade\r\nPragma: no-cache\r\nCache-Control: no-cache\r\nUpgrade: websocket\r\n\r\n"""

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
        for evt in self.ws:
            if not self.listening:
                break
            self.dispatch(evt)

    def dispatch(self, evt):
        if evt["type"] == "tickle":
            self.update()
        self.last = time.time()
                    
def push_format(push, sent, users):
    fields = []
    # TODO: shorten long fields
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
#    elif push["type"] == "checklist":
#        self.queue(push)

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
    fields.append("\u231a " + pretty_date(time.time() - push["modified"]))
    
    return "03│ ⁍ │ " + " · ".join(fields)

class PushBullet(Callback):
    def __init__(self, server):
        self.server = server
        self.configf = server.get_config_dir("pushbullet.json")
        self.config = Config(self.configf, default={"accounts":{}, "users":{}})
        self.listeners = []
        self.skip = set()
        self.sent = set()
        self.channels = {}
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
        req = requests.get("https://api.pushbullet.com/v2/pushes", params=params, headers=headers)
        pushes = req.json()["pushes"]
        if not pushes:
            return
        for push in pushes:
            if push["iden"] in self.skip:
                self.skip.remove(push["iden"])
            else:
                if push["iden"] not in self.sent:
                    @command("reply", r"(?:(https?://\S+|:.+?:))?\s*(.*)")
                    def pushreply(server, message, link, text, push=push):
                        user = push["sender_email"]
                        return self.send_push.funct(self, server, message, user, link, text)
                    self.server.reply_hook = pushreply
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

    @command("help", "(.*?)(?: pushbullet)?")
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
                steps = ["If you don't have an account: Set up an account at http://www.pushbullet.com/ and install pushbullet on your devices", "Type /msg %s .setpush %s" % (server.nick, user)] + steps
        else:
            return "03│ ⁍ │ Type .setpush \x02email\x02, then go to 12https://www.pushbullet.com/add-friend\x0f and add \x0303%s\x03 as a friend." % email            
        if email is None:
            return "03│ ⁍ │ %s: type .setpush \x02email\x02, then go to 12https://www.pushbullet.com/add-friend\x0f and add \x0303%s\x03 as a friend." % (user, email)
        else:
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

        push["body"] = " · from " + msg.address.nick

        if link:
            if link.startswith(":"):
                link = image_search(link[1:-1])[0]["url"] 
            push["url"] = link
            push["type"] = "link"
        else:
            push["type"] = "note"
        if text:
            if ": " in text:
                push["title"], text = text.split(": ", 1)
            push["body"] = text + push["body"]
        push["email"] = user
        self.sent.add(self.push(push, acc["token"]))

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

__initialise__ = PushBullet
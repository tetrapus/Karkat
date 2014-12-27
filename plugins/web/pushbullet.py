import socket
import json
import time
import threading
import ssl
import os
import requests
from functools import partial

from bot.events import Callback, command
from util.text import Buffer, pretty_date
from util.files import Config
from util.services import url

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
                    

class PushBullet(Callback):
    def __init__(self, server):
        self.server = server
        self.configf = server.get_config_dir("pushbullet.json")
        self.config = Config(self.configf, default={"accounts":{}, "users":{}})
        self.listeners = []
        self.listen()
        super().__init__(server)

    def listen(self):
        for channel, account in self.config["accounts"].items():
            self.listeners.append(PushListener(account["token"], partial(self.update, channel)))
        for listener in self.listeners:
            listener.start()

    def update(self, account):
        acc = self.config["accounts"][account]
        params = {"modified_after": acc["last"]}
        headers = {"Authorization": acc["token"]}
        req = requests.get("https://docs.pushbullet.com/v2/pushes/", params=params, headers=headers)
        pushes = req.json()["pushes"]
        if not pushes:
            return
        for push in pushes:
            fields = []
            # TODO: shorten long fields
            if push["type"] in ["note", "link"]:
                message_field = []
                if "title" in push:
                    message_field.append("\x0303%s\x03" % push["title"])
                if "body" in push:
                    message_field.append(push["body"])
                if message_field:
                    fields.append(" ".join(message_field))
                if "url" in push:
                    fields.append(url.format(url.shorten(push["url"])))
            elif push["type"] == "address":
                if "name" in push:
                    fields.append("\x0303 📍 %s\x03" % push["name"])
                if "address" in push:
                    fields.append(push["address"])
            elif push["type"] == "file":
                if "file_url" in push:
                    fields.append(url.format(url.shorten(push["file_url"])))
                if "body" in push:
                    fields.append(push["body"])
            elif push["type"] == "checklist":
                self.queue(push)

            users = self.config["users"]
            email = push["sender_email"]
            if email.lower() in users:
                user = users[email.lower()]
            else:
                user = "\x0303" + email + "\x03"

            fields.append("from " + user)
            fields.append("\u231a " + pretty_date(time.time() - push["modified"]))

            self.server.message("03│ ⁍ │ " + " · ".join(fields), account)

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
            conf[email.lower()] = msg.address.nick
        return "03│ ⁍ │ Associated %s with pushbullet account %s." % (msg.address.nick, email)

    @command("pushassoc", r"(#\S+)\s+(\S+)", admin=True)
    def add_channel(self, server, msg, channel, token):
        account = {"token": token, "last": time.time()}
        with self.config as conf:
            conf["accounts"][server.lower(channel)] = account
        listener = PushListener(account["token"], partial(self.update, channel))
        self.listeners.append(listener)
        listener.start()
        return "03│ ⁍ │ Done."

__initialise__ = PushBullet
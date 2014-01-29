import time
import json
import traceback
import random
import os
import hashlib
import subprocess

from util.text import pretty_date
from util.services import pysnap, imgur, url
from bot.events import Callback, command

def savevideo(data):
    fchars = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', '|', '-', '_']
    template = "/home/joey/Dropbox/Public/Snaps/%s.mp4"
    fname = random.choice(fchars)
    while os.path.exists(template % fname):
        fname += random.choice(fchars)
    with open(template % fname, "wb") as f:
        f.write(data)
    return fname

def savegif(data):
    fname = savevideo(data)
    subprocess.call("ffmpeg -i /home/joey/Dropbox/Public/Snaps/%(id)s.mp4 -vf scale=320:-1 -r 10 /tmp/snapchat-%(pid)s-%(id)s.%%04d.png" % {"pid": os.getpid(), "id": fname}, shell=True)
    subprocess.call("rm /tmp/snapchat-%(pid)s-%(id)s.0001.png" % {"pid": os.getpid(), "id": fname}, shell=True)
    subprocess.call("convert -delay 5 -loop 0 /tmp/snapchat-%(pid)s-%(id)s.*.png /home/joey/Dropbox/Public/Snaps/%(id)s.gif" % {"pid": os.getpid(), "id": fname}, shell=True)
    subprocess.call("rm /tmp/snapchat-%(pid)s-%(id)s.*.png" % {"pid": os.getpid(), "id": fname}, shell=True)
    return fname

class Snap(Callback):

    SETTINGS_FILE = "snapchat.json"

    def __init__(self, server):
        self.settingsf = server.get_config_dir(self.SETTINGS_FILE)
        try:
            self.settings = json.load(open(self.settingsf))
        except FileNotFoundError:
            self.settings = {}
        
        self.accounts = {i: pysnap.Snapchat() for i in self.settings}
        for i in self.settings:
            self.accounts[i].login(self.settings[i]["username"], self.settings[i]["password"])
        self.cache = {}

        super().__init__(server)

    def snapsave(self, data, gif=False):
        sig = hashlib.md5(data).hexdigest()
        if sig in self.cache:
            return self.cache[sig]
        res = None

        # Check if image file.
        if pysnap.is_image(data):
            # Upload to imgur
            response = imgur.upload(data)
            res = response["data"]["link"]
        elif pysnap.is_video(data):
            if gif:
                gifid = savegif(data)
                if os.path.getsize("/home/joey/Dropbox/Public/Snaps/%s.gif" % gifid) < 2097152:
                    res = imgur.upload(open("/home/joey/Dropbox/Public/Snaps/%s.gif" % gifid, "rb").read())["data"]["link"]
                else:
                    res = url.shorten("http://dl.dropboxusercontent.com/u/5321377/Snaps/%s.gif" % savegif(data))
            else:
                res = url.shorten("http://dl.dropboxusercontent.com/u/5321377/Snaps/%s.mp4" % savevideo(data))

        self.cache[sig] = res
        return res

    @command("snapassoc", r"([^ ]+)\s+([^ ]+)\s+([^ ]+)", admin=True)
    def associate(self, server, message, channel, username, password):
        # try to login
        res = pysnap.Snapchat()
        if not res.login(username, password):
            return "Could not log in."
        channel = server.lower(channel)
        if channel in self.accounts:
            self.accounts[channel].logout()
        self.accounts[channel] = res
        self.settings[server.lower(channel)] = {"username": username, "password": password, "snaps": {}, "last": time.time()}
        json.dump(self.settings, open(self.settingsf, "w"))
        return "Associated %s with username %s successfully." % (channel, username)

    def newsnaps(self, channel):
        account = self.accounts[channel]

        if channel not in self.accounts or channel not in self.settings:
            return
        self.settings[channel]["last"] = time.time()
        snaps = account.get_snaps(self.settings[channel]["last"])
        for snap in snaps:
            try:
                if snap["id"] in self.settings[channel]["snaps"]:
                    continue
                blob = account.get_blob(snap["id"])
                if not blob:
                    self.settings[channel]["snaps"][snap["id"]] = None
                    continue
                print(snap)
                print("*** Saving", snap["id"])
                url = self.snapsave(blob, gif=snap["media_type"] == 2)
                print("*** URL:", url)
                self.settings[channel]["snaps"][snap["id"]] = url
                account.mark_viewed(snap["id"])
                yield "08│12 %s via %s (⌚ %s)" % (url, snap["sender"], pretty_date(time.time() - snap["sent"]/1000) if snap["sent"] else "Unknown")
            except:
                traceback.print_exc()
        json.dump(self.settings, open(self.settingsf, "w"))

    @command("snaps")
    def getnewsnaps(self, server, message):
        channel = server.lower(message.context)

        yield from self.newsnaps(channel)

    def checksnaps(self, server, line) -> "ALL":
        for channel in self.settings:
            if time.time() - self.settings[channel]["last"] > 60:
                for i in self.newsnaps(channel):
                    server.message(i, channel)

    @command("block", "(.*)", admin=True)
    def block(self, server, message, username):
        channel = server.lower(message.context)
        if channel not in self.accounts:
            return "08│ No associated snapchat for this channel."
        account = self.accounts[channel]
        if account.block(username):
            return "08│ Blocked %s." % username
        else:
            return "08│ Could not block %s." % username



__initialise__ = Snap
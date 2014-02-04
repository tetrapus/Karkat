import time
import json
import traceback
import random
import os
import re
import hashlib
import subprocess

from util.text import pretty_date
from util.services import pysnap
from util import scheduler
from bot.events import Callback, command

snapfolder = "/var/www/snaps"
public_url = "http://s.n0.ms/"

def save(data, fmt):
    fchars =  "abcdefghijklmnopqrstuvwxyz-_+=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:@~,."
    template = snapfolder + "/%s." + fmt
    fname = random.choice(fchars)
    while os.path.exists(template % fname):
        fname += random.choice(fchars)
    with open(template % fname, "wb") as f:
        f.write(data)
    return fname

def save_as(data, fmt):
    if fmt == "gif":
        return gifify(save(data, "mp4"))
    else:
        return save(data, fmt)

def gifify(fname):
    var = {"pid": os.getpid(), "id": fname, "folder": snapfolder}
    subprocess.call("ffmpeg -i %(folder)s/%(id)s.mp4 -vf scale=320:-1 -r 12 /tmp/snapchat-%(pid)s-%(id)s.%%04d.png" % var, shell=True)
#    subprocess.call("rm /tmp/snapchat-%(pid)s-%(id)s.0001.png" % var, shell=True)
    subprocess.call("convert -delay 25x300 -loop 0 /tmp/snapchat-%(pid)s-%(id)s.*.png %(folder)s/%(id)s.gif" % var, shell=True)
    subprocess.call("rm /tmp/snapchat-%(pid)s-%(id)s.*.png" % var, shell=True)
    return fname

class Snap(Callback):

    SETTINGS_FILE = "snapchat.json"
    DELETION_FILE = "snapchat-deletion.json"

    def __init__(self, server):
        self.settingsf = server.get_config_dir(self.SETTINGS_FILE)
        try:
            self.settings = json.load(open(self.settingsf))
        except FileNotFoundError:
            self.settings = {}
        
        self.deletionf = server.get_config_dir(self.DELETION_FILE)
        try:
            self.deletion = json.load(open(self.deletionf))
        except FileNotFoundError:
            self.deletion = {}
        self.accounts = {i: pysnap.Snapchat() for i in self.settings}
        for i in self.settings:
            self.accounts[i].login(self.settings[i]["username"], self.settings[i]["password"])
        self.cache = {}
        self.checker = scheduler.schedule_after(60, self.checksnaps, args=(server,), stop_after=None)

        super().__init__(server)

    def add_deletion(self, username, id, link):
        self.deletion.setdefault(username.lower(), {}).update({id: link})
        
        json.dump(self.deletion, open(self.deletionf, "w"))
        
    def snapsave(self, data, media_type):
        sig = hashlib.md5(data).hexdigest()
        if sig in self.cache:
            return self.cache[sig]
        res = None

        filetype = ["jpg", "mp4", "gif"][media_type]

        res = public_url + save_as(data, filetype) + "." + filetype

        self.cache[sig] = res
        return res

    @command("snapassoc", r"([^ ]+)\s+([^ ]+)\s+([^ ]+)", admin=True)
    def associate(self, server, message, channel, username, password):
        # try to login
        res = pysnap.Snapchat()
        if not res.login(username, password):
            return "08│👻│04 Could not log in."
        channel = server.lower(channel)
        if channel in self.accounts:
            self.accounts[channel].logout()
        self.accounts[channel] = res
        self.settings[server.lower(channel)] = {"username": username, "password": password, "snaps": {}, "last": time.time(), "history":[]}
        json.dump(self.settings, open(self.settingsf, "w"))
        return "08│👻│04 Associated %s with username %s successfully." % (channel, username)

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
                url = self.snapsave(blob, snap["media_type"])
                print("*** URL:", url)
                self.settings[channel]["snaps"][snap["id"]] = url
                self.settings[channel].setdefault("history", []).append(snap)
                account.mark_viewed(snap["id"])
                yield "08│👻│ 12%s · via %s · ⌚ %s" % (url, snap["sender"], pretty_date(time.time() - snap["sent"]/1000) if snap["sent"] else "Unknown")
            except:
                traceback.print_exc()
        json.dump(self.settings, open(self.settingsf, "w"))

    @Callback.background
    @command("update")
    def getnewsnaps(self, server, message):
        channel = server.lower(message.context)

        yield from self.newsnaps(channel)

    def checksnaps(self, server):
        for channel in self.settings:
            for i in self.newsnaps(channel):
                server.message(i, channel)

    @command("block", "(.*)", admin=True)
    def block(self, server, message, username):
        channel = server.lower(message.context)
        if channel not in self.accounts:
            return "08│👻│04 No associated snapchat for this channel."
        account = self.accounts[channel]
        if account.block(username):
            return "08│👻│ Blocked %s." % username
        else:
            return "08│👻│04 Could not block %s." % username

    @command("snaps", r"(?:(last|first)\s+(?:(?:(\d+)(?:-|\s+to\s+))?(\d*))\s*)?((?:gifs|videos|snaps|pics|clips)(?:(?:\s+or\s+|\s+and\s+|\s*/\s*|\s*\+\s*)(?:gifs|videos|snaps|pics|clips))*)?(?:from\s+(\S+(?:(?:\s+or\s+|\s+and\s+|\s*/\s*|\s*\+\s*)\S+)*))?")
    def search(self, server, message, anchor, frm, to, typefilter, users):
        context = server.lower(message.context)
        if context not in self.settings:
            yield "08│👻│04 No associated snapchat for this channel."
        if not anchor:
            frm, to, anchor = -1, -2 if message.prefix == "." else -6, -1
        elif anchor.lower() == "last":
            frm, to, anchor = -int(frm or 1), -int(to) if to else None, -1
        elif anchor.lower() == "first":
            frm, to, anchor == int(frm or 1)-1, int(to)-1 if to else None, 1
        types = {"gifs": {2},
                 "videos": {1},
                 "snaps": {0, 1, 2},
                 "pics": {0},
                 "clips": {1, 2}}
        filtr = set()
        for i in re.split(r"\s+or\s+|\s+and\s+|\s*/\s*|\s*\+\s*", typefilter):
            filtr |= types[i.lower()]
        users = {i.lower() for i in re.split(r"\s+or\s+|\s+and\s+|\s*/\s*|\s*\+\s*", users)}

        history = self.settings[context]["history"]
        history = [i for i in history if i["media_type"] in filtr and i["sender"].lower() in users]
        results = history[frm:to:anchor][:1 if message.prefix == "." else 5]
        for i in results:
            yield "08│👻│ 12%s · via %s · ⌚ %s" % (self.settings[context]["snaps"][i["id"]], i["sender"], pretty_date(time.time() - i["sent"]/1000) if i["sent"] else "Unknown")

    def __destroy__(self, server):
        self.checker.cancel()

__initialise__ = Snap
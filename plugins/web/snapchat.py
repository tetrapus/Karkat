import time
import json
import traceback
import random
import os
import re
import hashlib
import subprocess

from io import BytesIO

import pysnap
from pysnap.utils import encrypt, make_media_id
import requests
from PIL import Image, ImageDraw, ImageFont

from util.text import pretty_date, ircstrip
from util import scheduler
from bot.events import Callback, command

snapfolder = "/var/www/snaps"
public_url = "http://xenon.tetrap.us/"

colors = [(204, 204, 204), (0, 0, 0), (53, 53, 179), (42, 140, 42), (195, 59, 59), (199, 50, 50), (128, 38, 127), (102, 54, 31), (217, 166, 65), (61, 204, 61), (25, 85, 85), (46, 140, 116), (69, 69, 230), (176, 55, 176), (76, 76, 76), (149, 149, 149)]

def drawtext(img, text, minsize=13, maxsize=133):
    lines = None
    size = maxsize + 5
    while size > minsize and not lines:
        size -= 5
        font = ImageFont.truetype("/usr/share/fonts/truetype/ttf-dejavu/DejaVuSansMono.ttf", size)
        fontsize = font.getsize("A")
        lines = textwrap(img.size, fontsize, text)
        if lines:
            break
    if not lines: return
    draw = ImageDraw.Draw(img)
    boldfont = ImageFont.truetype("/usr/share/fonts/truetype/ttf-dejavu/DejaVuSansMono-Bold.ttf", size)
    color = None
    bold = False
    for i, line in enumerate(lines):
        line = list(line)
        j = 0
        while line:
            char = line.pop(0)
            if char == "\x03":
                color = None
                if line and line[0] in "0123456789":
                    color = int(line.pop(0))
                    if line and line[0] in "0123456789":
                        color *= 10
                        color += int(line.pop(0))
            elif char == "\x0f":
                bold = False
                color = None
            elif char == "\x02":
                bold = not bold
            else:
                if color == None:
                    try:
                        samples = []
                        for ioff in [0.33, 0.66]:
                            for joff in [0.33, 66]:
                                pixel = img.getpixel((int(5 + (j+joff) * fontsize[0]), int((i+ioff)*(fontsize[1]))))
                                samples.append(sum(pixel[:3]) / 3)
                        c = {True: (255, 255, 255), False: (15, 15, 15)}[sum(samples)/len(samples) < 100]
                    except:
                        c = (255, 255, 255)
                else:
                    c = colors[color % len(colors)]
                if bold:
                    f = boldfont
                else:
                    f = font
                draw.text((5 + j * fontsize[0], i*(fontsize[1]+10)), char, c, font=f)
                j += 1

    return img

def textwrap(dim, unit, text):
    # Calculate max characters
    width, height = (dim[0] - 10) // unit[0], dim[1] // (unit[1] + 10)
    text = text.split("\n")
    alines = []
    for line in text:
        line = line.split(" ")
        if any(len(ircstrip(i)) > width for i in line):
            return
        lines = [line[0]]
        for i in line[1:]:
            if len(ircstrip(lines[-1])) + len(ircstrip(i)) + 1 > width:
                lines.append(i)
            else:
                lines[-1] += " " + i
        alines.extend(lines)
    if len(alines) <= height:
        return alines


def save(data, fmt):
    fchars =  "abcdefghijklmnopqrstuvwxyz-_+=~ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
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
    subprocess.call("ffmpeg -i '%(folder)s/%(id)s.mp4' -vf scale=320:-1 -r 12 '/tmp/snapchat-%(pid)s-%(id)s.%%04d.png'" % var, shell=True)
    subprocess.call("convert -delay 25x300 -loop 0 /tmp/snapchat-%(pid)s-%(id)s.*.png '%(folder)s/%(id)s.gif'" % var, shell=True)
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
        self.server = server

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
                self.server.lasturl = url
                yield "08│👻│ 12%s · from %s · ⌚ %s" % (url, snap["sender"], pretty_date(time.time() - snap["sent"]/1000) if snap["sent"] else "Unknown")
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

    @command("snap", r"(\S+)(?:\s+(http://\S+))?(?:\s+(.+))?")
    def send(self, server, message, user, background, text):
        acc = self.accounts[server.lower(message.context)]
        if background:
            bg = Image.open(BytesIO(requests.get(background.strip()).content))
        else:
            bg = Image.new("RGBA", (640, 960), (0, 0, 0))
        if bg.size[0] > 4096 or bg.size[1] > 4096:
            return "04│👻│ Image too large."
        if text:
            text = text.replace("\\", "\n")
            text += "\n -\x02%s" % message.address.nick
        else:
            text = "via %s" % message.address.nick
        img = drawtext(bg, text)
        if not img:
            return "04│👻│ Could not fit text on the image."
        f = BytesIO()
        img.save(f, "jpeg")
        f.seek(0)
        media_id = make_media_id(acc.username)
        r = acc._request('upload', {
            'username': acc.username,
            'media_id': media_id,
            'type': 0
            }, files={'data': encrypt(f.read())})
        if len(r.content) != 0:
            return "04│👻│ Failed to upload snap."
        acc.send(media_id, user, time=10)
        return "08│👻│ Sent snap to: %s" % (",".join(user.split(",")))
        

    @command("snaps", r"^(?:(last|first)\s+(?:(?:(\d+)(?:-|\s+to\s+))?(\d*))\s*)?((?:gifs|videos|snaps|pics|clips)(?:(?:\s+or\s+|\s+and\s+|\s*/\s*|\s*\+\s*)(?:gifs|videos|snaps|pics|clips))*)?(?:\s*(?:from|by)\s+(\S+(?:(?:\s+or\s+|\s+and\s+|\s*/\s*|\s*\+\s*)\S+)*))?(?:\s*to\s+(\S+))?$", templates={Callback.USAGE: "08│👻│04 Usage: .snaps [first/last index] [type] [by user] [to channel]"})
    def search(self, server, message, anchor, frm, to, typefilter, users, context):
        if not context:
            context = message.context
        elif "#" not in context:
            target = [i for i in self.settings if self.settings[i]["username"].lower() == context.lower()]
            if not target:
                yield "08│👻│04 No associated channel for that snapchat account."
                return
            context = target[0]
        context = server.lower(context)
        if context not in self.settings:
            yield "08│👻│04 No associated snapchat for this channel."
            return

        new = []
        if not any((anchor, frm, to, typefilter, users)):
            new = list(self.newsnaps(context))
            for i in new:
                yield i + " [NEW]"
                if context != server.lower(message.context):
                    server.message(i, message.context)
            new = [i.rsplit("·", 1)[0] for i in new]

        if not anchor:
            frm, to, anchor = -1, -2 if message.prefix == "." else -5, -1
        elif anchor.lower() == "last":
            frm, to, anchor = -int(frm or 1), -int(to)-1 if to else None, -1
        elif anchor.lower() == "first":
            frm, to, anchor = int(frm or 1)-1, int(to) if to else None, 1
        types = {"gifs": {2},
                 "videos": {1},
                 "snaps": {0, 1, 2},
                 "pics": {0},
                 "clips": {1, 2}}
        filtr = set()
        if not typefilter: typefilter = "snaps"
        for i in re.split(r"\s+or\s+|\s+and\s+|\s*/\s*|\s*\+\s*", typefilter):
            filtr |= types[i.lower()]
        if users:
            users = {i.lower() for i in re.split(r"\s+or\s+|\s+and\s+|\s*/\s*|\s*\+\s*", users)}
        history = self.settings[context]["history"]
        history = [i for i in history if (i["media_type"] in filtr) and ((not users) or (i["sender"].lower() in users))]
        results = history[frm:to:anchor][:1 if message.prefix == "." else 5]
        for i in results:
            server.lasturl = self.settings[context]["snaps"][i["id"]]
            res = "08│👻│ 12%s · from %s · ⌚ %s" % (self.settings[context]["snaps"][i["id"]], i["sender"], pretty_date(time.time() - i["sent"]/1000) if i["sent"] else "Unknown")
            if res.rsplit("·", 1)[0] not in new:
                yield res

    def __destroy__(self, server):
        self.checker.cancel()

__initialise__ = Snap
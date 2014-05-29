# clone of http://willyoupressthebutton.com/
# I make lots of obvious mistakes when I'm sleepy
# inb4 obvious mistakes

import sys
import json
import random
import math

from bot.events import Callback, command

class Wyp(Callback):
    QFILE = "wyps.json"

    def __init__(self, server):
        self.qfile = server.get_config_dir(self.QFILE)
        try:
            with open(self.qfile) as f:
                self.wyps = json.load(f)
        except:
            self.wyps = {}
        self.active = "04●"
        super().__init__(server)

    @command("addbutton makebutton addwyp makewyp", r"(.+)")
    def queue(self, server, msg, item):
        wyp = self.wyps.setdefault(item, {})
        self.active = item
        self.save()
        return "\x0306│\x03 Button added"

    @command("fuckbutton destroy ripbutton")
    def destroy(self, server, msg):
        item = self.active
        nick = msg.address.nick
        wyp = self.wyps.setdefault(item, {})
        wyp[server.lower(nick)] = None
        self.save()
        return "\x0306│\x03 You attack the button. " + self.displayPresses(item)        

    @command("button wyptb wyp willyoupressthebutton willyoupress")
    def preview(self, server, msg):
        self.active = random.choice(list(self.wyps.keys()))
        return self.display()

    @command("press yes")
    def press(self, server, msg):
        item = self.active
        nick = msg.address.nick
        wyp = self.wyps.setdefault(item, {})
        wyp[server.lower(nick)] = 1
        self.save()
        return "\x0306│\x03 You pressed the button. " + self.displayPresses(item)

    @command("nopress no")
    def noPress(self, server, msg):
        item = self.active
        nick = msg.address.nick
        wyp = self.wyps.setdefault(item, {})
        wyp[server.lower(nick)] = 0
        self.save()
        return "\x0306│\x03 You chose not to press the button. " + self.displayPresses(item)

    def displayPresses(self, item=None):
        if item is None:
            item = self.active
        wyp = self.wyps.get(item)
        num = len(wyp.keys())
        numPress = list(wyp.values()).count(1)
        stats = "%s out of %s people pressed the button (%.2f%%)" % (numPress, num, numPress / num * 100)
        health = 1
        if None in wyp.values():
            health -= list(wyp.values()).count(None) / self.average()
            if health < 0:
                del self.wyps[item]
                self.save()
                stats += ". The button has been destroyed. RIP, button."
            bar = list("  ʜᴇᴀʟᴛʜ  ")
            bar.insert(min(0, math.ceil(health * 10)), ",14")
            stats += " " + bar
        return stats
            

    def display(self, item=None):
        return "\x0306│\x03 Will you press the button? " + self.active

    def average(self):
        return sum(len(i.values()) for i in self.wyps.values()) / len(self.wyps)

    def save(self):
        with open(self.qfile, "w") as f:
            json.dump(self.wyps, f)


__initialise__ = Wyp

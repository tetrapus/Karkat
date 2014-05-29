# clone of http://willyoupressthebutton.com/
# I make lots of obvious mistakes when I'm sleepy
# inb4 obvious mistakes

import sys
import json
import random

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
        self.active = ""
        super().__init__(server)

    @command("addbutton makebutton addwyp makewyp", r"(.+)")
    def queue(self, server, msg, item):
        wyp = self.wyps.setdefault(item, {})
        self.active = item
        self.save()
        return "\x0306│\x03 Button added"

    @command("button wyptb wyp willyoupressthebutton willyoupress")
    def preview(self, server, msg):
        self.active = random.choice(list(self.wyps.keys()))
        return self.display()

    @command("press", r"(.*)")
    def press(self, server, msg, item=None):
        if item is None:
            item = self.active
        nick = msg.address.nick
        wyp = self.wyps.setdefault(item, {})
        wyp[server.lower(nick)] = 1
        self.save()
        return "\x0306│\x03 You pressed the button. " + self.displayPresses(item)

    @command("nopress", r"(.*)")
    def noPress(self, server, msg, item=None):
        if item is None:
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
        numPress = sum(wyp.values())
        return numPress + " out of " + num + " people pressed the button. (" + str(numPress / num * 100) + "%)."

    def display(self, item=None):
        return "\x0306│\x03 Will you press the button? " + self.active

    def save(self):
        with open(self.qfile, "w") as f:
            json.dump(self.wyps, f)


__initialise__ = Wyp

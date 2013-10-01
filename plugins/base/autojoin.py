import os
import json

from util.irc import Callback


class AutoJoin(object):

    CHANFILE = "autojoin.txt"
    cb = Callback()

    def __init__(self, name, bot, printer):
        self.stream = printer
        self.cb.initialise(name, bot, printer)
        self.chanfile = bot.get_config_dir(self.CHANFILE)

        try:
            self.chans = json.load(open(self.chanfile, "r"))
        except:
            # File doesn't exist
            os.makedirs(bot.get_config_dir(), exist_ok=True)
            self.chans = []
            self.sync()
        self.server = bot

        bot.register("invite", self.onInvite)
        bot.register("376", self.join)
        bot.register("privmsg", self.trigger)

    def sync(self):
        with open(self.chanfile, "w") as cf:
            cf.write(json.dumps(self.chans))

    @cb.threadsafe
    def join(self, line):
        if self.chans:
            self.stream.raw_message("JOIN :%s" % (",".join(self.chans)))

    @cb.threadsafe
    def onInvite(self, line):
        words = line.split()
        if self.server.is_admin(words[0]) or self.server.isIn(words[3][1:], self.chans):
            self.stream.raw_message("JOIN %s" % words[3])

    @cb.command("autojoin", public=":", private="")
    def trigger(self, msg):
        if msg.context.startswith("#"):
            if self.server.isIn(msg.context, self.chans):
                self.chans.remove(self.server.lower(msg.context))
                self.sync()
                return "12Auto-join⎟ Channel removed."
            else:
                self.chans.append(self.server.lower(msg.context))

                self.sync()
                return "12Auto-join⎟ Channel added."


__initialise__ = AutoJoin
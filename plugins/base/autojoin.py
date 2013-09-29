import os

from irc import Callback


class AutoJoin(object):

    CHANFILE = "autojoin.txt"
    cb = Callback()

    def __init__(self, name, bot, printer):
        self.stream = printer
        self.cb.initialise(name, bot, printer)
        self.chanfile = bot.get_config_dir(self.CHANFILE)

        try:
            self.chans = open(self.chanfile, "r").read()
        except:
            # File doesn't exist
            os.makedirs(bot.get_config_dir(), exist_ok=True)
            self.chans = ""
            open(self.chanfile, "w")
        self.server = bot

        bot.register("invite", self.onInvite)
        bot.register("376", self.join)
        bot.register("privmsg", self.trigger)

    @cb.threadsafe
    def join(self, line):
        if self.chans:
            self.stream.raw_message("JOIN %s" % self.chans)

    @cb.threadsafe
    def onInvite(self, line):
        words = line.split()
        if self.server.is_admin(words[0]) or words[3][1:].lower() in self.chans.lower().split(","):
            self.stream.raw_message("JOIN %s" % words[3])

    @cb.command("autojoin", public=":", private="")
    def trigger(self, msg):
        if msg.context.startswith("#"):
            if msg.context.lower() in self.chans.split(","):
                chans = self.chans.split(",")
                chans.remove(msg.context.lower())
                self.chans = ",".join(chans)
                return "12Auto-join⎟ Channel removed."
            else:
                self.chans = ",".join(self.chans.split(",") + [msg.context.lower()])

                return "12Auto-join⎟ Channel added."
            with open(self.chanfile, "w") as cf:
                cf.write(self.chans)

__initialise__ = AutoJoin
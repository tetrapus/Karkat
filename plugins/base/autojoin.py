import os
from irc import Address, Message, Callback

class AutoJoin(object):
    #    chans = open("autojoin.txt").read().strip() if "-t" not in sys.argv else "#karkat" # TODO: #docopt

    CHANFILE = "autojoin.txt"

    def __init__(self, name, bot, printer):
        self.stream = printer
        self.chanfile = os.path.join("config", name, self.CHANFILE)
        os.makedirs(os.path.join("config", name), exist_ok=True)

        try:
            self.chans = open(self.chanfile, "r").read()
        except:
            # File doesn't exist
            self.chans = ""
            open(self.chanfile, "w")
        self.server = bot

        bot.register("invite", self.onInvite)
        bot.register("376", self.join)
        bot.register("privmsg", self.trigger)

    @Callback.threadsafe
    def join(self, line):
        if self.chans:
            self.stream.raw_message("JOIN %s" % self.chans)

    @Callback.threadsafe
    def onInvite(self, line):
        words = line.split()
        if Address(words[0]).mask in self.server.admins or words[3][1:].lower() in self.chans.lower().split(","):
            self.stream.raw_message("JOIN %s" % words[3])

    def trigger(self, line):
        msg = Message(line)
        words = msg.text.split()
        if words[0].lower() == ":autojoin" and msg.context.startswith("#"):
            if msg.context.lower() in self.chans.split(","):
                chans = self.chans.split(",")
                chans.remove(msg.context.lower())
                self.chans = ",".join(chans)
                self.stream.message("12Auto-join⎟ Channel removed.", msg.context)
            else:
                self.chans = ",".join(self.chans.split(",") + [msg.context.lower()])

                self.stream.message("12Auto-join⎟ Channel added.", msg.context)
            with open(self.chanfile, "w") as cf:
                cf.write(self.chans)

__initialise__ = AutoJoin
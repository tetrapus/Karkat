import os
import json

from util.irc import Callback, command


class AutoJoin(object):

    CHANFILE = "autojoin.txt"

    def __init__(self, server):
        self.chanfile = server.get_config_dir(self.CHANFILE)

        try:
            self.chans = json.load(open(self.chanfile, "r"))
        except:
            # File doesn't exist
            os.makedirs(server.get_config_dir(), exist_ok=True)
            self.chans = []
            self.sync()

        server.register("invite", self.onInvite)
        server.register("376", self.join)
        server.register("privmsg", self.trigger)

    def sync(self):
        with open(self.chanfile, "w") as cf:
            cf.write(json.dumps(self.chans))

    @Callback.threadsafe
    def join(self, server, line):
        if self.chans:
            server.printer.raw_message("JOIN :%s" % (",".join(self.chans)))

    @Callback.threadsafe
    def onInvite(self, server, line):
        words = line.split()
        if server.is_admin(words[0]) or server.isIn(words[3][1:], self.chans):
            server.printer.raw_message("JOIN %s" % words[3])

    @command("autojoin", public=":", private="")
    def trigger(self, server, msg):
        if msg.context.startswith("#"):
            if server.isIn(msg.context, self.chans):
                self.chans.remove(server.lower(msg.context))
                self.sync()
                return "12Auto-join│ Channel removed."
            else:
                self.chans.append(server.lower(msg.context))

                self.sync()
                return "12Auto-join│ Channel added."


__initialise__ = AutoJoin
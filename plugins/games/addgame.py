import os
import time

from bot.events import Callback
from util.irc import command
from util.text import generate_vulgarity

class AddGame(Callback):

    ADDFILE = "addgame.txt" 

    def __init__(self, server):
        self.addfile = server.get_config_dir(self.ADDFILE)
        self.msged = {}

        try:
            self.num = int(open(self.addfile, "r").read().strip())
        except:
            # File doesn't exist
            os.makedirs(server.get_config_dir(), exist_ok=True)
            self.num = 0
            open(self.addfile, "w").write(str(self.num))

        self.history = {}
        server.register("privmsg", self.trigger)
        server.register("privmsg", self.subtract)
        super().__init__(server)

    @command("subtract decrement multiply times halve double divide modulo tetrate power exponentiate factorial negate".split(), public=".", private="")
    def subtract(self, server, msg):
        msged = msg.context
        if msged in self.msged and time.time() - self.msged[msged] < 600:
            return "WHAT DID I FUCKING SAY, %s?" % generate_vulgarity()
        self.msged[msged] = time.time()
        return "YOU CAN ONLY ADD, %s." % generate_vulgarity()

    @command("add increment".split(), public=".", private="")
    def trigger(self, server, msg):
        nick = server.lower(msg.address.nick)
        if nick in self.history:
            self.history[nick] = [(t, d) for t, d in self.history[nick] if time.time() - t < 150]
            self.history[nick].append((time.time(), time.time() - self.history[nick][-1][0] if self.history[nick] else 0))
            self.history[nick] = self.history[nick][-4:]
        else:
            self.history[nick] = [(time.time(), 0)]
        
        if sum(i[0] for i in self.history[nick]) / len(self.history[nick]) < 1.5 or (len(self.history[nick]) - 1 and sum(abs(self.history[nick][i][-1] - self.history[nick][i-1][-1]) for i in range(1, len(self.history[nick]))) / len(self.history[nick]) < 2):
            server.printer.message("hey %s, fuck off and let others have a go" % generate_vulgarity().lower(), msg.address.nick, "NOTICE")
        else:
            self.num += 1
            open(self.addfile, 'w').write(str(self.num))

            return "02Thanks %s, 03%s"%(msg.address.nick, "the number has been increased to %s."%self.num)

__initialise__ = AddGame
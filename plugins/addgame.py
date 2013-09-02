import os
import time
from irc import Address, Message


class AddGame(object):

    ADDFILE = "addgame.txt" 

    def __init__(self, name, bot, printer):
        self.stream = printer
        self.addfile = os.path.join("config", name, self.ADDFILE)
        os.makedirs(os.path.join("config", name), exist_ok=True)

        try:
            self.num = int(open(self.addfile, "r").read().strip())
        except:
            # File doesn't exist
            self.num = 0
            open(self.addfile, "w").write(str(self.num))
        self.history = {}
        bot.register("privmsg", self.trigger)

    def trigger(self, line):
        msg = Message(line)
        nick = msg.address.nick
        if msg.text.lower() == ".add":
            if nick in self.history:
                self.history[nick] = [(t, d) for t, d in self.history[nick] if time.time() - t < 150]
                self.history[nick].append((time.time(), time.time() - self.history[nick][-1][0] if self.history[nick] else 0))
                self.history[nick] = self.history[nick][-4:]
            else:
                self.history[nick] = [(time.time(), 0)]
            
            if sum(i[0] for i in self.history[nick]) / len(self.history[nick]) < 1.5 or (len(self.history[nick]) - 1 and sum(abs(self.history[nick][i][-1] - self.history[nick][i-1][-1]) for i in range(1, len(self.history[nick]))) / len(self.history[nick]) < 2):
                self.printer.message("fuck you bitch i ain't no adding machine", nick, "NOTICE")
            else:
                self.num += 1
                open(self.addfile, 'w').write(str(self.num))

                self.printer.message("02Thanks for that %s, 03%s"%(nick, "The number has been increased to %s."%self.num))

__initialise__ = AddGame
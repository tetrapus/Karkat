import time
from irc import Address, Message

class AddGame(object):
    def __init__(self, path):
        self.path = path
        self.num = int(open(path).read().strip())
        self.history = {}

    def initialise(self, name, bot, printer):
        # NTS: add name-pathing and merge into __init__
        self.printer = printer

    def trigger(self, x, y):
        nick = Address(x[0]).nick
        if Message(y).text.lower() == ".add":
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
                open(self.path, 'w').write(str(self.num))

                self.printer.message("02Thanks for that %s, 03%s"%(nick, "The number has been increased to %s."%self.num))
addg = AddGame("./addgame")

__initialise__ = addg.initialise
__callbacks__ = {"privmsg": [addg.trigger]}
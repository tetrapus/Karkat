import os
import time
import random

from util.irc import Callback


def generate_vulgarity():
    swears = ["FUCK", "SHIT", "DICK", "TWAT", "CUNT", "FISH", "CRAP", "ASS", "TIT", "PUSSY", "COCK", "DOUCHE", "CUM", "PISS", "MAN", "CRUD"]
    nouns = ["STAIN", "BAG", "FUCKER", "TARD", "WAFFLE", "NIPPLE", "BOOB", "BURGER", "EATER", "HOLE", "PONY", "NUTS", "JUICE", "CHODE", "SLUT", "BREATH", "WHORE", "DONKEY", "GOBBLER", "NUGGET", "BRAIN", "MUNCHER", "SUCKER", "STICK", "FACE", "TOOL", "WAGON", "WAD", "BUTT", "BUCKET", "BOX"]
    swearnoun = ["DIPSHIT", "FUCKWIT", "DUMBASS", "CORNHOLE", "LIMPDICK", "PIGSHIT"]
    if random.random() < 0.05:
        vulgarity = random.choice(swearnoun)
    else:
        vulgarity = random.choice(swears) + random.choice(nouns)

    return vulgarity

class AddGame(object):

    ADDFILE = "addgame.txt" 
    cb = Callback()

    def __init__(self, name, bot, printer):
        self.cb.initialise(name, bot, printer)
        self.addfile = bot.get_config_dir(self.ADDFILE)
        self.printer = printer
        self.msged = {}

        try:
            self.num = int(open(self.addfile, "r").read().strip())
        except:
            # File doesn't exist
            os.makedirs(bot.get_config_dir(), exist_ok=True)
            self.num = 0
            open(self.addfile, "w").write(str(self.num))

        self.history = {}
        bot.register("privmsg", self.trigger)
        bot.register("privmsg", self.subtract)

    @cb.command("subtract decrement multiply times halve double divide modulo tetrate power exponentiate factorial negate".split(), public=".", private="")
    def subtract(self, msg):
        msged = msg.context
        if msged in self.msged and time.time() - self.msged[msged] < 600:
            return "WHAT DID I FUCKING SAY, %s?" % generate_vulgarity()
        self.msged[msged] = time.time()
        return "YOU CAN ONLY ADD, %s." % generate_vulgarity()

    @cb.command("add increment".split(), public=".", private="")
    def trigger(self, msg):
        nick = self.cb.bot.lower(msg.address.nick)
        if nick in self.history:
            self.history[nick] = [(t, d) for t, d in self.history[nick] if time.time() - t < 150]
            self.history[nick].append((time.time(), time.time() - self.history[nick][-1][0] if self.history[nick] else 0))
            self.history[nick] = self.history[nick][-4:]
        else:
            self.history[nick] = [(time.time(), 0)]
        
        if sum(i[0] for i in self.history[nick]) / len(self.history[nick]) < 1.5 or (len(self.history[nick]) - 1 and sum(abs(self.history[nick][i][-1] - self.history[nick][i-1][-1]) for i in range(1, len(self.history[nick]))) / len(self.history[nick]) < 2):
            self.printer.message("hey %s, fuck off and let others have a go" % generate_vulgarity().lower(), msg.address.nick, "NOTICE")
        else:
            self.num += 1
            open(self.addfile, 'w').write(str(self.num))

            return "02Thanks %s, 03%s"%(msg.address.nick, "the number has been increased to %s."%self.num)

__initialise__ = AddGame
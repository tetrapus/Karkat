import random
from util.irc import command
from functools import lru_cache

@lru_cache(maxsize=4096)
def getinfo(username):
    info = {}
    info["sex"] = random.choice(["M"] * 10 + ["Male"] * 6 + ["F", "F", "Female"] + ["FtM", "MtF"])
    info["location"] = random.choice("Sydney California Chicago UK USA NY Washington Toronto Wales Perth Netherlands Iceland Kansas LA Michigan Florida NC Arizona England Australia".split())
    info["age"] = random.randrange(13, 20)
    info["picture"] = random.choice(open("imgdump.txt").read().split())
    info["sexuality"] = random.choice("Straight Gay Bisexual Homosexual Pansexual Gay Heterosexual Bi".split())
    info["starsign"] = random.choice("Aries   Taurus  Gemini  Cancer  Leo     Virgo   Libra   Scorpio     Sagittarius     Capricorn   Aquarius    Pisces".split())
    return info

@command("info", "(.+)", private="", public=".")
def infonot(server, message, args):
    return args + ": %(sex)s / %(location)s / %(age)s / %(picture)s / %(sexuality)s / %(starsign)s" % getinfo(args.lower())

__callbacks__ = {"privmsg": [infonot]}
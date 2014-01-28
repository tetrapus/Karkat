import random
import re

from bot.events import command

@command("choose", "(.+)", prefixes=("", "."))
def choose(server, msg, query):
    return "\x0309│\x03 " + random.choice(re.split(r",|\bor\b", query)).strip()

__callbacks__ = {"privmsg": [choose]}
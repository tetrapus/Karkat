import random
import re

from bot.events import command

@command("choose", "(.+)", prefixes=("", "."))
def choose(server, msg, query):
    return "\x0309│\x03 " + random.choice(re.split(",|or", query)).strip()

__callbacks__ = {"privmsg": [choose]}
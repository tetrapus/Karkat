import random
import re

from bot.events import command, Callback

@Callback.threadsafe
@command("choose", "(.+)", prefixes=("", "."))
def choose(server, msg, query):
    if "," not in query: return
    return "\x0309│\x03 " + random.choice(re.split(r",|\bor\b", query)).strip()

__callbacks__ = {"privmsg": [choose]}
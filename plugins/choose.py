import random

from bot.events import command

@command("choose", "(.+)")
def choose(server, msg, query):
    return "\x0309│\x03 " + random.choice(query.split(",")).strip()

__callbacks__ = {"privmsg": [choose]}
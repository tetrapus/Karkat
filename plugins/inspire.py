"""
Create social-ready inspirational quotes and image macros.
"""

from bot.events import command

@command
def draw(server, msg):
    raise NotImplementedError("Not yet implemented.")

__callbacks__ = {"privmsg": [draw]}
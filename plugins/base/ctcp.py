"""
Handles CTCP replies.
"""

import os
import yaml

from pathlib import Path

from util.irc import Message


DEFAULT_REPLY_PATH = Path("data/default_ctcp.yaml")
REPLY_FILENAME = Path("ctcp.yaml")


def __initialise__(server):
    """ Define the functions in a closure. """
    replies = {}

    try:
        replies.update(yaml.safe_load(DEFAULT_REPLY_PATH.open()))
    except OSError:
        pass

    conf = server.config_dir/REPLY_FILENAME

    try:
        replies.update(yaml.safe_load(conf.open()))
    except OSError:
        pass

    if replies:
        replies = {key.upper(): value for key, value in replies.items()}

        def ctcpreply(server, line):
            """ Reply to ctcp requests """
            msg = Message(line)
            text = msg.text
            if len(text) > 1 and text[0] == text[-1] == "\x01":
                text = text[1:-1].split(" ")
                command = text[0].upper()
                if command in replies:
                    server.printer.raw_message(
                        "NOTICE %s :\x01%s %s\x01" % (
                            msg.address.nick,
                            command,
                            replies[command].format(*text)
                        )
                    )

        server.register("privmsg", ctcpreply)
    else:
        print(
            "%s: Warning: No config files found. "
            "CTCP response module not loaded." % __name__
        )

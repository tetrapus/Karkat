#! /usr/bin/python3
# -*- coding: utf-8 -*-
"""
Usage: %(name)s [options] --config=FILE [plugin]...

Options:
    -h --help               Show this screen.
    --version               Show version.
    -v N, --verbosity=N     Set verbosity [default: 1]
    -c FILE, --config=FILE  Set server config [default: default.yaml]
"""

"""
Defining a Karkat plugin.

The following can optionally be defined to hook into karkat:
__callbacks__: A mapping of callbacks.
__icallbacks__:  A mapping of inline callbacks.
__initialise__(name, botobj, printer) : A function to initialise the module.
"""


import collections
import functools
import inspect
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time

import yaml
import docopt

from threads import ColourPrinter, Caller, StatefulBot
from irc import Address, Callback, Message, Command
from text import Buffer, TimerBuffer, average

__version__ = 2.0

socket.setdefaulttimeout(1800)

GP_CALLERS = 2

#TODO: Move connection object and subclasses
# TODO: Turn subclasses into objects owned by the connection thread.

try:
    server = StatefulBot(sys.argv[1])
except (OSError, IndexError):
    print("Usage: %s <config>" % sys.argv[0])
    sys.exit(1)
server.connect()
printer = server.printer

class Allbots:
    def __init__(self, bots, args = ""):
        self.bots = bots
        self.args = args
    def __call__(self, *data):
        pref = self.args + (" " * bool(self.args))
        for i in self.bots:
            i.sendline(pref + (" ".join(data)))
    def __getattr__(self, d):
        return Allbots(self.bots, self.args + " " + d)
bot = Allbots([server])

# 1010100100100010001011000001000011100000110010111000101100000100100110100111000001000001100000100110010010011000101

def authenticate(words, line):
    if "-i" in sys.argv:
        try:
            password = sys.argv[sys.argv.index("-i")+1]
        except IndexError:
            return
        else:
            server.sendline("msg nickserv identify %s" % password)


def log(line):
    if "-d" in sys.argv:
        print("[%s] %s" % (server.server[0], line))

flist = {
         "376" : [#authenticate, # plugin
                  lambda *x: printer.start(), # Bot
                  ], # plugin
         "ALL" : [],
        }

inline = {
         "privmsg" : [lambda y: printer.set_target(Message(y).context),  # Bot ???
                    ],
         "ping"    : [lambda y: server.sendline("PONG " + y.split()[1])], # Bot
         "ALL"     : [log], # plugin
         "DIE"     : []
}


if __name__ == "__main__":
    #args = docopt.docopt()
    if "-f" in sys.argv:
        exec(open("features.py").read())
        # Temporary.

    servername = sys.argv[1].split(".")[0]

    plugins = __import__("plugins") # temporary
    modules = plugins.__all__

    while modules:
        mod = modules.pop()
        if "__all__" in dir(mod):
            # Subpackage. Import submodules.
            modules.extend(mod.__all__)
            continue

        if "__initialise__" in dir(mod):
            mod.__initialise__(servername, server, printer)
            print("Initialising %s" % mod.__name__)
        else:
            print("Warning: No initialiser for %s" % mod.__name__)
        if "__callbacks__" in dir(mod):
            for trigger in mod.__callbacks__:
                flist.setdefault(trigger, []).extend(mod.__callbacks__[trigger])
                print("    Registered callbacks: %s" % ", ".join(i.__name__ for i in mod.__callbacks__[trigger]))
        if "__icallbacks__" in dir(mod):
            for trigger in mod.__icallbacks__:
                flist.setdefault(trigger, []).extend(mod.__icallbacks__[trigger])
                print("    Registered inlines: %s" % ", ".join(i.__name__ for i in mod.__icallbacks__[trigger]))

        print("Loaded %s" % mod.__name__)

    server.register_all(flist)
    server.register_alli(inline)

    print("Running...")
    server.start()

    while server.connected:
        try:
            exec(input())
        except KeyboardInterrupt:
            print("Terminating...")
            server.connected = False
            server.sock.send("QUIT\r\n".encode("utf-8"))
        except BaseException:
            sys.excepthook(*sys.exc_info())

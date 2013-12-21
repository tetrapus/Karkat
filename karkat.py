#! /usr/bin/python3
# -*- coding: utf-8 -*-
"""
Usage: %(name)s [options] <config>

Options:
    -h --help                           Show this message.
    --version                           Show version.
    -p PACKAGE, --plugins=PACKAGE       Set plugin package [default: plugins]
    -e PLUGINS, --exclude=PLUGINS       Don't load these plugins
    -d --debug                          Turn on debugging
    -i PASSWORD, --identify=PASSWORD    Identify with the given password
    -a --auth                           Auth instead of identify
    -r --restart                        Restart on disconnect
    -c NUM, --connections=NUM           Number of output connections [default: 1]
"""

import socket
import sys
import subprocess
from collections import deque

import docopt

from bot.threads import StatefulBot, Printer, Bot
from util.irc import Callback

__version__ = 2.0

socket.setdefaulttimeout(1800)

GP_CALLERS = 2


def main():
    """
    Karkat's mainloop simply spawns a server and registers all plugins.
    You can replace this.
    """
    args = docopt.docopt(__doc__ % {"name": sys.argv[0]}, version=__version__)
    exclude = args["--exclude"].split(",") if args["--exclude"] else []

    if args["--debug"]:
        debug = 0.15
    else:
        debug = None

    server = StatefulBot(args["<config>"], debug=debug)

    if int(args["--connections"]) > 1:
        def cleanup(output):
            output.connected = False

        outputs = [Bot(args["<config>"]) for i in range(int(args["--connections"])-1)]
        for output in outputs:
            output.connect()
            server.printer.add(output)
            server.register("DIE", cleanup)
            output.start()

    if args["--restart"]:
        server.restart = True
    server.connect()

    plugins = deque(args["--plugins"].split(","))
    loaded = []

    while plugins:
        plugin = plugins.popleft()
        if plugin.__name__ in exclude:
            print("Skipping %s" % plugin.__name__)
            continue
        try:
            __import__(plugin)
            module = sys.modules[plugin]
        except ImportError:
            print("Warning: %s not loaded." % (plugin))
        else:
            if "__modules__" in dir(module):
                plugins.extend("%s.%s" % (plugin, i) for i in module.__modules__)
            loaded.append(module)

    for module in loaded:

        print("Loading %s" % module.__name__)
        server.loadplugin(module)

    if args["--identify"]:
        def authenticate(server, line):
            """ Sends nickserv credentials after the server preamble. """
            if args["--auth"]:
                cmd = "nickserv AUTH %s"
            else:
                cmd = "nickserv IDENTIFY %s"
            server.sendline(cmd % args["--identify"])

        server.register("376", authenticate)
    if args["--debug"]:
        @Callback.inline
        def log(server, line):
            """ Prints all inbound irc messages. """
            print("%s → %s" % (server.server[0], line))
        server.printer.verbosity = Printer.FULL_MESSAGE | Printer.QUEUE_STATE
        server.register("ALL", log)

    print("Running...")
    server.start()
    try:
        server.join()
    except KeyboardInterrupt:
        print("Terminating...")
        server.connected = False
        server.sock.send("QUIT\r\n".encode("utf-8"))
    if server.restart is True:
        print("Restarting...")
        subprocess.call(sys.argv)

if __name__ == "__main__":
    main()

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
"""

import socket
import sys
import subprocess

import docopt

from bot.threads import StatefulBot, loadplugin, Printer
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
    server = StatefulBot(args["<config>"])

    server.connect()

    servername = args["<config>"].split(".")[0]

    modules = args["--plugins"].split(",")
    for mod in modules: 
        __import__(args["--plugins"])

    modules = [sys.modules[i] for i in modules]

    while modules:
        mod = modules.pop()
        if mod.__name__ in exclude:
            print("Skipping %s" % mod.__name__)
            continue
        if "__modules__" in dir(mod):
            # Subpackage. Import submodules.
            for submodule in mod.__modules__:
                modules.append(submodule)

        print("Loading %s" % mod.__name__)
        loadplugin(mod, servername, server, server.printer)

    if args["--identify"]:
        def authenticate(line):
            """ Sends nickserv credentials after the server preamble. """
            if args["--auth"]:
                cmd = "nickserv AUTH %s"
            else:
                cmd = "nickserv IDENTIFY %s"
            server.sendline(cmd % args["--identify"])

        server.register("376", authenticate)
    if args["--debug"]:
        @Callback.inline
        def log(line):
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

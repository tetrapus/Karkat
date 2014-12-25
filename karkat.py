#! /usr/bin/env python3.3
# -*- coding: utf-8 -*-
"""
Usage: %(name)s [options] <config>

Options:
    -h --help                          Show this message.
    --version                          Show version.
    -p PACKAGE, --plugins=PACKAGE      Set plugin package [default: plugins]
    -e PLUGINS, --exclude=PLUGINS      Don't load these plugins
    -d --debug                         Turn on debugging
    -i PASSWORD, --identify=PASSWORD   Identify with the given password
    -s --stdin                         Take password from STDIN
    -r --restart                       Restart on disconnect
    -c NUM, --connections=NUM          Number of output connections [default: 1]
"""

import os
import socket
import sys
from collections import deque

import docopt

from bot.threads import StatefulBot, Printer, Bot
from util.irc import Callback, Message
import util.text
import util.scheduler

__version__ = 2.0

socket.setdefaulttimeout(1800)

GP_CALLERS = 2


def main():
    """
    Karkat's mainloop simply spawns a server and registers all plugins.
    You can replace this.
    """
    # Parse command line args
    args = docopt.docopt(__doc__ % {"name": sys.argv[0]}, version=__version__)
    exclude = args["--exclude"].split(",") if args["--exclude"] else []
    config_file = args["<config>"]
    num_connections = int(args["--connections"])
    
    if args["--stdin"]:
        args["--identify"] = input("Password: ")
        sys.argv.extend(["--identify", args["--identify"]])

    if args["--debug"]:
        debug = 0.15
    else:
        debug = None

    server = StatefulBot(config_file, debug=debug)

    if int(args["--connections"]) > 1:
        def cleanup(output):
            """ Signal main thread to terminate """
            output.connected = False

        outputs = [Bot(config_file) for i in range(num_connections-1)]
        for output in outputs:
            output.connect()
            server.printer.add(output)
            server.register("DIE", cleanup)
            output.start()

    if args["--restart"]:
        server.restart = True
    server.connect()
    os.makedirs(server.get_config_dir(), exist_ok=True)

    plugins = deque(args["--plugins"].split(","))
    loaded = []

    while plugins:
        plugin = plugins.popleft()
        if plugin in exclude:
            print("Skipping %s" % plugin)
            continue
        try:
            __import__(plugin)
            mod = sys.modules[plugin]
        except ImportError:
            print("Warning: %s not loaded." % (plugin))
        else:
            if "__modules__" in dir(mod):
                plugins.extend("%s.%s" % (plugin, i) for i in mod.__modules__)
            loaded.append(mod)

    for module in loaded:

        print("Loading %s" % module.__name__)
        server.loadplugin(module)

    if args["--identify"]:
        def authenticate(server, line):
            """ Sends nickserv credentials after the server preamble. """
            msg = Message(line)
            if msg.address.nick == "NickServ":
                if "is a registered nick." in msg.text:
                    cmd = "nickserv AUTH %s"
                elif msg.text.startswith("This nickname is registered."):
                    cmd = "nickserv IDENTIFY %s"
                else:
                    return
                server.sendline(cmd % args["--identify"])

        server.register("notice", authenticate)
    if args["--debug"]:
        @Callback.inline
        def log(server, line):
            """ Prints all inbound irc messages. """
            print("%s → %s" % (server.server[0], util.text.ircstrip(line)))
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

    util.scheduler.stop()

    if server.restart is True:
        print("Restarting...")
        sys.stdout.flush()
        sys.stderr.flush()
        os.execv(sys.argv[0], sys.argv)

if __name__ == "__main__":
    main()

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
"""

"""
Defining a Karkat plugin.

The following can optionally be defined to hook into karkat:
__callbacks__: A mapping of callbacks.
__icallbacks__:  A mapping of inline callbacks.
__initialise__(name, botobj, printer) : A function to initialise the module.
__destroy__(): A function triggered on bot death.
"""

import socket
import sys
import subprocess

import docopt

from threads import StatefulBot, loadplugin
from irc import Callback

__version__ = 2.0

socket.setdefaulttimeout(1800)

GP_CALLERS = 2

if __name__ == "__main__":
    args = docopt.docopt(__doc__ % {"name": sys.argv[0]}, version=__version__)
    exclude = args["--exclude"].split(",")
    server = StatefulBot(args["<config>"])

    server.connect()
    printer = server.printer

    servername = args["<config>"].split(".")[0]

    __import__(args["--plugins"])

    modules = sys.modules[args["--plugins"]].__all__

    while modules:
        mod = modules.pop()
        if mod.__name__ in exclude:
            print("Skipping %s" % mod.__name__)
            continue
        if "__all__" in dir(mod):
            # Subpackage. Import submodules.
            modules.extend(mod.__all__)
            continue

        loadplugin(mod, servername, server, server.printer)
        print("Loaded %s" % mod.__name__)

    if args["--identify"]:
        def authenticate(line):
            server.sendline("msg nickserv :identify %s" % args["--identify"])
        server.register("376", authenticate)
    if args["--debug"]:
        @Callback.inline
        def log(line):
            print("[%s] %s" % (server.server[0], line))
        server.register("ALL", log)

    print("Running...")
    server.start()
    try:
        server.join()
    except KeyboardInterrupt:
        print("Terminating...")
        server.connected = False
        server.sock.send("QUIT\r\n".encode("utf-8"))
    if server.restart == True:
        print("Restarting...")
        subprocess.call(sys.argv)

#! /usr/bin/python3
# -*- coding: utf-8 -*-
"""
Usage: %(name)s [options] <config>

Options:
    -h --help                           Show this message.
    --version                           Show version.
    -v N, --verbosity=N                 Set verbosity [default: 1]
    -p PACKAGE, --plugins=PACKAGE       Set plugin package [default: plugins]
    -e MODULES, --exclude=MODULES       Comma separated list of modules to exlcude
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

#TODO: Move connection object and subclasses
# TODO: Turn subclasses into objects owned by the connection thread.
if __name__ == "__main__":
    args = docopt.docopt(__doc__ % {"name": sys.argv[0]})

    server = StatefulBot(args["<config>"])

    server.connect()
    printer = server.printer

    servername = args["<config>"].split(".")[0]

    plugins = __import__("plugins") # temporary
    modules = plugins.__all__

    while modules:
        mod = modules.pop()
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

"""
    while server.connected:
        try:
            exec(input())
        except KeyboardInterrupt:
            print("Terminating...")
            server.connected = False
            server.sock.send("QUIT\r\n".encode("utf-8"))
        except BaseException:
            sys.excepthook(*sys.exc_info())
"""
#! /usr/bin/python3
# -*- coding: utf-8 -*-
"""
Usage: %(name)s [options] <config>

Options:
    -h --help                       Show this screen.
    --version                       Show version.
    -v N, --verbosity=N             Set verbosity [default: 1]
    -c FILE, --config=FILE          Set server config [default: default.yaml]
    -p PACKAGE, --plugins=PACKAGE   Set plugin package [default: plugins]
    -e MODULES, --exclude=MODULES   Comma separated list of modules to exlcude
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

import docopt

from threads import StatefulBot, loadplugin
from irc import Callback

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

def authenticate(words, line):
    if "-i" in sys.argv:
        try:
            password = sys.argv[sys.argv.index("-i")+1]
        except IndexError:
            return
        else:
            server.sendline("msg nickserv identify %s" % password)

@Callback.inline
def log(line):
    if "-d" in sys.argv:
        print("[%s] %s" % (server.server[0], line))

flist = {
         "376" : [#authenticate, # plugin
                  ], 
        }

inline = {
         "privmsg" : [#Callback.inline(lambda y: printer.set_target(Message(y).context)),  # Bot ???
                    ],
         "ALL"     : [Callback.inline(log)], # plugin
}


if __name__ == "__main__":
    args = docopt.docopt(__doc__ % {"name": sys.argv[0]})
    print (args)
    #if "-f" in sys.argv:
    #    exec(open("features.py").read())
    #    # Temporary.

    servername = sys.argv[1].split(".")[0]

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

    server.register_all(flist)
    server.register_all(inline)

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

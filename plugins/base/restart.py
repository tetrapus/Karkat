"""
Triggers a bot restart.
"""

from util.irc import command

@command("restart", public=":", private="", admin=True)
def set_restart(server, message):
    """ Set the restart flag and disconnect. """
    server.restart = True
    if message.arg is None:
        server.printer.raw_message("QUIT :Restarting...")
    else:
        server.printer.raw_message("QUIT :Restarting: " + message.arg)

@command("quit", public=":", private="", admin=True)
def shut_down(server, message):
    """ Disconnect from the server, ensuring that the restart flag is unset. """
    server.restart = False
    if message.arg is None:
        server.printer.raw_message("QUIT :Shutting down")
    else:
        server.printer.raw_message("QUIT :Shutting down: " + message.arg)

__callbacks__ = {"privmsg": [set_restart, shut_down]}

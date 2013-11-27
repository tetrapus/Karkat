from util.irc import command

@command("restart", public=":", private="", admin=True)
def set_restart(server, message):
    server.restart = True
    server.printer.raw_message("QUIT :Restarting...")
__callbacks__ = {"privmsg": [set_restart]}
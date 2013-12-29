""" Sets mode +B on connect. """

def set_botmode(server, line):
    server.printer.raw_message("MODE %s +B" % server.nick)

__callbacks__ = {"001": [set_botmode]}

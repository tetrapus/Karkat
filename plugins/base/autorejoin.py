""" Rejoins a channel when kicked. """

def autorejoin(server, line):
    words = line.split()
    if server.eq(words[3], server.nick):
        server.sendline("JOIN %s" % words[2])

__callbacks__ = {"kick": [autorejoin]}

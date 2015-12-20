from bot.events import Callback
from util.irc import Address

class Accounts(object):
    def __init__(self):
        self.registered = {}


class Registration(Callback):
    def __init__(self, server):
        server.registered = {}
        self.__callbacks__ = {
            "join": [self.joined],
            "307":  [self.identified],
            "330":  [self.identified],
            "nick": [self.nick],
            "quit": [self.quit],
            "352":  [self.who],
            "kick": [self.kick],
            "part": [self.part]
        }
        super().__init__(server)
    
    @Callback.inline
    def joined(self, server, line):
        words = line.split()
        nick = server.lower(Address(words[0]).nick)            
        if nick not in server.registered:
            server.registered[nick] = False
            #server.printer.raw_message("WHOIS :%s" % nick)

    @Callback.inline
    def identified(self, server, line):
        words = line.split()
        nick = server.lower(words[3])
        server.registered[nick] = True

    @Callback.inline
    def nick(self, server, line):
        words = line.split()
        del server.registered[server.lower(Address(words[0]).nick)]
        server.registered[server.lower(words[2][1:])] = False        
        #server.printer.raw_message("WHOIS %s" % words[2])


    def part(self, server, line):
        words = line.split()
        channel = server.lower(words[2])
        nick = Address(words[0]).nick
        if all(not server.isIn(nick, users) for chan, users in server.channels.items() if not server.eq(channel, chan)):
            del server.registered[server.lower(nick)]

    def kick(self, server, line):
        words = line.split()
        channel = server.lower(words[2])
        nick = words[3]
        if all(not server.isIn(nick, users) for chan, users in server.channels.items() if not server.eq(channel, chan)):
            del server.registered[server.lower(nick)]


    @Callback.inline
    def quit(self, server, line):
        words = line.split()
        del server.registered[server.lower(Address(words[0]).nick)]

    @Callback.background
    def who(self, server, line):
        words = line.split()
        nick = server.lower(words[7])
        if nick not in server.registered:
            server.registered[nick] = False
            #server.printer.raw_message("WHOIS :%s" % nick)
        

__initialise__ = Registration
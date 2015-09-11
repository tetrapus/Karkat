import time
import datetime
import re

from bot.events import Callback, command
from util.irc import IRCEvent

# TODO: Caching
#       Scrollback
#       sed
#       search

def abstime(timestamp):
    date = datetime.datetime.utcfromtimestamp(timestamp)
    if date.year == datetime.datetime.utcfromtimestamp(time.time()):
        return date.strftime("%B %-d, %H:%M")
    else:
        return date.strftime("%B %-d, %Y")


def timefmt(timestamp):
    timediff = int(time.time() - timestamp)

    minutes, seconds = divmod(timediff, 60)
    if not minutes:
        return "%d seconds ago" % seconds
    hours, minutes = divmod(minutes, 60)
    if not hours:
        return "%d minutes ago" % minutes
    days, hours = divmod(hours, 24)
    if not days:
        if minutes > (5 + hours):
            return "%d hours %d mins ago" % (hours, minutes)
        else:
            return "%d hours ago" % hours
    if days < 10:
        if hours > days:
            return "%d days %d hours ago" % (days, hours)
        else:
            return "%d days ago" % days
    else:
        return abstime(timestamp)


def msgfmt(evt):
    if evt.args[1].startswith("\x01ACTION ") and evt.args[1].endswith("\x01"):
        return "\x0306•\x03 %s %s" % (evt.sender.nick, evt.args[1][8:-1])
    elif evt.args[1][0] == evt.args[1][-1] == "\x01":
        return "\x0306• CTCP\x03 %s" % (evt.args[1][1:-1])
    return "\x0315<\x03%s\x0315>\x03 %s" % (evt.sender.nick, evt.args[1])

def noticefmt(evt):
    if evt.args[1].startswith("\x01ACTION ") and evt.args[1].endswith("\x01"):
        return "\x0313•\x03 %s %s" % (evt.sender.nick, evt.args[1][8:-1])
    elif evt.args[1][0] == evt.args[1][-1] == "\x01":
        return "\x0313• NCTCP\x03 %s" % (evt.args[1][1:-1])
    return "\x0313-\x03%s\x0313-\x03 %s" % (evt.sender.nick, evt.args[1])

def nickfmt(evt):
    return "\x0303•\x03 %s changed their nick to %s" % (evt.sender.nick, evt.args[0])

def quitfmt(evt):
    if len(evt.args) == 1:
        quitmsg = " (%s)" % evt.args[0]
    else:
        quitmsg = ""
    return "\x0307•\x03 %s disconnected%s" % (evt.sender.nick, quitmsg)

def partfmt(evt):
    if len(evt.args) == 2:
        partmsg = " (%s)" % evt.args[1]
    else:
        partmsg = ""
    return "\x0307•\x03 %s left %s%s" % (evt.sender.nick, evt.args[0], partmsg)

def joinfmt(evt):
    return "\x0303•\x03 %s joined %s" % (evt.sender.nick, evt.args[0])

def traceuser(address, logs, lower):
    userinf = {(address.nick, address.ident, address.mask)}
    for ts, line in logs:
        try:
            evt = IRCEvent(line)
        except:
            print("[Logger] Warning: Could not parse %s" % line)
            continue
        if evt.type == "NICK" and (evt.sender.nick, evt.sender.ident, evt.sender.mask) in userinf:
            userinf.add((evt.args[0], evt.sender.ident, evt.sender.mask))
        elif evt.type == "JOIN" and any(lower(evt.sender.nick) == lower(nick)
                                     or (evt.sender.ident, evt.sender.mask)  == (ident, mask)
                                     for nick, ident, mask in userinf):
            userinf.add((evt.sender.nick, evt.sender.ident, evt.sender.mask))
    return userinf
            

class Logger(Callback):
    formatters = {"NICK": nickfmt,
                  "QUIT": quitfmt,
                  "PART": partfmt,
                  "NOTICE": noticefmt,
                  "PRIVMSG": msgfmt,
                  "JOIN": joinfmt}

    def __init__(self, server):
        self.logs = []
        self.logpath = server.get_config_dir("log.txt")
        self.sedchans = []
        try: open(self.logpath, "x")
        except FileExistsError: pass
        with open(self.logpath) as logfile:
            for line in logfile:
                try:
                    timestamp, text = line.split(" ", 1)
                    self.logs.append((float(timestamp), text.rstrip("\n")))
                except:
                    print("[Logger] Warning: Could not parse %s" % line)
        super().__init__(server)

    @Callback.inline
    def log(self, server, line) -> "ALL":
        timestamp = time.time()
        with open(self.logpath, "a") as logfile:
            logfile.write("%f %s\n" % (timestamp, line))
        self.logs.append((timestamp, line))
    
    @command("seen lastseen", r"(\S+)")
    def seen(self, server, msg, user):
        if server.eq(user, msg.address.nick):
            return "04⎟ You're right there!"
        types = ['NICK', 'QUIT', 'PART', 'NOTICE', 'PRIVMSG', 'JOIN']
        for timestamp, line in reversed(self.logs):
            try:
                evt = IRCEvent(line)
                if evt.type not in types:
                    continue
                if evt.type in ["PART", "NOTICE", "PRIVMSG", "JOIN"] and not server.eq(evt.args[0], msg.context):
                    continue
                if server.eq(evt.sender.nick, user) or (evt.type == "NICK" and server.eq(evt.args[0], user)):
                    if server.isIn(user, server.channels.get(server.lower(msg.context))):
                        status = " · \x0312online now"
                    else:
                        for nick, _, _ in traceuser(evt.sender, filter(timestamp.__lt__, self.logs), server.lower):
                            if server.isIn(nick, server.channels.get(server.lower(msg.context))):
                                status = " · \x0312online as %s" % nick
                                break
                        else:
                            status = ""
                    return "%s · \x1d%s%s" % (self.formatters[evt.type](evt), timefmt(timestamp), status)
            except:
                print("[Logger] Warning: Could not parse %s" % line)
        return "04⎟ I haven't seen %s yet." % user

    @command("last lastspoke lastmsg", r"(\S)+")
    def lastspoke(self, server, msg, user):
        if server.eq(user, msg.address.nick):
            return "04⎟ You just spoke!"
        for timestamp, line in reversed(self.logs):
            try:
                evt = IRCEvent(line)
                if evt.type != "PRIVMSG" or not server.eq(evt.args[0], msg.context):
                    continue
                if server.eq(evt.sender.nick, user):
                    return "%s · \x1d%s" % (msgfmt(evt), timefmt(timestamp))
            except:
                print("[Logger] Warning: Could not parse %s" % line)
        return "04⎟ I haven't seen %s speak yet." % user

    @msghandler
    def substitute(self, server, msg):
        match = re.match(r"^(\S+:\s+)?s(\W)(.*?)\1(.*?)(\1g?)?$", msg.text)
        if match:
            target, sep, pattern, sub, flags = match.groups()
            if target is not None: target = target.rstrip(": ")
            if flags is not None: flags = set(flags[1:])
            pattern = re.escape(pattern)
            for timestamp, line in reversed(self.logs):
                # TODO: implement real regular expressions
                # also self-regex
                try:
                    evt = IRCEvent(line)
                    if (evt.type == "PRIVMSG" 
                        and server.eq(msg.context, evt.args[0])
                        and (target is None or server.eq(target, evt.sender.nick))
                        and re.match(pattern, evt.args[1], flags=re.IGNORECASE)):
                        return msgfmt(re.sub(pattern, sub, evt.args[1], count=0 if 'g' in flags else 1, flags=re.IGNORECASE))
                except:
                    print("[Logger] Warning: Could not parse %s" % line)
__initialise__ = Logger
import time
import re
import random

from bot.events import Callback, command
from util.text import pretty_date
from util.irc import Address, Message
#from util import scheduler


time_expression = r"((?:(?:\d+|an?)\s*(?:[wdhms]|(?:sec|min|second|minute|hour|day|week|wk|hr)s?)\s*)+)"

seconds_map = {"w": 604800,
               "wk": 604800,
               "week": 604800,
               "d": 24 * 60 * 60,
               "day": 24 * 60 * 60,
               "h": 60 * 60,
               "hr": 60 * 60,
               "hour": 60 * 60, 
               "m": 60,
               "min": 60,
               "minute": 60,
               "": 1,
               "sec": 1,
               "second": 1}

def parse_time(expr):
    if not expr:
        return 0
    tokens = re.split(r"(\d+|an?)", expr)
    tokens = tokens[1:]
    tokens = [i.strip() for i in tokens]
    units = zip(tokens[::2], tokens[1::2])
    seconds = 0
    for num, unit in units:
        if num.isdigit():
            num = int(num)
        else:
            num = 1
        seconds += num * seconds_map[unit.rstrip("s").lower()]
    return seconds

class Reminder(Callback):
    def __init__(self, server):
        self.waiting = {}
        self.reminders = {}
        self.server = server
        super().__init__(server)

    @command("remind tell note send", r"^(?:to\s+)?(\S+)\s+(?:(?:in|after)\s+%(time)s\s+)?(?:that\s+)?(.+?)(?:\s+(?:in|after)\s+%(time)s)?(?:\s+via\s+(snapchat|pm|notice|channel message|message|private message))?(?:\s+every\s+%(time)s(?:\s+until\s+(cancelled|active))?)?$" % {"time": time_expression})
    def reminder(self, server, msg, user, after, text, after2, method, repeat, cancel):
        after = parse_time(after or after2)
        repeat = parse_time(repeat)
        method = (method or "channel message").lower()
        if method == "snapchat":
            return "Snapchat not yet implemented."

        self.reminders.setdefault(server.lower(user), []).append({"sender": msg.address, "message": text, "method": method, "time": time.time()})
        return "user=%(user)s, after=%(after)s, text=%(text)s, method=%(method)s, repeat=%(repeat)s, cancel=%(cancel)s" % locals()

    def privmsg_check(self, server, line) -> "privmsg":
        msg = Message(line)
        address = msg.address
        if server.lower(address.nick) in self.reminders:
            self.send_messages(address.nick, msg.context)

    def join_check(self, server, line) -> ["join", "nick"]:
        hostmask, method, context = line.split()
        address = Address(hostmask)
        if method.lower() == "join":
            channel = context[1:]
        else:
            channel = random.choice([i for i in server.channels if server.isIn(address.nick, server.channels[i])])
        if server.lower(address.nick) in self.reminders:
            self.send_messages(address.nick, channel)        

    def send_messages(self, user, context):
        for i in self.reminders[self.server.lower(user)]:
            method = {"pm": (user, "PRIVMSG"),
                     "private message": (user, "PRIVMSG"),
                     "message": (context, "PRIVMSG"),
                     "channel message": (context, "PRIVMSG"),
                     "notice": (user, "NOTICE")}[i["method"]]
            self.server.message("03│ ✉ │ %s: %s · from %s · ⌚ %s" % (user, i["message"], i["sender"], pretty_date(time.time() - i["time"])), *method)
        self.reminders[self.server.lower(user)] = []

__initialise__ = Reminder

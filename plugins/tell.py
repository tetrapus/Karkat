import time
import re
import random
import uuid
import json

from bot.events import Callback, command
from util.text import pretty_date
from util.irc import Address, Message
from util import scheduler


time_expression = r"((?:(?:\d+|\ban?\b)\s*(?:[wdhms]|(?:sec|min|second|minute|hour|day|week|wk|hr)s?)\s*)+)"

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
    tokens = re.split(r"(\d+|\ban?\b)", expr)
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

    REMINDERF = "reminders.json"

    def __init__(self, server):
        self.waiting = {}
        try:
            self.reminders = json.load(open(server.get_config_dir(self.REMINDERF)))
        except FileNotFoundError:
            self.reminders = {}
        else:
            for user in [i["sender"] for i in sum(self.reminders.values(), [])]:
                comchans = [i for i in server.channels if server.isIn(user, server.channels[i])]
                if comchans:
                    self.send_messages([i for i in server.channels[comchans[0]] if server.lower(i) == server.lower(user)][0], comchans[0])

        self.server = server
        super().__init__(server)

    @command("remind tell note send", r"^(?:to\s+)?(\S+):?\s+(?:(?:in|after)\s+%(time)s\s+)?(?:that|to\s+)?(what to \S+|.+?)(?:\s+(?:in|after)\s+%(time)s)?(?:\s+via\s+(snapchat|pm|notice|channel message|message|private message|#\S+))?(?:\s+every\s+%(time)s(?:\s+until\s+(cancelled|active))?)?$" % {"time": time_expression})
    def reminder(self, server, msg, user, after, text, after2, method, repeat, cancel):
        # TODO: handle inactive people
        # TODO: print reminders in last-spoke channel
        after = parse_time(after or after2)
        repeat = parse_time(repeat)
        method = (method or "channel message").lower()
        text = re.sub("\bs?he's\b", "you're", text, flags=re.IGNORECASE)
        text = re.sub("\bs?he|they\b\s+(\S+)s", r"you \1", text, flags=re.IGNORECASE)
        if user.lower() in ["me", "self"]:
            user = msg.address.nick
        if method == "snapchat":
            return "Snapchat not yet implemented."
        if re.match(r"what\s+to\s+\S+|(again\s+)later", text, re.IGNORECASE):
            return "Not yet implemented"

        jobid = uuid.uuid4().hex
        job = {"id": jobid, "sender": msg.address.nick, "message": text, "method": method, "time": time.time(), "after": after + time.time(), "channel": msg.context}

        def setreminder(job):
            self.waiting.setdefault(server.lower(user), {}).pop(jobid, None)
            comchans = sorted([i for i in server.channels if server.isIn(user, server.channels[i])], key=lambda x:not server.eq(x, msg.context))
            if comchans:
                self.send_messages([i for i in server.channels[comchans[0]] if server.lower(i) == server.lower(user)][0], comchans[0])
        
        self.reminders.setdefault(server.lower(user), []).append(job)

        if after:
            self.waiting.setdefault(server.lower(user), {})[jobid] = {"job": scheduler.schedule_after(after, setreminder, args=(job,)), "args": job}
        else:
            setreminder(job)

        with open(self.server.get_config_dir(self.REMINDERF), "w") as f:
            json.dump(self.reminders, f)

        return "user=%(user)s, after=%(after)s, text=%(text)s, method=%(method)s, repeat=%(repeat)s, cancel=%(cancel)s" % locals()

    def common_channels(self, user, user2=None):
        common = [i for i in self.server.channels if self.server.isIn(user, self.server.channels[i])]
        if user2:
            common = [i for i in common if self.server.isIn(user2, self.server.channels[i])]

    def privmsg_check(self, server, line) -> "privmsg":
        msg = Message(line)
        address = msg.address
        if server.lower(address.nick) in self.reminders:
            self.send_messages(address.nick, msg.context)

    def join_check(self, server, line) -> "join":
        hostmask, method, context = line.split()
        address = Address(hostmask)
        channel = context[1:]
        if server.lower(address.nick) in self.reminders:
            self.send_messages(address.nick, channel)       

    def nick_check(self, server, line) -> "nick":
        hostmask, method, nick = line.split()
        nick = nick[1:]

        channel = random.choice([i for i in server.channels if server.isIn(nick, server.channels[i])])
        if server.lower(nick) in self.reminders:
            self.send_messages(nick, channel)

    def send_messages(self, user, context, immediate=False):
        for i in self.reminders[self.server.lower(user)]:
            if time.time() >= i["after"] - 1: # Fudge factor
                method = {"pm": (user, "PRIVMSG"),
                         "private message": (user, "PRIVMSG"),
                         "message": (context, "PRIVMSG"),
                         "channel message": (context, "PRIVMSG"),
                         "notice": (user, "NOTICE")}[i["method"]]
                self.server.message("03│ ✉ │ %s: %s · from %s · ⌚ %s" % (user, i["message"], i["sender"], pretty_date(time.time() - i["time"])), *method)
                self.reminders[self.server.lower(user)].remove(i)
        with open(self.server.get_config_dir(self.REMINDERF), "w") as f:
            json.dump(self.reminders, f)

    def __destroy__(self, server):
        for i in self.waiting:
            for job in i.values():
                job["job"].cancel()

__initialise__ = Reminder

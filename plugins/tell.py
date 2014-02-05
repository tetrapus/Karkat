import re

from bot.events import Callback, command
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
        super().__init__(server)

    @command("remind tell note send", r"^(?:to\s+)?(\S+)\s+(?:in\s+%(time)s\s+)?(?:that\s+)?(.+?)(?:\s+via\s+(snapchat|pm|notice|globally))?(?:\s+every\s+%(time)s(?:\s+until\s+(cancelled|active))?)?$" % {"time": time_expression})
    def reminder(self, server, msg, user, after, text, method, repeat, cancel):
        return "user=%(user)s, after=%(after)s, text=%(text)s, method=%(method)s, repeat=%(repeat)s, cancel=%(cancel)s" % locals()

__initialise__ = Reminder

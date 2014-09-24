import random
import re
import time
import string

from bot.events import command, Callback, msghandler
from util.text import ircstrip
from util.scheduler import schedule_after

def strip(x):
    return "".join(i for i in ircstrip(x) if i in string.printable)

class Aggregator(Callback):
    def __init__(self, server):
        self.decision = {}
        self.results = {}
        super().__init__(server)

    @Callback.inline
    @command("choose", "(.+)", prefixes=("", "."))
    def choose(self, server, msg, query):
        if "," not in query: return
        context = server.lower(msg.context)
        self.decision[context] = time.time()
        self.results[context] = {strip(i.strip()): 0 for i in re.split(r",|\bor\b", query)}
        choose = random.choice(list(self.results[context].keys()))
        self.results[context][choose] += 1
        schedule_after(4, self.report, args=(server, msg.context))
        return "\x0309│\x03 " + choose

    @Callback.inline
    @msghandler
    def aggregate(self, server, msg):
        context = server.lower(msg.context)
        if context in self.decision and time.time() - self.decision[context] < 5:
            for i in self.results[context]:
                if re.match(r"(\S+: %s|\S+ chose '%s')$"%(re.escape(i), re.escape(i)), strip(msg.text)):
                    self.results[context][i] += 1

    def report(self, server, channel):
        data = sorted(self.results[server.lower(channel)].items(), key=lambda x: -x[1])
        if len(data) < 2: return
        choice = data[0][1]
        output = " · ".join("%s%s (%d)\x0f" % ("\x02" if i[1] == choice else "", i[0], i[1]) for i in data)
        server.message("\x039│\x03 " + output, channel)

__initialise__ = Aggregator

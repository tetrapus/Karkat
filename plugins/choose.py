import random
import re
import time
import string
import unicodedata

from bot.events import command, Callback, msghandler
from util.text import ircstrip
from util.scheduler import schedule_after

def strip(x):
    return "".join(i for i in ircstrip(x.strip()) 
                     if not unicodedata.category(i).startswith("C"))

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
        self.results[context] = {strip(i): 0 for i in re.split(r",|\bor\b", query)}
        schedule_after(1, self.report, args=(server, msg.context))

    @Callback.inline
    @msghandler
    def aggregate(self, server, msg):
        context = server.lower(msg.context)
        if context in self.decision and time.time() - self.decision[context] < 2:
            self.decision[context] = time.time()
            for i in self.results[context]:
                if re.match(r"(\S+: %s|\S+ chose '%s')$"%(re.escape(i), re.escape(i)), strip(msg.text)):
                    self.results[context][i] += 1

    def report(self, server, channel):
        if time.time() - self.decision[server.lower(channel)] < 2:
            schedule_after(1, self.report, args=(server, channel))
            return
        results = self.results[server.lower(channel)]
        highest = max(results.values())
        choice = random.choice([i for i in results if results[i] == highest])
        results[choice] += 1
        server.message("\x0309│\x03 " + choice, channel)
        data = sorted(results.items(), key=lambda x: -x[1])
        if len(data) < 2: 
            return
        output = " · ".join("%s%s (%d)\x0f" % ("\x02" if i[0] == choice else "", i[0], i[1]) for i in data)
        server.message("\x039│\x03 " + output, channel)

__initialise__ = Aggregator

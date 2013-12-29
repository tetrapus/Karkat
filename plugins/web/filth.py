"""
Calculates the filth ratio of a query via google.
"""

import re
import random
import requests
import urllib.parse
import json

from bot.events import Callback, command
from util.irc import Address


class PiracyMonitor(Callback):
    
    ipscan = True
    IPFILE = "iplog"
    
    def __init__(self, server):
        self.ipfile = server.get_config_dir(self.IPFILE)
        try:
            self.known = json.load(open(self.ipfile))
        except FileNotFoundError:
            self.known = {}
        super().__init__(server)

    def savestate(self):
        with open(self.ipfile, "w") as ipfile:
            json.dump(self.known, ipfile)

    @Callback.background
    def trigger(self, server, line) -> "ALL":
        words = line.split(" ")
        if not self.ipscan: 
            return
        
        ips = re.findall(r"(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)[-.]){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)", words[0])
        
        if not ips:
            return 
        
        ip = "".join(x if x.isdigit() else "." for x in ips[0])
        
        if ip in self.known: 
            return
        
        self.known[Address(words[0]).nick] = ip
        self.savestate()
        
        
class FilthRatio(Callback):

    def __init__(self, server):
        self.ips = PiracyMonitor(server)
        super().__init__(server)

    def filthratio(self, query, ip):
        query = urllib.parse.quote(query)
        safeRequest = requests.get("http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s&safe=active&userip=%s" % (query, ip), headers={"Referer" : "http://www.tetrap.us/"}).json()
        unsafeRequest = requests.get("http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s&userip=%s" % (query, ip), headers={"Referer" : "http://www.tetrap.us/"}).json()
        try:
            ratio = float(safeRequest["responseData"]["cursor"]["estimatedResultCount"])
        except KeyError:
            ratio = 0
        
        ratio /= float(unsafeRequest["responseData"]["cursor"]["estimatedResultCount"])
        
        return 1-ratio

    @Callback.threadsafe
    @command("filth", "(.+)")
    def trigger(self, server, message, query):
        try:
            user = message.address.nick
            if user not in self.ips.known:
                ip = random.choice(list(self.ips.known.values()))
            else:
                ip = self.ips.known[user]
            data = self.filthratio(query, ip)
            color = [4, 7, 8, 9, 3][int(min(max(0, data*5), 4))]
            return "06%s│ %s 06│%.2d %.2f%%" % ("Filth Ratio" if message.prefix != "." else "", query, color, data*100)
        except TypeError:
            return "05Filth Ratio│ Error: Google is an asshole."
        except KeyError:
            return "05Filth Ratio│ The fuck is %r?" % query

__initialise__ = FilthRatio
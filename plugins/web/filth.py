"""
Calculates the filth ratio of a query via google.
"""

import random
import requests
import urllib.parse

from bot.events import Callback, command
        
        
class FilthRatio(Callback):

    def __init__(self, server):
        super().__init__(server)
        if "iptracker" in dir(server):
            self.ips = server.iptracker.known
        else:
            self.ips = {"Lion": "114.76.231.168", "svkampen": "198.46.132.150"}


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
            if user not in self.ips:
                ip = random.choice(list(self.ips.values()))
            else:
                ip = self.ips[user]
            data = self.filthratio(query, ip)
            color = [4, 7, 8, 9, 3][int(min(max(0, data*5), 4))]
            return "06%s│ %s 06│%.2d %.2f%%" % ("Filth Ratio" if message.prefix != "." else "", query, color, data*100)
        except TypeError:
            return "05Filth Ratio│ Error: Google is an asshole."
        except KeyError:
            return "05Filth Ratio│ The fuck is %r?" % query

__initialise__ = FilthRatio
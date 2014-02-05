"""
Calculates the filth ratio of a query via google.
"""

import random
import requests
import urllib.parse as urllib

from bot.events import Callback, command
        

class FilthRatio(Callback):
    """
    Each filth ratio object keeps a pool of IP addresses from the server it came
    from, to help identify itself to google.
    """


    api_endpoint = "http://ajax.googleapis.com/ajax/services/search/web?"

    def __init__(self, server):
        super().__init__(server)
        if "iptracker" in dir(server):
            self.ips = server.iptracker.known
        else:
            self.ips = {"Lion": "114.76.231.168", "svkampen": "198.46.132.150"}


    def filthratio(self, query, userip):
        """
        Requests data from google and returns the filth ratio.
        """
        query = urllib.quote(query)
        request = {"q": query, "userip": userip, "v":"1.0"}
        headers = {"Referer" : "http://www.tetrap.us/"}
        unsafe = requests.get(self.api_endpoint + urllib.urlencode(request), 
                              headers=headers).json()
        request.update({"safe": "active"})
        safe = requests.get(self.api_endpoint + urllib.urlencode(request), 
                            headers=headers).json()
        try:
            ratio = safe["responseData"]["cursor"]["estimatedResultCount"]
        except KeyError:
            ratio = 0

        ratio = float(ratio)        

        ratio /= float(unsafe["responseData"]["cursor"]["estimatedResultCount"])
        
        return 1-ratio

    @Callback.threadsafe
    @command("filth", "(.+)")
    def trigger(self, server, message, query):
        """
        Calculate the filth ratio for a query.
        """
        try:
            user = message.address.nick
            if user not in self.ips:
                userip = random.choice(list(self.ips.values()))
            else:
                userip = self.ips[user]
            data = self.filthratio(query, userip)
            color = [4, 7, 8, 9, 3][int(min(max(0, data*5), 4))]
            return "06%s│ %s 06│%.2d %.2f%%" % (
                                "Filth Ratio" if message.prefix != "." else "", 
                                query, 
                                color, 
                                data * 100)
        except TypeError:
            return "05Filth Ratio│ Error: Google is an asshole."
        except KeyError:
            return "05Filth Ratio│ The fuck is %r?" % query

__initialise__ = FilthRatio

import json
import re

from bot.events import Callback
from util.irc import Address

class IPTracker(Callback):
    
    ipscan = True
    IPFILE = "iplog"
    
    def __init__(self, server):
        self.ipfile = server.get_config_dir(self.IPFILE)
        try:
            self.known = json.load(open(self.ipfile))
        except FileNotFoundError:
            self.known = {}
        server.iptracker = self
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

__initialise__ = IPTracker
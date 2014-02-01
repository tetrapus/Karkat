from util.services import url as URL
from util.irc import Callback, command
import re

class LinkGrabber(object):
        
    def __init__(self):
        self.links = {}
        
    @Callback.background
    def trigger_linkget(self, server, line):
        x = list(line.split(" "))
        if x[2][0] == "#":
            x[3] = x[3][1:]
            self.links.setdefault(server.lower(x[2]), []).extend([i for i in x[3:] if re.match("^(http|https|ftp)\://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,3}(:[a-zA-Z0-9]*)?/?([a-zA-Z0-9\-\._\?\,\'/\\\+&%\$#\=~])*$", i)])

lg = LinkGrabber()

@Callback.threadsafe
@command("shorten shortgo bl bitly bit.ly".split(), "(.*)", private="!", public="@.",
			usage="12│ 🔗 │ Usage: !shorten <url>",
			error="05│ 🔗 │ Unable to generate shortlink.")
def shortgo(server, message, url):
    if not url: url = lg.links[server.lower(message.context)][-1]
    return "12%s│ %s" % ("" * message.text.startswith("@"), URL.format(URL.shorten(url)))

__callbacks__ = {"privmsg": [shortgo, lg.trigger_linkget]}
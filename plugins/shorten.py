from util.services import url as URL
from util.irc import Callback
import re

def __initialise__(name, server, printer):
    cb = Callback()
    cb.initialise(name, server, printer)

    class LinkGrabber(object):
            
        def __init__(self):
            self.links = {}
            
        @Callback.background
        def trigger_linkget(self, line):
            x = list(line.split(" "))
            if x[2][0] == "#":
                x[3] = x[3][1:]
                self.links.setdefault(server.lower(x[2]), []).extend([i for i in x[3:] if re.match("^(http|https|ftp)\://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,3}(:[a-zA-Z0-9]*)?/?([a-zA-Z0-9\-\._\?\,\'/\\\+&%\$#\=~])*$", i)])

    lg = LinkGrabber()
    server.register("privmsg", lg.trigger_linkget)

    @cb.threadsafe
    @cb.command("shorten shortgo bl bitly bit.ly".split(), "(.*)", private="!", public="@.",
    			usage="12bit.ly│ Usage: !shorten <url>",
    			error="05bit.ly│ Unable to generate shortlink.")
    def shortgo(message, url):
        if not url: url = lg.links[server.lower(message.context)][-1]
        return "12%s│ %s" % ("bit.ly" * message.text.startswith("@"), URL.format(URL.shorten(url)))

    server.register("privmsg", shortgo)
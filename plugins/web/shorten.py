"""
Interface to bit.ly link shortening service.
"""

from util.services import url as URL
from bot.events import Callback, command
import re


urlexpr = re.compile(r"^(http|https|ftp)\://"\
                     r"[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,3}"\
                     r"(:[a-zA-Z0-9]*)?"\
                     r"/?([a-zA-Z0-9\-\._\?\,\'/\\\+&%\$#\=~])*$")

templates = {Callback.USAGE: "12│ 🔗 │ Usage: !shorten <url>",
             Callback.ERROR: "05│ 🔗 │ Unable to generate shortlink."}

class LinkGrabber(object):
    """
    Scrapes links from channel messages.
    """

    def __init__(self):
        self.links = {}
        
    @Callback.background
    def trigger(self, server, line):
        """
        Scrape for URLs
        """
        words = list(line.split(" "))
        if words[2][0] == "#":
            words[3] = words[3][1:]
            self.links.setdefault(server.lower(words[2]), 
                                  []).extend([i for i in words[3:] 
                                                if urlexpr.match(i)])

    def last(self, channel):
        """
        Return the last linked URL in a channel.
        """
        return self.links[channel][-1]

grabber = LinkGrabber()

@Callback.threadsafe
@command("shorten shortgo bl bitly bit.ly", "(.*)", templates=templates)
def shortgo(server, message, url):
    """
    Shorten a URL. If no URL is provided, shorten the last posted URL.
    """
    if not url: 
        url = grabber.last(server.lower(message.context))
    return "12%s│ %s" % ("🔗" * message.text.startswith("@"), 
                             URL.format(URL.shorten(url)))

__callbacks__ = {"privmsg": [shortgo, grabber.trigger]}

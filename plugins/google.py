import re
import urllib.parse as urllib

import requests

from util.irc import Callback
from util.text import unescape

cb = Callback()

templates = {"@": "%(color).2d⎟ 02%(title)s\n%(color).2d⎟ 03↗ %(url)s\n%(color).2d⎟ %(description)s",
             ".": "%(color).2d⎟ %(title)s 12↗ %(url)s",
             "!": "%(color).2d⎟ %(title)s 12↗ %(url)s"}

maxlines = {"@": 1,
            ".": 4,
            "!": 6}
deflines = {"@": 1,
            ".": 1,
            "!": 4}

@cb.threadsafe
@cb.command(["google", "search"], "(-\d\s+)?(.+)", private="!", public=".@",
            usage="12Google⎟ Usage: !google [-NUM_RESULTS] <query>",
            error="04Google⎟ Error: Could not fetch google results.")
def google(message, nresults, query):
    if nresults:
        nresults = min(-int(nresults.strip()), maxlines[message.prefix])
    else:
        nresults = deflines[message.prefix]

    page = requests.get("http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s" % urllib.quote(query)).json()

    if page["responseData"]["results"]:
        if any("suicide" in i["title"].lower() for i in page["responseData"]["results"]):
            page = requests.get("http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s" % urllib.quote("it gets better")).json()
        for i, result in enumerate(page["responseData"]["results"]): 
            if i >= nresults: return
            data = {"color" : [12, 5, 8, 3][i % 4],
                    "title" : unescape(result["title"].replace("<b>", "").replace("</b>", "")),
                    "url"   : result["unescapedUrl"],
                    "description": re.sub(r"\s+", 
                                          " ", 
                                          unescape(result["content"].replace("<b>", "").replace("</b>", "")))}
            yield templates[message.prefix] % data
    else:
        yield "05Google⎟ No results found."


__initialise__ = cb.initialise
__callbacks__  = {"privmsg": [google]}
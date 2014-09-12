import requests
import random
import re

from bot.events import command
from util.services import url

def get_rand_link(sub):
    for i in range(5):
        try:
            link = requests.get("http://reddit.com/r/%s/random.json"%sub).json()[0]["data"]["children"][0]["data"]
            if link["is_self"]: continue
        except:
            continue
        else:
            return link

@command("5050 fiftyfifty", r"(?:([A-Za-z0-9][A-Za-z0-9_]{2,20}(?:,\s+[A-Za-z0-9][A-Za-z0-9_]{2,20})*)\s+([A-Za-z0-9][A-Za-z0-9_]{2,20}(?:,\s+[A-Za-z0-9][A-Za-z0-9_]{2,20})*))?")
def fiftyfifty(server, message, good, bad):
    if good and bad:
        good, bad = random.choice(re.split(r",\s+", good)), random.choice(re.split(r",\s+", bad))
        good, bad = get_rand_link(good), get_rand_link(bad)
        if good is None or bad is None:
            return "Couldn't find a link post"
        title, link = "[50/50] %s | %s" % (good["title"], bad["title"]), random.choice([good, bad])

    else:
        link = get_rand_link("fiftyfifty")
        if link is None:
            return "Couldn't find a link post"
        title = link["title"]
    
    return "│ %s · \x0312\x1f%s" % (title, url.shorten(link["url"]))

__callbacks__ = {"privmsg": [fiftyfifty]}
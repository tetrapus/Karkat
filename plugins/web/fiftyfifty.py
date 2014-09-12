import requests
import random
import re

from bot.events import command
from util.services import url

def get_rand_link(sub):
    try:
        links = requests.get("http://reddit.com/r/%s/%s.json" % (sub, random.choice(["new", "hot"])), headers={"User-Agent": "Karkat/3.0 by Lyucit"}).json()["data"]["children"]
        links = [i["data"] for i in links if not i["data"]["is_self"]]
        if not links:
            return
    except:
        return    
    else:
        return random.choice(links)

@command("5050 50/50 fiftyfifty", r"(?:([A-Za-z0-9][A-Za-z0-9_]{2,20}(?:,\s+[A-Za-z0-9][A-Za-z0-9_]{2,20})*)\s+([A-Za-z0-9][A-Za-z0-9_]{2,20}(?:,\s+[A-Za-z0-9][A-Za-z0-9_]{2,20})*))?")
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
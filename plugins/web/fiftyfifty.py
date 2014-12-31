import requests
import random
import re

from bot.events import command
from util.services import url
from util.text import unescape

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

subreddit_rx = r"[A-Za-z0-9][A-Za-z0-9_]{2,20}"

defaults = [[["fiftyfifty"]], 
            [["aww"], ["spacedicks"]],
            [["gonewild"], ["mangonewild"]]]

@command("5050 50/50 fiftyfifty", r"(.*)")
def fiftyfifty(server, message, sublist):
    if not sublist:
        sublist = random.choice(defaults)
    else:
        sublist = [[i for i in x.strip().split() if re.match(subreddit_rx, i)] for x in sublist.split("|")]
    subs = [random.choice(i) for i in sublist]
    links = [get_rand_link(i) for i in subs]
    if None in links:
        return "\x0304│ 50/50 |\x0304 Couldn't find a link post."
    link = random.choice(links)["url"]
    titles = " | ".join(i["title"] for i in links)
    if len(sublist) > 1:
        titles = "%s \x0308│\x03 %s" % ("/".join(["%d"%(100//len(sublist))]*len(sublist)), titles)
    else:
        titles = re.sub(r"^\[50/50\] ", "50/50 \x0308│\x03 ", titles)
    return "\x0308│\x03 %s · \x0312\x1f%s" % (titles, url.shorten(link))

__callbacks__ = {"privmsg": [fiftyfifty]}
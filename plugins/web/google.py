"""
Perform google web searches.
"""

import re
import urllib.parse as urllib

import requests

from bot.events import Callback, command
from util.text import unescape

exceptions = {Callback.USAGE: "12Google│ "\
                              "Usage: !google [-NUM_RESULTS] <query>",
              Callback.ERROR: "04Google│ "\
                              "Error: Could not fetch google results."}

templates = {'@': "%(color).2d│ 02%(title)s\n%(color).2d│"\
                  " 03↗ %(url)s\n%(color).2d│ %(description)s",
             '.': "%(color).2d│ %(title)s 12↗ %(url)s",
             '!': "%(color).2d│ %(title)s 12↗ %(url)s"}

maxlines = {'@': 1,
            '.': 4,
            '!': 6}
deflines = {'@': 1,
            '.': 1,
            '!': 4}

google_api_url = "http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q="


def google(query, nresults, retry=None):
    """
    Perform a google search and return the first nresults results.

    If a result matches a key in retry, the query is replaced with the value
    of that key.
    """
    page = requests.get(google_api_url + urllib.quote(query)).json()
    data = []

    if page["responseData"]["results"]:
        for keyword in retry or {}:
            if any(keyword in i["title"].lower() 
                    for i in page["responseData"]["results"]):
                return google(retry[keyword], nresults)

        for i, result in enumerate(page["responseData"]["results"]): 
            if i >= nresults: 
                break

            data.append({"color" : [12, 5, 8, 3][i % 4],
                    "title": unescape(re.sub("</?b>", "", result["title"])),
                    "url"  : result["unescapedUrl"],
                    "description": re.sub(r"\s+", 
                                          " ", 
                                          unescape(re.sub("</?b>", "", 
                                                    result["content"])))})
    return data

@Callback.threadsafe
@command("google gooogle goooogle gooooogle search g", r"(-\d\s+)?(.+)",
         templates=exceptions)
def google_template(server, message, nresults, query):
    """
    Perform a google search and print the first n results.
    If a search is a gooo+gle search, use the number of extra 'o's as nresults.
    """
    if message.command.lower() in ["gooogle", "goooogle", "gooooogle"]:
        nresults = "-%d" % (len(message.command) - 5)

    if nresults:
        nresults = min(-int(nresults.strip()), maxlines[message.prefix])
    else:
        nresults = deflines[message.prefix]

    response = google(query, nresults, {"suicide": "it gets better"})
    for data in response:
        yield templates[message.prefix] % data
    if not response:
        yield "05Google│ No results found."


__callbacks__  = {"privmsg": [google_template]}

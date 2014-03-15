import requests
import re

from bot.events import command, Callback
from util.services import url
from util.text import unescape

exceptions = {Callback.USAGE: "12Google Images│ "\
                              "Usage: .image [-NUM_RESULTS] <query>",
              Callback.ERROR: "04Google Images│ "\
                              "Error: Could not fetch google image results."}


templates = {'@': "%(color).2d│ 02%(title)s · %(content)s\n"\
                  "%(color).2d│ 12↗ %(url)s · %(width)s×%(height)s · 03%(fullurl)s",
             '.': "%(color).2d│ 12↗ %(url)s · %(width)s×%(height)s · 03%(fullurl)s",
             '!': "%(color).2d│ 12↗ %(url)s · %(width)s×%(height)s · 03%(fullurl)s"}

maxlines = {'@': 1,
            '.': 4,
            '!': 6}
deflines = {'@': 1,
            '.': 1,
            '!': 4}


@command("image img", r"(-[fgpclsn\d]\s+)?(.+)", templates=exceptions)
def image(server, msg, nresults, query):
    """
    Image search.

    Search for the given terms on Google. If a number is given, it will display
    that result.

    Code adapted from kochira :v
    """

    if nresults:
        nresults = min(-int(nresults), maxlines[msg.prefix])
    else:
        nresults = deflines[msg.prefix]

    r = requests.get(
        "https://ajax.googleapis.com/ajax/services/search/images",
        params={
            "safe": "off",
            "v": "1.0",
            "rsz": nresults,
            "q": query
        }
    ).json()

    results = r.get("responseData", {}).get("results", [])

    results = results[:nresults]

    for i, result in enumerate(results):
        yield templates[msg.prefix] % {"color" : [12, 5, 8, 3][i % 4],
                                       "url": url.shorten(result["url"]),
                                       "fullurl": result["visibleUrl"],
                                       "width": result["width"],
                                       "height": result["height"],  
                                       "content": unescape(re.sub("</?b>", "", 
                                                    result["content"])),
                                       "title": unescape(re.sub("</?b>", "", 
                                                    result["title"]))}
    if not results:
        yield "12Google Images│ No results."

__callbacks__ = {"privmsg": [image]}
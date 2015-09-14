from util.services.youtube import youtube as yt
from util import parallelise

from util.irc import Callback, command

templates = {"@": "04│ %(title)s 12↗ http://youtu.be/%(url)s\n04│ by %(channel)s · %(views)s views · %(likebar)s",
             ".": "04│ %(title)s · by %(channel)s 12↗ http://youtu.be/%(url)s",
             "!": "04│ %(title)s 12↗ http://youtu.be/%(url)s\n04│ by %(channel)s · %(views)s views · %(likebar)s"}

lines = {"@": 1,
         ".": 1,
         "!": 3}

@Callback.background
def refresh_tokens(server, line):
    with yt.keylock:
        if yt.tokensExpired():
            yt.refresh_tokens()


def likebar(likes, dislikes, minwidth=16):
    likestr = "👍 {:,}".format(likes)
    dislikestr = "👎 {:,}".format(dislikes)
    spaces = max(minwidth - len(likestr) - len(dislikestr), 0) + 1
    bar = list(likestr + (" " * spaces) + dislikestr)
    width = len(bar)
    if likes and dislikes:
        ratio = int(likes * width / (likes + dislikes))
        bar.insert(ratio, "\x0315")
    return "\x0312\x1f" + "".join(bar) + "\x1f"

@Callback.threadsafe
@command(["youtube", "yt"], r"(-\d\s+)?(.+)", public=".@", private="!",
            usage="04│ ▶ │ Usage: [.@]youtube [-NUM_RESULTS] <query>",
            error="04│ ▶ │ Failed to get search results.")
def youtube(server, message, nresults, query):
    if nresults:
        nresults = min(-int(nresults.strip()), lines[message.prefix])
    else:
        nresults = lines[message.prefix]

    results = yt.search(query, results=nresults)

    for i in results:
        data = {"title": i["snippet"]["title"],
                "url": i["id"]["videoId"]}

        if message.prefix != ".":
            channelinfo, stats = parallelise([lambda: yt.get_channel_info(i["snippet"]["channelId"]),
                                              lambda: yt.stats(i["id"]["videoId"])])
            data["likebar"] = likebar(int(stats["likeCount"]), int(stats["dislikeCount"]))
            data["views"] = "{:,}".format(int(stats["viewCount"]))
            data["channel"] = channelinfo["title"]
        else:
            channelinfo = yt.get_channel_info(i["snippet"]["channelId"])
            data["channel"] = channelinfo["title"]
        yield templates[message.prefix] % data

__callbacks__ = {"privmsg": [youtube],
                 "ALL": [refresh_tokens]}

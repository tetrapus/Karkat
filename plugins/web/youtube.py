from util.services.youtube import youtube as yt

from util.irc import Callback, command

templates = {"@": "04│ ▶ │ %(title)s\n04│ ▶ │ 15by %(channel)s 12↗ http://youtu.be/%(url)s",
             ".": "04│ %(title)s 12↗ http://youtu.be/%(url)s",
             "!": "04│ ▶ │ %(title)s\n04│ ▶ │ 15by %(channel)s 12↗ http://youtu.be/%(url)s"}

lines = {"@": 1,
         ".": 1,
         "!": 3}

@Callback.background
def refresh_tokens(server, line):
    if yt.tokensExpired():
        yt.refresh_tokens()

@Callback.threadsafe
@command(["youtube", "yt"], "(-\d\s+)?(.+)", public=".@", private="!",
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
                "channel": i["snippet"]["channelTitle"],
                "url": i["id"]["videoId"]}
        yield templates[message.prefix] % data

__callbacks__ = {"privmsg": [youtube],
                 "ALL": [refresh_tokens]}

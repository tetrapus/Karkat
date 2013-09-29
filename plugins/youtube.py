from youtube import youtube as yt

from irc import Callback

templates = {"@": "You04Tube⎟ %(title)s\nYou04Tube⎟ 15by %(channel)s 12↗ http://youtu.be/%(url)s",
             ".": "You04Tube⎟ %(title)s 12↗ http://youtu.be/%(url)s",
             "!": "You04Tube⎟ %(title)s 12↗ http://youtu.be/%(url)s"}

lines = {"@": 1,
         ".": 3,
         "!": 6}

def __initialise__(name, bot, stream):
    cb = Callback()
    cb.initialise(name, bot, stream)

    @cb.command(["youtube", "yt"], "(-\d\s+)?(.+)", public=".@", private="!",
                usage="You04Tube⎟ Usage: [.@]youtube [-NUM_RESULTS] <query>",
                error="You04Tube⎟ Failed to get search results.")
    def youtube(message, nresults, query):
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

        

    bot.register("privmsg", youtube)

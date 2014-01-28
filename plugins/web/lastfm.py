import collections
import json
import math
import os
import re
import sys
import time
from urllib.parse import quote_plus, urlencode
from functools import partial

import requests
import yaml

import util

from util.services import url
from bot.events import Callback, command
from util.text import pretty_date, graphs

try:
    import pylast
    apikeys = yaml.safe_load(open("config/apikeys.conf"))["last.fm"]

except ImportError:
    print("[%s] Error: pylast is a dependency, install with\n"
          "$ pip install pylast" % __name__, 
          file=sys.stderr)
    raise
except:
    print("Error: invalid or nonexistant last.fm api key.", file=sys.stderr)
    raise ImportError("Could not load module.")

class YTFallback(object):
    API_URL = "https://gdata.youtube.com/feeds/api/videos?q=%s&alt=json"

    @staticmethod
    def get_music_video(query):
        data = requests.get(YTFallback.API_URL % quote_plus(query)).json()
        title = data["feed"]["entry"][0]["title"]["$t"]
        link = data["feed"]["entry"][0]["link"][0]["href"]
        link = re.findall("v=(.+)&", link)[0]

        if YTFallback.is_match(query, title):
            return (title, link)

    @staticmethod
    def is_match(query, result):
        # Quick heuristic: test if there are common words between the titles
        query, title = query.split(), result.split()
        qfilter = {"".join(filter(str.isalpha, i)).lower() for i in query}
        qtfilter = {"".join(filter(str.isalpha, i)).lower() for i in query}
        tfilter = {"".join(filter(str.isalpha, i)).lower() for i in title}
        common = len({i for i in qfilter & tfilter if len(i) > 2})
        return common >= 2 and qtfilter & tfilter

try:
    from util.services import youtube
except ImportError:
    yt = YTFallback
    print("Warning: Youtube module not loaded, using slow heuristic version.")
else:
    yt = youtube.youtube

def cut(songs, seconds=25 * 60):
    if not songs: return []
    split = [[songs.pop(0)]]

    songs = collections.deque(songs)
    while songs:
        song = songs.popleft()
        if int(split[-1][-1].timestamp) - int(song.timestamp) > seconds:
            split.append([song])
        else:
            split[-1].append(song)

    return split

class LastFM(Callback):

    FILENAME = "lastfm_users.json"
    COMPARE_FILE = "lastfm_compare.json"
    API_URL = "http://ws.audioscrobbler.com/2.0/?"

    GRAPHS = {".": graphs.GRAPH_DOTS,
              ":": graphs.GRAPH_FILLED_DOTS,
              "#": graphs.GRAPH_BLOCK,
              "+": graphs.GRAPH_DOS,
              "|": graphs.GRAPH_FILLED_UNICODE,
              "!": graphs.GRAPH_UNICODE}

    def __init__(self, server):
        self.userfile = server.get_config_dir(self.FILENAME)
        try:
            self.users = json.load(open(self.userfile))
        except:
            # File doesn't exist or is corrupt
            os.makedirs(server.get_config_dir(), exist_ok=True)
            self.users = {}
            self.savefile()

        if not os.path.exists(server.get_config_dir(self.COMPARE_FILE)):
            with open(server.get_config_dir(self.COMPARE_FILE), "w") as conf:
                conf.write("{}")

        self.network = pylast.LastFMNetwork(
            api_key    = apikeys["key"],
            api_secret = apikeys["secret"]
        )

        super().__init__(server)

    @staticmethod
    def get_youtube(query):
        return url.format("http://youtu.be/" + yt.get_music_video(query)[1])

    @staticmethod
    def get_listens(username, mbid):
        # Populates a trackdata with listens and loveds.
        trackdata = {}
        colors = [1, 14, 15]
        try:
            args = urlencode({"method": "track.getInfo",
                              "api_key": apikeys["key"],
                              "mbid": mbid,
                              "username": username,
                              "format": "json"})
            extradata = requests.get(LastFM.API_URL + args).json()["track"]
            
            trackdata["loved"] = "04♥ · " * int(extradata["userloved"])
            listens, listeners, scrobbled = [int(extradata[x]) for x in ("userplaycount", "listeners", "playcount")]
            # Calculate average playcount per listener
            averagepc = scrobbled/listeners

            trackdata["listens"] = "%.2d↺ %d listens " % (colors[::-1][(listens > averagepc) + (listens > 2*averagepc)], listens)
        except:
            pass

        return trackdata

    @staticmethod
    def get_yt_data(trackname):
        trackdata = {}
        try:
            youtube = LastFM.get_youtube(trackname)
            if youtube:
                trackdata["link"] = "12↗ %s" % youtube
                trackdata["barelink"] = youtube
                trackdata["dotlink"] = "· %s" % youtube
        except:
            pass
        return trackdata

    @staticmethod
    def get_album(track):
        trackdata = {}
        album = track.get_album()
        if album:
            trackdata["album"] = " · %s" % album.get_name()
        return trackdata

    @command("setlfm savelfm save", "([^ ]*)")
    def setlfm(self, server, message, username):
        nick = server.lower(message.address.nick)
        if not username:
            username = message.address.nick
        self.users[nick] = username
        self.savefile()
        return "04Last.FM│ Associated %s with Last.FM user %s." % (message.address.nick, username)

    @Callback.threadsafe
    @command("listens", r"([-.:#+|!]\d+(?:\s+|\b))?((?:\d+[dhms])*)\s*(.*)",
             templates={Callback.USAGE: "04Last.FM│ Usage: [.@]listens [(\d+[dhms])+] [user]",    
                        Callback.ERROR: "04Last.FM│ Couldn't retrieve Last.FM playing history."})
    def listen_history(self, server, message, size, period, username):
        timevals = {"d": 24 * 60 * 60, 
                    "h": 60 * 60, 
                    "m": 60, 
                    "s": 1}
        nick = message.address.nick
        server.printer.message("\x0304│\x03 Fetching Last.FM listen history, please wait...", message.address.nick, "NOTICE")
        if not username:
            username = nick
        user = username

        lowername = server.lower(username)
        if lowername in self.users:
            user = self.users[lowername]

        user = self.network.get_user(user)
        tracks = user.get_recent_tracks(limit=200)
        now = time.time()

        if period:
            timespan = 0
            for i in re.findall(r"\d+[dhms]", period):
                timespan += int(i[:-1]) * timevals[i[-1]]
        else:
            timespan = now - int(tracks[-1].timestamp)

        values = 36 if message.prefix != "." else 24

        data = [0 for i in range(values)]
        usedtracks = []
        for track in tracks:
            timeago = now - int(track.timestamp)
            if timeago <= timespan:
                data[int(timeago * values / (timespan+1))] += 1
                usedtracks.append(track)


        if message.prefix != ".":
            height = 5
            graph = graphs.graph_dos
        else:
            height = 1
            graph = partial(graphs.graph, symbols=LastFM.GRAPHS["#"])

        # Formatting
        if size:
            if size[0] in LastFM.GRAPHS:
                graph = partial(graphs.graph, symbols=LastFM.GRAPHS[size[0]])
            height = max(min(int(size[1:].strip()), 5), 1)

        largest = max(data)
        data = graphs.normalise(data)

        if message.prefix == ".":
            data = ["04│" + i for i in graph(data, height).split("\n")]
        else:
            data = graph(data, height).split("\n")
            data = ["%2d %s" % (round(largest/9*(8-2*i)), s) if not i % 2 else "   " + s for i, s in enumerate(data)]
        if len(usedtracks) > 1:
            average = len(usedtracks) / (int(usedtracks[0].timestamp) - int(usedtracks[-1].timestamp))
        else:
            average = 0

        groups = cut(usedtracks)
        runs = sum(int(i[0].timestamp) - int(i[-1].timestamp) for i in groups) / len(groups)

        meta = ["%s (%s)" % (username, self.users[lowername]) if lowername in self.users else username,
                " %d songs/%.1f hours" % (len(usedtracks), timespan / (60*60)),
                " %dm/bar" % (timespan / (60 * values)),
                " %.2f songs per day" % (average * 24 * 60 * 60),
                " %dm average play time" % (runs / 60)]
        data = ["%s04│ %s" % i for i in zip(data, meta)]

        for i in data:
            yield i

    @Callback.threadsafe
    @command("np", "(-\d+)?\s*([^ ]*)", 
             templates={Callback.USAGE: "04Last.FM│ Usage: [.!@]np [-d] [user]",
                        Callback.ERROR: "04Last.FM│ Couldn't retrieve Last.FM playing history."},
             prefixes=("!", ".@"))
    def now_playing(self, server, message, lastnum, username):
        difftime = collections.OrderedDict()
        difftime["start"] = time.time()
        colors = [1, 14, 15]
        if not username:
            username = message.address.nick

        if lastnum:
            lastnum = -int(lastnum)

        lowername = server.lower(username)
        if lowername in self.users:
            username = self.users[lowername]

        user = self.network.get_user(username)

        trackdata = {i:"" for i in ("duration", "timeago", "title", "artist", "link", "listens", "loved", "barelink", "tad", "album", "dotlink")}
        difftime["user"] = time.time()
        track, recent = util.parallelise([user.get_now_playing, lambda: user.get_recent_tracks(limit=lastnum or 1)])
        difftime["np"] = time.time()
        if not track or lastnum:
            recent = recent[-1]
            since = time.time() - int(recent.timestamp)
            # Calculate colour
            scolour = colors[min(2, int(math.log(since/60 +1, 60)))]
            trackdata["timeago"] = "%.2d⌚ %s " % (scolour, pretty_date(since))
            trackdata["tad"] = "· %s" % trackdata["timeago"]
            track = recent.track
            difftime["recent"] = time.time()
        
        trackdata["duration"] = "⌛ %dm%.2ds" % divmod(track.get_duration()/1000, 60)
        trackdata["artist"], trackdata["title"] = (track.get_artist(), track.get_title())
        trackname = "%(artist)s - %(title)s" % trackdata

        jobs = [lambda: self.get_yt_data(trackname), lambda: self.get_listens(username, track.get_mbid()), lambda: self.get_album(track)]

        if message.prefix in "!@":
            # Provide full template
            template = "04Last.FM│ %(loved)s%(artist)s%(album)s · %(title)s\n"\
                       "04Last.FM│ %(listens)s%(timeago)s%(duration)s %(link)s"
        else:
            template = "04│ %(loved)s%(artist)s · %(title)s (%(duration)s) %(tad)s%(dotlink)s"
        difftime["template"] = time.time()
        for i in util.parallelise(jobs):
            trackdata.update(i)
        final = time.time()
        for i in difftime:
            print("[Last.FM] %s: %f" % (i, final - difftime[i]))
        return template % trackdata

    @Callback.threadsafe
    @command("compare", "([^ ]+)(?:\s+([^ ]+))?",
     templates={Callback.USAGE: "04Last.FM│ Usage: [.@]compare user1 [user2]",
                Callback.ERROR: "04Last.FM│ Couldn't retrieve Last.FM user data.",
                ValueError: "04Last.FM│ Last.FM compatibility service is down."})
    def compare(self, server, message, user1, user2):
        if not user2:
            users = (message.address.nick, user1)
        else:
            users = (user1, user2)
        users_display = ["%s (%s)" % (i, self.users[server.lower(i)]) if server.lower(i) in self.users else i for i in users]
        users = [self.users[server.lower(i)] if server.lower(i) in self.users else i for i in users]
        first = self.network.get_user(users[0])
        tasteometer, artists = first.compare_with_user(users[1])
        _artists = [i.name for i in artists]
        tasteometer = float(tasteometer)
        if tasteometer < 0:
            raise ValueError("tasteometer returned invalid value")
        overflow = ""
        artistlimit = 40 if message.prefix == "." else 400
        if not artists:
            common = "Absolutely nothing"
        elif len(artists) == 1:
            common = artists.pop(0).name
        else:
            common = artists.pop(0).name
            while len(common) < artistlimit and len(artists) > 1:
                common += ", " + artists.pop(0).name
            if len(artists) == 1:
                common += " and %s" % artists.pop(0).name
            else:
                overflow = (" and %d+ more" % len(artists)) * bool(len(artists))

        # Cache results.
        with open(server.get_config_dir(self.COMPARE_FILE)) as compfile:
            data = json.load(compfile)
            data.update({"%s %s" % tuple(sorted(users)): [tasteometer, _artists]})
        with open(server.get_config_dir(self.COMPARE_FILE), "w") as compfile:
            json.dump(data, compfile)

        if message.prefix == ".":
            yield "04│ %.2d%.1f%% 04│ %s%s" % ([4, 7, 8, 9, 3][int(tasteometer * 4.95)], tasteometer * 100, common, "..." if overflow else "")
        else:
            yield "04Last.FM│ %s ⟺ %s: %.2d%.1f%% compatible" % (users_display[0], users_display[1], [4, 7, 8, 9, 3][int(tasteometer * 4.95)], tasteometer * 100)
            yield "04Last.FM│ %s%s in common." % (common, overflow)

    @command("besties", "(.*)")
    def besties(self, server, message, user):
        raise NotImplementedError

    @command("lastfm", "(.*)")
    def lastfm(self, server, message, user):
        if not user:
            user = message.address.nick

        lowername = server.lower(user)
        if lowername in self.users:
            return "04│04 http://last.fm/user/" + self.users[lowername]
        return "04│04 %s has not associated their last.fm." % user


    def savefile(self):
        json.dump(self.users, open(self.userfile, "w"))

__initialise__ = LastFM
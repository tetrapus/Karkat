import collections
import json
import math
import os
import re
import sys
import time
import random
import operator
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

        self.compare_file = server.get_config_dir(self.COMPARE_FILE)

        if not os.path.exists(self.compare_file):
            with open(self.compare_file, "w") as conf:
                conf.write("{}")

        self.network = pylast.LastFMNetwork(
            api_key    = apikeys["key"],
            api_secret = apikeys["secret"]
        )

        self.lastcompare = 0
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

    @command("setlfm savelfm save", r"(\S*)")
    def setlfm(self, server, message, username):
        nick = server.lower(message.address.nick)
        if not username:
            username = message.address.nick
        self.users[nick] = username
        self.savefile()
        return "04│ ♫ │ Associated %s with Last.FM user %s." % (message.address.nick, username)

    @Callback.threadsafe
    @command("listens", r"([-.:#+|!]\d+(?:\s+|\b))?((?:\d+[dhms])*)\s*(.*)",
             templates={Callback.USAGE: "04│ ♫ │ Usage: [.@]listens [(\d+[dhms])+] [user]",    
                        Callback.ERROR: "04│ ♫ │ Couldn't retrieve Last.FM playing history."})
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
    @command("np", r"(-\d+)?\s*(\S*)", 
             templates={Callback.USAGE: "04│ ♫ │ Usage: [.!@]np [-d] [user]",
                        Callback.ERROR: "04│ ♫ │ Couldn't retrieve Last.FM playing history."},
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
            template = "04│ ♫ │ %(loved)s%(artist)s%(album)s · %(title)s\n"\
                       "04│ ♫ │ %(listens)s%(timeago)s%(duration)s %(link)s"
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
    @command("compare", r"(\S+)(?:\s+(\S+))?",
     templates={Callback.USAGE: "04│ ♫ │ Usage: [.@]compare user1 [user2]",
                Callback.ERROR: "04│ ♫ │ Couldn't retrieve Last.FM user data.",
                ValueError: "04│ ♫ │ Last.FM compatibility service is down."})
    def compare(self, server, message, user1, user2):
        if not user2:
            users = (message.address.nick, user1)
        else:
            users = (user1, user2)
        users_display = ["%s (%s)" % (i, self.users[server.lower(i)]) if server.lower(i) in self.users else i for i in users]
        users = [self.users[server.lower(i)] if server.lower(i) in self.users else i for i in users]
        tasteometer, artists = self.cached_compare(*users)
        if tasteometer < 0:
            raise ValueError("tasteometer returned invalid value")
        overflow = ""
        artistlimit = 40 if message.prefix == "." else 400
        if not artists:
            common = "Absolutely nothing"
        elif len(artists) == 1:
            common = artists.pop(0)
        else:
            common = artists.pop(0)
            while len(common) < artistlimit and len(artists) > 1:
                common += ", " + artists.pop(0)
            if len(artists) == 1:
                common += " and %s" % artists.pop(0)
            else:
                overflow = (" and %d+ more" % len(artists)) * bool(len(artists))

        if message.prefix == ".":
            yield "04│ %.2d%.1f%% 04│ %s%s" % ([15, 14, 11, 10, 3][int(tasteometer * 4.95)], tasteometer * 100, common, "..." if overflow else "")
        else:
            yield "04│ ♫ │ %s and %s are %.2d%.1f%% compatible" % (users_display[0], users_display[1], [15, 14, 11, 10, 3][int(tasteometer * 4.95)], tasteometer * 100)
            yield "04│ ♫ │ %s%s in common." % (common, overflow)


    def cached_compare(self, user1, user2):
        first = self.network.get_user(user1)
        tasteometer, artists = first.compare_with_user(user2)
        users = [user1, user2]
        artists = [i.name for i in artists]
        tasteometer = float(tasteometer)
        with open(self.compare_file) as compfile:
            data = json.load(compfile)
            data.update({("%s %s" % tuple(sorted(users))).lower(): [tasteometer, artists]})
        with open(self.compare_file, "w") as compfile:
            json.dump(data, compfile)

        self.lastcompare = time.time()
        return tasteometer, artists

    def clear_cache(self):
        with open(self.compare_file, "w") as compfile:
            json.dump({}, compfile)

    def compare_rand(self, server, line) -> "ALL":
        if time.time() - self.lastcompare > max(300, len(self.users)**2):
            user1 = random.choice(list(self.users.values()))
            user2 = random.choice(list(self.users.values()))
            self.cached_compare(user1, user2)

    def username_to_nick(self, username):
        possible = [i for i in self.users if self.users[i].lower() == username.lower()]
        if possible:
            return sorted(possible, key=lambda x: -len(x))[0]

    @command("besties", "(.*)")
    def besties(self, server, message, username):
        if not username:
            username = message.address.nick
        lowername = server.lower(username)
        if lowername in self.users:
            username = self.users[lowername]
        luser = username.lower()

        with open(self.compare_file) as compfile:
            data = json.load(compfile)
        matches = {}
        for users, similarity in data.items():
            if type(similarity) == float: print(users, similarity)
            users = users.split(" ", 1)
            if luser in users and luser != username.lower():
                users.remove(luser)
                matches[users[0]] = similarity
        users = sorted(matches.items(), key=lambda x: -x[1][0])
        if message.prefix == ".":
            similar_to = ""
            rlen = len(username)
            while users:
                user, similarity = users.pop(0)
                nick = self.username_to_nick(user)
                if nick is not None and nick != user:
                    user = "%s (%s)" % (nick, user)
                tasteometer = similarity[0]
                similar_to += "4│ " + user + " · %.2d%.1f " % ([15, 14, 11, 10, 3][int(tasteometer * 4.95)], tasteometer * 100)
                rlen += len(user) + 9 - (tasteometer < 0.1)
                if rlen > 42: break
            return "04│ %s %s04│15 %d ᴜɴᴋɴᴏᴡɴ" % (self.username_to_nick(username) or username, similar_to, len(self.users) - len(matches))
        # TODO: longform command

    @command("lastfm", "(\S*)", templates={Callback.USAGE: "04│ ♫ │ Usage: [.@]lastfm nick"})
    def lastfm(self, server, message, user):
        if not user:
            user = message.address.nick

        lowername = server.lower(user)
        if lowername in self.users:
            return "04│ ♫ │ 12http://last.fm/user/" + self.users[lowername]
        return "04│ ♫ │ %s has not associated their Last.FM" % user

    @command("collage", "(-[cap]+\s+)?((?:(?:3x3|4x4|5x5|2x8|7d|1m|3m|6m|12m|overall)\s*)+)?(\S+)?")
    def collage(self, server, message, flags, data, user):
        tapmusic = "http://tapmusic.net/lastfm/collage.php?"
        if not user:
            user = message.address.nick
        lowername = server.lower(user)
        if lowername in self.users:
            user = self.users[lowername]

        defaults = {"user": user, "type": "overall", "size": "3x3"}
        for i in (flags or []):
            if i in "cap":
                defaults[{"c":"caption","a":"artistonly","p":"playcount"}[i]] = "true"
        
        if data:
            for i in data.split():
                if "x" in i:
                    defaults["size"] = i
                else:
                    defaults["type"] = {"7d": "7day", "1m": "1month", "3m": "3month", "6m": "6month", "12m": "12month", "overall":"overall"}[i]

        return "04│ "+url.format(url.shorten(tapmusic + urlencode(defaults)))


    def savefile(self):
        json.dump(self.users, open(self.userfile, "w"))

__initialise__ = LastFM
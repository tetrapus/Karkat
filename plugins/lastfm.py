import collections
import json
import math
import os
import re
import sys
import time
import urllib.parse as urllib

import requests
import yaml

import util

from util.services import url
from util.irc import Callback, command
from util.text import pretty_date, graph

try:
    import pylast
    apikeys = yaml.safe_load(open("config/apikeys.conf"))["last.fm"]

except ImportError:
    print("[%s] Warning: pylast is a dependency, install with\n$ pip install pylast" % __name__, file=sys.stderr)
except:
    print("Warning: invalid or nonexistant api key.", file=sys.stderr)
    print("%s not loaded." % __name__, file=sys.stderr)
else:
    try:
        from util.services import youtube
    except ImportError:
        yt = None
        print("Warning: Youtube module not loaded, using slow heuristic version.")
    else:
        yt = youtube.youtube

    class LastFM(object):

        FILENAME = "lastfm_users.json"

        def __init__(self, server):
            self.userfile = server.get_config_dir(self.FILENAME)
            try:
                self.users = json.load(open(self.userfile))
            except:
                # File doesn't exist or is corrupt
                os.makedirs(server.get_config_dir(), exist_ok=True)
                self.users = {}
                self.savefile()

            self.network = pylast.LastFMNetwork(
                api_key    = apikeys["key"],
                api_secret = apikeys["secret"]
            )

            server.register("privmsg", self.now_playing)
            server.register("privmsg", self.compare)
            server.register("privmsg", self.setlfm)
            server.register("privmsg", self.listenHistory)

        @staticmethod
        def get_youtube(query):
            if yt is None:
                data  = requests.get("https://gdata.youtube.com/feeds/api/videos?q=%s&alt=json" % urllib.quote_plus(query)).text
                data  = json.loads(data)
                title = data["feed"]["entry"][0]["title"]["$t"]
                data  = data["feed"]["entry"][0]["link"][0]["href"]
                data  = re.findall("v=(.+)&", data)[0]
                # Quick heuristic: test if there are common words between the titles
                qfilter = {"".join(filter(str.isalpha, i)).lower() for i in query.split()}
                qtfilter = {"".join(filter(str.isalpha, i)).lower() for i in query.split()}
                tfilter = {"".join(filter(str.isalpha, i)).lower() for i in title.split()}
                if len({i for i in qfilter & tfilter if len(i) > 2}) >= 2 and qtfilter & tfilter:
                    return url.format("http://youtu.be/" + data)
            else:
                return url.format("http://youtu.be/" + yt.get_music_video(query)[1]) # Don't check title for now.

        @staticmethod
        def get_listens(username, mbid):
            # Populates a trackdata with listens and loveds.
            trackdata = {}
            colors = [1, 14, 15]
            try:
                args = urllib.urlencode({"method": "track.getInfo",
                                         "api_key": apikeys["key"],
                                         "mbid": mbid,
                                         "username": username,
                                         "format": "json"})
                extradata = requests.get("http://ws.audioscrobbler.com/2.0/?" + args).json()["track"]
                
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

        @command("setlfm savelfm".split(), "([^ ]*)")
        def setlfm(self, server, message, username):
            nick = server.lower(message.address.nick)
            if not username:
                username = message.address.nick
            self.users[nick] = username
            self.savefile()
            return "04Last.FM│ Associated %s with Last.FM user %s." % (message.address.nick, username)

        @Callback.threadsafe
        @command("listens", r"((?:\d+[dhms])*)\s*(.*)",
                 usage="04Last.FM│ Usage: [.@]listens [(\d+[dhms])+] [user]",
                 error="04Last.FM│ Couldn't retrieve Last.FM playing history.",)
        def listenHistory(self, server, message, period, username):
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

            values = 36

            data = [0 for i in range(values)]
            usedtracks = []
            for track in tracks:
                timeago = now - int(track.timestamp)
                if timeago <= timespan:
                    data[int(timeago * values / (timespan+1))] += 1
                    usedtracks.append(track)

            largest = max(data)
            if largest:
                data = [round(i * 9 / largest) for i in data]
            data = graph(data, minheight=4)
            data = ["%2d %s" % (round(largest/9*(8-2*i)), s) if not i % 2 else "   " + s for i, s in enumerate(data)]
            if len(usedtracks) > 1:
                average = len(usedtracks) / (int(usedtracks[0].timestamp) - int(usedtracks[-1].timestamp))
            else:
                average = 0
            meta = ["%s (%s)" % (username, self.users[lowername]) if lowername in self.users else username,
                    " %d songs" % len(usedtracks),
                    " %.1f hours total" % (timespan / (60*60)),
                    " %d minute periods" % (timespan / (60 * values)),
                    " %.2f songs per day" % (average * 24 * 60 * 60)]
            data = ["%s04│ %s" % (j, i) for i, j in zip(meta, data)]

            for i in data:
                yield i

        @Callback.threadsafe
        @command("np", "(-\d+)?\s*([^ ]*)", 
                 usage="04Last.FM│ Usage: [.!@]np [-d] [user]",
                 error="04Last.FM│ Couldn't retrieve Last.FM playing history.",
                 private="!",
                 public=".@")
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
                    usage="04Last.FM│ Usage: [.@]compare user1 [user2]",
                    error="04Last.FM│ Couldn't retrieve Last.FM user data.")
        def compare(self, server, message, user1, user2):
            if not user2:
                users = (message.address.nick, user1)
            else:
                users = (user1, user2)
            users_display = ["%s (%s)" % (i, self.users[server.lower(i)]) if server.lower(i) in self.users else i for i in users]
            users = [self.users[server.lower(i)] if server.lower(i) in self.users else i for i in users]
            first = self.network.get_user(users[0])
            tasteometer, artists = first.compare_with_user(users[1])
            tasteometer = float(tasteometer)
            overflow = ""
            if not artists:
                common = "Absolutely nothing"
            elif len(artists) == 1:
                common = artists.pop(0).name
            else:
                common = artists.pop(0).name
                while len(common) < 40 and len(artists) > 1:
                    common += ", " + artists.pop(0).name
                if len(artists) == 1:
                    common += " and %s" % artists.pop(0).name
                else:
                    overflow = (" and %d+ more" % len(artists)) * bool(len(artists))

            yield "04Last.FM│ %s ⟺ %s: %.2d%.1f%% compatible" % (users_display[0], users_display[1], [4, 7, 8, 9, 3][int(tasteometer * 4.95)], tasteometer * 100)
            yield "04Last.FM│ %s%s in common." % (common, overflow)


        def savefile(self):
            json.dump(self.users, open(self.userfile, "w"))

    __initialise__ = LastFM

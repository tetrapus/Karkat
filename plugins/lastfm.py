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
from util.irc import Callback
from util.text import pretty_date

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
    cb = Callback()

    class LastFM(object):

        FILENAME = "lastfm_users.json"

        def __init__(self, name, bot, printer):
            self.userfile = bot.get_config_dir(self.FILENAME)
            try:
                self.users = json.load(open(self.userfile))
            except:
                # File doesn't exist or is corrupt
                os.makedirs(bot.get_config_dir(), exist_ok=True)
                self.users = {}
                self.savefile()

            self.network = pylast.LastFMNetwork(
                api_key    = apikeys["key"],
                api_secret = apikeys["secret"]
            )
            cb.initialise(name, bot, printer)

            bot.register("privmsg", self.now_playing)
            bot.register("privmsg", self.compare)

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

        @cb.command("np", "(-s\s*)?([^ ]*)", 
                    usage="04Last.FM⎟ Usage: [.@]np [-s] [user]",
                    error="04Last.FM⎟ Couldn't retrieve Last.FM playing history.",
                    private="!",
                    public=".@")
        def now_playing(self, message, save, username):
            difftime = collections.OrderedDict()
            difftime["start"] = time.time()
            colors = [1, 14, 15]
            nick = cb.bot.lower(message.address.nick)
            if save:
                self.users[nick] = username
                self.savefile()

            if not username:
                username = message.address.nick

            lowername = cb.bot.lower(username)
            if lowername in self.users:
                username = self.users[lowername]

            user = self.network.get_user(username)

            trackdata = {i:"" for i in ("duration", "timeago", "title", "artist", "link", "listens", "loved", "barelink", "tad")}
            difftime["user"] = time.time()
            track, recent = util.parallelise([user.get_now_playing, lambda: user.get_recent_tracks(limit=1)])
            #track = user.get_now_playing()
            difftime["np"] = time.time()
            if not track:
                recent = recent[0]
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

            jobs = [lambda: self.get_yt_data(trackname), lambda: self.get_listens(username, track.get_mbid())]

            if message.prefix in "!@":
                # Provide full template
                template = "04Last.FM⎟ %(loved)s%(artist)s · %(title)s\n"\
                           "04Last.FM⎟ %(listens)s%(timeago)s%(duration)s %(link)s"
            else:
                template = "04Last.FM⎟ %(loved)s%(artist)s · %(title)s (%(duration)s) %(tad)s%(dotlink)s"
            difftime["template"] = time.time()
            for i in util.parallelise(jobs):
                trackdata.update(i)
            final = time.time()
            for i in difftime:
                print("[Last.FM] %s: %f" % (i, final - difftime[i]))
            return template % trackdata

        @cb.command("compare", "([^ ]+)(?:\s+([^ ]+))?",
                    usage="04Last.FM⎟ Usage: [.@]compare user1 [user2]",
                    error="04Last.FM⎟ Couldn't retrieve Last.FM user data.")
        def compare(self, message, user1, user2):
            if not user2:
                users = (message.address.nick, user1)
            else:
                users = (user1, user2)
            users = [self.users[cb.bot.lower(i)] if cb.bot.lower(i) in self.users else i for i in users]
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
                    overflow = (" and %d more" % len(artists)) * bool(len(artists))

            yield "04Last.FM⎟ %s ⟺ %s: %.2d%.1f%% compatible" % (users[0], users[1], [4, 7, 8, 9, 3][int(tasteometer * 4.95)], tasteometer * 100)
            yield "04Last.FM⎟ %s%s in common." % (common, overflow)


        def savefile(self):
            json.dump(self.users, open(self.userfile, "w"))

    __initialise__ = LastFM

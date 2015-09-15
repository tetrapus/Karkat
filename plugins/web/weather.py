import sys
import json
import datetime

import requests
import yaml
import xml.etree.ElementTree as xml

import util
from bot.events import Callback, command
from util.text import pretty_date


try:
    apikey = yaml.safe_load(open("config/apikeys.conf"))["wunderground"]["key"]
except:
    print("Error: invalid or nonexistant wunderground api key.", file=sys.stderr)
    raise ImportError("Could not load module.")

weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
icons = {"flurries": "❄", "rain": "☔", "sleet": "⛆", "snow": "☃", "tstorms": "⛈", "clear": "☀", "cloudy": "☁", "fog": "🌁", "hazy": "🌁", "unknown": "?"}

def icon_to_unicode(icon):
    if icon.startswith("mostly") or icon.startswith("partly"): return "\x032⛅\x0f"
    if icon.startswith("chance"):
        color = 12
        icon = icon[6:]
    else:
        color = 2
    return "\x03%d%s\x0f" % (color, icons.get(icon, "?"))

class Weather(Callback):
    countryformats = ["%(city)s, %(region_name)s", "%(city)s, %(country_name)s"]
    SETTINGS_FILE = "wolfram_users.json"

    def __init__(self, server):
        self.settingsf = server.get_config_dir(self.SETTINGS_FILE)
        self.server = server
        super().__init__(server)

    def getusersettings(self, user):
        userinfo = json.load(open(self.settingsf))
        settings = {}
        user = self.server.lower(user)
        if user in userinfo:
            data = userinfo[user]
            if "location" in data:
                settings["location"] = data["location"]
            if "ip" in settings:
                settings["ip"] = data["ip"]
            elif "iptracker" in dir(self.server) and user in self.server.iptracker.known:
                settings["ip"] = self.server.iptracker.known[user]
        return settings

    @staticmethod
    def get_location(location):
        return requests.get("http://autocomplete.wunderground.com/aq", params={"query":location}).json()["RESULTS"][0]

    def get_locid(self, location):
        try:
            return "zmw:%s.json" % (self.get_location(location)["zmw"])
        except:
            raise LookupError("Location unrecognised")

    def get_user_locid(self, user):
        userinfo = self.getusersettings(user)
        if "location" in userinfo:
            return self.get_locid(userinfo["location"])
        elif "ip" in userinfo:
            return "autoip.json?geo_ip=" + userinfo["ip"]
        else:
            raise KeyError("User info not found.")

    def guess_locid(self, user, location):
        if location:
            return self.get_locid(location)
        else:
            return self.get_user_locid(user)

    @command("time", r"(.*)")
    def get_time(self, server, message, user):
        if not user:
            user = message.address.nick
            # No arguments, get sender's time
        try:
            try:
                location = self.get_user_locid(user)
                # Try treating the argument as a user
            except KeyError:
                try:
                    location = self.get_locid(user)
                    # Try treating argument as a location
                except KeyError:
                    return "04│ ☀ │ I don't know where you live! Set your location with .set location \x02city\x02 or specify it manually."
        except LookupError:
            return "04│ ☀ │ No timezone information for your location."

            
        wurl = "http://api.wunderground.com/api/%s/conditions/q/%s" % (apikey, location)
        lurl = "http://api.wunderground.com/api/%s/astronomy/q/%s" % (apikey, location)
        weather, astro = util.parallelise([lambda: requests.get(wurl).json(), lambda: requests.get(lurl).json()])
        try:
            weather = weather["current_observation"]
            astro = astro["moon_phase"]
        except:
            return "04│ ☀ │ No timezone data."
        sunrise, now, sunset = (int(astro["sunrise"]["hour"]), int(astro["sunrise"]["minute"])), (int(astro["current_time"]["hour"]), int(astro["current_time"]["minute"])), (int(astro["sunset"]["hour"]), int(astro["sunset"]["minute"]))
        if sunrise < now < sunset:
            sigil = "\x0307☀\x03"
        else:
            sigil = "\x032🌙\x03"
        localtime = int(weather["local_epoch"])
        timezone = weather["local_tz_offset"]
        polarity, hours, mins = timezone[0], int(timezone[1:3]), int(timezone[3:5])
        offset = hours * 60 * 60 + mins * 60
        localtime = localtime + offset if polarity == "+" else localtime - offset
        localtime = datetime.datetime.utcfromtimestamp(localtime)
        date = "%(weekday)s, %(month)s %(day)s, %(year)s" % {"weekday": weekdays[localtime.weekday()], "month": months[localtime.month-1], "day": localtime.day, "year": localtime.year}
        return "2│ %(sigil)s %(hour).2d:%(minute).2d:%(second).2d %(ampm)s \x0315%(timezone)s\x03 · %(date)s" % {"timezone": weather["local_tz_short"], "sigil":sigil, "hour": localtime.hour % 12, "minute": localtime.minute, "second": localtime.second, "date": date, "ampm": "am" if localtime.hour < 12 else "pm"}

    @command("weather", "(.*)")
    def get_weatherdata(self, server, message, location):
        user = message.address.nick

        try:
            loc_id = self.guess_locid(user, location)
        except KeyError:
            return "04│ ☀ │ I don't know where you live! Set your location with .set location \x02city\x02 or specify it manually."
        except LookupError:
            return "04│ ☀ │ Location not recognised."

        data = "http://api.wunderground.com/api/%s/conditions/q/%s" % (apikey, loc_id)
        data = requests.get(data).json()
        try:
            data = data["current_observation"]
        except:
            return "04│ ☀ │ Couldn't figure out the weather."
        station = data["station_id"]
        conditions = {"location"     : data["display_location"]["full"],
                      "weather"      : data["weather"],
                      "temperature"  : data["temperature_string"],
                      "feels_like"   : data["feelslike_string"],
                      "wind"         : data["wind_string"],
                      "windchill"    : data["windchill_string"],
                      "humidity"     : data["relative_humidity"],
                      "visibility"   : data["visibility_km"],
                      "precipitation": data["precip_today_metric"],
                      "UV"           : data["UV"],
                      "icon"         : icon_to_unicode(data["icon"])
                      }
        t = data["temp_c"]
        temperature_color = [2, 12, 14, 7, 4][(t > 6) + (t > 16) + (t > 26) + (t > 36)]
        temperature = "%d °C \x0315%d °F\x03" %(data["temp_c"], data["temp_f"])
        pieces = ["%s %s" % (conditions["icon"], conditions["weather"]), "\x03%d🌡 %s" % (temperature_color, temperature)]
        pieces.append("%s humidity" % data["relative_humidity"])
        pieces.append("⌚ " + pretty_date(int(data["local_epoch"]) - int(data["observation_epoch"])))
        return "2│ %s 2│ %s" % (data["display_location"]["full"], " · ".join(pieces))

    @command("metar", r"(\w\w\w\w)", templates={Callback.ERROR: "4│ METAR resolution failed.",
                                                Callback.USAGE: "4│ Please supply a valid 4 character ICAO airport code."})
    def metar(self, server, msg, station):
        station = station.upper()
        airports = json.load(open("data/airports.json"))
        station_name = airports.get(station, station)
        params = {"dataSource":"metars",
                  "requestType": "retrieve",
                  "format": "xml",
                  "hoursBeforeNow": "3",
                  "mostRecent": "true",
                  "stationString": station}
        query = requests.get("https://www.aviationweather.gov/adds/dataserver_current/httpparam", params=params)
        data = xml.fromstring(query.content)
        metar = data.find("data").find("METAR").find("raw_text").text
        return "2│ %s 2│ %s" % (station_name, metar)



__initialise__ = Weather

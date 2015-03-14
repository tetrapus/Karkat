'''
import shelve

class Weather(object):

    locationdata = shelve.open("weather/defaults", writeback=True)
    locationhistory = shelve.open("weather/history", writeback=True)
    countryformats = ["%(city)s, %(region_name)s", "%(city)s, %(country_name)s"]

    api_key = apikeys["wunderground"]["key"]

    @classmethod
    def guess_location(cls, user):
        if user in cls.locationdata:
            return cls.locationdata["user"]
        elif user in cls.locationhistory:
            return max(cls.locationhistory[user], key=list.count) + ".json"
        elif user in ipscan.known:
            return "autoip.json?geo_ip=" + ipscan.known[user]

    def get_weatherdata(self, user):
        location = self.guess_location(user)
        if location:
            data = "http://api.wunderground.com/api/%s/conditions/q/%s" % (self.api_key, location)
            data = json.loads(urllib.urlopen(data).read())
            data = data["current_observation"]
            station = data["station_id"]
            # Store history.
            self.locationhistory.setdefault("user", []).append(station)
            conditions = {"location"     : data["display_location"]["full"],
                          "time"         : pretty_date(int(data["local_epoch"]) - int(data["observation_epoch"])),
                          "weather"      : data["weather"],
                          "temperature"  : data["temperature_string"],
                          "feels_like"   : data["feelslike_string"],
                          "wind"         : data["wind_string"],
                          "windchill"    : data["windchill_string"],
                          "humidity"     : data["relative_humidity"],
                          "visibility"   : data["visibility_km"],
                          "precipitation": data["precip_today_metric"],
                          "UV"           : data["UV"]
                          }
            format = u"""12%(location)s (%(time)s)                  Wunderground
⎜%(weather)s, %(temperature)s                   Feels like %(feels_like)s⎟
⎜%(wind)s                                       Wind chill %(windchill)s⎟
⎜%(humidity)s humidity, visibility %(visibility)skm, %(precipitation)smm of precipitation. UV Index %(UV)s⎟
⎜Monday:       ⎟""" % conditions
        return format"

'''
import sys
import json
import datetime

import requests
import yaml

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

    @command("time", r"(.+)")
    def get_time(self, server, message, location):
        user = message.address.nick
        if not location:
            userinfo = self.getusersettings(user)
            if not userinfo:
                return "04│ ☀ │ I don't know where you live! Set your location with .set location \x02city\x02 or specify it manually."
    
            if "location" in userinfo:
                try:
                    loc_data = self.get_location(userinfo["location"])["zmw"]
                except:
                    return "04│ ☀ │ No timezone information for your location."
                location = "zmw:%s.json" % loc_data
            else:
                location = "autoip.json?geo_ip=" + userinfo["ip"]
        else:
            userinfo = self.getusersettings(location)
            if not userinfo:
                location = "zmw:%s.json" % self.get_location(location)["zmw"]
    
            elif "location" in userinfo:
                try:
                    loc_data = self.get_location(userinfo["location"])["zmw"]
                except:
                    try:
                        loc_data = self.get_location(location)["zmw"]
                    except:
                        return "04│ ☀ │ No timezone information for that location."
                location = "zmw:%s.json" % loc_data
            else:
                location = "autoip.json?geo_ip=" + userinfo["ip"]
            
        wurl = "http://api.wunderground.com/api/%s/conditions/q/%s" % (apikey, location)
        lurl = "http://api.wunderground.com/api/%s/astronomy/q/%s" % (apikey, location)
        weather, astro = util.parallelise([lambda: requests.get(wurl).json(), lambda: requests.get(lurl).json()])
        try:
            weather = weather["current_observation"]
            astro = astro["moon_phase"]
        except:
            return "04│ ☀ │ No timezone data."
        sunrise, now, sunset = (astro["sunrise"]["hour"], astro["sunrise"]["minute"]), (astro["current_time"]["hour"], astro["current_time"]["minute"]), (astro["sunset"]["hour"], astro["sunset"]["minute"])
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
        return "2│ %(sigil)s %(hour)s:%(minute)s:%(second)s %(ampm)s \x0315%(timezone)s\x03 · %(date)s" % {"timezone": weather["local_tz_short"], "sigil":sigil, "hour": localtime.hour % 12, "minute": localtime.hour, "second": localtime.second, "date": date, "ampm": "am" if localtime.hour < 12 else "pm"}

    @command("weather", "(.*)")
    def get_weatherdata(self, server, message, location):
        user = message.address.nick
        # TODO: refactor
        if not location:
            userinfo = self.getusersettings(user)
            if not userinfo:
                return "04│ ☀ │ I don't know where you live! Set your location with .set location \x02city\x02 or specify it manually."
    
            if "location" in userinfo:
                try:
                    loc_data = self.get_location(userinfo["location"])["zmw"]
                except:
                    return "04│ ☀ │ No weather information for your location."
                location = "zmw:%s.json" % loc_data
            else:
                location = "autoip.json?geo_ip=" + userinfo["ip"]
        else:
            try:
                loc_data = self.get_location(location)["zmw"]
            except:
                return "04│ ☀ │ No weather information for that location."
            location = "zmw:%s.json" % loc_data
        
        data = "http://api.wunderground.com/api/%s/conditions/q/%s" % (apikey, location)
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

__initialise__ = Weather
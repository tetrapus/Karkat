import sys
import yaml
import requests
import socketserver
import http.server
import threading
from urllib.parse import parse_qs

from bot.events import Callback, command
from util.files import Config
from util.services.url import shorten

try:
    apikeys = yaml.safe_load(open("config/apikeys.conf"))["google"]
except:
    print("Warning: invalid or nonexistant api key.", file=sys.stderr)
    print("Will not print location of yos", file=sys.stderr)
    apikeys = {}


class YoCollector(threading.Thread):
    PORT = 7010

    def __init__(self, server, callback):
        self.server = server
        class YoHandler(http.server.BaseHTTPRequestHandler):
            def do_HEAD(self):
                route, request = self.path.split("?", 1)
                route = route[1:]
                request = parse_qs(request)
                if "username" in request:
                    callback(route, request)
        self.httpd = socketserver.TCPServer(("", self.PORT), YoHandler)
        super().__init__()

    def run(self):
        self.httpd.serve_forever()
            
class Yo(Callback):
    def __init__(self, server):
        self.server = server
        self.yodaemon = YoCollector(server, self.yo_receive)
        self.yodaemon.start()
        self.routesf = server.get_config_dir("yo_routes.json")
        self.routes = Config(self.routesf, default={})

        self.usersf = server.get_config_dir("yo_users.json")
        self.users = Config(self.usersf, default={})

        self.keysf = server.get_config_dir("yo_keys.json")
        self.keys = Config(self.keysf, default={})
        super().__init__()

    @command("yoassoc", r"(#\S+)\s+(\S+)\s+(.+)", admin=True)
    def yoassoc(self, server, message, channel, route, apikey):
        self.routes[route] = server.lower(channel)
        self.keys[server.lower(channel)] = apikey
        return "13│🖐│ Associated /%s with %s (account %s)" % (route, channel, apikey)

    @command("setyo", r"(\S+)")
    def setyo(self, server, message, username):
        self.users[server.lower(message.address.nick)] = username
        return "13│🖐│ Associated %s with yo account %s. This currently does nothing." % (message.address.nick, username)

    @command("yo", r"(\S+)(?:\s+(\S+))")
    def yo(self, server, message, username, link):
        ctx = server.lower(message.address.context)
        if ctx not in self.keys:
            return "04│🖐│ This channel doesn't have a yo account."
        args = {"api_token": self.keys[ctx], 'username':username}
        if link: args["link"] = link
        data = requests.post("http://api.justyo.co/yo/", data=link)
        try:
            data = data.json()
        except:
            return "04│🖐│ Yo's fucked up."
        else:
            if "success" in data:
               return "13│🖐│ Yo'd at %s" % username
            else:
                return "04│🖐│ " + data["error"]

    @staticmethod
    def latlong_to_addr(latlong):
        latlong = latlong.replace(";", ",")
        format_data = "\x0312\x1f%s\x1f\x03" % shorten("https://www.google.com/maps/search/%s" % latlong)
        if "key" in apikeys:
            data = requests.get("https://maps.googleapis.com/maps/api/geocode/json", params={"latlong": latlong, "key": apikeys["key"]})
            try: addr = data["results"][0]["formatted_address"]
            except: pass 
            else: format_data = addr + " · " + format_data
        return format_data

    def yo_receive(self, route, evt):
        if route in self.routes:
            if "link" in evt:            
                self.server.message("04│🖐│ Yo, check out \x0312\x1f%s\x1f\x03 · from %s" % (shorten(evt["link"]), evt["username"]), self.routes[route])
            elif "location" in evt:
                self.server.message("04│🖐│ Yo, I'm at \x0312\x1f%s\x1f\x03 · from %s" % (self.latlong_to_addr(evt["location"]), evt["username"]), self.routes[route])
            else:
                self.server.message("04│🖐│ Yo! · from %s" % evt["username"], self.routes[route])


__initialise__ = Yo

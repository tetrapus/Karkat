from xml.etree import ElementTree as etree
import collections
import difflib
import re
import sys
import time
import json
import urllib.parse
import urllib.request

import yaml 

from . import parser

from util.services import url as URL
from util.irc import Message
from bot.events import Callback, command
from util.text import striplen, spacepad, justifiedtable
from util import parallelise

try:
    apikeys = yaml.safe_load(open("config/apikeys.conf"))["wolfram"]
except:
    print("Warning: Wolfram module not loaded: invalid or nonexistant api key.", file=sys.stderr)
    print("Request an apikey at https://developer.wolframalpha.com/portal/apisignup.html and place in apikeys.conf as wolfram.key.<key>", file=sys.stderr)
    raise ImportError("Module not loaded.")


class WolframAlpha(Callback):

    t_max = 64
    h_max = 7
    t_lines = 12
    timeout = 45

    SETTINGS_FILE = "wolfram_users.json"

    results = ["Result", "Response", "Infinite sum", "Decimal approximation", "Decimal form", "Limit", "Definition", "Definitions", "Description", "Balanced equation", "Chemical names and formulas", "Conversions to other units", "Roots", "Root", "Definite integral", "Plot", "Plots"]
    input_categories = ["Input interpretation", "Input"]

    def __init__(self, server):
        self.server = server
        self.printer = server.printer
        self.last = None
        self.cache = {}
        self.settingsf = server.get_config_dir(self.SETTINGS_FILE)
        self.ips = {}
        if "iptracker" in dir(server):
            self.ips = server.iptracker.known
        try:
            self.settings = json.load(open(self.settingsf))
        except:
            self.settings = {}

        super().__init__(server)

    def breakdown(self, data, width):
        """
        Uses heuristics to guess the data type of a piece of data, then generates an appropriate representation.
        Parses meta, lists, numbers, URLs, numbered lists and tables.
        Truncates long or multiple lines.
        """

        data = parser.delete_blank(data)
        data = parser.transpose_prepare(data)
        data = parser.replace_encoded_chars(data)
        data = parser.replace_symbol_words(data)
        data = parser.parse_maths(data)
        data = parser.parse_supersubs(data)
        data = parser.parse_all_sqrts(data)
        data = parser.shorten_urls(data)
        data = parser.rechunk(data)
        data = parser.format(data)

        return data
        
    def wolfram(self, query, location=None, ip=None):
        # Cache results for 5 minutes
        if query in self.cache and time.time() - self.cache[query][0] > 300:
            return self.cache[query][1]

        params = {"appid": apikeys["key"], "input":query, "scantimeout":str(self.timeout)}

        if location is not None:
            params["location"] = location
        if ip is not None:
            params["ip"] = ip

        response = urllib.request.urlopen("http://api.wolframalpha.com/v2/query?"+urllib.parse.urlencode(params), timeout=self.timeout)
        response = etree.parse(response)
        data = collections.OrderedDict()
        for pod in response.findall("pod"):
            title = pod.get("title")
            data[title] = "\n".join([i.findtext("plaintext") or i.find("img").get("src") for i in pod.findall("subpod")])
            if not data[title].strip(): 
                del data[title]
        self.cache[query] = [time.time(), data]

        return data
        
    def wolfram_format(self, query, category=None, h_max=None, user=None, wasettings={}):
        try:
            if self.last is not None:
                query = query.replace("$_", self.last)
            answer, url = parallelise([lambda: self.wolfram(query, **wasettings), lambda: URL.shorten("http://www.wolframalpha.com/input/?i=%s" % urllib.parse.quote_plus(query))])
            if "Result" in answer and "(" not in answer["Result"]:
                self.last = answer["Result"]
            else:
                self.last = "(%s)" % query
        except urllib.error.URLError:
            return "05Wolfram08Alpha failed to respond. Try again later or go to " + URL.format(url)
            
        if not answer:
            return "05Wolfram08Alpha returned no results for '07%s'" % query
        
        for i in self.input_categories:
            if i in answer:
                header = answer[i]
                remove = i
                break
        else: 
            header ="'%s'"%query
            remove = False
        
        header = str.join(" ", header.split())
        
        h_max = h_max or self.h_max
        
        if not category:
            results = answer
            if remove:
                results = collections.OrderedDict([(k, v) for k, v in answer.items() if k != remove])
            
            if category is not None:
                # Guess the category
                for i in self.results:
                    if i in answer:
                        results = {i: results[i]}
                        break
                else:
                    results = {list(results.keys())[0]: list(results.values())[0]}
        else:
            results = max(answer, key=lambda x:difflib.SequenceMatcher(None, category, x).ratio())
            results = {results:answer[results]}
        
        output = [spacepad("05Wolfram08Alpha 04 ", " %s" % header, self.t_max)]
        t_max = striplen(output[0])
        
        results = collections.OrderedDict([(k, self.breakdown(v.split("\n"), t_max - 3)) for k, v in results.items()])
        
        total_lines = sum([min(len(results[x]), h_max) for x in results])
        
        if total_lines > self.t_lines:
            # Too many lines, print the available categories instead.
            for i in justifiedtable(sorted(results.keys(), key=len) + ["05Categories"], t_max-3):
                output.append(" 04⎪ %s" % i)
            output[-1] = " 04⎩" + output[-1][5:]
        elif results:
            if len(results) == 1 and len(list(results.values())[0]) == 1:
                # Single line: Shorten output
                catname = list(results.keys())[0]
                if catname in self.results:
                    output = ["08│ %s " % list(results.values())[0][0]]
                else:
                    output = [spacepad("08│ %s " % list(results.values())[0][0], "07%s" % catname, t_max)]
            else:
                for category in results:
                    lines = [x.rstrip() for x in results[category]]

                    output.append(spacepad(" 08⎨ %s " % lines.pop(0), " 07%s" % category, t_max))
                    truncated = lines[:h_max]
                    for line in truncated:
                        output.append(" 08⎪ " + line)

                    if len(truncated) < len(lines):
                        omission = "%d more lines" % (len(lines) - h_max + 1)
                        length = t_max - len(omission) - 6 - len(url)
                        output[-1] = " 08✁ " + url + " " + ("-"*int(length)) + " 07%s" % omission
        else:
            output.append(" 08‣ 05No plaintext results. See " + URL.format(URL.shorten("http://www.wolframalpha.com/input/?i=%s" % urllib.parse.quote_plus(query))))
        return "\n".join(i.rstrip() for i in output)

    def getoutputsettings(self, target):
        if self.server.isIn(target, self.settings):
            return self.settings[self.server.lower(target)]["h_max"]
        else:
            return self.h_max

    def getusersettings(self, user):
        wasettings = {}
        user = self.server.lower(user)
        if user in self.settings:
            settings = self.settings[user]
            if "location" in settings:
                wasettings["location"] = settings["location"]
            if "ip" in settings:
                wasettings["ip"] = settings["ip"]
            elif "iptracker" in dir(self.server) and user in self.server.iptracker.known:
                wasettings["ip"] = self.server.iptracker.known[user]
        return wasettings

    @command("waset", r"(\S+)(?:\s+(.+))?", templates={
                Callback.USAGE:"05Wolfram Settings04⎟ Usage: [.@](waset) 03(ip|location) [value]"})
    def update_settings(self, server, msg, varname, value):
        var = varname.lower()
        nick = server.lower(msg.address.nick) 
        if varname not in ("location", "ip"):
            return "05Wolfram Settings04⎟ No such setting."
        elif value is None:
            try:
                value = repr(self.settings[nick][var])
            except:
                value = "not set"
            return "05Wolfram Settings05⎟ Your %s is currently %s." % (var, value) 
        else:
            if nick in self.settings:
                self.settings[nick][var] = value
            else:
                self.settings[nick] = {var: value}
            json.dump(self.settings, open(self.settingsf, "w"))
            return "05Wolfram Settings05⎟ Your %s has been set to %r." % (var, value)


    @Callback.threadsafe
    def shorthand_trigger(self, server, line) -> "privmsg":
        message = Message(line)
        user, context = message.address, message.context
        pattern = re.match(r"([~`])(.*?\1 ?|([\"']).*?\3 ?|[^ ]+ )(.+)", message.text)
        if pattern:
            prefix, category, quoted, query = pattern.groups()
            category = category.rstrip()
            if quoted:
                category = category[1:-1]
            elif category and category[-1] == prefix:
                category = category[:-1]

            target, msgtype = {"~": (context,   "PRIVMSG"),
                             "`": (user.nick, "NOTICE")}[prefix]

            self.printer.message(self.wolfram_format(query, category, h_max=self.getoutputsettings(target), wasettings=self.getusersettings(user.nick)), target, msgtype)

    @Callback.threadsafe
    @command(["wa", "wolfram"], "(.+)", templates={
                Callback.USAGE:"05Wolfram08Alpha04⎟ Usage: [.@](wa|wolfram) 03query"})
    def trigger(self, server, message, query):
        return self.wolfram_format(query, h_max=self.getoutputsettings(message.context), wasettings=self.getusersettings(message.address.nick))

__initialise__ = WolframAlpha

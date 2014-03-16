# import random
# import re


# class AI(object):
#     rickroll = open("./rickroll.txt").readlines()
#     bots = "Binary Linux Google Hurd Viengoos adiosToreador gallowsCalibrator terminallyCapricious apocalypseArisen arsenicCatnip Jaheira Soap".split()
#     nolearn = ["#trivion", "#uno", "#lounge"]
    
#     def __init__(self, db="./Uncalibrated", writeback=False):
#         """ Creates an artificial stupidity object using the specified
#             shelf. """
#         #import shelve
#         #self.shelf = shelve.open(filename=db, writeback=writeback)
#         self.files = [open("%s/%s"%(db, i), "r", errors='ignore') for i in ["binary", "data", "rate", "blacklist"]]
#         self.shelf = {}
#         self.shelf["blacklist"] = set([x.rstrip('\r') for x in self.files[3].read().split("\n")])
#         self.shelf["rate"] = set([x.rstrip('\r') for x in self.files[2].read().split("\n")])
#         self.shelf["data"] = set([x.rstrip('\r') for x in self.files[1].read().split("\n")])
#         self.shelf["DATA"] = set([x.rstrip('\r') for x in self.files[0].read().split("\n")])
#         #self.shelf = dict(zip(["DATA", "data", "rate", "blacklist"], [set([x.rstrip('\r') for x in i.read().split("\n")]) for i in self.files]))
#         self.shelf["rate"] = float(list(self.shelf["rate"])[0])
#         self.last = ["Nothing.", "Nothing.", "Nothing."]
#         self.recent = []
#         self.lsource = ""
#         self.constructrate = 0.314159265359                             # pi/10
#         self.lowerrate = 0.115572734979                                 # pi/10e
#         self.correctionrate = 0.66180339887498948                       # (1 + sqrt(5)) / 20 + 0.5
#         self.tangentrate = 0.164493406685                               # pi^2 / 6
#         self.wadsworthrate = 0.20322401432901574                            # sqrt(413)/100
#         self.wadsworthconst = 0.3
#         self.suggestrate = 0                                            # not implemented and this is a terrible idea
#         self.grammerifyrate = 0                                         # not implemented and also a terrible idea
#         self.internetrate = 90.01                                       # what does this even mean
#         self.sentiencerate = 0.32                                       # oh god oh god oh god

#     def storeData(self, data, nick):
#         shelf = {True: "DATA", False: "data"}[data.isupper()]
#         if [True for i in self.shelf["blacklist"] if nick.lower() == i.lower()]: return
#         if data not in self.shelf[shelf]: self.last[0] = '"%s\x0f"'%data
#         stored_string = [] #haha get it, because it's a list
#         for i in data.split():
#             textonly = "".join(x for x in i if x.isalpha()).lower()
#             if (nick.lower() in server.channels and textonly in [filter(str.isalpha, k).lower() for k in server.channels[nick.lower()] if list(filter(str.isalpha, k))]) or textonly in list(map(str.lower, server.nicks)):
#                 stored_string += [i.lower().replace(textonly, "Binary")]
#             else:
#                 stored_string += [i]
#         self.shelf[shelf].update([" ".join(stored_string)])

#     def getData(self, data, nick = ""):
#         sdata = ["Binary" if i.lower() in list(map(str.lower, server.nicks)) else i for i in data.split()]

#         pool = self.shelf["DATA"]
#         if random.random() < self.lowerrate:
#             pool = self.shelf["data"]
#         choices = [i for i in pool if random.choice(sdata).lower() in i.lower() and i.lower().strip() != data.lower().strip()]
#         if len(choices) < random.choice([2,3]):
#             choices = []
#             for i in range(random.randrange(3,9)):
#                 choices.append(random.choice(tuple(pool)))
#         answer = random.choice(choices)
#         self.recent.append(answer)
#         self.lsource = str(answer)
#         if choices[1:] and random.random() < self.constructrate:
#             common = set()
#             stuff = set(choices)
#             stuff.remove(answer)
#             words = set()
#             for i in stuff:
#                 words |= set([x.lower() for x in i.split()])
#             common = set(answer.lower().split()) & words
#             if common:
#                 self.lsource = ""
#                 word = list(common)[0]
#                 other = random.choice([i for i in stuff if word in i.lower().split()])
#                 self.recent.append(other)
#                 print(("Value constructed. Baseword: %r :: Seeds: %r & %r" % (word, answer, other)))
#                 answer = " ".join(answer.split()[:answer.lower().split().index(word)] + other.split()[other.lower().split().index(word):])
        
#         if random.random() < self.wadsworthrate and answer[0] != "\x01":
#             truncate = int(self.wadsworthconst * len(answer))
#             truncate, keep = answer[:truncate], answer[truncate:]
#             answer = keep.lstrip() if keep.startswith(" ") else (truncate.split(" ")[-1] + keep).lstrip()
#             print(("Wadsworthing. Throwing away %r, product is %r" % (truncate, answer)))
        
#         answer = answer.split(" ")
        
#         if random.random() < self.correctionrate:
#             fixed = []
#             for i in answer:
#                 correction = spellchecker.spellcheck(i.lower())
#                 fixed.append(i if not correction else correction[i.lower()][0])
#             if " ".join(answer) != " ".join(fixed):
#                 print(("Spellchecked. Original phrase: %r ==> %r" % (" ".join(answer), " ".join(fixed))))
#                 answer = fixed
            
#         if random.random() < self.tangentrate:
#             print(("Reprocessing data. Current state: %r" % (" ".join(answer))))
#             answer = self.getData(" ".join(answer), nick).split(" ")
        
#         rval = [nick if filter(str.isalnum, i).lower() in list(map(str.lower, server.nicks)) + ["binary", "linux"] else (i.lower().replace("bot", random.choice(["human","person"])) if i.lower().find("bot") == 0 and (i.lower() == "bot" or i[3].lower() not in "ht") else i) for i in answer]
            
#         rval = str.join(" ", rval).strip().replace("BINARY", nick)
#         self.last[1], self.last[2] = '"%s\x0f"'%(str.join(" ", sdata)), '"%s\x0f"'%(str(rval))
#         self.recent = self.recent[-10:]
#         if rval[0] == "\x01" and rval[-1] != "\x01": rval += "\x01"

#         return rval.upper()
           
#     def getStats(self):
#         return 'Lines learned: %s :: Last learned: %s :: Last reacted to: %s :: Last replied with: %s // Reply rate [%s%%]'%(len(self.shelf["data"])+len(self.shelf["DATA"]), self.last[0], self.last[1], self.last[2], self.shelf["rate"]*100)

#     def getSettings(self):
#         return "CONSTRUCT[%f%%] LOWER[%f%%] SPELLING[%f%%] TANGENT[%f%%] WADSWORTH[%f%%@%f%%] GOOGLE[%f%%] GRAMMER[%f%%] INTERNET[%f%%] SENTIENCE[%f%%]" % (self.constructrate*100, self.lowerrate*100, self.correctionrate*100, self.tangentrate*100, self.wadsworthconst*100, self.wadsworthrate*100, self.suggestrate*100, self.grammerifyrate*100, self.internetrate*100, self.sentiencerate*100)

#     @Callback.background
#     def ircTrigger(self, l, data):
#         target = l[2]
#         data = Message(data).text
#         if data.lower() == ":ai":
#             printer.message(self.getStats(), target)
#             return
#         if data.lower() == ":settings":
#             printer.message(self.getSettings(), target)
#             return
#         if not re.match(r"^[\w\01]", data[0]) or (Address(l[0]).nick == "Binary" and not data.isupper()) or ("script" in Address(l[0]).nick.lower()) or ("bot" in l[0][:l[0].find("@")].lower()) or Address(l[0]).nick in self.bots: return
#         if l[2].lower() not in self.shelf["blacklist"] | set(map(str.lower, server.nicks)) and Address(l[0]).nick not in self.shelf["blacklist"] and (data.isupper() or [i for i in data.split() if filter(str.isalpha, i).lower().rstrip('s') in list(map(str.lower, server.nicks))]):
#             for i in range(int(self.shelf["rate"]//1 + (random.random() < self.shelf["rate"]%1))):
#                 response = self.getData(data, Address(l[0]).nick)
#                 response = re.sub(URL.regex, lambda x: URL.format(URL.shorten(URL.uncaps(x.group(0)))), response)
#                 if response:
#                     if Address(l[0]).nick.lower() == "bucket" and "IS" in response.split()[1:-1]:
#                         bot.privmsg(target, ":Bucket, %s"%(response.lower()))
#                     else: 
#                         printer.message(response, target)
#         elif l[2].lower() == server.nick.lower():
#             response = self.getData(data, Address(l[0]).nick)
#             response = re.sub(URL.regex, lambda x: URL.format(URL.shorten(URL.uncaps(x.group(0)))), response)
#             if response:
#                 printer.message(response, target)
#         if l[2].lower() in self.nolearn and not data.isupper() or Address(l[0]).nick.lower() == "bucket": return
#         self.storeData(data, target)
           
#     def purge(self, keyword=None, replace=None):
#         if self.lsource and not keyword: keyword = self.lsource
#         elif not keyword:
#             printer.message("Couldn't purge, no usable data available.")
#             return
#         lines = [x for x in self.recent if keyword in x]
#         if len(lines) == 0:
#             printer.message("Couldn't purge, no matches found.")
#         elif len(lines) > 1:
#             printer.message("Matching items: %s" % (" | ".join(lines)))
#         else:
#             line = lines[0]
#             try:
#                 self.shelf["DATA"].remove(line)
#                 if replace: 
#                     self.shelf["DATA"] |= set([replace])
#                 printer.message("Purged %r from databank."%(line))
#             except:
#                 printer.message("Couldn't purge- manual search required.")
#             else:
#                 self.recent.remove(line)
#     def close(self):
#         fs = [open("./Uncalibrated/%s"%i, "w") for i in ["binary", "data", "blacklist"]]
#         for i in ["DATA", "data", "blacklist"]:
#             f = fs.pop(0)
#             f.write(str.join("\n", self.shelf[i]))
#             f.close()

import os
import re
import random
import requests
import time
import json

from bot.events import Callback, command
from util.irc import Message
from util.text import ircstrip


class Mutators(object):
    @staticmethod
    def cobed(line, weights):
        print("Cobedising. In: %s" % line)
        line = requests.get("http://cobed.gefjun.rfw.name/", params={"q": ircstrip(line.lower())}, headers={"X-Cobed-Auth": "kobun:nowbunbun"}).text.upper()
        print("           Out: %s" % line)
        line = re.sub(r"^\S+:\s*", "", line)
        weights["cobedise"] += 1
        return line

class AI(Callback):
    learningrate = 0.025
    laughter = {"lol": 1, "lmao": 1, "rofl": 1, "ha": 0.5, "lmfao": 1.5}
    positive = "amazing woah cool nice sweet awesome yay ++ good great true yep".split()
    negative = "lame boring what ? uh why wtf confuse terrible awful -- wrong nope sucks".split()
    coeff = "wow fucking ur really"

    def __init__(self, server):
        self.configdir = server.get_config_dir("AI")
        if not os.path.exists(self.configdir):
            os.makedirs(self.configdir, exist_ok=True)
        try:
            self.lines = open(self.configdir + "/caps.txt").read().split("\n")
        except FileNotFoundError:
            self.lines = ["HELLO"]
        self.server = server
        super().__init__(server)

        try:
            self.settings = json.load(open(self.configdir + "/settings.json"))
        except:
            self.settings = {
                "construct": 0.314159265359,                             # pi/10
                "lower": 0.115572734979,                                 # pi/10e
                "correction": 0.66180339887498948,                       # (1 + sqrt(5)) / 20 + 0.5
                "tangent": 0.164493406685,                               # pi^2 / 6
                "wadsworth": 0.20322401432901574,                            # sqrt(413)/100
                "wadsworthconst": 0.3,
                "cobedise": 0.0429,                                      # Kobun's filth ratio
                "suggest": 0,                                            # not implemented and this is a terrible idea
                "grammerify": 0,                                         # not implemented and also a terrible idea
                "internet": 90.01,                                       # what does this even mean
                "sentience": 0.32,                                       # oh god oh god oh god
            }

        try:
            self.istats = json.load(open(self.configdir + "/inputs.json"))
        except:
            self.istats = {}

        self.last = ""
        self.lasttime = 0
        self.lastmsg = ""
        self.context = []

        self.lastlines = []


    def continuity(self, words, retain):
        # Boost probability of common words being used as the seed
        self.context.extend(list(set(self.last.upper().split()) & set(words)) + self.last.split())
        if "\x01ACTION" in words:
            self.context.extend("\x01ACTION") # Increase probability of repeated actions in context
        random.shuffle(self.context)
        # Calculate # of words to keep
        retain = int(len(self.context) * retain * 1.15)
        self.context = self.context[:retain]
        # Add all words from prior text
        text = words + list(self.context)
        return text
        

    def getline(self, sender, text):
        weights = {i: 0 for i in self.settings}
        inputs = []

        words = text.upper().split()

        words = self.continuity(words, random.random())

        choices = [i for i in self.lines if random.choice(words).lower() in i.lower() and i.lower().strip() != text.lower().strip()]
        if len(choices) < random.choice([2,3]):
            choices = []
            for i in range(random.randrange(3,9)):
                choices.append(random.choice(tuple(self.lines)))
        answer = random.choice(choices)
        inputs.append(answer)

        self.last = answer

        if choices[1:] and random.random() < self.settings["construct"]:
            common = set()
            stuff = set(choices)
            stuff.remove(answer)
            words = set()
            for i in stuff:
                words |= set([x.lower() for x in i.split()])
            common = set(answer.lower().split()) & words
            if common:
                word = list(common)[0]
                other = random.choice([i for i in stuff if word in i.lower().split()])
                inputs.append(other)
                print(("Value constructed. Baseword: %r :: Seeds: %r & %r" % (word, answer, other)))
                answer = " ".join(answer.split()[:answer.lower().split().index(word)] + other.split()[other.lower().split().index(word):])
                # Using construct algorithm
                weights["construct"] += 1
        
        if random.random() < self.settings["wadsworth"] and answer[0] != "\x01":
            truncate = int(self.settings["wadsworthconst"] * len(answer))
            truncate, keep = answer[:truncate], answer[truncate:]
            answer = keep.lstrip() if keep.startswith(" ") else (truncate.split(" ")[-1] + keep).lstrip()
            print(("Wadsworthing. Throwing away %r, product is %r" % (truncate, answer)))
            # Using wadsworth algorithm
            weights["wadsworth"] += 1
        
        answer = answer.split(" ")
        
        if hasattr(self.server, "spellcheck") and random.random() < self.settings["correction"]:
            fixed = []
            for i in answer:
                correction = self.server.spellcheck(i.lower())
                fixed.append(i if not correction else correction[i.lower()][0])
            if " ".join(answer) != " ".join(fixed):
                print(("Spellchecked. Original phrase: %r ==> %r" % (" ".join(answer), " ".join(fixed))))
                answer = fixed
                # Using spellchecker algorithm
                weights["correction"] += 1
            
        if random.random() < self.settings["tangent"]:
            print(("Reprocessing data. Current state: %r" % (" ".join(answer))))
            answer, child_weights, child_inputs = self.getline(sender, " ".join(answer))
            answer = answer.split(" ")
            inputs.append(child_inputs)
            # Using tangent algorithm
            weights = {k: v/2 + child_weights[k] for k, v in weights.items()}
            weights["tangent"] += 1
        
        rval = [sender if "".join(k for k in i if i.isalnum()).lower() in list(map(str.lower, self.server.nicks)) + ["binary", "disconcerted"] else (i.lower().replace("bot", random.choice(["human","person"])) if i.lower().find("bot") == 0 and (i.lower() == "bot" or i[3].lower() not in "ht") else i) for i in answer]
            
        rval = " ".join(rval).strip().upper().replace("BINARY", sender.upper())

        if random.random() < self.settings["cobedise"]:
            try:
                rval = Mutators.cobed(rval, weights)
            except:
                print("Cobed failed.")

        # Fix mismatching \x01s
        if rval[0] == "\x01" and rval[-1] != "\x01": 
            rval += "\x01"

        return rval, weights, inputs

    def addline(self, users, line):
        for i in users:
            line = re.sub(r"\b%s\b" % re.escape(i), "BINARY", line, flags=re.IGNORECASE)
        self.lines.append(re.sub(r"\b(pipey|karkat|\|)\b", "BINARY", line, flags=re.IGNORECASE))
        with open(self.configdir + "caps.txt", "w") as f:
            f.write("\n".join(self.lines))

    @Callback.background
    def capsmsg(self, server, line) -> "privmsg":
        msg = Message(line)
        if not (msg.text[0].isalpha() or msg.text[0] == "\x01"):
            return
        if msg.text.lower().startswith("%s:" % server.nick.lower()) or (msg.text.isupper() or "karkat" in msg.text.lower() or "pipey" in msg.text.lower()):
            response, weights, inputs = self.getline(msg.address.nick, msg.text.upper())
            server.message(response, msg.context)
            self.lasttime = time.time()
            self.lastmsg = response
            self.lastlines.append((time.time(), weights, inputs))
        if msg.text.isupper() and msg.text not in self.lines:
            self.addline(server.channels[server.lower(msg.context)], msg.text.upper())

    @command("purge", admin=True)
    def purge(self, server, message):
        start = len(self.lines)
        self.lines = [i for i in self.lines if i.upper() != self.last.upper()]
        with open(self.configdir + "caps.txt", "w") as f:
            f.write("\n".join(self.lines))
        return "Removed %d instance(s) of %r from shouts." % (start - len(self.lines), self.last)

    def score(self, text):
        msg = text.lower()
        # Positive reactions include:
        # Laughter
        score = 0
        for i in self.laughter:
            score += self.laughter[i] * msg.count(i)
        # Positivity
        for i in self.positive:
            score += msg.count(i)
        # Negativity
        for i in self.negative:
            score -= msg.count(i)

        # Activations:
        if msg.startswith("%s:" % self.server.nick.lower()) or (text.isupper() or "karkat" in msg or "pipey" in msg):
            score += 0.5
        else:
            score -= 0.05

        # Emotional aggravators
        coeff = 1
        for i in self.coeff:
            coeff += 0.5 * msg.count(i)

        return score * coeff

    def adjust_weights(self, server, line) -> "privmsg":
        msg = Message(line)
        score = self.score(msg.text)
        now = time.time()
        self.lastlines = [i for i in self.lastlines if now - 90 < i[0]]
        for t, weights, inputs in self.lastlines:
            c = self.learningrate * score * (now - t) / 90
            for k in weights:
                self.settings[k] += c
            for i in inputs:
                self.istats.setdefault(i, 1)
                self.istats[i] += c
        self.settings = {k: min(1, max(0, v)) for k, v in self.settings.items()}

        with open(self.configdir + "/settings.json", "w") as f:
            json.dump(self.settings, f)
        with open(self.configdir + "/inputs.json", "w") as f:
            json.dump(self.istats, f)

    def shh(self, server, line) -> "privmsg":
        if re.match("shh+", Message(line).text) and time.time() - self.lasttime < 30:
            msg = ""
            for i in self.lastmsg:
                if i in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    msg += "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ"[ord(i) - 65]
                else:
                    msg += i                    
            server.message(msg, Message(line).context)

__initialise__ = AI


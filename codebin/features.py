# -*- coding: utf-8 -*-


import re
import random
import sqlite3
import time
import urllib
import shelve
import yaml
import json
import difflib
import fractions
import threading
import sys
import collections
import decimal
import enchant
import math

from xml.etree import ElementTree as etree
from text import *
from irc import *


apikeys = yaml.safe_load(open("apikeys.conf"))


class PiApproximator(object):
    precision = 75
    pichan = "#approximatelypi"
    exactpi = "3.141592653589793238462643383279502884197169399375105820974944592307816406286208998628034825342117067982148086513282306647093844609550582231725359408128481117450284102701938521105559644622948954930381964428810975665933446128475648233786783165271201909145649"
    
    def __init__(self, fname="piApprox"):
        self.piFile = fname
        self.activated = False
        pi = open("piApprox").read().split()
        self.iterations = int(pi.pop(0))
        self.pi = fractions.Fraction(int(pi.pop(0)), int(pi.pop(0)))
        self.nextIteration()
        
    def nextIteration(self):
        self.last = fractions.Fraction(self.pi.numerator, self.pi.denominator)
        self.iterations += 1;
        self.pi += fractions.Fraction(4*(-1)**self.iterations, 2*self.iterations+1)
        return self.pi
    
    def getApproximation(self):
        approximation = (self.pi + self.last) / 2
        return decimal.Decimal(approximation.numerator) / decimal.Decimal(approximation.denominator)
    
    def __call__(self, *data):
        self.trigger(*data)
    
    @Callback.background
    def trigger(self, *data):
        if not self.activated:
            return
    
        decimal.getcontext().prec = self.precision
        self.nextIteration()
        approximation = self.getApproximation()
        printer.message("pi ~= %s" % (approximation), self.pichan)
        with open(self.piFile, "wb") as piFile:
            piFile.write("%d %d %d" % (self.iterations, self.pi.numerator, self.pi.denominator))
    
    @Callback.threadsafe
    def metatrigger(self, x, y):
        if x[3].lower() == "::pi":
            length = len("%d/%d" % (self.pi.numerator, self.pi.denominator))
            precision = 0
            approximation = str(self.getApproximation())
            while precision < len(min(approximation, self.exactpi, key=len)) and approximation[precision] == self.exactpi[precision]:
                precision += 1
            
            printer.message("%d iterations, estimated correct to %d decimal places. Fractional representation is %d characters long." % (self.iterations, precision-1, length), x[2])
    def activate(self, *data):
        self.activated = True
        
        
piApprox = PiApproximator()
import requests
class Youtube(object):
    refresh = apikeys["youtube"]["channel"]
    appid = apikeys["youtube"]["appid"]
    secret = apikeys["youtube"]["secret"]

    def __init__(self):
        self.refresh_tokens()

    def request_auth(self):
        import webbrowser
        webbrowser.open("https://accounts.google.com/o/oauth2/auth?client_id=%s&redirect_uri=urn:ietf:wg:oauth:2.0:oob&response_type=code&scope=https://www.googleapis.com/auth/youtube" % self.appid)

    def get_auth_tokens(self, authtoken):
        payload = {"code": authtoken,
                   "client_id": self.appid,
                   "client_secret": self.secret,
                   "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
                   "grant_type": "authorization_code"}
        answer = requests.post("https://accounts.google.com/o/oauth2/token", data=payload).json()
        self.token = answer["access_token"]
        self.refresh = answer["refresh_token"]
        self.refresh_after = time.time() + int(answer["expires_in"])
        return answer

    def refresh_tokens(self):
        payload = {"client_id": self.appid,
                   "client_secret": self.secret,
                   "refresh_token": self.refresh,
                   "grant_type": "refresh_token"}
        answer = requests.post("https://accounts.google.com/o/oauth2/token", data=payload).json()
        self.token = answer["access_token"]
        self.refresh_after = time.time() + int(answer["expires_in"])
        return answer

    def tokensExpired(self):
        return time.time() > self.refresh_after

    def apimethod(funct):
        @functools.wraps(funct)
        def wrapper(self, *args, **kwargs):
            if self.tokensExpired():
                self.refresh_tokens()
            return funct(self, *args, **kwargs)
        return wrapper

    @apimethod
    def get_playlist_id(self, channel):
        payload = {"part": "snippet", "mine": "true", "maxResults":"50", "access_token": self.token}
        answer = requests.get("https://www.googleapis.com/youtube/v3/playlists", params=payload).json()
        for result in answer["items"]:
            if result["snippet"]["title"] == channel:
                return result["id"]

    @apimethod
    def create_playlist(self, playlist):
        payload = {
                    "snippet": {
                            "title": playlist
                            },
                    "status": {
                                "privacyStatus": "public"
                                }
                    }
        params = {"part": "snippet,status", "access_token": self.token}
        answer = requests.post("https://www.googleapis.com/youtube/v3/playlists", params=params, data=json.dumps(payload), headers={"Content-Type": "application/json"}).json()
        return answer["id"]

    @apimethod
    def playlist_insert(self, playlist, item):
        params = {"part": "snippet", "access_token": self.token}

        payload = {
                    "snippet": {
                        "playlistId": playlist,
                        "resourceId": {
                            "videoId": item,
                            "kind": "youtube#video"
                            }
                        }
                    }
        answer = requests.post("https://www.googleapis.com/youtube/v3/playlistItems", data=json.dumps(payload), params=params, headers={"Content-Type": "application/json"}).json()
        return answer

    def trigger(self, words, line):
        message = Message(line)
        videos = re.findall("(?:youtube\.com/watch\?(?:.+&)?v=|youtu\.be/)([a-zA-Z0-9-_]+)", message.message)
        if videos:
            playlist = self.get_playlist_id(message.context) or self.create_playlist(message.context)
            for video in videos:
                self.playlist_insert(playlist, video)

#yt = Youtube()

class Translator(object):
    dict_us = enchant.Dict("en_US")
    dict_normal = enchant.Dict("en_GB")

    def translate(self, line, fromd, tod):
        answer = []
        for i in line.split(" "):
            if not tod.check(i) and fromd.check(i):
                answer.append(tod.suggest(i)[0])
            else:
                answer.append(i)
        return " ".join(answer)

    def math_trigger(self, x, y):
        return
        if x[2] == "#math":
            fromd, tod = self.dict_us, self.dict_normal
            target = "#maths"
            prelude = "[#math] Translated American English:"
        elif x[2] == "#maths":
            fromd, tod = self.dict_normal, self.dict_us
            target = "#math"
            prelude = "[#maths] Translated to 'Murican:"
        else: return
        line = y.split(" ", 3)[-1][1:]
        user = Address(x[0]).nick
        if line.lower().startswith("\x01action") and line.endswith("\x01"):
            line = line[7:-1]
            user = "* %s" % user
        else:
            user = "<\xe2\x80\xae%s\xe2\x80\xad>" % (user[::-1])
        line = self.translate(line, fromd, tod)
        printer.message("%s %s %s" % (prelude, user, line), target)

translator = Translator()

class PiracyMonitor(object):
    
    ipscan = True
    ipfile = "./iplog"
    
    def __init__(self):
        self.known = dict([(str(x), str(y)) for x, y in json.loads(open(self.ipfile).read()).items()])
    
    def savestate(self):
        with open(self.ipfile, "w") as ipfile:
            ipfile.write(json.dumps(self.known))

    @Callback.background
    def trigger(self, x, y):
        if not self.ipscan: return
        
        ips = re.findall(r"(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)[-.]){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)", x[0])
        
        if ips: ips = ips[0]
        else: return
        
        ips = str().join(map(lambda x: x if x.isdigit() else ".", ips))
        
        if ips in self.known: return
        
        self.known[Address(x[0]).nick] = ips
        self.savestate()
        
        
ipscan = PiracyMonitor()
    
    
class CAHPlayer(object):
    def __init__(self, nick):
        self.nick = nick
        self.hand = []
        self.points = 0
        self.responses = None
        self.bets = None
        
    def addCard(self, card):
        self.hand.append(card)
            
    def addPoints(self, points=1):
        self.points += points
        
    def score(self):
        return self.points
    
    def setResponses(self, responses):
        self.responses = [self.hand[i-1] for i in responses]
    
    def setBet(self, bet):
        self.bets = [self.hand[i-1] for i in bet] or None
    
    def popResponses(self):
        value = list(self.responses or [])
        for i in value:
            self.hand.remove(i)
        self.responses = None
        return value
    
    def popBets(self):
        value = list(self.bets or [])
        for i in value:
            self.hand.remove(i)
        self.bets = None
        return value
    
    def printHand(self):
        with printer.buffer(self.nick, "NOTICE") as buffer:
            for i, card in enumerate(self.hand):
                buffer += "00,01 15,14 01,15  %d. %s" % (i+1, card[0].upper() + card[1:])
            buffer += "00,01 15,14 01,15  You have %d points." % self.points
    
class CAHDeck(object):
    def __init__(self):
        pass

class CardsAgainstHumanity(object):
    black = [i.strip() for i in open("cah/black.txt").read().split("\n")]
    white = [i.strip() for i in open("cah/white.txt").read().split("\n")]
    expansionqs = [i.strip() for i in open("cah/questions.txt").read().split("\n")]
    expansionas = [i.strip() for i in open("cah/answers.txt").read().split("\n")]
    
    def __init__(self, channel, rounds=None, black=[], white=[], rando=False, numcards=10, minplayers=3, bets=True, firstto=None, ranked=False):
        self.lock = threading.Lock()
        self.questions = self.black[:] + black[:]
        random.shuffle(self.questions)
        
        self.answers = self.white[:] + white[:]
        random.shuffle(self.answers)
        
        self.usedanswers = []
        
        self.state = "signups"
        self.channel = channel
        self.rounds = rounds
        self.maxcards = numcards
        self.minplayers = minplayers
        self.bets = not ranked or bets
        self.firstto = None
        self.ranked = ranked
        
        self.players = []
        self.allplayers = []
        
        self.round = 0
        self.czar = None
        self.question = None
        
        if rando:
            self.addRando()
        else: self.rando = None
        
    def addPlayer(self, player):
        if player in [x.nick for x in self.players]:
            return False
        elif player in [x.nick for x in self.allplayers]:
            p = [i for i in self.allplayers if i.nick == player][0]
        else:
            p = CAHPlayer(player)
            self.allplayers.append(p)
            self.repopulate(p)

        self.players.append(p)
        if self.state == "collect":
            p.printHand()
        return True
        
    def addRando(self):
        try:
            self.rando = self.getPlayer("Rando Cardrissian")
        except IndexError:
            randos = [x for x in self.allplayers if x.nick == "Rando Cardrissian"]
            if randos:
                self.rando = randos[0]
            else:
                self.rando = CAHPlayer("Rando Cardrissian")        
                self.allplayers.append(self.rando)
            
        self.players.append(self.rando)
        self.repopulate(self.rando)
        if not self.rando.responses and self.state == "collect":
            self.rando.setResponses(random.sample(range(1, len(self.rando.hand)+1), self.numcards()))
        self.repopulate(self.rando)
            
    def removeRando(self):
        self.remove(self.rando)
        self.rando = None
        self.judge()
            
    def getPlayer(self, nick):
        for i in self.players:
            if i.nick == nick:
                return i
        raise IndexError("No such player.")
           
    def repopulate(self, player):
        while len(player.hand) < self.maxcards:
            try:
                card = self.answers.pop()
            except IndexError:
                printer.message("00,01 15,14 01,15  Reshuffling deck...", self.channel)
                self.answers = self.usedanswers[:]
                self.usedanswers = []
                random.shuffle(self.answers)
            else:
                self.usedanswers.append(card)
                player.hand.append(card)
           
    def subs(self, x, sub):
        if x.group(2):
            if re.match(r"\w", sub[-1]):
                sub = "%s" % sub
            else:
                sub = "%s%s" % (sub[:-1], sub[-1])
        else:
            sub = "%s" % sub.rstrip(".")
        if x.group(1) is None:
            return sub
        elif x.group(1) == "^":
            return sub.upper()
        elif x.group(1) == "*":
            return "" + (" ".join(i[0].upper() + i[1:] for i in sub[1:].split()))
        else:
            return x.group(1) + sub[:2].upper() + sub[2:]
           
    def substitute(self, cards):
        if "_" not in self.question:
            return self.question + " " + cards[0][0].upper() + cards[0][1:]
        else:
            answer = self.question
            for i in cards:
                answer = re.sub(r"([^\w,] |^|[*^])?_+(\.)?", lambda x: self.subs(x, i), answer, count=1)
            return answer

    def numcards(self):
        if "_" not in self.question: return 1
        else: return len(re.findall("_+", self.question))
            
    def printplayers(self):
        printer.message("00,01 15,14 01,15  Scores: " + (", ".join("%s - %s"%(i.nick if i != self.czar else "%s"%i.nick, i.score()) for i in sorted(self.players, key=CAHPlayer.score)[::-1])), self.channel)
        
    def chooseprompt(self, rnum, forcenext=False): 
        if self.state == "collect" and self.round == rnum:
            printer.message("00,01 15,14 01,15  Waiting for: %s" % (", ".join(i.nick for i in self.players if not (i.responses or i == self.czar))), self.channel)
            if forcenext: threading.Timer(45, self.removeall, args=(rnum,)).start()
            else: threading.Timer(60, self.chooseprompt, args=(rnum,), kwargs={"forcenext":True}).start()
        
    def removeall(self, rnum):
        if self.state == "collect" and self.round == rnum:
            printer.message("00,01 15,14 01,15  Removing from the game: %s" % (", ".join(i.nick for i in self.players if not (i.responses or i == self.czar))), self.channel)
            for i in self.players:
                if not i.responses:
                    self.remove(i)
            self.judge()
        
    def endgame(self):
        self.state = "failed"
        with printer.buffer(self.channel) as buffer:
            buffer += "00,01 Cards Against Humanity  is over!"
            players = sorted(self.allplayers, key=CAHPlayer.score)[::-1]
            for i, player in enumerate(players):
                if i and players[i-1].score() == player.score():
                    rank = "   "
                else:
                    rank = ordinal(i+1)
                buffer += "00,01 15,14 01,15  %s: %s - %d points" % (rank, player.nick, player.score())
 
    def isEndGame(self):
        return not (self.questions) or (self.rounds and self.round >= self.rounds) or len(self.players) < self.minplayers or (self.firstto and any(i.score() >= self.firstto for i in self.players))
 
    def next(self):
        if self.isEndGame():
            self.endgame()
            return

        self.state = "collect"
        self.czar = self.players.pop()
        self.players.insert(0, self.czar)
        if self.czar == self.rando:
            self.czar = self.players.pop()
            self.players.insert(0, self.czar)
        self.round += 1
        
        self.printplayers()
        printer.message("00,01 15,14 01,15  %s will be the Card Czar for Round %d." % (self.czar.nick, self.round), self.channel)
        self.question = self.questions.pop()
        printer.message("00,01 %s " % re.sub("[*^]_+", "_______", self.question), self.channel)
        
        numanswers = self.numcards()
        numanswers = "a card" if numanswers == 1 else ("%d cards" % numanswers)

        for player in self.players:
            self.repopulate(player)
            if player == self.rando:
                player.setResponses(random.sample(range(1, len(player.hand)+1), self.numcards()))
            elif player != self.czar:
                printer.message("00,01 15,14 01,15  Please !choose %s." % numanswers, player.nick, "NOTICE")
                player.printHand()
            else:
                printer.message("00,01 15,14 01,15  You're the Card Czar! Once all the responses to come in, you can pick the best.", player.nick, "NOTICE")

        threading.Timer(75, self.chooseprompt, args=(self.round,)).start()

    def judge(self):
        if not [i for i in self.players if i.responses is None and i != self.czar] and self.state != "judge":
            self.order = [i for i in self.players if i != self.czar] + [i for i in self.players if i.bets and i != self.czar]
            random.shuffle(self.order)
            
            with printer.buffer(self.channel) as buffer:
                buffer += "00,01 15,14 01,15  All cards are in. %s, please pick the best %s" % (self.czar.nick, "response." if not self.ranked or len(self.players) < 4 else "%d responses." % min(len(self.players) - 2, 3))
                for i, player in enumerate(self.order):
                    response = player.responses if self.order.index(player) == i else player.bets
                    buffer += "00,01 15,14 01,15  %d. %s" % (i+1, self.substitute(response))
            self.state = "judge"

    def logwinner(self, wins):
        with sqlite3.connect("cah/statistics.db") as logdata:
            timestamp = time.time()
            visited = set()
            for player in self.order:
                if player == self.czar or player in visited: continue
                origrank = self.order.index(player)
                if player.bets:
                    betrank = self.order.index(player, origrank+1)
                    if origrank in wins:
                        origrank = wins.index(origrank) + 1
                    else: origrank = 0
                    if betrank in wins:
                        betrank = wins.index(betrank) + 1
                    else: betrank = 0
                    logdata.execute("INSERT INTO white VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (timestamp, player.nick, self.channel, self.round, self.czar.nick, self.question, ", ".join(player.responses), 1, origrank))
                    logdata.execute("INSERT INTO white VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (timestamp, player.nick, self.channel, self.round, self.czar.nick, self.question, ", ".join(player.bets), 1, betrank))
                else:
                    if origrank in wins:
                        origrank = wins.index(origrank) + 1
                    else: origrank = 0
                    logdata.execute("INSERT INTO white VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (timestamp, player.nick, self.channel, self.round, self.czar.nick, self.question, ", ".join(player.responses), 0, origrank))
                visited.add(player)

    def pick(self, number):
        # Logging
        try:
            self.logwinner([number-1] if type(number) == int else [i-1 for i in number])
        except sqlite3.ProgrammingError:
            sys.__stdout__.write("sqlite3 error\n")

        with printer.buffer(self.channel) as buff:
            if self.ranked:
                points = len(number)
                for i, choice in enumerate(number):
                    player = self.order[choice - 1]
                    response = player.popResponses() if self.order.index(player) == choice - 1 else player.popBets()
                    buff += "00,01 15,14 01,15  %s. %s: 00,01 %s " % (ordinal(i+1), player.nick, self.substitute(response))
                    player.addPoints(points)
                    points -= 1
            else:
                points = 1
                for i in {i for i in self.order if i.bets}:
                    i.points -= 1
                    points += 1
                winner = self.order[number - 1]
                winning = winner.popResponses() if self.order.index(winner) == number - 1 else winner.popBets()
                winner.addPoints(points)
                buff += "00,01 15,14 01,15  %s picked %s's response: 00,01 %s " % (self.czar.nick, winner.nick, self.substitute(winning))
            for i in self.order:
                response = i.popResponses() or i.popBets()
                if response:
                    buff += "00,01 15,14 01,15  %s: %s" % (i.nick, self.substitute(response))
        self.next()
    
    def remove(self, player):
        self.players.remove(player)
        if self.state == "collect" and self.isEndGame():
            self.endgame()

    
    def start(self):
        if self.state == "signups":
            if len(self.players) < self.minplayers:
                self.state = "failed"
                printer.message("00,01 Cards Against Humanity  has failed to gather enough interest.", self.channel)
            else:
                self.state = "started"
                printer.message("00,01 Cards Against Humanity  begins!", self.channel)
                self.next()
        
    def failed(self): 
        return self.state == "failed"

def savecards():
    with open("cah/questions.txt", "w") as f: f.write("\n".join(CardsAgainstHumanity.expansionqs))
    with open("cah/answers.txt", "w") as f: f.write("\n".join(CardsAgainstHumanity.expansionas))

def loadcards():
    CardsAgainstHumanity.expansionqs = [i.strip() for i in open("cah/questions.txt").read().split("\n")]
    CardsAgainstHumanity.expansionas = [i.strip() for i in open("cah/answers.txt").read().split("\n")]
    
class CAHBot(object):
    games = {}
    lock = threading.Lock()
    
    @Callback.threadsafe
    def trigger(self, x, sdata):
        channel = x[2].lower()
        nick = Address(x[0]).nick
        if not channel.startswith("#"):
            return
            
        elif x[3] in [":!Q.", ":!A."]:
            if x[3][2] == "Q":
                data = " ".join(x[4:])
                data = re.sub("_+", "_______", data)
                with self.lock:
                    CardsAgainstHumanity.expansionqs.append(data)
                    with open("cah/questions.txt", "w") as f: f.write("\n".join(CardsAgainstHumanity.expansionqs))
                printer.message("00,01 15,14 01,15  Added: 00,01 %s " % (data), channel)
            else:
                data = " ".join(x[4:])
                data = data.strip()
                if re.search("[^.?!]$", data): data += "."                
                with self.lock:
                    CardsAgainstHumanity.expansionas.append(data)
                    with open("cah/answers.txt", "w") as f: f.write("\n".join(CardsAgainstHumanity.expansionas))
                printer.message("00,01 15,14 01,15  Added: 01,00 %s " % (data), channel)
        elif channel in self.games and not self.games[channel].failed():
            game = self.games[channel]
            with game.lock:
                if x[3].lower() == ":!join":
                    if game.addPlayer(nick):
                        printer.message("00,01 15,14 01,15  %s is our %s player." % (nick, ordinal(len(game.players) - bool(game.rando))), channel)
                    else:
                        printer.message("00,01 15,14 01,15  %s is already in the game." % nick, channel)
                elif x[3].lower() == ":!score":
                    game.printplayers()
                elif x[3].lower() == ":!rando":
                    if game.rando:
                        printer.message("00,01 15,14 01,15  Rando Cardrissian is now out of the game.", channel)
                        game.removeRando()
                    else:
                        printer.message("00,01 15,14 01,15  Rando Cardrissian is now playing.", channel)
                        game.addRando()
                elif game.state == "signups" and x[3][1:].lower() in ["!start", "!go", "!begin"]:
                    if len(game.players) > 2 and nick in [x.nick for x in game.players]:
                        game.start()
                    else:
                        printer.message("00,01 15,14 01,15  The game can't begin without at least 3 players.", channel)
                elif nick in [x.nick for x in game.players]:
                    player = game.getPlayer(nick)
                    if x[3].lower() == ":!discard" and player.points:
                        args = " ".join(x[4:])
                        args = args.replace(",", " ")
                        cards = sorted(list(set(map(int, filter(str.isdigit and 1 <= int(x) <= len(player.hand), args.split())))))[::-1]
                        if len(cards) > game.maxcards / 2:
                            printer.message("00,01 15,14 01,15  You can't discard more than half your hand at once.", nick, "NOTICE")
                        else:
                            for i in cards:
                                game.answers.append(player.hand.pop(i-1))
                            random.shuffle(game.answers)
                            game.repopulate(player)
                            player.points -= 1
                            player.printHand()
                    elif x[3].lower() == ":!hand":
                        game.repopulate(player)
                        player.printHand()
                    elif x[3].lower() in [":!choose", ":!pick"]:
                        if player != game.czar and game.state == "collect":
                            args = sdata.split(" ", 4)[-1]
                            if "," in args and game.bets:
                                if player.points:
                                    args, bet = args.split(",")
                                    bet = [int(i) for i in bet.strip().split()]
                                else:
                                    printer.message("00,01 15,14 01,15  Not enough points to bet, sorry.", nick, "NOTICE")
                            else:
                                bet = []
                            args = [int(i) for i in args.split()]
                            if all((bet + args).count(i) == 1 and 1 <= i <= len(player.hand) for i in bet + args) and (len(args) == game.numcards() and len(bet) in [game.numcards(), 0]):
                                player.setResponses(args)
                                player.setBet(bet)
                                printer.message("Your response: 00,01 %s " % game.substitute(player.responses), nick, "NOTICE")
                                if bet:
                                    printer.message("       Backup: 00,01 %s " % game.substitute(player.bets), nick, "NOTICE")
                            else:
                                printer.message("00,01 15,14 01,15  Invalid arguments.", nick, "NOTICE")
                            if not [i for i in game.players if i.responses is None and i != game.czar]:
                                game.judge()
                        elif player == game.czar and game.state == "judge":
                            if x[4].isdigit() and 1 <= int(x[4]) <= len(game.order) and game.ranked == False:
                                game.pick(int(x[4]))
                            elif len(x[4:]) == min(len(game.players) - 2, 3) and all(map(str.isdigit and 1 <= int(n) <= len(game.order) and x[4:].count(n) == 1, x[4:])) and game.ranked == True:
                                game.pick([int(i) for i in x[4:])])
                            else:
                                printer.message("00,01 15,14 01,15  Invalid arguments.", nick, "NOTICE")
                                
                    elif x[3].lower() == ":!leave":
                        if player == game.czar and game.state == "judge":
                            printer.message("00,01 15,14 01,15  HEY GODDAMNIT COME BACK %s" % player.nick.upper(), channel)
                        else:
                            printer.message("00,01 15,14 01,15  %s is quitting the game, quitter." % player.nick, channel)
                            game.remove(player)
                            if game.state != 'failed':
                                if player == game.czar:
                                    for i in game.players:
                                        i.responses = None
                                        i.bets = None
                                    game.next()
                                game.judge()
                    elif x[3].lower() == ":!score":
                        game.printplayers()
        elif x[3].lower() in [":!cah", ":!cards"]:
            args = self.parseSettings(sdata.split(" ", 4)[-1])
            self.games[channel] = CardsAgainstHumanity(channel, **args)
            printer.message("00,01 Cards Against Humanity  will begin in a minute. Want to !join us?", channel)
            threading.Timer(150, self.games[channel].start).start()

    @staticmethod
    def parseSettings(args):
        kwargs = {}
        words = args.split()
        rounds, cards, firstto = re.search(r"\b([1-9]\d*) rounds\b", args), re.search(r"\b([5-9]|[1-9]\d+) cards\b", args), re.search(r"\bfirst to ([1-9]\d*)\b", args)

        if  rounds: kwargs["rounds"]  = int(rounds.group(1))
        if   cards: kwargs["cards"]   = int(cards.group(1))
        if firstto: kwargs["firstto"] = int(firstto.group(1))
        if "rando"       in words: kwargs["rando"]  = True
        if "ranked"      in words: kwargs["ranked"] = True
        if "betless" not in words: kwargs["bets"]   = False
        if "classic" not in words:
            kwargs["black"] = CardsAgainstHumanity.expansionqs[:]
            kwargs["white"] = CardsAgainstHumanity.expansionas[:]

        return kwargs


cah = CAHBot()


class HelpFiles(object):
    mapping = {"cah":"cah", "cards":"cah", "cards against humanity":"cah",
               "wa":"wolfram","wolfram":"wolfram","wolfram alpha":"wolfram", "wolfram|alpha":"wolfram",
               "ai":"ai",
               "spellchecker":"spelling", "spellcheck":"spelling", "spell":"spelling", "spelling":"spelling",
               "suggest":"suggest", "complete":"suggest", "google suggest":"suggest", "google complete":"suggest", "autocomplete":"suggest",
               "pi":"pi", "approximatelypi":"pi", "pi approximator":"pi", "piapprox":"pi",
               "mspa":"homestuck", "homestuck":"homestuck", "update":"homestuck",
               "google":"search", "search":"search",
               "filth":"filth", "filth ratio":"filth",
               "shorten":"shorten", "bit.ly":"shorten", "bitly":"shorten", "url shortener":"shorten", "url":"shorten", "shortgo":"shorten",
               "add game":"inc", "add":"inc", "inc":"inc", "increment":"inc", "incrementation":"inc", "++":"inc", "i++":"inc", "numbers":"inc"}
    @Callback.threadsafe
    def trigger(self, x, y):
        if " ".join(x[4:]).lower() in self.mapping:
            section = "#"+self.mapping[" ".join(x[4:]).lower()]
        else:
            section = ""
        if x[3].lower() == "::help": printer.message("See http://www.tetrap.us/karkat%s for documentation." % section, x[2])
    

class AI(object):
    rickroll = open("./rickroll.txt").readlines()
    bots = "Binary Linux Google Hurd Viengoos adiosToreador gallowsCalibrator terminallyCapricious apocalypseArisen arsenicCatnip Jaheira Soap".split()
    nolearn = ["#trivion", "#uno", "#lounge"]
    
    def __init__(self, db="./Uncalibrated", writeback=False):
        """ Creates an artificial stupidity object using the specified
            shelf. """
        #import shelve
        #self.shelf = shelve.open(filename=db, writeback=writeback)
        self.files = [open("%s/%s"%(db, i), "r", errors='ignore') for i in ["binary", "data", "rate", "blacklist"]]
        self.shelf = {}
        self.shelf["blacklist"] = set([x.rstrip('\r') for x in self.files[3].read().split("\n")])
        self.shelf["rate"] = set([x.rstrip('\r') for x in self.files[2].read().split("\n")])
        self.shelf["data"] = set([x.rstrip('\r') for x in self.files[1].read().split("\n")])
        self.shelf["DATA"] = set([x.rstrip('\r') for x in self.files[0].read().split("\n")])
        #self.shelf = dict(zip(["DATA", "data", "rate", "blacklist"], [set([x.rstrip('\r') for x in i.read().split("\n")]) for i in self.files]))
        self.shelf["rate"] = float(list(self.shelf["rate"])[0])
        self.last = ["Nothing.", "Nothing.", "Nothing."]
        self.recent = []
        self.lsource = ""
        self.constructrate = 0.314159265359                             # pi/10
        self.lowerrate = 0.115572734979                                 # pi/10e
        self.correctionrate = 0.66180339887498948                       # (1 + sqrt(5)) / 20 + 0.5
        self.tangentrate = 0.164493406685                               # pi^2 / 6
        self.wadsworthrate = 0.20322401432901574                            # sqrt(413)/100
        self.wadsworthconst = 0.3
        self.suggestrate = 0                                            # not implemented and this is a terrible idea
        self.grammerifyrate = 0                                         # not implemented and also a terrible idea
        self.internetrate = 90.01                                       # what does this even mean
        self.sentiencerate = 0.32                                       # oh god oh god oh god

    def storeData(self, data, nick):
        ## Bucket check.
        if "bucket" in data.lower() or "bucket" == nick.lower():
            return 
    
        shelf = {True: "DATA", False: "data"}[data.isupper()]
        if [True for i in self.shelf["blacklist"] if nick.lower() == i.lower()]: return
        if data not in self.shelf[shelf]: self.last[0] = '"%s\x0f"'%data
        stored_string = [] #haha get it, because it's a list
        for i in data.split():
            textonly = "".join(x for x in i if x.isalpha()).lower()
            if (nick.lower() in server.channels and textonly in [filter(str.isalpha, k).lower() for k in server.channels[nick.lower()] if filter(str.isalpha, k)]) or textonly in map(str.lower, server.nicks):
                stored_string += [i.lower().replace(textonly, "Binary")]
            else:
                stored_string += [i]
        self.shelf[shelf].update([" ".join(stored_string)])

    def getData(self, data, nick = ""):
        if "bucket" in data.lower():
            data = data.lower().replace("bucket", "sex")
        sdata = ["Binary" if i.lower() in map(str.lower, server.nicks) else i for i in data.split()]

        pool = self.shelf["DATA"]
        if random.random() < self.lowerrate:
            pool = self.shelf["data"]
        choices = [i for i in pool if random.choice(sdata).lower() in i.lower() and i.lower().strip() != data.lower().strip()]
        if len(choices) < random.choice([2,3]):
            choices = []
            for i in range(random.randrange(3,9)):
                choices.append(random.choice(tuple(pool)))
        answer = random.choice(choices)
        self.recent.append(answer)
        self.lsource = str(answer)
        if choices[1:] and random.random() < self.constructrate:
            common = set()
            stuff = set(choices)
            stuff.remove(answer)
            words = set()
            for i in stuff:
                words |= set([x.lower() for x in i.split()])
            common = set(answer.lower().split()) & words
            if common:
                self.lsource = ""
                word = list(common)[0]
                other = random.choice([i for i in stuff if word in i.lower().split()])
                self.recent.append(other)
                print("Value constructed. Baseword: %r :: Seeds: %r & %r" % (word, answer, other))
                answer = " ".join(answer.split()[:answer.lower().split().index(word)] + other.split()[other.lower().split().index(word):])
        
        if random.random() < self.wadsworthrate and answer[0] != "\x01":
            truncate = int(self.wadsworthconst * len(answer))
            truncate, keep = answer[:truncate], answer[truncate:]
            answer = keep.lstrip() if keep.startswith(" ") else (truncate.split(" ")[-1] + keep).lstrip()
            print("Wadsworthing. Throwing away %r, product is %r" % (truncate, answer))
        
        answer = answer.split(" ")
        
        if random.random() < self.correctionrate:
            fixed = []
            for i in answer:
                correction = spellchecker.spellcheck(i.lower())
                fixed.append(i if not correction else correction[i.lower()][0])
            if " ".join(answer) != " ".join(fixed):
                print("Spellchecked. Original phrase: %r ==> %r" % (" ".join(answer), " ".join(fixed)))
                answer = fixed
            
        if random.random() < self.tangentrate:
            print("Reprocessing data. Current state: %r" % (" ".join(answer)))
            answer = self.getData(" ".join(answer), nick).split(" ")
        
        rval = [nick if filter(str.isalnum, i).lower() in map(str.lower, server.nicks) + ["binary", "linux"] else (i.lower().replace("bot", random.choice(["human","person"])) if i.lower().find("bot") == 0 and (i.lower() == "bot" or i[3].lower() not in "ht") else i) for i in answer]
            
        rval = str.join(" ", rval).strip().replace("BINARY", nick)
        self.last[1], self.last[2] = '"%s\x0f"'%(str.join(" ", sdata)), '"%s\x0f"'%(str(rval))
        self.recent = self.recent[-10:]
        if rval[0] == "\x01" and rval[-1] != "\x01": rval += "\x01"

        return rval.upper()
           
    def getStats(self):
        return 'Lines learned: %s :: Last learned: %s :: Last reacted to: %s :: Last replied with: %s // Reply rate [%s%%]'%(len(self.shelf["data"])+len(self.shelf["DATA"]), self.last[0], self.last[1], self.last[2], self.shelf["rate"]*100)

    def getSettings(self):
        return "CONSTRUCT[%f%%] LOWER[%f%%] SPELLING[%f%%] TANGENT[%f%%] WADSWORTH[%f%%@%f%%] GOOGLE[%f%%] GRAMMER[%f%%] INTERNET[%f%%] SENTIENCE[%f%%]" % (self.constructrate*100, self.lowerrate*100, self.correctionrate*100, self.tangentrate*100, self.wadsworthconst*100, self.wadsworthrate*100, self.suggestrate*100, self.grammerifyrate*100, self.internetrate*100, self.sentiencerate*100)

    @Callback.background
    def ircTrigger(self, l, data):
        target = l[2]
        data = Message(data).text
        if data.lower() == ":ai":
            printer.message(self.getStats(), target)
            return
        if data.lower() == ":settings":
            printer.message(self.getSettings(), target)
            return
        if not re.match(r"^[\w\01]", data[0]) or (Address(l[0]).nick == "Binary" and not data.isupper()) or ("script" in Address(l[0]).nick.lower()) or ("bot" in l[0][:l[0].find("@")].lower()) or Address(l[0]).nick in self.bots: return
        if l[2].lower() not in self.shelf["blacklist"] | set(map(str.lower, server.nicks)) and Address(l[0]).nick not in self.shelf["blacklist"] and (data.isupper() or [i for i in data.split() if filter(str.isalpha, i).lower().rstrip('s') in map(str.lower, server.nicks)]):
            for i in range(int(self.shelf["rate"]//1 + (random.random() < self.shelf["rate"]%1))):
                response = self.getData(data, Address(l[0]).nick)
                response = re.sub(URL.regex, lambda x: URL.format(URL.shorten(URL.uncaps(x.group(0)))), response)
                if response:
                    if Address(l[0]).nick.lower() == "bucket" and "IS" in response.split()[1:-1]:
                        bot.privmsg(target, ":Bucket, %s"%(response.lower()))
                    else: 
                        printer.message(response, target)
        elif l[2].lower() == server.nick.lower():
            response = self.getData(data, Address(l[0]).nick)
            response = re.sub(URL.regex, lambda x: URL.format(URL.shorten(URL.uncaps(x.group(0)))), response)
            if response:
                printer.message(response, target)
        if l[2].lower() in self.nolearn and not data.isupper() or Address(l[0]).nick.lower() == "bucket": return
        self.storeData(data, target)
           
    def purge(self, keyword=None, replace=None):
        if self.lsource and not keyword: keyword = self.lsource
        elif not keyword:
            printer.message("Couldn't purge, no usable data available.")
            return
        lines = filter(lambda x: keyword in x, self.recent)
        if len(lines) == 0:
            printer.message("Couldn't purge, no matches found.")
        elif len(lines) > 1:
            printer.message("Matching items: %s" % (" | ".join(lines)))
        else:
            line = lines[0]
            try:
                ai.shelf["DATA"].remove(line)
                if replace: ai.shelf["DATA"] |= set([replace])
                printer.message("Purged %r from databank."%(line))
            except:
                printer.message("Couldn't purge- manual search required.")
            else:
                self.recent.remove(line)
    def close(self):
        fs = [open("./Uncalibrated/%s"%i, "w") for i in ["binary", "data", "blacklist"]]
        for i in ["DATA", "data", "blacklist"]:
            f = fs.pop(0)
            f.write(str.join("\n", self.shelf[i]))
            f.close()
ai = AI()


class FilthRatio(object):
    def filthratio(self, query, user=None):
        if user not in ipscan.known:
            ip = random.choice(ipscan.known.values())
        else:
            ip = ipscan.known[user]
        safeRequest = urllib.request.Request("http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s&safe=active&userip=%s" % (query, ip), None, {"Referer" : "http://www.tetrap.us/"})
        unsafeRequest = urllib.request.Request("http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s&userip=%s" % (query, ip), None, {"Referer" : "http://www.tetrap.us/"})
        try:
            ratio = float(json.decoder.JSONDecoder().decode(urllib.request.urlopen(safeRequest).read())["responseData"]["cursor"]["estimatedResultCount"])
        except KeyError:
            ratio = 0
        
        ratio /= float(json.decoder.JSONDecoder().decode(urllib.request.urlopen(unsafeRequest).read())["responseData"]["cursor"]["estimatedResultCount"])
        
        return 1-ratio

    @Callback.threadsafe
    @command("filth", "(.+)")
    def trigger(self, message, query):
        try:
            data = self.filthratio(urllib.quote(query), message.address.nick)
            return "05Filth ratio for %r ⎟ %.2f%%" % (query, data*100)
        except TypeError:
            return "05Filth ratio⎟ Error: Google is an asshole."
        except KeyError:
            return "05Filth ratio for %r ⎟ The fuck is that?" % query

class Checker(threading.Thread):

    interval = 75
    
    def __init__(self, *args):
    
        self.checking = True
        self.mspaFile = "./mspaFile"
        try:
            with open(self.mspaFile) as data:
                self.mspaData = data.read()
        except IOError:
            self.mspaData = ""
        self.mspaData = [tuple([i for i in i.split(" ", 2)]) for i in self.mspaData.split("\n")]

        self.last = None
        
        threading.Thread.__init__(self, *args)
        
        
    def run(self):
        while self.checking:
            self.ircFormat()
            for _ in range(self.interval):
                if self.checking:
                    time.sleep(1)
        print("Stopped checking.")
        
        
    def checkMSPA(self):
        try:
            page = urllib.urlopen("http://mspaintadventures.com/").read()
        except:
            return
        results = re.findall("(\d\d/\d\d/\d\d)\s+- <a href=\"(.+?)\">\"(.+?)\"</a><br>", page)
        
        if results != self.mspaData:
            with open(self.mspaFile, "wb") as mspasave:
                mspasave.write("\n".join(str.join(" ", i) for i in results))
            
            try:
                index  = results.index(self.mspaData[0])
            except:
                index = None
            
            self.mspaData = results
            return results[:index] if index else results
                
    def ircFormat(self):
        x = self.checkMSPA()
        if x:
            printer.message("\x02> \x0303%s\x02\x0f %sat \x1f\x0312http://mspaintadventures.com/%s\x0f\x1f" % (x[-1][-1], ("and \x0307%s more\x0f update%s " % (len(x) - 1, "s" if len(x) > 2 else "")) if len(x) - 1 else "", x[-1][1]), "#homestuck")

checker = Checker()
checker.start()

def joinchecker():
    global checker
    checker.checking = False
    checker.join()

    
def die(data="QUIT"):
    bot.quit(":" + ai.getData(data))
    globals()["connected"] = False

callbacks = {
         "privmsg" : [
                      ipscan.trigger,
                      ai.ircTrigger,
                      google,
                      complete_trigger,
                      wa.trigger,
                      addg.trigger,
                      FilthRatio().trigger,
                      shortgo,
                      piApprox.metatrigger,
                      spellchecker.correctChannel, 
                      spellchecker.updateKnown, 
                      spellchecker.passiveCorrector,
                      spellchecker.activeCorrector, 
                      cah.trigger,
                      HelpFiles().trigger,
                      translator.math_trigger,
                      #yt.trigger
                     ],
         "join" : [ipscan.trigger,
                   #lambda x: spellchecker.dictionary.add(Address(x[0]).nick) if not spellchecker.dictionary.check(Address(x[0]).nick) else None,
                  ],
         "353" : [lambda x, y: [ipscan.trigger(i if i.startswith(":") else ":"+i[1:], "") for i in x[5:]],
                 ]}
inlines = {
         "DIE" : [ai.close,
                  joinchecker
                 ]
        }

for i in callbacks:
    flist.setdefault(i, []).extend(callbacks[i])
for i in inlines:
    inline.setdefault(i, []).extend(inlines[i])
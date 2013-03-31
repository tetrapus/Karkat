#! /usr/bin/python
# -*- coding: utf-8 -*-

import collections
import decimal
import difflib
import enchant
import fractions
import json
import math
import os
import random
import re
import shelve
import shlex
import signal
import socket
import sqlite3
import subprocess
import sys
import thread
import threading
import time
import urllib
import urllib2
from xml.etree import ElementTree as etree
import yaml

from threads import ColourPrinter, Caller
from irc import Address, Callback
from text import pretty_date, ordinal, ircstrip, striplen, justifiedtable, aligntable, Buffer

if "init" in sys.argv:
    # Initialise files
    pass #TODO


socket.setdefaulttimeout(1800)

GP_CALLERS = 2
connected = True

apikeys = yaml.safe_load(open("apikeys.conf"))

class Connection(object):
    def __init__(self, conf):
        config = yaml.safe_load(open(conf))
        self.sock = None
        self.server = tuple(config["Server"])
        self.username = config["Username"]
        self.realname = config["Real Name"]
        self.mode = config.get("Mode", 0)
        
        self.nick = None
        self.nicks = config["Nick"]

    def connect(self):
        self.sock = socket.socket()
        self.sock.connect(self.server)

        # Try our first nickname.
        nicks = collections.deque(self.nicks)
        self.nick = nicks.popleft()
        self.sendline("NICK %s" % self.nick)
        # Create a temporary buffer while we find a working nickname
        buff = Buffer()
        while buff.append(self.sock.recv(1)):
            for line in buff:
                if line.startswith("PING"):
                    # We're done here.
                    self.sendline("PONG %s" % line.split()[-1])
                    break
                words = line.split()
                errdict = {"433": "Invalid nickname, retrying.", "436": "Nickname in use, retrying."}
                if words[1] == "432":
                    raise ValueError("Arguments sent to server are invalid; are you sure the configuration file is correct?")
                elif words[1] in errdict:
                    print >> sys.stderr, errdict[words[1]]
                    self.nick = nicks.popleft()
                    self.sendline("NICK %s" % self.nick)
            else:
                # If we haven't broken out of the loop, our nickname is not valid.
                continue
            break
        self.sendline("USER %s %s * :%s\r\n" % (self.username, self.mode, self.realname))

    def sendline(self, line):
        self.sock.send("%s\r\n" % line)


class ServerState(Connection):
    """ Beware of thread safety when manipulating server state. If a callback
    interacts with this class, it must either not be marked threadsafe, or be
    okay with the fact the state can change under your feet. """

    # TODO: Store own state
    # TODO: Interact with connection threads
    # TODO: Extend interface to search for users and return lists and things.
    #       See xchat docs for interface ideas.
    # TODO: Fix nickname case rules and do sanity checking

    def __init__(self, conf):
        super(ServerState, self).__init__(conf)
        self.channels = {}

    def userLeft(self, words, line):
        """ Handles PARTs """
        nick = Address(words[0]).nick
        channel = words[2].lower()
        if nick.lower() == self.nick.lower():
            del self.channels[channel]
        else:
            self.channels[channel].remove(nick)

    def userQuit(self, words, line):
        """ Handles QUITs"""
        nick = Address(words[0]).nick
        for i in self.channels:
            if nick in self.channels[i]:
                self.channels[i].remove(nick)

    def userJoin(self, words, line):
        """ Handles JOINs """
        nick = Address(words[0]).nick
        channel = words[2][1:].lower()
        if nick.lower() == self.nick.lower():
            self.channels[channel] = []
            bot.who(words[2]) # TODO: replace with connection object shit.
        else:
            self.channels[channel].append(nick)

    def joinedChannel(self, words, line):
        """ Handles 352s (WHOs) """
        self.channels[words[3].lower()].append(words[7])

    def userNickchange(self, words, line):
        """ Handles NICKs """
        nick = Address(words[0]).nick
        newnick = words[2][1:]
        for i in self.channels:
            if nick in self.channels[i]:
                self.channels[i][self.channels[i].index(nick)] = newnick
        if nick.lower() == self.nick.lower():
            self.nick = newnick

    def userKicked(self, words, line):
        """ Handles KICKs """
        nick = words[3]
        channel = words[2].lower()
        self.channels[channel].remove(nick)

try:
    server = ServerState(sys.argv[1])
except (OSError, IndexError):
    print "Usage: %s <config>" % sys.argv[0]
    sys.exit(1)
server.connect()
s = server.sock


printer = ColourPrinter(s)
sys.stdout = printer
callers   = [Caller() for _ in range(GP_CALLERS + 2)] # Make 4 general purpose callers.
caller    = callers[1] # second caller is the general caller
bg_caller = callers[0] # first caller is the background caller
for c in callers: 
    c.start()


class URL(object):

    ssite = "http://api.bitly.com/v3/shorten?"
    bitly = {'login': apikeys["bit.ly"]["user"], 'apiKey':apikeys["bit.ly"]["key"], 'format': "json"}
    regex = re.compile(r"\b(\w+://)?\w+(\.\w+)+/[^\s]*\b")
        
    @classmethod
    def uncaps(cls, url):
        page = json.decoder.JSONDecoder().decode(urllib.urlopen("http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s" % urllib.quote(url)).read())
        urls = [i["unescapedUrl"].encode("utf-8") for i in page["responseData"]["results"]]
        urls = [(difflib.SequenceMatcher(None, url.upper(), x.upper()).ratio(), x) for x in urls]
        urls = filter(lambda x: x[0] > 0.8, urls)
        if urls: return max(urls, key=lambda x:x[0])[1]
        else: return url.lower()
        
    @classmethod
    def format(cls, url):
        return "\x0312\x1f%s\x1f\x03" % url
    
    @classmethod
    def shorten(cls, url):
        if not url.lower().startswith("http://"):
            url = "http://" + url
        data = urllib.urlopen(cls.ssite + urllib.urlencode(cls.bitly) + "&longUrl=" + urllib.quote(url)).read()
        data = json.decoder.JSONDecoder().decode(data)
        return data["data"]["url"].encode("utf-8")        
                                

def codify(x):
    data = dict(zip(('HOSTMASK', 'TYPE', 'CONTEXT', 'MESSAGE'), x.split(" ",3)))
    data["CONTEXT"] = Address(data["HOSTMASK"]).nick if data["CONTEXT"] == server.nick else data["CONTEXT"]
    return data

@Callback.threadsafe
def shortgo(x, y):
    if len(x) > 3 and len(x[3]) > 2 and x[3][1] in "!@" and x[3][2:].lower() in ["shorten", "shortgo", "bl", "bitly", "bit.ly"]:
        target, msgtype = x[2], "PRIVMSG"
        nick = Address(x[0]).nick
        if target[0] != "#": 
            target = nick
        
        try:
            data = URL.shorten(" ".join(x[4:]))
        except:
            printer.message("「 ShortGo 」 That didn't work somehow.", target, msgtype)
        else:
            printer.message("「 ShortGo 」 %s" % URL.format(data), target, msgtype)

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


class SpellChecker(object):
    channels = {}
    users = {}
    immune = ["soap"]
    dictionary = enchant.DictWithPWL("en_US", pwl="ircwords")
    alternate = enchant.Dict("en_GB")
    threshhold = 2
    reset_at = 1500
    reset_to = int(round(math.log(reset_at)))
    last = None
    wordsep = "/.:^&*|+=-?,_"

    literalprefixes = ".!/@<`~"
    dataprefixes = "#$<[/"
    contractions = ["s", "d", "ve", "nt"]
    delrioisms = ["dong", "lix", "saq", "dix"]

    @classmethod
    def stripContractions(cls, word):
        last = word.rsplit("'", 1)[-1].lower()
        return word[:-len(last) - 1] if last in cls.contractions else word

    @classmethod
    def isWord(cls, word):
        # delrioisms are not words.
        for i in cls.delrioisms:
            if i in word.lower():
                return False

        # excessively non-alpha strings are not words.
        if len(filter(lambda x: not (x.isalpha() or x in "'"), word)) >= cls.threshhold:
            return False

        # words prefixed with the following are not real words
        if word[0] in cls.dataprefixes:
            return False
        return True

    @classmethod
    def isLiteral(cls, sentence):
        return not sentence or sentence[0] in cls.literalprefixes

    @classmethod
    def spellcheck(cls, sentence):
        sentence = ircstrip(sentence)
        if cls.isLiteral(sentence): return
        sentence = [cls.stripContractions(i) for i in sentence.split() if cls.isWord(i)]
        errors = [i for i in sentence if not (cls.dictionary.check(i) or cls.alternate.check(i))]
        suggestions = [set(cls.alternate.suggest(i)) | set(cls.dictionary.suggest(i)) for i in errors]
        # reduce the suggestions
        suggestions = [{filter(lambda x: x.isalpha() or x in "'", i).lower() for i in x} for x in suggestions]
        wrong = []
        append = {}
        for i, word in enumerate(errors):
            if filter(str.isalpha, word).lower() not in suggestions[i]:
            
                token = set(word) & set(cls.wordsep)
                if token:
                    token = token.pop()
                    words = word.split(token)
                    suggested = [cls.spellcheck(i) for i in words]
                    suggested = [i.values()[0] if i else None for i in suggested]
                    if all(suggested):
                        wrong.append(word)
                    elif any(suggested):
                        if suggested[0]:
                            suggested = suggested[0]
                            suggested = [i + token + words[1] for i in suggested]
                        else:
                            suggested = suggested[1]
                            suggested = [words[0] + token + i for i in suggested]
                        append[word] = suggested
                else:
                    # Repetition for emphasis is allowed over a threshhold
                    string = re.escape(word)
                    pattern = re.sub(r"(.+?)\1\1+", r"(\1)+", string, flags=re.IGNORECASE)
                    truncated = re.sub(r"(.+?)\1\1+", r"\1\1", word, flags=re.IGNORECASE)
                    truncated2 = re.sub(r"(.+?)\1\1+", r"\1", word, flags=re.IGNORECASE)
                    suggestions[i] |= set(cls.alternate.suggest(truncated)) | set(cls.dictionary.suggest(truncated)) | set(cls.alternate.suggest(truncated2)) | set(cls.dictionary.suggest(truncated2))
                    if not any(re.match(pattern, x) for x in suggestions[i]):
                        wrong.append(word)

        if wrong or append: 
            wrong = {i: cls.alternate.suggest(i) for i in wrong}
            wrong.update(append)
            return wrong # Give a dictionary of words : [suggestions]
    
    @Callback.background
    def passiveCorrector(self, x, line):
        nick = Address(x[0]).nick
        if not self.dictionary.check(nick):
            self.dictionary.add(nick)
        nick = nick.lower()
        if len(x[3]) > 1 and x[3][1] in "@!.:`~/": return
        target = x[2]
        if target[0] != "#": 
            target = Address(x[0]).nick
        data = self.spellcheck(codify(line)["MESSAGE"][1:])
        with sqlite3.connect("spellchecker.db") as typos:
            for i in (data or []):
                typos.execute("INSERT INTO typos VALUES (?, ?, ?, ?)", (time.time(), nick, target, i))
        user = self.users.setdefault(Address(x[0]).nick.lower(), [0, 0])
        user[0] += len(data) if data else 0
        user[1] += len(x) - 3
        if user[1] > self.reset_at:
            user[0] /= self.reset_to
            user[1] /= self.reset_to
        if data and user[1] and nick not in self.immune and ((x[2].lower() in self.channels and 1000*user[0]/user[1] > self.channels[x[2].lower()]) or (nick in self.channels and 1000*user[0]/user[1] > self.channels[nick])):
            printer.message(("%s: " % Address(x[0]).nick) + str.join(", " ,[k + " -> " + (v[0] if v else "[????]") for k,v in data.iteritems()]), target)
            if len(data) == 1:
                self.last = data.keys()[0]
            else:
                self.last = None
            
    @Callback.threadsafe
    def activeCorrector(self, x, y):
        if len(x) > 4 and len(x[3]) > 2 and x[3][1:].lower() == "!spell":
            nick, msgtype = (codify(y)["CONTEXT"], "PRIVMSG")
            if nick[0] != "#": 
                nick = Address(x[0]).nick
            
            query = x[4]
            
            if (self.dictionary.check(query) or self.alternate.check(query)):
                printer.message("%s, that seems to be spelt correctly." % Address(x[0]).nick, nick, msgtype)
            else:
                suggestions = self.alternate.suggest(query)[:6]
                printer.message("Possible correct spellings: %s" % ("/".join(suggestions)), nick, msgtype)
    
    def updateKnown(self, x, y):
        newword = re.match(r":(%s[^\a]?\s*)?([^\s]+)( i|')s a( real)? word.*" % server.nick, " ".join(x[3:]), flags=re.IGNORECASE)
        notword = re.match(r":(%s[^\a]?\s*)?([^\s]+) is(n't| not) a( real)? word.*" % server.nick, " ".join(x[3:]), flags=re.IGNORECASE)

        if newword:
            word = newword.group(2)
            
            if word.lower() == "that":
                word = self.last
            if not word:
                printer.message("What is?", x[2] if x[2][0] == "#" else Address(x[0]).nick)
            elif self.dictionary.check(word):
                printer.message("I KNOW.", x[2] if x[2][0] == "#" else Address(x[0]).nick)
            else:
                self.dictionary.add(word)
                printer.message("Oh, sorry, I'll remember that.", x[2] if x[2][0] == "#" else Address(x[0]).nick) 
        if notword:
            word = notword.group(2)
            if self.dictionary.is_added(word):
                self.dictionary.remove(word)
                printer.message("Okay then.", x[2] if x[2][0] == "#" else Address(x[0]).nick) 
            else:
                printer.message("I DON'T CARE.", x[2] if x[2][0] == "#" else Address(x[0]).nick)
                
    def correctChannel(self, x, y):
        if len(x) == 5 and x[3].lower().startswith(":!spellcheck") and (x[4].lower() in ["on", "off"] or x[4].isdigit()):
            nick, msgtype = (codify(y)["CONTEXT"], "PRIVMSG")
            if nick[0] != "#": 
                nick = Address(x[0]).nick
            if x[4].lower() == "off":
                if nick.lower() in self.channels:
                    del self.channels[nick.lower()]
                    printer.message("FINE.", nick, msgtype)
                else:
                    printer.message("IT'S OFF DICKBUTT", nick, msgtype)
            else:
                query = int(x[4]) if x[4].isdigit() else 0
                self.channels[nick.lower()] = query
                printer.message("DONE.", nick, msgtype) 


spellchecker = SpellChecker()
spellchecker.dictionary._add = spellchecker.dictionary.add
spellchecker.dictionary.add = lambda x: spellchecker.dictionary._add(x) if "\n" not in x else sys.__stdout__.write("fuck you.")
# TODO: Reintegrate spellchecker callbacks that update the nicklist.
   
@Callback.threadsafe
def ajoinoi(l, sl):
    if Address(l[0]).nick in ["Lyucit","Lukion","Hexadecimal", "Lion"] or l[3][1:].lower() in server.channels:
        bot.join(":%s" % l[3][1:])


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
    

def getexpr(expr, mapping):
    """ 
    Tries to balance the brackets of an expression.
    Will return the empty string or an expression wrapped in brackets.
    """
    count = 0
    brackets = 0
    queue = collections.deque(expr)
    while queue:
        temp = queue.popleft()
        if temp == "(":
            brackets += 1
        elif temp == ")":
            brackets -= 1
        elif temp not in mapping: return ""
        count += 1
        if brackets <= 0: break
    if brackets or count == 1: return ""
    try:
        assert expr[0] + expr[count-1] == "()" or not expr
    except: 
        print >> sys.__stdout__, "%s | %s | %s" % (expr, expr[0] + expr[count-1], expr[:count])
    return expr[:count]

def substitute(regex, sub, raw_subset):
    greedy = regex.group(1).decode("utf-8")
    subset = "".join(sub.keys())

    if greedy.startswith("("):
        expr = getexpr(greedy, subset)
        if expr:
            result = u"".join(map(lambda x: sub[x].decode("utf-8"), expr[1:-1])).replace(" ", "")
            result += greedy[len(expr):]
        else: result = regex.group(0)[0]+greedy
    else:
        result = u""
        for i in greedy:
            if i in raw_subset:
                result += sub[i].decode("utf-8")
            else:
                break
        result += greedy[len(result):]
    return result.encode("utf-8")
    
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
    black = filter(str.strip, open("cah/black.txt").read().split("\n"))
    white = filter(str.strip, open("cah/white.txt").read().split("\n"))
    expansionqs = filter(str.strip, open("cah/questions.txt").read().split("\n"))
    expansionas = filter(str.strip, open("cah/answers.txt").read().split("\n"))
    
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
        if player in map(lambda x: x.nick, self.players):
            return False
        elif player in map(lambda x: x.nick, self.allplayers):
            p = filter(lambda x: x.nick == player, self.allplayers)[0]
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
            randos = filter(lambda x: x.nick == "Rando Cardrissian", self.allplayers)
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
    CardsAgainstHumanity.expansionqs = filter(str.strip, open("cah/questions.txt").read().split("\n"))
    CardsAgainstHumanity.expansionas = filter(str.strip, open("cah/answers.txt").read().split("\n"))
    
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
                    if len(game.players) > 2 and nick in map(lambda x:x.nick, game.players):
                        game.start()
                    else:
                        printer.message("00,01 15,14 01,15  The game can't begin without at least 3 players.", channel)
                elif nick in map(lambda x:x.nick, game.players):
                    player = game.getPlayer(nick)
                    if x[3].lower() == ":!discard" and player.points:
                        args = " ".join(x[4:])
                        args = args.replace(",", " ")
                        cards = sorted(list(set(map(int, filter(lambda x: x.isdigit() and 1 <= int(x) <= len(player.hand), args.split())))))[::-1]
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
                                    bet = map(int, bet.strip().split())
                                else:
                                    printer.message("00,01 15,14 01,15  Not enough points to bet, sorry.", nick, "NOTICE")
                            else:
                                bet = []
                            args = map(int, args.split())
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
                            elif len(x[4:]) == min(len(game.players) - 2, 3) and all(map(lambda n: n.isdigit() and 1 <= int(n) <= len(game.order) and x[4:].count(n) == 1, x[4:])) and game.ranked == True:
                                game.pick(map(int, x[4:]))
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

class WolframAlpha(object):

    appid = apikeys["wolfram"]["key"]
    t_min = 40
    t_max = 72
    cat_outlier = 18 # Maximum width of outlier column.
    timeout = 45
    h_max = 8
    t_lines = 14
    nerf = ["implosion"]
    ascii = [chr(i) for i in range(128)]

    results = ["Result", "Response", "Infinite sum", "Decimal approximation", "Decimal form", "Limit", "Definition", "Definitions", "Description", "Balanced equation", "Chemical names and formulas", "Conversions to other units", "Roots", "Root", "Definite integral", "Plot", "Plots"]
    
    # TODO: Implement timeout.
    
    def __init__(self, appid=None):
        if appid is not None:
            self.appid = appid
        
    def breakdown(self, data, width):
        """
        Uses heuristics to guess the data type of a piece of data, then generates an appropriate representation.
        Parses meta, lists, numbers, URLs, numbered lists and tables.
        Truncates long or multiple lines.
        """
        sub = {"0":"₀","1":"₁","2":"₂","3":"₃","4":"₄","5":"₅","6":"₆","7":"₇",
               "8":"₈","9":"₉","+":"₊","-":"₋","=":"₌","(":"₍",")":"₎","a":"ₐ",
               "e":"ₑ","h":"ₕ","i":"ᵢ","k":"ₖ","l":"ₗ","m":"ₘ","n":"ₙ","o":"ₒ",
               "p":"ₚ","r":"ᵣ","s":"ₛ","t":"ₜ","u":"ᵤ","v":"ᵥ","x":"ₓ"," ": "",
               }
        sup = {"0":"⁰","1":"¹","2":"²","3":"³","4":"⁴","5":"⁵","6":"⁶","7":"⁷",
               "8":"⁸","9":"⁹","+":"⁺","-":"⁻","=":"⁼","(":"⁽",")":"⁾","a":"ᵃ",
               "b":"ᵇ", "c":"ᶜ","d":"ᵈ","e":"ᵉ","f":"ᶠ","g":"ᵍ","h":"ʰ","i":"ⁱ",
               "j":"ʲ","k":"ᵏ","l":"ˡ","m":"ᵐ","n":"ⁿ","o":"ᵒ","p":"ᵖ","r":"ʳ",
               "s":"ˢ","t":"ᵗ","u":"ᵘ","v":"ᵛ","w":"ʷ","x":"ˣ","y":"ʸ","z":"ᶻ",
               " ":" ", "_":"-", "T":"ᵀ",
               }
        symbols = {"lambda": "λ", "e":"ℯ", "theta":"θ", "infinity":"∞", "pi":"π", "integral":"∫", "element":"∈", "intersection":"∩", "union":"∪", "IMPLIES":"⇒", "sqrt":"√‾", "sum":"∑", "product":"∏", "constant":"08 Constant"}
        supset = "abcdefghijklmnoprstuvwxyz0123456789_T"
        subset = "aehiklmnoprstuvx0123456789"
        
        hasHeadings = False
        # remove blank lines:
        data = [i.replace("^transpose", "^T") for i in data if i.strip()]
        
        data = [re.sub(r"\\:([a-f0-9]{4})", lambda x: unichr(int(x.group(1), 16)).encode("utf-8"), i) for i in data]
        
        if len(filter(str.isalpha, reduce(lambda x, y: x.replace(y, ""), symbols.keys(), "".join(data)))) < len("".join(data)) / 2:
            # Probably mathematical!
            data = [re.sub(r"[a-z]+", lambda x: symbols[x.group(0).lower()] if x.group(0) in symbols else x.group(0), i, flags=re.IGNORECASE) for i in data]
        newdata = []
        for line in data:
            sups = ""
            while sups != line:
                sups = line
                line = re.sub("\\^(.+)", lambda s: substitute(s, sup, supset), line, flags=re.IGNORECASE)
            subs = ""
            while subs != line:
                subs = line
                line = re.sub("_(.+)", lambda s: substitute(s, sub, subset), line, flags=re.IGNORECASE)
            newdata.append(line)
        data = newdata
        
        nometadata = [i for i in data if not (i.lstrip().startswith("(") and i.rstrip().endswith(")"))]
        if len({i.count("|") for i in nometadata}) == 1: # fix when matrices are nested in lists.
            # Probably an aligned table!
            isMatrix = len(nometadata) > 1 and nometadata[0].count("(") == nometadata[0].count(")") + 1 and nometadata[-1].count(")") == nometadata[-1].count("(") + 1
            meta = [(i, string) for i, string in enumerate(data) if string.lstrip().startswith("(") and string.rstrip().endswith(")")]
            for i, string in meta:
                data.remove(string)
            if isMatrix:
                prematrix, data[0] = data[0].split("(", 1)
                data[-1], postmatrix = data[-1].rsplit(")", 1)
            data = [[cell.strip() for cell in row.split("|")] for row in data]

            if data and not data[0][0]:
                hasHeadings = True
            if isMatrix:
                data = aligntable(data, "  ")
                data[0]    =  "⎛%s⎞" % data[0]
                data[1:-1] = ["⎜%s⎟" % i for i in data[1:-1]]
                data[-1]   =  "⎝%s⎠" % data[-1]
                data = [(" "*len(prematrix.decode("utf-8")))+i for i in data]
                data[len(data)/2] = prematrix + data[len(data)/2].lstrip() + postmatrix
            else: data = aligntable(data)
            for i, string in meta[::-1]:
                data.insert(i, string)
        
        if hasHeadings: data[0] = "%s" % data[0]
        return data
        
    def wolfram(self, query):
        response = urllib2.urlopen("http://api.wolframalpha.com/v2/query?"+urllib.urlencode({"appid":self.appid, "input":query, "scantimeout":str(self.timeout)}), timeout=self.timeout)
        response = etree.parse(response)
        data = collections.OrderedDict()
        for pod in response.findall("pod"):
            title = pod.get("title").encode("utf-8")
            data[title] = "\n".join([i.findtext("plaintext") or URL.format(URL.shorten(i.find("img").get("src"))) for i in pod.findall("subpod")]).encode("utf-8")
            if not data[title].strip(): 
                del data[title]
            # TODO: move url formatting to breakdown function.
        return data
        #return collections.OrderedDict([(i[0],unescape(i[1])) for i in re.findall("<pod title='(.+?)'.+?<plaintext>(.*?)</plaintext>.*?</pod>", response, re.DOTALL) if i[1]])
        
    @Callback.threadsafe
    def trigger(self, x, y):
        """
        - Name: Wolfram|Alpha
        - Identifier: Wolfram
        - Syntax: [~`]03category 03query or [!@]wa 03query (category may be bracketted for multiple words)
        - Description: Send a query to 05Wolfram08Alpha. 
        - Access: ALL
        - Type: Command 
        """
        if len(x) > 3 and len(x[3]) > 2 and ((x[3][1] in "!@" and x[3][2:].lower() in ["wolfram", "wa"]) or x[3][1] in "~`" and (len(x) > 4 or (len(x) > 3 and len(x[3]) > 3 and x[3][2] in "`~"))):

            nick, msgtype = (codify(y)["CONTEXT"], "PRIVMSG")  if x[3][1] in "@~" else ("llama", "NOTICE")
            if nick[0] != "#": 
                nick = Address(x[0]).nick
            h_max = self.h_max
            if nick.lower() in self.nerf or Address(x[0]).nick.lower() in self.nerf:
                h_max = 3
            category = None
            if x[3][1] in "~`":
                if x[3][2] not in "({[<":
                    if x[3][1] == x[3][2]:
                        category = False
                        query = " ".join([x[3][3:]] + x[4:])
                    else:
                        category = x[3][2:]
                        query = " ".join(x[4:])
                else:
                    query = codify(y)["MESSAGE"]
                    category = query[3:query.find({"(":")", "{":"}", "[":"]", "<":">"}[query[2]])]
                    query = str.rstrip(query[len(category)+4:])
            else:
                query = " ".join(x[4:])
            
            try:
                answer = self.wolfram(query)
            except urllib2.URLError:
                printer.message("05Wolfram08Alpha failed to respond. Try again soon or go to 12http://www.wolframalpha.com/input/?i=%s" % urllib.quote_plus(query), nick, msgtype)
                return
                
            if not answer:
                printer.message("05Wolfram08Alpha returned no results for '07%s'" % query, nick, msgtype)
                return
            
            if "Input interpretation" in answer: 
                topthing = answer["Input interpretation"]
                remove = "Input interpretation"
            elif "Input" in answer: 
                topthing = answer["Input"]
                remove = "Input"
            else: 
                topthing ="'%s'"%query
                remove = False
            
            topthing = str.join(" ", topthing.split())
            
            t_max = self.t_max
            
            if category is None:
                results = answer
                if remove:
                    results = collections.OrderedDict([(k, v) for k, v in results.iteritems() if k != remove])
            elif not category:
                for i in self.results:
                    if i in answer:
                        category = i
                        break
                else:
                    category = "res"

            if category:
                results = max(answer, key=lambda x:difflib.SequenceMatcher(None, category, x).ratio())
                results = {results:answer[results]}

                # TODO: add a thing to automatically detect if it's small enough. Else:
            
            if t_max - 15 - striplen(topthing) < 0:
                t_max = striplen(topthing) + 15
            
            results = collections.OrderedDict([(k, self.breakdown(v.split("\n"), t_max - 3)) for k, v in results.iteritems()])
            
            total_lines = sum([min([len(results[x]), h_max]) for x in results])
            
            if total_lines > self.t_lines:
                res = ["05Wolfram08Alpha 04 %s %s" % (" "*(t_max-15-striplen(topthing)), topthing)]
                z = justifiedtable(sorted(results.keys(), key=len), t_max-3)
                for i in z:
                    res.append(" 04⎜ %s" % i)
                res.append(" 04‣ ‣ ‣                                                      05Available Categories")
            elif results:
                if len(results) == 1 and len(results.values()[0]) == 1:
                    if len(results.values()[0][0]) > 65:
                        # Case: 1 long line
                        res = ["05Wolfram08Alpha 04⎟ 07%s 04⎜%s" % (results.keys()[0], results.values()[0][0])]
                    else:
                        # Case: 1 short line
                        res = ["05Wolfram08Alpha 04⎜%s%s04⎟ 07%s" % (results.values()[0][0], " "*(self.t_max-15-striplen(results.values()[0][0])), results.keys()[0])]
                else:
                    res = ["05Wolfram08Alpha 04 %s %s" % (" "*(t_max-15-striplen(topthing)), topthing)]
                    for i in results:
                        z = [x.rstrip() for x in results[i]]
                        if striplen(z[0]) + 4 > t_max:
                            res.append(" 04⎜ 07%s" % i)
                        else:
                            first = z.pop(0)
                            res.append(" 04⎜ %s%s 07%s" % (first, " "*(t_max-4-striplen(first) - striplen(i)), i))
                        if len(z) == h_max:
                            q = z[:h_max]
                        else:
                            q = z[:h_max-1]
                        for m in q:
                            if m and m == getexpr(m, self.ascii):
                                res.append(" 08‣ 05%s" % m[1:-1])
                            else:
                                res.append(" 08⎜ %s" % m)
                        if len(q) != len(z):
                            omission = "%d more lines omitted" % (len(z) - h_max)
                            res.append(" 08• • •%s07%s"%((t_max-6 - striplen(omission)) * " ",omission))
            else:
                res.append(" 08‣ 05No plaintext results. See 12http://www.wolframalpha.com/input/?i=%s05" % urllib.quote_plus(query))
            res = [i.rstrip() for i in res]
            printer.message("\n".join(res), nick, msgtype)
wa = WolframAlpha()


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
    
    
def complete(query):
    import json
    data = urllib.urlopen("http://suggestqueries.google.com/complete/search?output=firefox&client=firefox&hl=en&q=%(searchTerms)s"%{"searchTerms":query}).read()
    data = json.JSONDecoder(encoding="ISO-8859-1").decode(data)[1]
    data = [i.encode("utf-8") for i in data]
    return data
    
 
def completetable(query, results, size=100, rowmax=None):
    biggest = len(max(results, key=len))
    columns = int((size-2) / (float(biggest)+3))
    if len(results) < columns:
        columns = len(results)
    rows = int(math.ceil(len(results)/float(columns)))
    rownum = ""
    if rowmax and rowmax < rows:
        while rows > rowmax:
            rows -= 1
            results = results[:rows*columns]
            biggest = len(max(results, key=len))
            columns = int((size-2) / (float(biggest)+3))
            rows = int(math.ceil(len(results)/float(columns)))
        rownum = "(first %d rows) " % rows
    data = ["12G04o08o12g03l04e12 suggest  %s%s%s'%s'"%(rownum, " "*(((columns if len(results) > columns else len(results)) * (biggest+3)) - 17 - len(query) - len(rownum)), " "*((15 + len(query) + len(rownum)) % columns) if len(results) < columns else "", query)]
    cellsize = (len(data[0]) - 26) / columns if columns*(biggest+3) < len(data[0]) - 25 else biggest
    for i in range(rows):
        line = results[i*columns:(i+1)*columns if len(results) > (i+1)*columns else len(results)]
        line = ["%s%s"%((x, " "*(cellsize-len(x))) if y == 0 or y + 1 < columns else (" "*(cellsize-len(x)), x)) for y, x in enumerate(line)]
        data.append("%s%s%s" %("\x0312|\x03 ", " \x0312|\x03 ".join(line), " \x0312|\x03"))
    if len(data) > 2 and len(data[-1]) < len(data[1]):
        replacement = list(data[-2])
        replacement.insert(len(data[-1])-5, "\x1f")
        data[-2] = "".join(replacement)
    data[-1] = ""+data[-1]
    return data     

@Callback.threadsafe
def complete_trigger(x, y):
    """
    - Name: Google Suggest
    - Identifier: Complete
    - Syntax: [!@](complete|suggest) 03query
    - Description: Ask Google for similar search queries.
    - Access: ALL
    - Type: Command
    """
    if len(x) > 3 and len(x[3]) > 2 and x[3][1] in "!@" and x[3][2:].lower() in ["complete", "suggest"]:
        nick, msgtype = (codify(y)["CONTEXT"], "PRIVMSG")  if x[3][1] == "@" else ("llama", "NOTICE")
        if nick[0] != "#": 
            nick = Address(x[0]).nick
            truncate = None
        else:
            truncate = 3
        if len(x) == 4:
            printer.message("「 03Google 12suggest 」 Syntax is [:@](complete|suggest) QUERY. @ will truncate the output to 3 lines, and send to the channel.", nick, msgtype)
        else:
            query = " ".join(x[4:])
            result = complete(query)
            if result:
                table = completetable(query, result, 100, truncate)
                printer.message("\n".join(table), nick, msgtype)
            else:
                printer.message("「 03Google 12suggest 」 No results.", nick, msgtype)
            #maxlen = len(max(result, key=len))
            
def average(x): return float(sum(x))/len(x) if x else 0.00

def benchmark(funct, args=(), kwargs={}, iterations=1000):
    values = []
    for i in xrange(iterations):
        values.append(time.time())
        funct(*args, **kwargs)
        values[-1] = time.time()-values[-1]
    return average(values)
    

class AutoJoin(object):
    chans = open("./autojoin.txt").read().strip() if "-t" not in sys.argv else "#homestuck,#adult"
    def join(self, x, y):
        bot.join(self.chans)
    def trigger(self, x, y):
        if x[3].lower() == "::autojoin" and x[2].startswith("#"):
            if x[2].lower() in self.chans.split(","):
                chans = self.chans.split(",")
                chans.remove(x[2].lower())
                self.chans = ",".join(chans)
                with open("./autojoin.txt", "w") as chanfile:
                    chanfile.write(self.chans)
                printer.message("Channel removed from autojoin.", x[2])
            else:
                self.chans = ",".join(self.chans.split(",") + [x[2].lower()])
                with open("./autojoin.txt", "w") as chanfile:
                    chanfile.write(self.chans)
                printer.message("Channel added to autojoin.", x[2])

aj = AutoJoin()

class AI(object):
    rickroll = open("./rickroll.txt").readlines()
    bots = "Binary Linux Google Hurd Viengoos adiosToreador gallowsCalibrator terminallyCapricious apocalypseArisen arsenicCatnip Jaheira Soap".split()
    nolearn = ["#trivion", "#uno", "#lounge"]
    
    def __init__(self, db="./Uncalibrated", writeback=False):
        """ Creates an artificial stupidity object using the specified
            shelf. """
        #import shelve
        #self.shelf = shelve.open(filename=db, writeback=writeback)
        self.files = [open("%s/%s"%(db, i), "r") for i in ["binary", "data", "rate", "blacklist"]]
        self.shelf = dict(zip(["DATA", "data", "rate", "blacklist"], [set([x.rstrip('\r') for x in i.read().split("\n")]) for i in self.files]))
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
            textonly = filter(str.isalpha, i).lower()
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
            for i in xrange(random.randrange(3,9)):
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
                print >> sys.__stdout__, "Value constructed. Baseword: %r :: Seeds: %r & %r" % (word, answer, other)
                answer = " ".join(answer.split()[:answer.lower().split().index(word)] + other.split()[other.lower().split().index(word):])
        
        if random.random() < self.wadsworthrate and answer[0] != "\x01":
            truncate = int(self.wadsworthconst * len(answer))
            truncate, keep = answer[:truncate], answer[truncate:]
            answer = keep.lstrip() if keep.startswith(" ") else (truncate.split(" ")[-1] + keep).lstrip()
            print >> sys.__stdout__, "Wadsworthing. Throwing away %r, product is %r" % (truncate, answer)
        
        answer = answer.split(" ")
        
        if random.random() < self.correctionrate:
            fixed = []
            for i in answer:
                correction = spellchecker.spellcheck(i.lower())
                fixed.append(i if not correction else correction[i.lower()][0])
            if " ".join(answer) != " ".join(fixed):
                print >> sys.__stdout__, "Spellchecked. Original phrase: %r ==> %r" % (" ".join(answer), " ".join(fixed))
                answer = fixed
            
        if random.random() < self.tangentrate:
            print >> sys.__stdout__, "Reprocessing data. Current state: %r" % (" ".join(answer))
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
        target = codify(data)["CONTEXT"]
        data = codify(data)["MESSAGE"][1:]
        if data.lower() == ":ai":
            printer.message(self.getStats(), target)
            return
        if data.lower() == ":settings":
            printer.message(self.getSettings(), target)
            return
        if not re.match(r"^[\w\01]", data[0]) or (Address(l[0]).nick == "Binary" and not data.isupper()) or ("script" in Address(l[0]).nick.lower()) or ("bot" in l[0][:l[0].find("@")].lower()) or Address(l[0]).nick in self.bots: return
        if l[2].lower() not in self.shelf["blacklist"] | set(map(str.lower, server.nicks)) and Address(l[0]).nick not in self.shelf["blacklist"] and (data.isupper() or [i for i in data.split() if filter(str.isalpha, i).lower().rstrip('s') in map(str.lower, server.nicks)]):
            for i in xrange(int(self.shelf["rate"]//1 + (random.random() < self.shelf["rate"]%1))):
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

@Callback.threadsafe
def google(x, y):
    if len(x) > 4 and len(x[3]) == 8 and x[3][1] in "!@." and x[3][2:].lower() == "google":
        nick, msgtype = (codify(y)["CONTEXT"], "PRIVMSG")  if x[3][1] == "@" else ("llama", "NOTICE")
        if nick[0] != "#": 
            nick = Address(x[0]).nick
        query = " ".join(x[4:])
        page = json.loads(urllib.urlopen("http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s" % urllib.quote(query) ).read())
        for i in page["responseData"]["results"]: 
            printer.message("「 07Google 」 03%s :: 12%s" % (i["titleNoFormatting"].encode("utf-8"), i["unescapedUrl"].encode("utf-8")), nick, msgtype)
            if x[3][1] != ".": break
        if not page["responseData"]["results"]: printer.message("「 07Google 」 14No results found.", nick, msgtype)


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
        print format.encode("utf-8")


class FilthRatio(object):

    def filthratio(self, query, user=None):
        if user not in ipscan.known:
            ip = random.choice(ipscan.known.values())
        else:
            ip = ipscan.known[user]
        safeRequest = urllib2.Request("http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s&safe=active&userip=%s" % (query, ip), None, {"Referer" : "http://www.tetrap.us/"})
        unsafeRequest = urllib2.Request("http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s&userip=%s" % (query, ip), None, {"Referer" : "http://www.tetrap.us/"})
        try:
            ratio = float(json.decoder.JSONDecoder().decode(urllib2.urlopen(safeRequest).read())["responseData"]["cursor"]["estimatedResultCount"])
        except KeyError:
            ratio = 0
        
        ratio /= float(json.decoder.JSONDecoder().decode(urllib2.urlopen(unsafeRequest).read())["responseData"]["cursor"]["estimatedResultCount"])
        
        return 1-ratio

    @Callback.threadsafe
    def trigger(self, x, y):
        if len(x) > 4 and len(x[3]) > 2 and x[3][1] in "!@" and x[3][2:].lower() == "filth":
            nick, msgtype = (x[2], "PRIVMSG")  if x[3][1] == "@" else ("llama", "NOTICE")
            if nick[0] != "#": 
                nick = Address(x[0]).nick
            
            query = " ".join(x[4:])
            try:
                data = self.filthratio(urllib.quote(query), nick)
                printer.message("「 05Filth ratio for %r 」 %.2f%%" % (query, data*100), nick, msgtype)
            except TypeError:
                printer.message("「 05Filth ratio 」 Error: Google is an asshole.", nick, msgtype)
            except KeyError:
                printer.message("「 05Filth ratio for %r 」 The fuck is that?" % (query), nick, msgtype)

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
            for _ in xrange(self.interval):
                if self.checking:
                    time.sleep(1)
        printer.message("Stopped checking.")
        
        
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

class Allbots:
    def __init__(self, bots, args = ""):
        self.bots = bots
        self.args = args
    def __call__(self, *data):
        pref = self.args + (" " * bool(self.args))
        for i in self.bots:
            i.send(pref + (" ".join(data)) + "\n")
    def __getattr__(self, d):
        return Allbots(self.bots, self.args + " " + d)
bot = Allbots([s])

# 1010100100100010001011000001000011100000110010111000101100000100100110100111000001000001100000100110010010011000101
        
        
class AddGame(object):
    def __init__(self, path):
        self.path = path
        self.num = int(open(path).read().strip())
        self.history = {}

    def trigger(self, x, y):
        target = codify(y)
        nick = Address(target["HOSTMASK"]).nick
        if target["MESSAGE"].split()[0].lower()[1:] == ".add":
            if nick in self.history:
                self.history[nick] = [(t, d) for t, d in self.history[nick] if time.time() - t < 150]
                self.history[nick].append((time.time(), time.time() - self.history[nick][-1][0] if self.history[nick] else 0))
                self.history[nick] = self.history[nick][-4:]
            else:
                self.history[nick] = [(time.time(), 0)]
            
            if sum(i[0] for i in self.history[nick]) / len(self.history[nick]) < 1.5 or (len(self.history[nick]) - 1 and sum(abs(self.history[nick][i][-1] - self.history[nick][i-1][-1]) for i in xrange(1, len(self.history[nick]))) / len(self.history[nick]) < 2):
                printer.message("fuck you bitch i ain't no adding machine", nick, "NOTICE")
            else:
                self.num += 1
                open(self.path, 'w').write(str(self.num))

                printer.message("02Thanks for that %s, 03%s"%(nick, "The number has been increased to %s."%self.num))
addg = AddGame("./addgame")


class Shell(threading.Thread):

    activeShell = False
    shellThread = None

    def __init__(self, shell):
        self.shell = shell
        self.stdout = shell.stdout
        self.stdin = shell.stdin
        threading.Thread.__init__(self)
    def run(self):
        started = time.time()
        for line in iter(self.stdout.readline, ""):
            print line
        Shell.activeShell = False
        if time.time() - started > 2:
            print "[Shell] Program exited with code %s"%(self.shell.poll())

    @classmethod
    def trigger(cls, words, line):
        if Address(words[0]).mask == "goes.rawr" and words[3] == ":$":
            args = line.split(" ", 4)[-1]

            if not cls.activeShell:
                try:
                    shell = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, preexec_fn=os.setsid)
                except OSError:
                    print "「 Shell Error 」 Command failed."
                    return
                cls.activeShell = True
                cls.shellThread = cls(shell)
                cls.shellThread.start()
            else:
                cls.shellThread.stdin.write(args + "\n")

    @classmethod
    def terminate(cls):
        if cls.activeShell:
            os.killpg(cls.shellThread.shell.pid, signal.SIGTERM)


       
class CallbackSystem(object):
    def __init__(self, config="callbacks.yaml"):
        pass

flist = {
         "privmsg" : [#spell,
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
                      aj.trigger,
                      translator.math_trigger,
                      Shell.trigger,
                     ],
         "PING" : [],
         "join" : [
                   server.userJoin,
                   ipscan.trigger,
                   #lambda x: spellchecker.dictionary.add(Address(x[0]).nick) if not spellchecker.dictionary.check(Address(x[0]).nick) else None,
                  ],
         "nick" : [
                    server.userNickchange,
                  ],
         "kick" : [
                    server.userKicked,
                    lambda x, y: bot.join(x[2]) if x[3].lower() == server.nick.lower() else None,
                  ],
         "quit" : [server.userQuit],
         "part" : [server.userLeft],
         "invite" : [
                     ajoinoi,
                    ],
         "353" : [lambda x, y: [ipscan.trigger(i if i.startswith(":") else ":"+i[1:], "") for i in x[5:]],
                 ],
         "352" : [server.joinedChannel],
         "376" : [aj.join,
                  lambda *x: printer.start(),
                  lambda x, y: bot.mode(server.nick, "+B")
                  #piApprox.activate
                  ],
         "ALL" : [
                  #piApprox,
                 ],
         "DIE" : [ai.close,

                 ]
        }



class Pipeline(object):
    def __init__(self, descriptor=None):
        self.steps = []
        if descriptor:
            for step in descriptor.split("|"):
                self.add(step.strip())

    def __repr__(self):
        return " | ".join(self.steps)

    def add(self, step, pos=None):
        if pos:
            self.steps.insert(pos, step)
        else:
            self.steps.append(step)
            pos = len(self.steps) - 1
        return pos

    # syntactic sugar
    def __or__(self, step):
        self.add(step)
        return self

    def remove(self, pos):
        del self.steps[pos]

    def run(self):
        procs = {}
        procs[0] = subprocess.Popen(shlex.split(self.steps[0]), stdout=subprocess.PIPE)
        if len(self.steps) > 1:
            i = 1
            for p in self.steps[1:]:
                procs[i] = subprocess.Popen(shlex.split(p), stdin=procs[i-1].stdout, stdout=subprocess.PIPE)
                procs[i-1].stdout.close()
        output = procs[len(procs) - 1].communicate()[0]
        return output


class PipelineWithSubstitutions(Pipeline):
    def __init__(self, descriptor=None, substitutions=None):
        Pipeline.__init__(self, descriptor)
        self.substitutions = substitutions

    def add(self, step, pos=None):
        for sub in self.substitutions:
            step = re.sub(sub, self.substitutions[sub], step)
        Pipeline.add(self, step, pos)
        

class VolatilePipeline(Pipeline):
    def __repr__(self):
        return self.run()
        
class PipeWrapper(object):
    def __sub__(self, thing):
        pipe = VolatilePipeline()
        pipe.add(thing)
        return pipe
        
run = PipeWrapper()

class Debugger(object):
    def __init__(self):
        self.curcmd = []
        self.codereact = []
        self.activeShell = 0

curcmd = []
codeReact = 0
            

def die(data="QUIT"):
    bot.quit(":" + ai.getData(data))
    globals()["connected"] = False

buff = Buffer()

try:
    while connected and buff.append(s.recv(1024)):
        for line_w_spaces in buff:
            line_w_spaces = line_w_spaces.rstrip()
            line = line_w_spaces.split()

            if line[1] == "PRIVMSG" and line[2][0] == "#": # This is an inline callback.
                printer.last = line[2]
            elif line[1] == "PRIVMSG": 
                printer.last = Address(line[0]).nick
            
            # TODO: implement priority callback.
            if line[0]=="PING":
                s.send("PONG %s\r\n" % line[1])
                for i in flist["PING"]:
                    try:
                        thread.start_new_thread(i,tuple())
                    except BaseException:
                        sys.excepthook(*sys.exc_info())

            if "@goes.rawr" in line[0] and line[1] == "PRIVMSG" and (line[3][1:] in [">>>", '"""'] + map(lambda x: x+",", server.nicks) or codeReact):
                if line[3][1:-1] in server.nicks and line[3][-1] == "," and line[4] == "undo":
                    # Delete the last command off the buffer
                    curcmd = curcmd[:-1]
                    print "oh, sure"
                elif codeReact:
                    # Code is being added to the buffer.
                    do = False
                    if line[3] == ':"""':
                        # We've finished a multiline input, evaluate.
                        codeReact = 0
                        do = True
                    else:
                        # Keep building
                        act = line_w_spaces.split(" ", 3)[-1]
                        if '"""' in act:
                            # Is the end of the input somewhere in the text?
                            act = act[:act.find('"""')]
                            codeReact = 0
                            do = True
                        curcmd += [act[1:]]
                    if do:
                        # Do we execute yet?
                        try:
                            print eval(chr(10).join(curcmd))
                        except:
                            try:
                                exec(chr(10).join(curcmd))
                            except BaseException, e:
                                print "\x02「\x02\x0305 hah error \x0307 \x0315%s\x03\x02」\x02 "%(repr(e)[:repr(e).find("(")]) + str(e)
                        curcmd = []
                    continue
                    
                elif line[3] == ':"""':
                    # Enable code building.
                    codeReact = 1
                    continue

                else:

                    act = line_w_spaces.split(" ", 3)[-1]
                    ret = ""
                    try:
                        act = str(act[act.index(" ")+1:]) # What the fuck?
                    except ValueError:
                        act = ""
                    if act and (act[-1] in "\\:" or act[0] in " \t@"):
                        curcmd += [act[:-1]] if act[-1] == "\\" else [act] #NTS add pre-evaluation syntax checking
                        continue
                    elif act and (act[0] + act[-1] == "\x02\x02"):
                        ret = str(act)[1:-1]
                        act = chr(10).join(curcmd)
                        curcmd = []
                    elif curcmd:
                        act = chr(10).join(curcmd) + "\n" + act
                        curcmd = []
                    try: 
                        assert "\n" not in act and not ret
                        output = eval(act)
                        if output != None: print output
                    except:
                        try:
                            exec(act)
                            if ret: print eval(ret)
                        except BaseException, e:
                            print "\x02「\x02\x0305 oh wow\x0307 \x0315%s \x03\x02」\x02 "%(repr(e)[:repr(e).find("(")]) + str(e)

            elif len(line) > 3 and line[1] == "PRIVMSG":
                # Why the hell is this in an elif?
                callertimeout = [_.last for _ in callers[2:]]
                longestqueue = max(callers[2:], key=lambda x: x.work.qsize())
                if all(callertimeout) and longestqueue.work.qsize() > 50:
                    print >> sys.__stdout__, "All queues backed up: expanding."
                    callers.append(Caller())
                    callers[-1].start()
                    callers.remove(longestqueue)
                    longestqueue.terminate()
                for c in callers[2:]:
                    ltime = c.last
                    if ltime and time.time() - ltime > 8:
                        print >> sys.__stdout__, "Caller is taking too long: forking."
                        callers.remove(c)
                        callers.append(Caller(c.dump()))
                        callers[-1].start()
                        print >> sys.__stdout__, "Caller added."

            if len(line) > 1 and line[1].lower() in [_.lower() for _ in flist.keys()]:
                for funct in flist[line[1].lower()]:
                    if Callback.isBackground(funct):
                        bg_caller.queue(funct, (line, line_w_spaces))
                    elif Callback.isThreadsafe(funct):
                        min(callers, key=lambda x: x.work.qsize()).queue(funct, (line, line_w_spaces))
                    else:
                        caller.queue(funct, (line, line_w_spaces))
            for i in flist["ALL"]:
                caller.queue(i, (line_w_spaces,))

finally:
    print >> sys.__stdout__, "Bot ended; terminating threads."

    s.close()
    connected = 0
    print >> sys.__stdout__, "Connection closed."

    for funct in flist["DIE"]:
        funct()
    print >> sys.__stdout__, "Cleaned up."

    for c in callers: c.terminate()
    printer.terminate()
    checker.checking = False
    print >> sys.__stdout__, "Terminating threads..."

    printer.join()
    for c in callers: c.join()
    checker.join()
    print >> sys.__stdout__, "Threads terminated."
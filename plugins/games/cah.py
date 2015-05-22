import threading
import random
import re
import sqlite3
import time
import sys
import os
import functools
import requests
import json

from util import cmp
from util.text import ordinal, unescape
from util.irc import Callback, Address, Message, command
from util.files import Config

CAHPREFIX = "01│14│15│ "
datadir = "data/CardsAgainstHumanity"
CONFIG_FILE = "cahsettings.json"

def defaultdeck(black, white):
    questions = [i.strip() for i in open(datadir + "/black.txt").read().split("\n")] + black
    answers = [i.strip() for i in open(datadir + "/white.txt").read().split("\n")] + white
    # Get questions from reddit
    reddit = requests.get("http://www.reddit.com/r/AskReddit/hot.json", headers={"User-Agent": "Karkat-CardsAgainstHumanity-Scraper"}).json()
    reddit = reddit["data"]["children"]
    titles = [i["data"]["title"] for i in reddit if i["data"]["title"].endswith("?")]
    # 5% of cards max should be reddit cards
    questions.extend(titles)

    # Get trends from Know Your Meme
    memes = requests.get("http://knowyourmeme.com/").text
    memes = re.findall("<h5 class='left'>Also Trending:</h5>(.+?)</div>", memes)
    memes = re.findall(">(.+?)</a>", memes[0])

    answers.extend([unescape(i) + "." for i in memes])

    ud = requests.get("http://urbandictionary.com/").text
    ud = re.findall(r"define\.php.*?>(.+?)<", ud)[1:]
    ud = [unescape(i) for i in ud]
    ud = [i[0].upper() + i[1:] + ("." * i[-1].isalpha()) for i in ud]
    answers.extend(ud)

    return questions, answers

def cardcast(cardset):
    questions = requests.get("https://api.cardcastgame.com/v1/decks/%s/calls" % cardset).json()
    answers = requests.get("https://api.cardcastgame.com/v1/decks/%s/responses" % cardset).json()
    questions = ["_".join(i["text"]) for i in questions]
    answers = ["_".join(i["text"]) for i in answers]
    deck = requests.get("https://api.cardcastgame.com/v1/decks/%s" % cardset).json()["name"]
    return questions, answers, deck

def find_deck(query):
    res = requests.get("https://api.cardcastgame.com/v1/decks", data={"limit": 1, "search": query, "sort": "rating"}).json()
    return res["results"]["data"][0]["code"]

# Dynamic cards:
# Black: Askreddit, yahoo answers
# White: Random username, google trends, random player, random song, twitter trending

class CardsAgainstHumanity(object):

    def __init__(self, printer, channel, rounds=None, black=[], white=[], rando=False, numcards=10, minplayers=3, bets=True, firstto=None, ranked=False, democracy=False, compact=True, cardset=None):
        self.printer = printer

        self.lock = threading.Lock()

        self.deck = None

        if cardset is not None:
            try:
                self.questions, self.answers, self.deck = cardcast(cardset)
            except:
                self.questions, self.answers = defaultdeck(black, white)
        else:
            self.questions, self.answers = defaultdeck(black, white)

        random.shuffle(self.questions)
        random.shuffle(self.answers)
        
        self.usedanswers = []
        
        self.state = "signups"
        self.channel = channel
        self.rounds = rounds
        self.maxcards = numcards
        self.minplayers = minplayers
        self.bets = not ranked or bets
        self.firstto = firstto
        self.ranked = ranked
        self.democracy = democracy
        self.compact = compact
        
        self.players = []
        self.allplayers = []
        
        self.round = 0
        self.czar = None
        self.question = None
        
        if rando:
            self.addRando()
        else: self.rando = None
        
    @classmethod
    def savecards(cls, directory):
        with open(directory + "/questions.txt", "w") as f: f.write("\n".join(cls.expansionqs))
        with open(directory + "/answers.txt", "w") as f: f.write("\n".join(cls.expansionas))

    @classmethod
    def loadcards(cls, directory):
        try:
            cls.expansionqs = [i.strip() for i in open(directory + "/questions.txt").read().split("\n") if i.strip()]
            cls.expansionas = [i.strip() for i in open(directory + "/answers.txt").read().split("\n") if i.strip()]
        except IOError:
            open(directory + "/questions.txt", "w")
            open(directory + "/answers.txt", "w")
            cls.expansionas, cls.expansionqs = [], []

    def addPlayer(self, player):
        if player in [x.nick for x in self.players]:
            return False
        elif player in [x.nick for x in self.allplayers]:
            p = [i for i in self.allplayers if i.nick == player][0]
        else:
            p = CAHPlayer(player, compact_hand=self.compact)
            self.allplayers.append(p)
            self.repopulate(p)
            self.answers.append(player)
            random.shuffle(self.answers)

        self.players.append(p)
        if self.state == "collect":
            p.getHand()
        return True

    def var(self, v):
        if v == "PLAYER":
            return random.choice(self.players).nick
        elif v == "CZAR": return self.czar.nick

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
            self.rando.setResponses(random.sample(list(range(1, len(self.rando.hand)+1)), self.numcards()))
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
                card = re.sub(r"\$([A-Z]+)", lambda x: self.var(x.group(1)), card)
            except IndexError:
                self.printer.message(CAHPREFIX + "Reshuffling deck...", self.channel)
                self.answers = self.usedanswers[:]
                self.usedanswers = []
                random.shuffle(self.answers)
            else:
                player.hand.append(card)
    
    @staticmethod 
    def subs(x, sub):
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
            return "" + (" ".join(i[0].upper() + i[1:] for i in sub[1:].split(" ")))
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
        self.printer.message(CAHPREFIX + "Scores 15│ " + (" · ".join("%s (%s)"%(i.nick if i != self.czar else "%s"%i.nick, i.score()) for i in sorted(self.players, key=CAHPlayer.score)[::-1])), self.channel)
        
    def chooseprompt(self, rnum, forcenext=False): 
        if self.state == "collect" and self.round == rnum:
            self.printer.message(CAHPREFIX + "Waiting for %s" % (", ".join(i.nick for i in self.players if not (i.responses or i == self.czar))), self.channel)
            if forcenext: threading.Timer(45, self.removeall, args=(rnum,)).start()
            else: threading.Timer(60, self.chooseprompt, args=(rnum,), kwargs={"forcenext":True}).start()
        
    def removeall(self, rnum):
        if self.state == "collect" and self.round == rnum:
            remove = [i for i in self.players if not (i.responses or i == self.czar)]
            self.printer.message(CAHPREFIX + "Removing from the game: %s" % (", ".join(i.nick for i in remove)), self.channel)
            for i in remove:
                self.remove(i)
            self.judge()
        
    def endgame(self):
        if self.state == "failed": return
        self.state = "failed"
        with self.printer.buffer(self.channel) as buffer:
            buffer += "01│00,01 Cards Against Humanity  is over!"
            players = sorted(self.allplayers, key=CAHPlayer.score)[::-1]
            for i, player in enumerate(players):
                if i and players[i-1].score() == player.score():
                    rank = "    "
                else:
                    rank = ordinal(i+1) + (" " if i < 9 else "")
                buffer += CAHPREFIX + "%s 01│ %s - %d point%s" % (rank, player.nick, player.score(), ["", "s"][cmp(1, player.score())])
 
    def isEndGame(self):
        return (not (self.questions) 
                or (self.rounds and self.round >= self.rounds) 
                or len(self.players) < self.minplayers 
                or (self.firstto and any(i.score() >= self.firstto for i in self.players)))
 
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
        time.sleep(0.5)
        self.printer.message(CAHPREFIX + "%s will be the Card Czar for Round %d%s." % (self.czar.nick, self.round, "of %d" % self.rounds if self.rounds else ""), self.channel)
        self.question = self.questions.pop()
        self.question = re.sub(r"\$([A-Z]+)", lambda x: self.var(x.group(1)), self.question)

        time.sleep(2)
        self.printer.message("01│00,01 %s " % re.sub("[*^]_+", "_______", self.question), self.channel)
        numanswers = self.numcards()
        numanswers = "a card" if numanswers == 1 else ("%d cards" % numanswers)

        for player in self.players:
            self.repopulate(player)
            if player == self.rando:
                player.setResponses(random.sample(list(range(1, len(player.hand)+1)), self.numcards()))
            elif player != self.czar:
                self.printer.message(CAHPREFIX + "Please !pick %s." % numanswers, player.nick, "NOTICE")
                player.printHand(self.printer)
            else:
                self.printer.message(CAHPREFIX + "You're the Card Czar! Once all the responses to come in, you can pick the best.", player.nick, "NOTICE")

        threading.Timer(75, self.chooseprompt, args=(self.round,)).start()

    def judge(self):
        if not [i for i in self.players if i.responses is None and i != self.czar] and self.state not in ["judge", "failed"]:
            self.order = [i for i in self.players if i != self.czar] + [i for i in self.players if i.bets and i != self.czar]
            random.shuffle(self.order)
            
            with self.printer.buffer(self.channel) as buffer:
                buffer += CAHPREFIX + "All cards are in. %s, please pick the best %s" % (self.czar.nick, "response." if not self.ranked or len(self.players) < 4 else "%d responses." % min(len(self.players) - 2, 3))
                for i, player in enumerate(self.order):
                    response = player.responses if self.order.index(player) == i else player.bets
                    self.usedanswers.append(response)
                    buffer += CAHPREFIX + "%d. %s" % (i+1, self.substitute(response))
            self.state = "judge"
            # TODO: Add judgement timer

    def logwinner(self, wins, logdir):
        with sqlite3.connect(logdir + "/statistics.db") as logdata:
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

        with self.printer.buffer(self.channel) as buff:
            if self.ranked:
                points = len(number)
                for i, choice in enumerate(number):
                    player = self.order[choice - 1]
                    response = player.popResponses() if self.order.index(player) == choice - 1 else player.popBets()
                    buff += CAHPREFIX + "%s. %s: 00,01 %s " % (ordinal(i+1), player.nick, self.substitute(response))
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
                buff += CAHPREFIX + "%s picked %s's response: 00,01 %s " % (self.czar.nick, winner.nick, self.substitute(winning))
            reveal = []
            for i in self.order:
                response = i.popResponses() or i.popBets()
                if response:
                    reveal.append("%s %s" % (i.nick, " ".join("01,00 %s " % ((i[0].upper() + i[1:]).rstrip(".")) for i in response)))
            output = [[]]
            for i in reveal:
                if sum(len(i) + 2 for i in output) + len(i) < 375:
                    output[-1].append(i)
                else:
                    output.append([i])
            for i in output:
                buff += CAHPREFIX + " · ".join(i)

        self.next()
    
    def remove(self, player):
        self.players.remove(player)
        if self.isEndGame():
            self.endgame()

    
    def start(self):
        if self.state == "signups":
            if len(self.players) < self.minplayers:
                self.state = "failed"
                self.printer.message("01│00,01 Cards Against Humanity  has failed to gather enough interest.", self.channel)
            else:
                self.state = "started"
                deck = ("(%s) " % self.deck) if self.deck is not None else ""
                self.printer.message("01│00,01 Cards Against Humanity %s begins!" % deck, self.channel)
                self.next()
        
    def failed(self): 
        return self.state == "failed"
        
class CAHBot(object):

    instances = []
    
    def __init__(self, server):
        self.instances.append(self)
        self.games = {}
        self.lock = threading.Lock()

        self.config = Config(server.get_config_dir(CONFIG_FILE))

        self.expansiondir = server.get_config_dir("CardsAgainstHumanity")
        if not os.path.exists(self.expansiondir):
            os.makedirs(self.expansiondir, exist_ok=True)
        if not os.path.exists(self.expansiondir + "/statistics.db"):
            # Initialise the db
            with sqlite3.connect(self.expansiondir + "/statistics.db") as db:
                db.execute("CREATE TABLE white (timestamp int, nick text, channel text, round int, czar text, prompt text, cards text, bet int, rank int);")

        CardsAgainstHumanity.loadcards(self.expansiondir)

        server.register("privmsg", self.trigger)
        server.register("privmsg", self.custom_cards)
        server.register("privmsg", self.remove_player)
#        server.register("nick". self.rename)

    @command("remove", "(.+)", admin=True, error="No such player.")
    def remove_player(self, server, message, player):
        game = self.games[message.context]
        player = game.getPlayer(player)
        game.remove(player)
        yield "Removed."
        if game.isEndGame(): game.endgame()
        game.judge()

    @Callback.threadsafe
    def custom_cards(self, server, line):
        printer = server.printer
        msg = Message(line)
        if len(msg.words) < 2 or not server.is_admin(msg.address.hostmask):
            return
        if msg.words[0] == "!Q.":
            data = re.sub("_+", "_______", msg.text.split(" ", 1)[-1])
            with self.lock:
                CardsAgainstHumanity.expansionqs.append(data)
                CardsAgainstHumanity.savecards(self.expansiondir)
            printer.message(CAHPREFIX + "Added: 00,01 %s " % (data), msg.context)
        elif msg.words[0] == "!A.":
            data = msg.text.split(" ", 1)[-1]
            data = data.strip()
            if re.search("[^.?!]$", data): data += "."                
            with self.lock:
                CardsAgainstHumanity.expansionas.append(data)
                CardsAgainstHumanity.savecards(self.expansiondir)
            printer.message(CAHPREFIX + "Added: 01,00 %s " % (data), msg.context)

    @staticmethod
    def gamecmd(funct):
        @functools.wraps(funct)
        def _(self, server, message, *args, **kwargs):
            channel = server.lower(message.context)
            if channel in self.games and not self.games[channel].failed():
                game = self.games[channel]
                with game.lock:
                    return funct(self, server, message, *args, **kwargs)
        return _


    @Callback.threadsafe
    def trigger(self, server, line):
        printer = server.printer
        x = line.split()
        channel = x[2].lower()
        nick = Address(x[0]).nick
        if not channel.startswith("#"):
            return
            
        elif channel in self.games and not self.games[channel].failed():
            game = self.games[channel]
            with game.lock:
                if x[3].lower() == ":!join":
                    if game.addPlayer(nick):
                        printer.message(CAHPREFIX + "%s is our %s player." % (nick, ordinal(len(game.players) - bool(game.rando))), channel)
                        if game.state == "collect":
                            printer.message("01│00,01 %s " % re.sub("[*^]_+", "_______", game.question), nick, "NOTICE")
                            player = game.getPlayer(nick)
                            game.repopulate(player)
                            player.printHand(printer)
                    else:
                        printer.message(CAHPREFIX + "%s is already in the game." % nick, channel)
                elif x[3].lower() == ":!score":
                    game.printplayers()
                elif x[3].lower() == ":!rando":
                    if game.rando:
                        printer.message(CAHPREFIX + "Rando Cardrissian is now out of the game.", channel)
                        game.removeRando()
                    else:
                        printer.message(CAHPREFIX + "Rando Cardrissian is now playing.", channel)
                        game.addRando()
                elif game.state == "signups" and x[3][1:].lower() in ["!start", "!go", "!begin"]:
                    if len(game.players) > 2 and nick in [i.nick for i in game.players]:
                        game.start()
                    elif len(game.players) > 2:
                        printer.message(CAHPREFIX + "I don't care what you think.", channel)
                    else:
                        printer.message(CAHPREFIX + "The game can't begin without at least 3 players.", channel)
                elif nick in [i.nick for i in game.players]:
                    player = game.getPlayer(nick)
                    if x[3].lower() == ":!discard" and player.points:
                        args = " ".join(x[4:])
                        args = args.replace(",", " ")
                        cards = sorted({int(i) for i in args.split() if i.isdigit() and 1 <= int(i) <= len(player.hand)})[::-1]
                        if len(cards) > game.maxcards / 2:
                            printer.message(CAHPREFIX + "You can't discard more than half your hand at once.", nick, "NOTICE")
                        else:
                            for i in cards:
                                game.answers.append(player.hand.pop(i-1))
                            random.shuffle(game.answers)
                            game.repopulate(player)
                            player.points -= 1
                            player.printHand(printer)
                    elif x[3].lower() == ":!hand":
                        game.repopulate(player)
                        player.printHand(printer)
                    elif x[3].lower() in [":!choose", ":!pick"]:
                        if player != game.czar and game.state == "collect":
                            args = line.split(" ", 4)[-1]
                            if "," in args and game.bets:
                                if player.points:
                                    args, bet = args.split(",")
                                    bet = [int(i) for i in bet.strip().split()]
                                else:
                                    printer.message(CAHPREFIX + "Not enough points to bet, sorry.", nick, "NOTICE")
                            else:
                                bet = []
                            args = [int(i) for i in args.split()]
                            if all((bet + args).count(i) == 1 and 1 <= i <= len(player.hand) for i in bet + args) and (len(args) == game.numcards() and len(bet) in [game.numcards(), 0]):
                                player.setResponses(args)
                                player.setBet(bet)
                                printer.message(CAHPREFIX + "00,01 Response 01,00 %s " % game.substitute(player.responses), nick, "NOTICE")
                                if bet:
                                    printer.message(CAHPREFIX + "01,00 Backup   01,00 %s " % game.substitute(player.bets), nick, "NOTICE")
                            else:
                                printer.message(CAHPREFIX + "Invalid arguments.", nick, "NOTICE")
                            if not [i for i in game.players if i.responses is None and i != game.czar]:
                                game.judge()
                        elif player == game.czar and game.state == "judge":
                            if x[4].isdigit() and 1 <= int(x[4]) <= len(game.order) and game.ranked == False:
                                # Logging
                                try:
                                    game.logwinner([int(x[4])-1], self.expansiondir)
                                except sqlite3.ProgrammingError:
                                    sys.stderr.write("sqlite3 error\n")
                                game.pick(int(x[4]))
                            elif len(x[4:]) == min(len(game.players) - 2, 3) and all([str.isdigit and 1 <= int(n) <= len(game.order) and x[4:].count(n) == 1 for n in x[4:]]) and game.ranked == True:
                                # Logging
                                try:
                                    game.logwinner([int(i)-1 for i in x[4:]], self.expansiondir)
                                except sqlite3.ProgrammingError:
                                    sys.stderr.write("sqlite3 error\n")
                                game.pick([int(i) for i in x[4:]])
                            else:
                                printer.message(CAHPREFIX + "Invalid arguments.", nick, "NOTICE")
                                
                    elif x[3].lower() in [":!leave", ":!quit"]:
                        printer.message(CAHPREFIX + "%s is quitting the game, quitter." % player.nick, channel)
                        game.remove(player)
                        if game.state != 'failed':
                            if player == game.czar:
                                game.czar = game.players.pop()
                                game.players.insert(0, game.czar)
                                if game.czar == game.rando:
                                    game.czar = game.players.pop()
                                    game.players.insert(0, game.czar)
                                
                                game.czar.responses = None
                                game.czar.bets = None
                                if game.state == "judge":
                                    game.state = "collect"
                                printer.message(CAHPREFIX + "%s is the new czar." % game.czar.nick, channel)

                            game.judge()
                    elif x[3].lower() == ":!score":
                        game.printplayers()
        elif x[3].lower() in [":!cah", ":!cards"]:
            args = self.parseSettings(line.split(" ", 4)[-1])
            self.games[channel] = CardsAgainstHumanity(printer, channel, **args)
            printer.message("01│00,01 Cards Against Humanity  will begin in a minute. Want to !join us?", channel)
            threading.Timer(150, self.games[channel].start).start()

    @staticmethod
    def parseSettings(args):
        kwargs = {}
        words = args.split()
        rounds, cards, firstto, deck = re.search(r"\b([1-9]\d*) rounds\b", args), re.search(r"\b([5-9]|[1-9]\d+) cards\b", args), re.search(r"\bfirst to ([1-9]\d*)\b", args), re.search("\bwith (#?)(.+)\b", args)

        if  rounds: kwargs["rounds"]  = int(rounds.group(1))
        if   cards: kwargs["numcards"]   = int(cards.group(1))
        if firstto: kwargs["firstto"] = int(firstto.group(1))
        if deck:
            if deck.group(1):
                kwargs["cardset"] = deck.group(2)
            else:
                try:
                    kwargs["cardset"] = find_deck(deck.group(2))
                except:
                    pass
        if "rando"       in words: kwargs["rando"]  = True
        if "ranked"      in words: kwargs["ranked"] = True
        if "betless" not in words: kwargs["bets"]   = False
        if "classic" not in words:
            kwargs["black"] = CardsAgainstHumanity.expansionqs[:]
            kwargs["white"] = CardsAgainstHumanity.expansionas[:]

        return kwargs

    @command("forcecompact", "(on|off)", public=":", private="", admin=True)
    def forcecompact(self, server, message, state):
        self.config["compact"] = state == "on"

__initialise__ = CAHBot

class CAHPlayer(object):
    def __init__(self, nick, compact_hand=False):
        self.nick = nick
        self.hand = []
        self.points = 0
        self.responses = None
        self.bets = None
        self.compact = compact_hand
        
    def rename(self, newname):
        self.nick = newname

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
    
    def printHand(self, printer):
        if self.compact:
            lines = self.get_compact_hand(printer.bot)
        else:
            lines = self.getHand()
        with printer.buffer(self.nick, "NOTICE") as buff:
            for i in lines:
                buff += i

    def getHand(self):
        lines = []
        for i, card in enumerate(self.hand):
            lines.append(CAHPREFIX + "%d. %s" % (i+1, card[0].upper() + card[1:]))
        lines.append(CAHPREFIX + "You have %d point%s." % (self.points, "" if self.points == 1 else "s"))
        return lines

    @staticmethod
    def fmt_card(card):
        card = card[0], (card[1][0].upper() + card[1][1:]).rstrip(".")
        return "00,01 %d 01,00 %s " % card

    def get_compact_hand(self, server):
        # assert len(self.hand) > 1
        lines = [CAHPREFIX + self.fmt_card((1, self.hand[0]))]
        for i, text in enumerate(self.hand[1:]):
            card = i+2, text
            line = lines[-1] + " " + self.fmt_card(card)
            if server.can_send(line, self.nick, "NOTICE"):
                lines[-1] = line
            else:
                lines.append(CAHPREFIX + self.fmt_card(card))
        return lines      
                
class CAHDeck(list):
    pass

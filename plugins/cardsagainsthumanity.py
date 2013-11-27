import threading
import random
import re
import sqlite3
import time
import sys
import os

from util.text import ordinal
from util.irc import Callback, Address


def __initialise__(name, bot, printer):
    datadir = "data/CardsAgainstHumanity"
    expansiondir = bot.get_config_dir("CardsAgainstHumanity")
    if not os.path.exists(expansiondir):
        os.makedirs(expansiondir, exist_ok=True)
    if not os.path.exists(expansiondir + "/statistics.db"):
        # Initialise the db
        with sqlite3.connect(expansiondir + "/statistics.db") as db:
            db.execute("CREATE TABLE white (timestamp int, nick text, channel text, round int, czar text, prompt text, cards text, bet int, rank int);")

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
        black = [i.strip() for i in open(datadir + "/black.txt").read().split("\n")]
        white = [i.strip() for i in open(datadir + "/white.txt").read().split("\n")]

        try:
            expansionqs = [i.strip() for i in open(expansiondir + "/questions.txt").read().split("\n")]
            expansionas = [i.strip() for i in open(expansiondir + "/answers.txt").read().split("\n")]
        except IOError:
            open(expansiondir + "/questions.txt", "w")
            open(expansiondir + "/answers.txt", "w")
            expansionas, expansionqs = [], []

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
                        rank = "    "
                    else:
                        rank = ordinal(i+1) + ":"
                    buffer += "00,01 15,14 01,15  %s %s - %d points" % (rank, player.nick, player.score())
     
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
                    player.setResponses(random.sample(list(range(1, len(player.hand)+1)), self.numcards()))
                elif player != self.czar:
                    printer.message("00,01 15,14 01,15  Please !choose %s." % numanswers, player.nick, "NOTICE")
                    player.printHand()
                else:
                    printer.message("00,01 15,14 01,15  You're the Card Czar! Once all the responses to come in, you can pick the best.", player.nick, "NOTICE")

            threading.Timer(75, self.chooseprompt, args=(self.round,)).start()

        def judge(self):
            if not [i for i in self.players if i.responses is None and i != self.czar] and self.state not in ["judge", "failed"]:
                self.order = [i for i in self.players if i != self.czar] + [i for i in self.players if i.bets and i != self.czar]
                random.shuffle(self.order)
                
                with printer.buffer(self.channel) as buffer:
                    buffer += "00,01 15,14 01,15  All cards are in. %s, please pick the best %s" % (self.czar.nick, "response." if not self.ranked or len(self.players) < 4 else "%d responses." % min(len(self.players) - 2, 3))
                    for i, player in enumerate(self.order):
                        response = player.responses if self.order.index(player) == i else player.bets
                        buffer += "00,01 15,14 01,15  %d. %s" % (i+1, self.substitute(response))
                self.state = "judge"

        def logwinner(self, wins):
            with sqlite3.connect(expansiondir + "/statistics.db") as logdata:
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
        with open(expansiondir + "/questions.txt", "w") as f: f.write("\n".join(CardsAgainstHumanity.expansionqs))
        with open(expansiondir + "/answers.txt", "w") as f: f.write("\n".join(CardsAgainstHumanity.expansionas))

    def loadcards():
        CardsAgainstHumanity.expansionqs = [i.strip() for i in open(expansiondir + "/questions.txt").read().split("\n")]
        CardsAgainstHumanity.expansionas = [i.strip() for i in open(expansiondir + "/answers.txt").read().split("\n")]
        
    class CAHBot(object):
        games = {}
        lock = threading.Lock()
        
        @Callback.threadsafe
        def trigger(self, sdata):
            x = sdata.split()
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
                        savecards()
                    printer.message("00,01 15,14 01,15  Added: 00,01 %s " % (data), channel)
                else:
                    data = " ".join(x[4:])
                    data = data.strip()
                    if re.search("[^.?!]$", data): data += "."                
                    with self.lock:
                        CardsAgainstHumanity.expansionas.append(data)
                        savecards()
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
                        if len(game.players) > 2 and nick in [i.nick for i in game.players]:
                            game.start()
                        elif len(game.players) > 2:
                            printer.message("00,01 15,14 01,15  I don't care what you think.", channel)
                        else:
                            printer.message("00,01 15,14 01,15  The game can't begin without at least 3 players.", channel)
                    elif nick in [i.nick for i in game.players]:
                        player = game.getPlayer(nick)
                        if x[3].lower() == ":!discard" and player.points:
                            args = " ".join(x[4:])
                            args = args.replace(",", " ")
                            cards = sorted(list(set(map(int, list(filter(str.isdigit and 1 <= int(x) <= len(player.hand), args.split()))))))[::-1]
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
                                elif len(x[4:]) == min(len(game.players) - 2, 3) and all([str.isdigit and 1 <= int(n) <= len(game.order) and x[4:].count(n) == 1 for n in x[4:]]) and game.ranked == True:
                                    game.pick([int(i) for i in x[4:]])
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
    bot.register("privmsg", cah.trigger)

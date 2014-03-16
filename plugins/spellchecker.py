import sys
import os
import math
import re
import sqlite3
import time
from util.text import ircstrip, strikethrough
from util.irc import Address, Message, command
from bot.events import Callback
try:
    import enchant
except ImportError:
    print("Enchant dependancy found, spellchecker not loaded.", file=sys.stderr)
else:
    class SpellChecker(Callback):
        DBFILE = "spellchecker.db"
        LOCKFILE = "ircwords_locked"
        users = {}
        reset_at = 1500
        reset_to = int(round(math.log(reset_at)))
        last = None
        last_correction = None
        threshhold = 2

        wordsep = "/.:^&*|+=-?,_()\""

        literalprefixes = ".!/@<`:~=+>"
        dataprefixes = list("#$<[/") + ["r/", "u/", "http://"]
        contractions = ["s", "d", "ve", "nt", "m"]
        prefixes = ["un", "de"]
        suffixes = ["ness", "ed", "s", "er", "y", "ey", "dom", "ism", "ship", "ment", "ity", "ify", "ful", "ish", "ess", "ize", "ise"]

        def __init__(self, server):
            self.name = server.name
            self.server = server

            os.makedirs(server.get_config_dir(), exist_ok=True)
            self.dictionary = enchant.DictWithPWL("en_US", 
                                             pwl=server.get_config_dir("ircwords"))
            self.alternate = enchant.Dict("en_GB")

            try:
                self.locked = open(server.get_config_dir(self.LOCKFILE)).read().split("\n")
            except:
                self.locked = []
                open(server.get_config_dir(self.LOCKFILE), "w")

            self.db = server.get_config_dir(self.DBFILE)
            if not os.path.exists(self.db):
                os.makedirs(server.get_config_dir(), exist_ok=True)
                # Initialise the db
                with sqlite3.connect(self.db) as db:
                    db.execute("CREATE TABLE typos (timestamp int, nick text, channel text, server text, word text);")
                    db.execute("CREATE TABLE settings (server text, context text, threshhold int);")

            self.dictionary._add = self.dictionary.add
            self.dictionary.add = lambda x: self.dictionary._add(x) if "\n" not in x else sys.__stdout__.write("fuck you.")

            server.spellcheck = self.spellcheck
            super().__init__(server)

        def getSettings(self, context):
            with sqlite3.connect(self.db) as db:
                c = db.cursor()
                c.execute("SELECT threshhold FROM settings WHERE server=? AND context=?", (self.name, self.server.lower(context)))
                result = c.fetchone()
                return result if result is None else result[0]

        def setThreshhold(self, context, threshhold):
            with sqlite3.connect(self.db) as db:
                db.execute("DELETE FROM settings WHERE server=? AND context=?", (self.name, self.server.lower(context)))
                if threshhold is not None:
                    db.execute("INSERT INTO settings VALUES (?, ?, ?)", (self.name, self.server.lower(context), threshhold))

        @classmethod
        def stripContractions(cls, word):
            if word[0] == word[-1] and word[0] in "'\"":
                word = word[1:-1]
            last = word.rsplit("'", 1)[-1].lower()
            return word[:-len(last) - 1] if last in cls.contractions else word

        @classmethod
        def isWord(cls, word):
            # excessively non-alpha strings are not words.
            if len([i for i in word if not (i.isalpha() or i in "'")]) >= cls.threshhold:
                return False

            # words prefixed with the following are not real words
            if any(word.startswith(i) for i in cls.dataprefixes):
                return False

            # words with unicode in them are not words
            if any(ord(c) > 127 for c in word):
                return False

            # words with dots in them are hostnames
            if "." in word.strip("."):
                return False

            return True

        @classmethod
        def isLiteral(cls, sentence):
            return any(sentence.startswith(i) for i in cls.literalprefixes)

        def spellcheck(self, sentence):
            sentence = ircstrip(sentence)
            if self.isLiteral(sentence): return
            words = set(sentence.split())

            sentence = [self.stripContractions(i) for i in words if self.isWord(i)]
            errors = [i for i in sentence if not (self.dictionary.check(i) or self.alternate.check(i))]
            suggestions = [set(self.alternate.suggest(i)) | set(self.dictionary.suggest(i)) for i in errors]
            # reduce the suggestions
            suggestions = [{"".join(z for z in i if z.isalpha() or z in "'").lower() for i in x} for x in suggestions]
            wrong = []
            append = {}
            for i, word in enumerate(errors):
                suffixless = {i.rstrip(suffix) for suffix in self.suffixes} - {word}
                if any(self.spellcheck(i) for i in suffixless):
                    continue
                elif "".join(i for i in word if i.isalpha()).lower() not in suggestions[i]:
                
                    token = set(word) & set(self.wordsep)
                    if token:
                        token = token.pop()
                        words = word.split(token)
                        suggested = [self.spellcheck(i) for i in words]
                        suggested = [list(i.values())[0] if i else None for i in suggested]
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
                        suggestions[i] |= set(self.alternate.suggest(truncated) 
                                              + self.dictionary.suggest(truncated) 
                                              + self.alternate.suggest(truncated2) 
                                              + self.dictionary.suggest(truncated2))
                        if not any(re.match(pattern, x) for x in suggestions[i]):
                            wrong.append(word)

            if wrong or append: 
                wrong = {i: self.alternate.suggest(i) for i in wrong}
                wrong.update(append)
                # wrong = {k: [i for i in v if difflib.SequenceMatcher(None, k, i).quick_ratio() > 0.6] for k, v in wrong.items()}
                return wrong # Give a dictionary of words : [suggestions]
        
        @Callback.background
        def passiveCorrector(self, server, line) -> "privmsg":
            msg = Message(line)
            nick = msg.address.nick
            if not self.dictionary.check(nick):
                self.dictionary.add(nick)
            nick = server.lower(nick)
            if msg.text and msg.text[0] in "@!.:`~/": 
                return
            if msg.text.startswith("\x01ACTION") and msg.text.endswith("\x01"):
                data = self.spellcheck(msg.text[8:-1])
            else:
                data = self.spellcheck(msg.text)

            user = self.users.setdefault(nick, [0, 0])
            user[0] += len(data) if data else 0
            user[1] += len(line.split(" ")) - 3
            if user[1] > self.reset_at:
                user[0] /= self.reset_to
                user[1] /= self.reset_to

            if data:
                with sqlite3.connect(self.db) as typos:
                    for i in data:
                        typos.execute("INSERT INTO typos VALUES (?, ?, ?, ?, ?)", (time.time(), nick, msg.context, self.name, i))

                threshhold_context = self.getSettings(msg.context)
                threshhold_user = self.getSettings(nick)
                if threshhold_user == threshhold_context == None:
                    return
                
                threshhold = min(threshhold_context, threshhold_user, key=lambda x: float("inf") if x is None else x)

                if user[1] and 1000*user[0]/user[1] > threshhold:
                    sentence_substitute = ircstrip(msg.text)
                    if sentence_substitute.startswith("\x01ACTION") and sentence_substitute.endswith("\x01"):
                        sentence_substitute = "%s %s" % (msg.address.nick, sentence_substitute[8:-1])
                    for word, sub in data.items():
                        sentence_substitute = sentence_substitute.replace(word, "\x02%s\x02" % sub[0] if sub else strikethrough(word))
                    server.message(("%s: " % msg.address.nick) + sentence_substitute, msg.context)
                    if len(data) == 1:
                        self.last = list(data.keys())[0]
                    else:
                        self.last = None
                
        @Callback.threadsafe
        @command("spell spellcheck".split(), "(.+)")
        def activeCorrector(self, server, msg, query):
            if (self.dictionary.check(query) or self.alternate.check(query)):
                return "%s, %s is spelt correctly." % (msg.address.nick, query)
            else:
                suggestions = self.alternate.suggest(query)[:6]
                return "Suggestions: %s" % ("/".join(suggestions))
        
        def updateKnown(self, server, y) -> "privmsg":
            x = y.split(" ")
            newword = re.match(r":(%s[^\a]?\s*)?([^\s]+)( i|')s a( real)? word(!| FORCE| LOCK)?.*" % server.nick, " ".join(x[3:]), flags=re.IGNORECASE)
            notword = re.match(r":(%s[^\a]?\s*)?([^\s]+)( isn't| is not|'s not) a( real)? word(!| FORCE| LOCK)?.*" % server.nick, " ".join(x[3:]), flags=re.IGNORECASE)
            match = newword or notword
            if not match: return

            if not server.is_admin(x[0]) and match.group(2).lower() in self.locked:
                server.message("FUCK OFF.", x[2] if x[2][0] == "#" else Address(x[0]).nick) 
                return

            if newword:
                word = newword.group(2)
                if word.lower() == "that":
                    word = self.last
                if server.is_admin(x[0]) and newword.group(5):
                    self.locked.append(word.lower())
                    self.saveLocked()
                if not word:
                    server.message("What is?", x[2] if x[2][0] == "#" else Address(x[0]).nick)
                elif self.dictionary.check(word):
                    server.message("I KNOW.", x[2] if x[2][0] == "#" else Address(x[0]).nick)
                else:
                    self.dictionary.add(word)
                    server.message("Oh, sorry, I'll remember that.", x[2] if x[2][0] == "#" else Address(x[0]).nick)
                    self.last_correction = word
            if notword:
                word = notword.group(2)
                if word.lower() == "that":
                    word = self.last_correction
                if server.is_admin(x[0]) and notword.group(5):
                    self.locked.append(word.lower())
                    self.saveLocked()
                if self.dictionary.is_added(word):
                    self.dictionary.remove(word)
                    server.message("Okay then.", x[2] if x[2][0] == "#" else Address(x[0]).nick) 
                else:
                    server.message("I DON'T CARE.", x[2] if x[2][0] == "#" else Address(x[0]).nick)
        
        def saveLocked(self):
            with open(self.server.get_config_dir(self.LOCKFILE), "w") as f:
                f.write("\n".join(self.locked))


        @command("spellchecker", "(on|off|\d+)", public=":", private=".")
        def correctChannel(self, server, msg, threshhold):
            context = {".": msg.address.nick, ":": msg.context}[msg.prefix]
            if threshhold == "off":
                if self.getSettings(context) is not None:
                    self.setThreshhold(context, None)
                    return "FINE."
                else:
                    return "IT'S OFF DICKBUTT"
            else:
                query = int(threshhold) if threshhold.isdigit() else 0
                self.setThreshhold(context, query)
                return "DONE."


    __initialise__ = SpellChecker
    # TODO: Reintegrate spellchecker callbacks that update the nicklist.

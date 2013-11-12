import sys
import os
import math
import re
import sqlite3
import time
from util.text import ircstrip, strikethrough
from util.irc import Address, Message, Callback
try:
    import enchant
except ImportError:
    print("Enchant dependancy found, spellchecker not loaded.", file=sys.stderr)
    raise

def __initialise__(name, server, printer):
    cb = Callback()
    cb.initialise(name, server, printer)
    class SpellChecker(object):
        DBFILE = "spellchecker.db"
        users = {}
        os.makedirs(server.get_config_dir(), exist_ok=True)
        dictionary = enchant.DictWithPWL("en_US", 
                                         pwl=server.get_config_dir("ircwords"))
        alternate = enchant.Dict("en_GB")
        threshhold = 2
        reset_at = 1500
        reset_to = int(round(math.log(reset_at)))
        last = None
        last_correction = None
        wordsep = "/.:^&*|+=-?,_"

        literalprefixes = ".!/@<`~"
        dataprefixes = "#$<[/"
        contractions = ["s", "d", "ve", "nt", "m"]

        def __init__(self):
            self.db = server.get_config_dir(self.DBFILE)
            if not os.path.exists(self.db):
                os.makedirs(server.get_config_dir(), exist_ok=True)
                # Initialise the db
                with sqlite3.connect(self.db) as db:
                    db.execute("CREATE TABLE typos (timestamp int, nick text, channel text, server text, word text);")
                    db.execute("CREATE TABLE settings (server text, context text, threshhold int);")

        def getSettings(self, context):
            with sqlite3.connect(self.db) as db:
                c = db.cursor()
                c.execute("SELECT threshhold FROM settings WHERE server=? AND context=?", (name, server.lower(context)))
                result = c.fetchone()
                return result if result is None else result[0]

        def setThreshhold(self, context, threshhold):
            with sqlite3.connect(self.db) as db:
                db.execute("DELETE FROM settings WHERE server=? AND context=?", (name, server.lower(context)))
                if threshhold is not None:
                    db.execute("INSERT INTO settings VALUES (?, ?, ?)", (name, server.lower(context), threshhold))

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
            if word[0] in cls.dataprefixes:
                return False

            # words with unicode in them are not words
            if any(ord(c) > 127 for c in word):
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
            suggestions = [{"".join(z for z in i if z.isalpha() or z in "'").lower() for i in x} for x in suggestions]
            wrong = []
            append = {}
            for i, word in enumerate(errors):
                if "".join(i for i in word if i.isalpha()).lower() not in suggestions[i]:
                
                    token = set(word) & set(cls.wordsep)
                    if token:
                        token = token.pop()
                        words = word.split(token)
                        suggested = [cls.spellcheck(i) for i in words]
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
                        suggestions[i] |= set(cls.alternate.suggest(truncated)) | set(cls.dictionary.suggest(truncated)) | set(cls.alternate.suggest(truncated2)) | set(cls.dictionary.suggest(truncated2))
                        if not any(re.match(pattern, x) for x in suggestions[i]):
                            wrong.append(word)

            if wrong or append: 
                wrong = {i: cls.alternate.suggest(i) for i in wrong}
                wrong.update(append)
                return wrong # Give a dictionary of words : [suggestions]
        
        @Callback.background
        def passiveCorrector(self, line):
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
                        typos.execute("INSERT INTO typos VALUES (?, ?, ?, ?, ?)", (time.time(), nick, msg.context, name, i))

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
                    printer.message(("%s: " % msg.address.nick) + sentence_substitute, msg.context)
                    if len(data) == 1:
                        self.last = list(data.keys())[0]
                    else:
                        self.last = None
                
        @Callback.threadsafe
        @cb.command("spell spellcheck".split(), "(.+)")
        def activeCorrector(self, msg, query):
            if (self.dictionary.check(query) or self.alternate.check(query)):
                return "%s, %s is spelt correctly." % (msg.address.nick, query)
            else:
                suggestions = self.alternate.suggest(query)[:6]
                return "Possible correct spellings: %s" % ("/".join(suggestions))
        
        def updateKnown(self, y):
            x = y.split(" ")
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
                    self.last_correction = word
            if notword:
                word = notword.group(2)
                if word.lower() == "that":
                    word = self.last_correction
                if self.dictionary.is_added(word):
                    self.dictionary.remove(word)
                    printer.message("Okay then.", x[2] if x[2][0] == "#" else Address(x[0]).nick) 
                else:
                    printer.message("I DON'T CARE.", x[2] if x[2][0] == "#" else Address(x[0]).nick)
        
        @cb.command("spellchecker", "(on|off|\d+)")
        def correctChannel(self, msg, threshhold):
            if threshhold == "off":
                if self.getSettings(msg.context) is not None:
                    self.setThreshhold(msg.context, None)
                    return "FINE."
                else:
                    return "IT'S OFF DICKBUTT"
            else:
                query = int(threshhold) if threshhold.isdigit() else 0
                self.setThreshhold(msg.context, query)
                return "DONE."


    spellchecker = SpellChecker()
    spellchecker.dictionary._add = spellchecker.dictionary.add
    spellchecker.dictionary.add = lambda x: spellchecker.dictionary._add(x) if "\n" not in x else sys.__stdout__.write("fuck you.")
    server.register("privmsg", spellchecker.correctChannel)
    server.register("privmsg", spellchecker.updateKnown)
    server.register("privmsg", spellchecker.activeCorrector)
    server.register("privmsg", spellchecker.passiveCorrector)
    # TODO: Reintegrate spellchecker callbacks that update the nicklist.

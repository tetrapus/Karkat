import sys
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
else:
    def __initialise__(name, server, printer):
        # Callback = Callback.initialise(name, bot, printer)
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
            contractions = ["s", "d", "ve", "nt", "m"]
            delrioisms = ["dong", "lix", "saq", "dix"]

            @classmethod
            def stripContractions(cls, word):
                if word[0] == word[-1] and word[0] in "'\"":
                    word = word[1:-1]
                last = word.rsplit("'", 1)[-1].lower()
                return word[:-len(last) - 1] if last in cls.contractions else word

            @classmethod
            def isWord(cls, word):
                # delrioisms are not words.
                for i in cls.delrioisms:
                    if i in word.lower():
                        return False

                # excessively non-alpha strings are not words.
                if len([i for i in word if not (i.isalpha() or i in "'")]) >= cls.threshhold:
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
                x = line.split(" ")
                nick = Address(x[0]).nick
                if not self.dictionary.check(nick):
                    self.dictionary.add(nick)
                nick = nick.lower()
                if len(x[3]) > 1 and x[3][1] in "@!.:`~/": return
                target = x[2]
                if target[0] != "#": 
                    target = Address(x[0]).nick
                data = self.spellcheck(Message(line).text)
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
                    sentence_substitute = ircstrip(Message(line).text)
                    for word, sub in data.items():
                        sentence_substitute = sentence_substitute.replace(word, "\x02%s\x02" % sub[0] if sub else strikethrough(word))
                    printer.message(("%s: " % Address(x[0]).nick) + sentence_substitute, target)
                    if len(data) == 1:
                        self.last = list(data.keys())[0]
                    else:
                        self.last = None
                    
            @Callback.threadsafe
            def activeCorrector(self, y):
                x = y.split(" ")
                if len(x) > 4 and len(x[3]) > 2 and x[3][1:].lower() == "!spell":
                    nick, msgtype = (Message(y).context, "PRIVMSG")
                    
                    query = x[4]
                    
                    if (self.dictionary.check(query) or self.alternate.check(query)):
                        printer.message("%s, that seems to be spelt correctly." % Address(x[0]).nick, nick, msgtype)
                    else:
                        suggestions = self.alternate.suggest(query)[:6]
                        printer.message("Possible correct spellings: %s" % ("/".join(suggestions)), nick, msgtype)
            
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
                if notword:
                    word = notword.group(2)
                    if self.dictionary.is_added(word):
                        self.dictionary.remove(word)
                        printer.message("Okay then.", x[2] if x[2][0] == "#" else Address(x[0]).nick) 
                    else:
                        printer.message("I DON'T CARE.", x[2] if x[2][0] == "#" else Address(x[0]).nick)
                        
            def correctChannel(self, y):
                x = y.split(" ")
                if len(x) == 5 and x[3].lower().startswith(":!spellcheck") and (x[4].lower() in ["on", "off"] or x[4].isdigit()):
                    nick, msgtype = (Message(y).context, "PRIVMSG")
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
        server.register("privmsg", spellchecker.correctChannel)
        server.register("privmsg", spellchecker.updateKnown)
        server.register("privmsg", spellchecker.activeCorrector)
        server.register("privmsg", spellchecker.passiveCorrector)
        # TODO: Reintegrate spellchecker callbacks that update the nicklist.
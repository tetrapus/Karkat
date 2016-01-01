import re, random
import threading, time

from bot.events import command, Callback
from util.irc import Message
from util.text import generate_vulgarity


class Stopwords(Callback):
    def __init__(self, server):
        self.stopwords = []

        super().__init__(server)

    def privileged(funct):
        def _(self, server, msg, *args, **kwargs):
            if "#lgbteam" not in server.channels:
                server.message("UNBAN #lgbteam", "ChanServ")
                server.sendline("JOIN #lgbteam")
                return "Internal consistency error, restarting core services. Please try again after the tone."
            if not server.eq(msg.context, "#lgbteens"):
                return
            user = msg.address
            if user.nick not in server.channels["#lgbteam"]:
                return "This is a privileged command. Please check your privilege and report any discrepancies to Lion."
            return funct(self, server, msg, *args, **kwargs)
        return _

    @command("stopword", "(.*)", prefixes=("", "."))
    @privileged
    def stopword(self, server, msg, stopword):
        if not stopword:
            server.message(", ".join(self.stopwords), user.nick, "NOTICE")
            return
        if stopword.isalnum():
            stopword = r"\b%s\b" % stopword
        self.stopwords.append(stopword)
        server.message("%s set stopword %r" % (user.nick, stopword), "#lgbteam")
        return "Alright, next %s to say %s gets banned." % (generate_vulgarity().lower(), stopword)

    @command("unstopword", "(.+)", prefixes=("", "."))
    @privileged
    def unstopword(self, server, msg, stopword):
        if stopword.isalnum():
            stopword = r"\b%s\b" % stopword
        if stopword in self.stopwords:
            self.stopwords.remove(stopword)
            server.message("%s removed stopword %r" % (user.nick, stopword), "#lgbteam")
            return "Removed stopword %r" % stopword
        else:
            return "Stopword not found."


    def monitor(self, server, line) -> "privmsg":
        msg = Message(line)
        user = msg.address
        if not server.eq(msg.context, "#lgbteens"):
            return
        if "#lgbteam" in server.channels and user.nick in server.channels["#lgbteam"]:
            return

        for i in self.stopwords:
            if re.search(i, msg.text, flags=re.IGNORECASE):
                server.printer.send("MODE #lgbteens +b *!*@%s" % user.mask)
                server.printer.send("KICK #lgbteens %s :%s" % (user.nick, random.choice(["THAT'S NUMBERWANG", "SAY THAT AGAIN BITCH", "WHAT", "AW YEAH", "JACKPOT!!!", "DID I FUCKING STUTTER", generate_vulgarity()])))
                thread = threading.Thread(target=lambda x:[time.sleep(10),
                                                           server.printer.send(x)], 
                                          args=("MODE #lgbteens -b *!*@%s" % user.mask,))
                thread.start()
                self.stopwords.remove(i)
                server.message("%s triggered stopword %r" % (user.nick, i), "#lgbteam")
                break

__initialise__ = Stopwords
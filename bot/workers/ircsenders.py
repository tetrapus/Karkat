""" Controls and linearises messages sent to IRC. """
import json
import time
import sys
import re
import random

from util.text import lineify, ircstrip
from util.irc import Address

from .worker import Worker


class PrinterBuffer(object):
    """
    Context manager for prettier printing.
    """
    # TODO: Move me
    # TODO: Refactor adpool into separate module
    try:
        adpool = json.load(open("ads.json"))
    except OSError:
        adpool = []
    lastad = 0

    def __init__(self, printer, recipient, method):
        """
        Obj is an object that supports the message method.
        """
        self.buffer = []
        self.recipient = recipient
        self.method = method
        self.sender = printer

    def __enter__(self):
        return self

    def add(self, line):
        """
        Add a line to the output.
        """
        self.buffer.append(line)

    def __iadd__(self, line):
        self.buffer.append(line)
        return self

    def __exit__(self, cls, value, traceback):
        if self.buffer:
            self.sender.message("\n".join(self.buffer),
                                self.recipient,
                                self.method)
            self.serve_ad()
            self.buffer = []

    def serve_ad(self):
        """ Serve an ad with the message. """
        if (
                len(self.__class__.adpool) and
                (time.time() - self.__class__.lastad >
                 151200 / len(self.__class__.adpool)) and
                random.random() > 0.8
        ):
            advert = self.__class__.adpool.pop()
            self.sender.message(
                "│ SPONSORED │ %s" % advert, self.recipient, self.method
            )
            with open("ads.json", "w") as ad_file:
                json.dump(self.__class__.adpool, ad_file)
            self.__class__.lastad = time.time()


class IRCSender(Worker):
    """ This queue-like thread controls the output to a socket."""

    QUIET = 0
    QUEUE_STATE = 1
    FULL_MESSAGE = 2
    TYPE_ONLY = 4

    def __init__(self, connection):
        super().__init__()
        self.bot = connection
        self.verbosity = self.TYPE_ONLY | self.QUEUE_STATE
        self.servername = connection.server[0]
        self.history = {}
        self.callbacks = []
        if hasattr(connection, "lower"):
            self.lower = connection.lower
        else:
            self.lower = str.lower

    def send(self, message):
        """
        Send data through the underlying socket.
        """
        self.bot.sendline(message)

    @staticmethod
    def pack(msg, recipient, method):
        """
        Return the IRC command for a targetted message.
        """
        return "%s %s :%s" % (method, recipient, msg)

    def can_send(self, msg, recipient, method):
        """
        Returns true if the message can probably be sent without
        truncation.
        """
        return self.bot.can_send(msg, recipient, method)

    def message(self, mesg, recipient, method="PRIVMSG"):
        """
        Send a message.
        """
        msg = lineify(str(mesg))
        self.history[self.lower(recipient)] = msg
        for message in [i for i in msg if i]:
            self.put(self.pack(message, recipient, method))
        return mesg  # Debugging

    def raw_message(self, mesg):
        self.work.put(mesg)

    def log(self, data):
        if self.verbosity != self.QUIET:
            # TODO: Turn this into an event callback.
            if self.verbosity & (self.FULL_MESSAGE | self.TYPE_ONLY):
                if self.verbosity & self.TYPE_ONLY:
                    output = data.split()[0]
                else:
                    output = ircstrip(data)
                sys.stdout.write("%s ← %s" % (self.servername, output))
            if self.work.qsize() and self.verbosity & self.QUEUE_STATE:
                sys.stdout.write(" ⬩ %d messages queued." % self.work.qsize())
            print()

    def process(self, data):
        try:
            self.send(data)
        except BaseException:
            print("Printer could not send: %r\n" % data, file=sys.stderr)
            sys.excepthook(*sys.exc_info())
        else:
            self.log(data)

    def buffer(self, recipient, method="PRIVMSG"):
        """
        Create a context manager with the given target and method bound to
        the current printer object.
        """
        return PrinterBuffer(self, recipient, method)

    def respond(self, line, method="PRIVMSG"):
        """
        Create a context manager which parses the input words and responds
        in PM if messaged, else in the channel.
        """
        if line[2].startswith("#"):
            target = line[2]
        else:
            target = Address(line[0]).nick
        return PrinterBuffer(self, target, method)


class ColourPrinter(IRCSender):
    """
    Add a default colour to messages.
    """
    def __init__(self, sock):
        super().__init__(sock)
        self.color = "14"
        self.hasink = True

    def defaultcolor(self, data):
        """
        Parse a message and colour it in.
        """
        value = []
        color = self.color
        for line in data.rstrip().split("\n"):
            if " " in line and line[0] + line[-1] == "\x01\x01":
                value.append(
                    "%s %s" % (
                        line.split(" ")[0],
                        self.defaultcolor(line.split(" ", 1)[-1])
                    )
                )
            else:
                line = re.sub(
                    r"\x03([^\d])",
                    lambda x: (("\x03%s" % (color)) + (x.group(1) or "")),
                    line
                )
                line = line.replace("\x0f", "\x0f\x03%s" % (color))
                line = line.replace(
                    "\x0f\x03%s\x0f\x03%s" % (color, color),
                    "\x0f"
                )
                value.append("\x03%s%s" % (color, line))
        return "\n".join(value)  # TODO: Minify.

    def pack(self, msg, recipient, method):
        msg = str(msg)
        if method.upper() in ["PRIVMSG", "NOTICE"] and self.hasink:
            msg = super().pack(self.defaultcolor(msg), recipient, method)
        else:
            msg = super().pack(msg, recipient, method)

        return msg


class MultiPrinter(ColourPrinter):
    def __init__(self, bot):
        super().__init__(bot)
        self.bots = [bot]
        self.outmap = {}

    def send(self, message):
        words = message.split(" ", 2)
        if (
                words[0].lower() not in ["notice", "privmsg"] or
                len(words) != 3 or
                words[1].startswith("#") or len(self.bots) == 1
        ):
            bot = 0
        elif words[1] in self.outmap:
            bot = self.outmap[words[1]]
        else:
            bot = min(
                range(len(self.bots)),
                key=lambda x: list(self.outmap.values()).count(x)
            )
            self.outmap[words[1]] = bot
        sys.stdout.write("[%d] " % bot)
        self.bots[bot].sendline(message)

    def add(self, bot):
        self.bots.append(bot)

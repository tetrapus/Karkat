""" This module contains the worker threads for Karkat's system. """

import os
import sys
import threading
import time
import queue
import re
import collections
import socket
import inspect
import fnmatch
import random
import json
import ssl

import yaml

import util
from util.irc import Address, Callback
from util.text import lineify, TimerBuffer, Buffer, ircstrip


class Work(queue.Queue):
    """
    This object is an iterable work queue.
    """

    class TERM(object):
        """
        The sentinel which represents a request to terminate the iterator.

        To use this object, append it to the queue.
        """
        def __init__(self):
            raise TypeError("TERM is a singleton!")

    def __init__(self):
        """
        Create a new Work Queue.
        """

        self._lock = threading.Lock()
        self.last = None
        queue.Queue.__init__(self)

    def __iter__(self):
        """
        The object itself is iterable. Returns self.
        """
        return self

    def __next__(self):
        """
        Tells the queue a task is done and deques a new one.
        """
        with self._lock:
            try:
                self.task_done()
            except ValueError:
                # This means first iteration. We don't really care.
                pass
            value = self.get()
            if value == Work.TERM:
                self.task_done()
                raise StopIteration
            else:
                self.last = value
                return value


class WorkerThread(threading.Thread, object):
    """
    A thread which feeds tasks off of a queue.
    """

    def __init__(self, work=None):
        threading.Thread.__init__(self)
        self.work = work or Work()

    def terminate(self):
        """
        Send a terminate signal to the thread, which tells the thread to exit
        after processing all previously queued work.
        """
        self.work.put(Work.TERM)


class PrinterBuffer(object):
    """
    Context manager for prettier printing.
    """
    try:
        adpool = json.load(open("ads.json"))
    except:
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

    def serve_ad(self):
        if len(self.__class__.adpool) and time.time() - self.__class__.lastad > 151200/len(self.__class__.adpool) and random.random() > 0.8:
            ad = self.__class__.adpool.pop()
            self.sender.message("│ SPONSORED │ %s" % ad, self.recipient, self.method)
            with open("ads.json", "w") as f:
                json.dump(self.__class__.adpool, f)
            self.__class__.lastad = time.time()

class Printer(WorkerThread):
    """ This queue-like thread controls the output to a socket."""

    QUIET = 0
    QUEUE_STATE = 1
    FULL_MESSAGE = 2
    TYPE_ONLY = 4

    def __init__(self, connection):
        WorkerThread.__init__(self)
        self.flush = False
        self.bot = connection
        self.verbosity = self.TYPE_ONLY | self.QUEUE_STATE
        self.servername = connection.server[0]
        self.history = {}
        if hasattr(connection, "lower"):
            self.lower = connection.lower
        else:
            self.lower = str.lower

    def send(self, message):
        """
        Send data through the underlying socket.
        """
        self.bot.sendline(message)

    def clear(self):
        """
        Tell the thread to remove rather than process all the queued data.
        """
        self.flush = True

    def message(self, mesg, recipient, method="PRIVMSG"):
        """
        Send a message.
        """
        msg = lineify(str(mesg))
        self.history[self.lower(recipient)] = msg
        for message in [i for i in msg if i]:
            self.work.put("%s %s :%s" % (method, recipient, message))
        return mesg # Debugging

    def raw_message(self, mesg):
        self.work.put(mesg)

    def log(self, data):
        if self.verbosity != self.QUIET:
            #TODO: Turn this into an event callback.
            if self.verbosity & (self.FULL_MESSAGE | self.TYPE_ONLY):
                if self.verbosity & self.TYPE_ONLY:
                    output = data.split()[0]
                else:
                    output = ircstrip(data)
                sys.stdout.write("%s ← %s" % (self.servername, output))
            if self.work.qsize() and self.verbosity & self.QUEUE_STATE:
                sys.stdout.write(" ⬩ %d messages queued." % self.work.qsize())
            print()

    def run(self):
        while True:
            for data in self.work:
                if not self.flush:
                    try:
                        self.send(data)
                    except BaseException:
                        print("Printer could not send: %r\n" % data, file=sys.stderr)
                        sys.excepthook(*sys.exc_info())
                    else:
                        self.log(data)
                else:
                    self.flush = False
                    self.work = Work()
                    break
            else:
                break

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


class ColourPrinter(Printer):
    """
    Add a default colour to messages.
    """
    def __init__(self, sock):
        Printer.__init__(self, sock)
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
                value.append("%s %s" % (line.split(" ")[0],
                                        self.defaultcolor(line.split(" ", 1)[-1])))
            else:
                line = re.sub("\x03([^\d])",
                              lambda x: (("\x03%s" % (color)) + (x.group(1) or "")),
                              line)
                line = line.replace("\x0f", "\x0f\x03%s" % (color))
                value.append("\x03%s%s" % (color, line))
        return ("\n".join(value)) # TODO: Minify.

    def message(self, msg, recipient=None, method="PRIVMSG"):
        msg = str(msg)
        if method.upper() in ["PRIVMSG", "NOTICE"] and self.hasink:
            super().message(self.defaultcolor(msg), recipient, method)
        else:
            super().message(msg, recipient, method)

        return msg


class MultiPrinter(ColourPrinter):
    def __init__(self, bot):
        super().__init__(bot)
        self.bots = [bot]
        self.outmap = {}

    def send(self, message):
        words = message.split(" ", 2)
        if words[0].lower() not in ["notice", "privmsg"] or len(words) != 3 or words[1].startswith("#") or len(self.bots) == 1:
            bot = 0
        elif words[1] in self.outmap:
            bot = self.outmap[words[1]]
        else:
            bot = min(range(len(self.bots)), key=lambda x: list(self.outmap.values()).count(x))
            self.outmap[words[1]] = bot
        sys.stdout.write("[%d] " % bot)
        self.bots[bot].sendline(message)

    def add(self, bot):
        self.bots.append(bot)

class InlineQueue(object):
    @staticmethod
    def queue(handler, args):
        try:
            handler(*args)
        except BaseException:
            print("Error in inline function " + handler.name, file=sys.stderr)
            sys.excepthook(*sys.exc_info())


class Caller(WorkerThread):
    """
    A worker thread for executing jobs asynchronously.
    """

    forklimit = 10

    def __init__(self, work=None):
        WorkerThread.__init__(self)
        self.last = None
        self.lastf = (None, None)

    def queue(self, funct, args):
        """
        Queue a job.
        """
        # TODO: Integrate forking
        # NOT THREADSAFE OH GOD FIX THIS
        self.work.put((funct, args))

    def dump(self):
        """
        Dumps the contents of the caller's queue, returns it, then terminates.
        """

        newq = Work()
        requeue = []
        with self.work._lock:
            # This blocks the queue.
            # The lock will be acquired after the queue feeds a task
            # to the caller, or the caller is still executing a task.
            lastarg = self.work.last
            while not self.work.empty():
                funct, args = self.work.get()
                if Callback.isThreadsafe(funct) or funct != lastarg:
                    newq.put((funct, args))
                else:
                    requeue.append((funct, args))
            for funct, args in requeue:
                # These functions aren't threadsafe, so we can't safely fork
                # off a queue with these tasks because we know that the
                # function is probably already executing.
                self.work.put((funct, args))
            self.terminate()
        return newq

    def terminate(self):
        """
        Send a 'TERM signal'
        """
        self.work.put(Work.TERM)

    def run(self):
        for funct, args in self.work:
            self.last = time.time()
            self.lastf = (funct, args)
            try:
                funct(*args)
            except BaseException:
                print("Error in function %s%s" % (funct.name, args))
                sys.excepthook(*sys.exc_info())
            self.last = None
        assert self.work.qsize() == 0

class Connection(threading.Thread, object):
    def __init__(self, conf, debug=None):
        super().__init__()
        config = yaml.safe_load(open(conf))
        self.sock = None
        self.server = tuple(config["Server"])
        self.username = config["Username"]
        self.realname = config["Real Name"]
        self.mode = config.get("Mode", 0)
        self.ssl = config.get("SSL", False)
        
        self.nick = None
        self.nicks = config["Nick"]

        self.admins = config["Admins"]
        self.config = config 
        self.name = conf.split(".")[0]

        self.connected = False
        self.restart = False

        self.printer = MultiPrinter(self)

        if debug is not None:
            self.buff = TimerBuffer(debug)
        else:
            self.buff = Buffer()

    def connect(self):
        self.sock = socket.socket()
        if self.ssl:
            self.sock = ssl.wrap_socket(self.sock)
        print("Connecting...")
        self.sock.connect(self.server)
        # Try our first nickname.
        nicks = collections.deque(self.nicks)
        self.nick = nicks.popleft()
        self.sendline("USER %s %s * :%s\r\n" % (self.username, 
                                                self.mode, 
                                                self.realname))
        print("Connected. Trying %s" % self.nick)
        self.sendline("NICK %s" % self.nick)
        # Find a working nickname
        while self.buff.append(self.sock.recv(1)):
            for line in self.buff:
                words = line.split()
                if line.startswith("PING") or words[1] == "001":
                    # We're done here.
                    self.sendline("PONG %s" % line.split()[-1])
                    break
                errdict = {"433": "Invalid nickname, retrying.", 
                           "436": "Nickname in use, retrying."}
                if words[1] == "432":
                    raise ValueError("Arguments sent to server are invalid; "\
                            "are you sure the configuration file is correct?")
                elif words[1] in errdict:
                    print(errdict[words[1]], file=sys.stderr)
                    self.nick = nicks.popleft()
                    self.sendline("NICK %s" % self.nick)
            else:
                # If we haven't broken out of the loop, our nickname is 
                # not valid.
                continue
            break
        self.connected = True
        self.printer.start()
        print("Connected.")

    def sendline(self, line):
        self.sock.send(("%s\r\n" % line).encode("utf-8"))

    def dispatch(self, line):
        """
        Dispatch and process a line of IRC.
        Override me.
        """
        return

    def cleanup(self):
            # TODO: decouple printer and connection.
            self.printer.terminate()
            print("Terminating threads...")

            self.printer.join()
            if "-d" in sys.argv and self.buff.log:
                print("%d high latency events recorded, max=%r, avg=%r" % (len(self.buff.log), max(self.buff.log), util.average(self.buff.log)))

    def run(self):
        try:
            while self.connected and self.buff.append(self.sock.recv(1024)):
                for line in self.buff:
                    self.dispatch(line)               

        finally:
            self.sock.close()
            print("Connection closed.")
            self.cleanup()            

            self.connected = False

    def message(self, *args, **kwargs):
        return self.printer.message(*args, **kwargs)

    def msg(self, target, message):
        return self.printer.message(message, target)


class EventHandler(object):
    GENERAL = 0
    INLINE = 1
    THREADSAFE = 2
    BACKGROUND = 4

    @property
    def isInline(self):
        return self.cbtype == self.INLINE

    @property
    def isThreadsafe(self):
        return self.cbtype == self.THREADSAFE

    @property
    def isBackground(self):
        return self.cbtype == self.BACKGROUND

    @property
    def isGeneral(self):
        return self.cbtype == self.GENERAL
    

    def __init__(self, trigger, function):
        self.trigger = trigger
        self.module = inspect.getmodule(function)
        self.name = function.__qualname__
        if self.module:
            self.name = self.module.__name__ + "." + self.name
        self.funct = function
        if Callback.isInline(function):
            self.cbtype = self.INLINE
        elif Callback.isThreadsafe(function):
            self.cbtype = self.THREADSAFE
        elif Callback.isBackground(function):
            self.cbtype = self.BACKGROUND
        else:
            self.cbtype = self.GENERAL

    def __call__(self, *args):
        return self.funct(*args)


class Bot(Connection):

    def __init__(self, conf, **kwargs):
        super().__init__(conf, **kwargs)
        self.callbacks = {"ALL": [], "DIE":[]}
        self.register("ping", self.pong)

    def get_config_dir(self, *subdirs):
        if "Data" in self.config:
            directory = self.config["Data"]
        else:
            directory = os.path.join("config", self.name)
        return os.path.join(directory, *subdirs)

    @Callback.inline
    def pong(self, server, line):
        self.sendline("PONG " + line.split(" ", 1)[1])

    def makeCallers(self, callers=2):
        # Make `callers` general purpose callers.
        self.callers = [Caller() for _ in range(callers + 2)]
        self.caller = {EventHandler.BACKGROUND: self.callers[0],
                        EventHandler.GENERAL: self.callers[1],
                        EventHandler.INLINE: InlineQueue,
                        }
        for c in self.callers: 
            c.start()

    def rebalance(self):
        longest = max(self.callers[2:], key=lambda x: x.work.qsize())
        if all(_.last for _ in self.callers[2:]) and longest.work.qsize() > 50:
            print("All queues backed up: expanding.")
            self.callers.append(Caller())
            self.callers[-1].start()
            self.callers.remove(longest)
            longest.terminate()
        for c in self.callers[2:]:
            ltime = c.last
            if ltime and time.time() - ltime > 8:
                print("Caller is taking too long executing %s%s: forking." % (c.lastf[0].name, c.lastf[1]))
                self.callers.remove(c)
                self.callers.append(Caller(c.dump()))
                self.callers[-1].start()
                print("Caller added.")

    def cleanup(self):
        super().cleanup()
        for funct in self.callbacks["DIE"]:
            funct(self)
        print("Cleaned up.")

        for c in self.callers: c.terminate()
        for c in self.callers: c.join()
        print("Threads terminated.")

    def run(self):
        self.makeCallers()
        super().run()

    def register_all(self, callbacks):
        for trigger in callbacks:
            for f in callbacks[trigger]:
                self.register(trigger, f)

    def register(self, trigger, funct):
        callback = EventHandler(trigger, funct)
        self.callbacks.setdefault(trigger, []).append(callback)

    def unregister_funct(self, callback, trigger=None):
        removed = []
        if trigger is not None:
            triggers = [trigger]
        else: 
            triggers = self.callbacks.keys()

        for i in triggers:
            while callback in self.callbacks[i]:
                self.callbacks[i].remove(callback)
                removed.append(i)

        return removed

    def unregister_name(self, funct, trigger=None):
        removed = []
        if trigger is not None:
            triggers = [trigger]
        else: 
            triggers = self.callbacks.keys()

        for i in triggers:
            remove = [i for i in self.callbacks[i] if i.name == funct]
            for f in remove:
                self.callbacks[i].remove(f)       
                removed.append(i)
        return removed

    def execute(self, handler, line):
        """ Executes a callback. """
        # TODO: replace queues with something more generic.
        if handler.isThreadsafe:
            handlerq = min(self.callers, key=lambda x: x.work.qsize())
        else:
            handlerq = self.caller[handler.cbtype]

        handlerq.queue(handler, (self, line))

    def dispatch(self, line):
        """
        Self-balancing threaded dispatch
        """
        line = line.rstrip()
        words = line.split()
        msgType = words[words[0] not in ["PING", "ERROR"]]

        self.rebalance()

        for funct in self.callbacks["ALL"] + self.callbacks.get(msgType.lower(), []):
            self.execute(funct, line)

    def loadplugin(self, mod):
        """ The following can optionally be defined to hook into karkat:
        __callbacks__: A mapping of callbacks.
        __icallbacks__:  A mapping of inline callbacks.
        __initialise__(name, botobj, printer) : A function to initialise the module.
        __destroy__(): A function triggered on bot death.
        """
        if "__initialise__" in dir(mod):
            mod.__initialise__(self)
            print("    Initialised %s." % mod.__name__)
        if "__callbacks__" in dir(mod):
            for trigger in mod.__callbacks__:
                for callback in mod.__callbacks__[trigger]:
                    self.register(trigger, callback)
                    print("        Registered callback: %s" % callback.__name__)
        if "__icallbacks__" in dir(mod):
            for trigger in mod.__icallbacks__:
                for callback in mod.__icallbacks__[trigger]:
                    self.register(Callback.inline(trigger), callback)
                    print("        Registered inline callback: %s" % callback.__name__)
        if "__destroy__" in dir(mod):
            self.register("DIE", mod.__destroy__)
            print("        Registered destructor: %s" % mod.__destroy__.__name__)

class SelectiveBot(Bot):
    def __init__(self, conf, **kwargs):
        super().__init__(conf, **kwargs)
        self.blacklist = {None:[]}

    def execute(self, handler, line):
        """ Executes a callback. """
        # TODO: replace queues with something more generic.
        # Check if PRIVMSG:
        data = line.split()
        if data[1] != "PRIVMSG" or not any(handler.module.__name__.startswith(i) for i in self.blacklist.get(data[2].lower(), self.blacklist[None])):
            super().execute(handler, line)


class IAL(object):
    def __init__(self):
        self.ial = set()

    def get(self, nick):
        for i in self.ial:
            if i.nick == nick:
                return i

class StatefulBot(SelectiveBot):
    """ Beware of thread safety when manipulating server state. If a callback
    interacts with this class, it must either be inlined, or be
    okay with the fact the state can change under your feet. """

    # TODO: Move into base module.
    # TODO: Store own state
    # TODO: Interact with connection threads
    # TODO: Extend interface to search for users and return lists and things.
    #       See xchat docs for interface ideas.
    # TODO: Fix nickname case rules and do sanity checking

    def __init__(self, conf, **kwargs):
        super().__init__(conf, **kwargs)
        self.features = []
        self.channels = {}
        self.server_settings = {}
        self.away = None
        self.valid_modes = ("", "")
        self.user_modes = {}
        self.channel_modes = {}
        self.listbuffer = {}
        self.topic = {}
        self.hostmask = None
        self.username = None
        self.rawmap = {346:"I", 348:"e", 367:"b", 386:"q", 388:"a"} # TODO: parse these.
        self.register_all({"quit" : [self.user_quit],
                           "part" : [self.user_left],
                           "join" : [self.user_join],
                           "nick" : [self.user_nickchange],
                           "kick" : [self.user_kicked],
                           "mode" : [self.channel_mode], 
                           "topic": [self.topic_changed],
                           "002"  : [self.on_connect],
                           "332"  : [self.channel_topic],  
                           "352"  : [self.joined_channel],
                           "005"  : [self.onServerSettings],
                           "306"  : [self.went_away],
                           "305"  : [self.came_back],
                           "301"  : [self.user_awaymsg],
                           "324"  : [self.joined_channel_modes]})
        for i in self.rawmap:
            self.register(str(i), self.list_builder)
            self.register(str(i+1), self.list_end)

    def nickcmp(self, nick1, nick2):
        """ Implements RFC-compliant nickcmp """
        return util.cmp(self.nickkey(nick1), self.nickkey(nick2))

    def nickkey(self, nick):
        """ Maps a nick to it's rfc-compliant lowercase form. """
        if self.server_settings.get("CASEMAPPING", "ascii") == "rfc1459":
            return util.rfc_nickkey(nick)
        else:
            return nick.lower()

    lower = nickkey # for convenience

    def isIn(self, nick, ls):
        return self.lower(nick) in [self.lower(i) for i in ls]

    def eq(self, nick1, nick2):
        return self.nickcmp(nick1, nick2) == 0

    def is_admin(self, address):
        return any(fnmatch.fnmatch(address, i) for i in self.admins) or any(address.endswith("@" + i) for i in self.admins)


    def parse_A_mode(self, channel, action, mode, args):
        settings = self.channel_modes.setdefault(self.lower(channel), {})
        settings = settings.setdefault(mode, [])
        arg = args.pop(0)

        if action == "+":
            settings.append(arg)
        else:
            settings.remove(arg)

    def parse_B_mode(self, channel, action, mode, args):
        settings = self.channel_modes.setdefault(self.lower(channel), {})
        arg = args.pop(0)

        if action == "+":
            settings[mode] = arg
        else:
            del settings[mode]
        
    def parse_C_mode(self, channel, action, mode, args):
        settings = self.channel_modes.setdefault(self.lower(channel), {})

        if action == "+":
            arg = args.pop(0)
            settings[mode] = arg
        else:
            del settings[mode]

    def parse_D_mode(self, channel, action, mode, args):
        settings = self.channel_modes.setdefault(self.lower(channel), {})

        if action == "+":
            settings[mode] = True
        else:
            del settings[mode]

    def parse_user_mode(self, channel, action, mode, args):
        settings = self.user_modes.setdefault(self.lower(channel), {})
        user = args.pop(0)
        settings = settings.setdefault(self.lower(user), [])
        if action == "+":
            settings.append(mode)
        else:
            settings.remove(mode)

    def set_modes(self, channel, modes, args):
        """
        Parses a string of channel modes.
        
        CHANMODES=A,B,C,D
            This is a list of channel modes according to 4 types.
            A = Mode that adds or removes a nick or address to a list. Always has a parameter.  Arity 1/1, List type
            B = Mode that changes a setting and always has a parameter.                         Arity 1/1, String or None
            C = Mode that changes a setting and only has a parameter when set                   Arity 1/0, String
            D = Mode that changes a setting and never has a parameter                           Arity 0/0, Boolean

            Note: Modes of type A return the list when there is no parameter present.
            Note: Some clients assumes that any mode not listed is of type D.
            Note: Modes in PREFIX are not listed but could be considered type B. 
        
        Private modes supported: Iebaq
        """
        types = zip(self.server_settings["CHANMODES"].split(",") + [self.valid_modes[0]], 
                    (self.parse_A_mode, self.parse_B_mode, self.parse_C_mode, self.parse_D_mode, self.parse_user_mode))
        action = "+"
        for i in modes:
            if i in "+-":
                action = i
            else:
                for flags, f in types:
                    if i in flags:
                        f(channel, action, i, args)
                        break
                else:
                    self.parse_D_mode(channel, action, i, args)

    def get_user_modes(self, channel, username):
        return self.user_modes.get(self.lower(channel), {}).get(self.lower(username), [])

    def rank_to_int(self, rank):
        if not rank:
            return 0
        elif rank in self.valid_modes[0]:
            return len(self.valid_modes[0]) - self.valid_modes[0].index(rank)
        elif rank in self.valid_modes[1]:
            return len(self.valid_modes[0]) - self.valid_modes[1].index(rank)

    def numeric_rank(self, channel, username):
        modes = self.get_user_modes(channel, username)
        modes = [self.rank_to_int(i) for i in modes]
        return max(modes or [0])

    def rank(self, channel, username):
        rank = self.numeric_rank(channel, username)
        return self.valid_modes[1][-rank] if rank else None

    def get_channel_modes(self, channel):
        return self.channel_modes.get(self.lower(channel), {})

    def get_topic(self, channel):
        return self.topic.get(self.lower(channel), None)

    def get_users(self, channel):
        return self.channels.get(self.lower(channel), [])

    def get_list(self, channel, mode):
        return self.get_channel_modes(channel).get(mode, [])
    
    @Callback.inline
    def topic_changed(self, server, line):
        words = line.split(" ", 3)
        self.topic[self.lower(words[2])] = words[-1][1:]

    @Callback.inline
    def channel_topic(self, server, line):
        words = line.split(" ", 4)
        self.topic[self.lower(words[3])] = words[-1][1:]

    @Callback.inline
    def list_builder(self, server, line):
        words = line.split(" ")
        self.listbuffer.setdefault((int(words[1]), self.lower(words[3])), []).append(words[4])

    @Callback.inline
    def list_end(self, server, line):
        words = line.split(" ")
        self.channel_modes.setdefault(self.lower(words[3]), {}).update({self.rawmap[int(words[1])-1]: self.listbuffer.get((int(words[1])-1, self.lower(words[3])), [])})
        self.listbuffer[int(words[1])-1, self.lower(words[3])] = []

    @Callback.inline
    def channel_mode(self, server, line):
        words = line.split(" ")
        channel, modes, args = words[2], words[3], words[4:]
        self.set_modes(channel, modes, args)


    @Callback.inline
    def joined_channel_modes(self, server, line):
        words = line.split(" ")
        channel, modes, args = words[3], words[4], words[5:]
        self.set_modes(channel, modes, args)


    @Callback.inline
    def went_away(self, server, line):
        assert self.eq(line.split()[2], self.nick)
        # Get away message
        self.sendline("WHOIS %s" % self.nick)


    @Callback.inline
    def came_back(self, server, line):
        assert self.eq(line.split()[2], self.nick)
        assert self.away
        self.away = None

    @Callback.inline
    def user_awaymsg(self, server, line):
        server, code, me, user, reason = line.split(" ", 4)
        if self.eq(me, self.nick):
            self.away = reason[1:]

    @Callback.inline
    def onServerSettings(self, server, line):
        """ Implements server settings on connect """
        for i in line.split()[2:]:
            if "=" not in i:
                self.server_settings[i] = True
            else:
                key, value = i.split("=", 1)
                self.server_settings[key] = value
    
        if "PREFIX" in self.server_settings:
            self.valid_modes = re.match(r"\((.+)\)(.+)", self.server_settings["PREFIX"]).groups()


    @Callback.inline
    def user_left(self, server, line):
        """ Handles PARTs """
        words = line.split()
        nick = Address(words[0]).nick
        channel = self.lower(words[2])
        if self.eq(nick, self.nick):
            del self.channels[channel]
        else:
            self.channels[channel].remove(nick)

    @Callback.inline
    def user_quit(self, server, line):
        """ Handles QUITs"""
        words = line.split()
        nick = Address(words[0]).nick
        for i in self.channels:
            if self.isIn(nick, self.channels[i]):
                self.channels[i].remove(nick) # Note: May error. This might indicate a logic error or a bastard server.

    @Callback.inline
    def user_join(self, server, line):
        """ Handles JOINs """
        words = line.split()
        nick = Address(words[0]).nick
        channel = self.lower(words[2][1:])
        if self.eq(nick, self.nick):
            self.channels[channel] = set()
            self.sendline("WHO %s" % words[2]) # TODO: replace with connection object shit.
            self.sendline("MODE %s" % words[2])
            for i in self.server_settings["CHANMODES"].split(",")[0]: # Lists
                self.sendline("MODE %s %s" % (words[2][1:], i))
        else:
            self.channels[channel].add(nick)

    @Callback.inline
    def joined_channel(self, server, line):
        """ Handles 352s (WHOs) """
        words = line.split()
        if self.eq(words[7], self.nick):
            self.username, self.hostmask = words[4], words[5]
        self.channels.setdefault(self.lower(words[3]), set()).add(words[7])
        self.user_modes.setdefault(self.lower(words[3]), {}).update({self.lower(words[7]): [self.valid_modes[0][self.valid_modes[1].index(i)] for i in words[8] if i in self.valid_modes[1]]})

    @Callback.inline
    def user_nickchange(self, server, line):
        """ Handles NICKs """
        words = line.split()
        nick = Address(words[0]).nick
        newnick = words[2][1:]
        for i in self.channels:
            if nick in self.channels[i]:
                self.channels[i].remove(nick)
                self.channels[i].add(newnick)
        if self.eq(nick, self.nick):
            self.nick = newnick

    @Callback.inline
    def user_kicked(self, server, line):
        """ Handles KICKs """
        words = line.split()
        nick = words[3]
        channel = self.lower(words[2])
        self.channels[channel].remove(nick)

    @Callback.inline
    def on_connect(self, server, line):
        """ Runs code on successful connection """
        self.sendline("WHO :%s" % self.nick)

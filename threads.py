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

import yaml

import util
from irc import Address, Callback
from text import lineify, TimerBuffer, average, Buffer


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


class WorkerThread(threading.Thread):
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


class Printer(WorkerThread):
    """ This queue-like thread controls the output to a socket."""

    def __init__(self, connection):
        WorkerThread.__init__(self)
        self.flush = False
        self.bot = connection

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
        for message in [i for i in str(mesg).split("\n") if i]:
            self.work.put("%s %s :%s" % (method, recipient, message))
        return mesg # Debugging

    def raw_message(self, mesg):
        self.work.put(mesg)

    def run(self):
        while True:
            for data in self.work:
                if not self.flush:
                    try:
                        self.send(data)
                    except BaseException as err:
                        print("Shit, printer error: %r\n" % err)
                        sys.excepthook(*sys.exc_info())
                    else:
                        sys.stdout.write(">>> %s" % data.split()[0]) #TODO: Replace with informative debug info
                        if self.work.qsize():
                            sys.stdout.write(" %d items queued." %
                                                 self.work.qsize())
                        sys.stdout.write("\n")
                else:
                    self.flush = False
                    self.work = Work()
                    break
            else:
                break

    def write(self, data):
        """
        Send a message. If data is a string, the message is sent to the
        current context, else it is assumed to be a 2-tuple containing
        (message, target).
        """
        if data.strip():
            if isinstance(data, str):
                data, channel = lineify(data), None
            else:
                data, channel = lineify(data[0]), data[1]
            for line in data:
                if line.strip():
                    self.message(line, channel)

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
                value.append("%s %s" % (line.split()[0],
                                        self.defaultcolor(" ".join(line.split()[1:]))))
            line = re.sub("\x03([^\d])",
                          lambda x: (("\x03%s" % (color)) + (x.group(1) or "")),
                          line)
            line = line.replace("\x0f", "\x0f\x03%s" % (color))
            value.append("\x03%s%s" % (color, line))
        return "\n".join(value)

    def message(self, msg, recipient=None, method="PRIVMSG"):
        if method.upper() in ["PRIVMSG", "NOTICE"] and self.hasink:
            mesg = self.defaultcolor(str(msg))
        super(ColourPrinter, self).message(mesg, recipient, method)
        return msg


class InlineQueue(object):
    @staticmethod
    def queue(handler, line):
        try:
            handler(line)
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
        for funct, arg in self.work:
            self.last = time.time()
            try:
                funct(arg)
            except BaseException:
                print("Error in function %s%s" % (funct.name, arg))
                sys.excepthook(*sys.exc_info())
            self.last = None
        assert self.work.qsize() == 0

class Connection(threading.Thread):
    def __init__(self, conf):
        super(Connection, self).__init__()
        config = yaml.safe_load(open(conf))
        self.sock = None
        self.server = tuple(config["Server"])
        self.username = config["Username"]
        self.realname = config["Real Name"]
        self.mode = config.get("Mode", 0)
        
        self.nick = None
        self.nicks = config["Nick"]

        self.admins = config["Admins"]
        self.config = config 
        self.name = conf.split(".")[0]

        self.connected = False
        self.restart = False

        # TODO: replace with options
        if "-d" in sys.argv:
            flag = sys.argv.index("-d")
            try:
                thresh = float(sys.argv[flag+1])
            except (IndexError, ValueError):
                thresh = 0.15
            self.buff = TimerBuffer(thresh)
        else:
            self.buff = Buffer()

    def connect(self):
        self.sock = socket.socket()
        self.sock.connect(self.server)

        # Try our first nickname.
        nicks = collections.deque(self.nicks)
        self.nick = nicks.popleft()
        self.sendline("NICK %s" % self.nick)
        # Find a working nickname
        while self.buff.append(self.sock.recv(1)):
            for line in self.buff:
                if line.startswith("PING"):
                    # We're done here.
                    self.sendline("PONG %s" % line.split()[-1])
                    break
                words = line.split()
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
        self.sendline("USER %s %s * :%s\r\n" % (self.username, 
                                                self.mode, 
                                                self.realname))
        self.connected = True
        self.printer = ColourPrinter(self)
        self.printer.start()

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
                print("%d high latency events recorded, max=%r, avg=%r" % (len(self.buff.log), max(self.buff.log), average(self.buff.log)))

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
        self.name = self.module.__name__ + "." + function.__qualname__
        self.funct = function
        if Callback.isInline(function):
            self.cbtype = self.INLINE
        elif Callback.isThreadsafe(function):
            self.cbtype = self.THREADSAFE
        elif Callback.isBackground(function):
            self.cbtype = self.BACKGROUND
        else:
            self.cbtype = self.GENERAL

    def __call__(self, line):
        return self.funct(line)


class Bot(Connection):

    def __init__(self, conf):
        super(Bot, self).__init__(conf)
        self.callbacks = {"ALL": [], "DIE":[]}
        self.register("ping", self.pong)

    def get_config_dir(self, *subdirs):
        if "Data" in self.config:
            directory = self.config["Data"]
        else:
            directory = os.path.join("config", self.name)
        return os.path.join(directory, *subdirs)

    @Callback.inline
    def pong(self, line):
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
                print("Caller is taking too long: forking.")
                self.callers.remove(c)
                self.callers.append(Caller(c.dump()))
                self.callers[-1].start()
                print("Caller added.")

    def cleanup(self):
        super(Bot, self).cleanup()
        for funct in self.callbacks["DIE"]:
            funct()
        print("Cleaned up.")

        for c in self.callers: c.terminate()
        for c in self.callers: c.join()
        print("Threads terminated.")

    def run(self):
        self.makeCallers()
        super(Bot, self).run()

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

        handlerq.queue(handler, line)

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

class SelectiveBot(Bot):
    def __init__(self, conf):
        super().__init__(conf)
        self.blacklist = {None:[]}

    def execute(self, handler, line):
        """ Executes a callback. """
        # TODO: replace queues with something more generic.
        # Check if PRIVMSG:
        data = line.split()
        if data[1] != "PRIVMSG" or handler.module.__name__ not in self.blacklist.get(data[2].lower(), self.blacklist[None]): 
            super().execute(handler, line)

def loadplugin(mod, name, bot, stream):
    if "__initialise__" in dir(mod):
        mod.__initialise__(name, bot, stream)
        print("    Initialised %s." % mod.__name__)
    if "__callbacks__" in dir(mod):
        for trigger in mod.__callbacks__:
            for callback in mod.__callbacks__[trigger]:
                bot.register(trigger, callback)
                print("        Registered callback: %s" % callback.__name__)
    if "__icallbacks__" in dir(mod):
        for trigger in mod.__icallbacks__:
            for callback in mod.__icallbacks__[trigger]:
                bot.register_i(trigger, callback)
                print("        Registered inline callback: %s" % callback.__name__)
    if "__destroy__" in dir(mod):
        bot.register_i("DIE", mod.__destroy__)
        print("        Registered destructor: %s" % mod.__destroy__.__name__)

class StatefulBot(SelectiveBot):
    """ Beware of thread safety when manipulating server state. If a callback
    interacts with this class, it must either be inlined, or be
    okay with the fact the state can change under your feet. """

    # TODO: Store own state
    # TODO: Interact with connection threads
    # TODO: Extend interface to search for users and return lists and things.
    #       See xchat docs for interface ideas.
    # TODO: Fix nickname case rules and do sanity checking

    def __init__(self, conf):
        super().__init__(conf)
        self.channels = {}
        self.server_settings = {}
        self.away = None
        self.register_all({"quit" : [self.user_quit],
                           "part" : [self.user_left],
                           "join" : [self.user_join],
                           "nick" : [self.user_nickchange],
                           "kick" : [self.user_kicked],
                           "352"  : [self.joined_channel],
                           "005"  : [self.onServerSettings],
                           "306"  : [self.went_away],
                           "305"  : [self.came_back],
                           "301"  : [self.user_awaymsg]})

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

    @Callback.inline
    def went_away(self, line):
        assert self.eq(self.line.split()[2], self.nick)
        # Get away message
        self.sendline("WHOIS %s" % self.nick)


    @Callback.inline
    def came_back(self, line):
        assert self.eq(self.line.split()[2], self.nick)
        assert self.away
        self.away = None

    @Callback.inline
    def user_awaymsg(self, line):
        server, code, me, user, reason = line.split(" ", 4)
        if self.eq(me, self.nick):
            self.away = reason[1:]

    @Callback.inline
    def onServerSettings(self, line):
        """ Implements server settings on connect """
        for i in line.split()[2:]:
            if "=" not in i:
                self.server_settings[i] = True
            else:
                key, value = i.split("=", 1)
                self.server_settings[key] = value

    @Callback.inline
    def user_left(self, line):
        """ Handles PARTs """
        words = line.split()
        nick = Address(words[0]).nick
        channel = self.lower(words[2])
        if self.eq(nick, self.nick):
            del self.channels[channel]
        else:
            self.channels[channel].remove(nick)

    @Callback.inline
    def user_quit(self, line):
        """ Handles QUITs"""
        words = line.split()
        nick = Address(words[0]).nick
        for i in self.channels:
            if self.isIn(nick, self.channels[i]):
                self.channels[i].remove(nick) # Note: May error. This might indicate a logic error or a bastard server.

    @Callback.inline
    def user_join(self, line):
        """ Handles JOINs """
        words = line.split()
        nick = Address(words[0]).nick
        channel = self.lower(words[2][1:])
        if self.eq(nick, self.nick):
            self.channels[channel] = set()
            self.sendline("WHO %s" % words[2]) # TODO: replace with connection object shit.
        else:
            self.channels[channel].add(nick)

    @Callback.inline
    def joined_channel(self, line):
        """ Handles 352s (WHOs) """
        words = line.split()
        self.channels.setdefault(self.lower(words[3]), set()).add(words[7])

    @Callback.inline
    def user_nickchange(self, line):
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
    def user_kicked(self, line):
        """ Handles KICKs """
        words = line.split()
        nick = words[3]
        channel = self.lower(words[2])
        self.channels[channel].remove(nick)

""" This module contains the worker threads for Karkat's system. """

import os
import sys
import threading
import time
import queue
import re
import collections
import socket
import fnmatch

import yaml

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
        self.sender.message("\n".join(self.buffer),
                            self.recipient,
                            self.method)


class Printer(WorkerThread):
    """ This queue-like thread controls the output to a socket."""

    def __init__(self, connection):
        WorkerThread.__init__(self)
        self.flush = False
        self.bot = connection
        self.last = "#homestuck"

    def set_target(self, channel):
        """ Set the default output channel. """
        self.last = channel

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

    def message(self, mesg, recipient=None, method="PRIVMSG"):
        """
        Send a message.
        """
        if not recipient:
            recipient = self.last
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
        color = self.color
        if " " in data and data[0] + data[-1] == "\x01\x01":
            return "%s %s" % (data.split()[0],
                              self.defaultcolor(" ".join(data.split()[1:])))
        data = re.sub("\x03([^\d])",
                      lambda x: (("\x03%s" % (color)) + (x.group(1) or "")),
                      data)
        data = data.replace("\x0f", "\x0f\x03%s" % (color))
        return "\x03%s%s" % (color, data)

    def message(self, msg, recipient=None, method="PRIVMSG"):
        if method.upper() in ["PRIVMSG", "NOTICE"] and self.hasink:
            mesg = self.defaultcolor(str(msg))
        super(ColourPrinter, self).message(mesg, recipient, method)
        return msg


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
                print("Error in function %s%s" % (funct.__name__, arg))
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


class Bot(Connection):
    def __init__(self, conf, cbs=None, icbs=None):
        super(Bot, self).__init__(conf)
        self.callbacks = cbs or {"ALL":[]}
        self.inline_cbs = icbs or {"ALL":[], "DIE":[], "ping": [self.pong]}

    def get_config_dir(self, *subdirs):
        if "Data" in self.config:
            directory = self.config["Data"]
        else:
            directory = os.path.join("config", self.name)
        return os.path.join(directory, *subdirs)

    def pong(self, line):
        self.sendline("PONG " + line.split(" ", 1)[1])

    def makeCallers(self, callers=2):
        # Make 4 general purpose callers.
        self.callers   = [Caller() for _ in range(callers + 2)] 
        self.caller    = self.callers[1] # second caller is the general caller
        self.bg_caller = self.callers[0] # first caller is the background caller
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
        for funct in self.inline_cbs["DIE"]:
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
        self.callbacks.setdefault(trigger, []).append(funct)

    def register_alli(self, callbacks):
        for trigger in callbacks:
            for f in callbacks[trigger]:
                self.register_i(trigger, f)

    def register_i(self, trigger, funct):
        self.inline_cbs.setdefault(trigger, []).append(funct)

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

    def unregister_ifunct(self, callback, trigger=None):
        removed = []
        if trigger is not None:
            triggers = [trigger]
        else: 
            triggers = self.inline_cbs.keys()

        for i in triggers:
            while callback in self.inline_cbs[i]:
                self.inline_cbs[i].remove(callback)       
                removed.append(i)
        return removed

    def unregister_name(self, funct, trigger=None):
        removed = []
        if trigger is not None:
            triggers = [trigger]
        else: 
            triggers = self.callbacks.keys()

        for i in triggers:
            remove = [i for i in self.callbacks[i] if i.__name__ == funct]
            for f in remove:
                self.callbacks[i].remove(f)       
                removed.append(i)
        return removed

    def unregister_iname(self, funct, trigger=None):
        removed = []
        if trigger is not None:
            triggers = [trigger]
        else: 
            triggers = self.inline_cbs.keys()

        for i in triggers:
            remove = [i for i in self.inline_cbs[i] if i.__name__ == funct]
            for f in remove:
                self.inline_cbs[i].remove(f)       
                removed.append(i)
        return removed

    def dispatch(self, line):
        """
        Self-balancing threaded dispatch
        """
        line = line.rstrip()
        words = line.split()

        if words[0] in ["PING", "ERROR"]:
            msgType = words[0]
        else:
            msgType = words[1]
        
        for funct in self.inline_cbs["ALL"]:
            try:
                funct(line)
            except BaseException:
                print("Error in inline function " + funct.__name__)
                sys.excepthook(*sys.exc_info())

        self.rebalance()

        for funct in self.callbacks["ALL"]:
            self.caller.queue(funct, line)

        # Inline functions: execute immediately.
        for funct in self.inline_cbs.get(msgType.lower(), []):
            try:
                funct(line)
            except BaseException:
                print("Error in inline function " + funct.__name__)
                sys.excepthook(*sys.exc_info())

        for funct in self.callbacks.get(msgType.lower(), []):
            if Callback.isBackground(funct):
                self.bg_caller.queue(funct, line)
            elif Callback.isThreadsafe(funct):
                min(self.callers, key=lambda x: x.work.qsize()).queue(funct, line)
            else:
                self.caller.queue(funct, line)

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

class StatefulBot(Bot):
    """ Beware of thread safety when manipulating server state. If a callback
    interacts with this class, it must either be inlined, or be
    okay with the fact the state can change under your feet. """

    # TODO: Store own state
    # TODO: Interact with connection threads
    # TODO: Extend interface to search for users and return lists and things.
    #       See xchat docs for interface ideas.
    # TODO: Fix nickname case rules and do sanity checking

    def __init__(self, conf, cbs=None, icbs=None):
        super(StatefulBot, self).__init__(conf, cbs, icbs)
        self.channels = {}
        self.register_alli({"quit"    : [self.user_quit],
         "part"    : [self.user_left],
         "join"    : [self.user_join],
         "nick"    : [self.user_nickchange],
         "kick"    : [self.user_kicked],
         "352"     : [self.joined_channel]})

    def is_admin(self, address):
        return any(fnmatch.fnmatch(address, i) for i in self.admins) or any(address.endswith("@" + i) for i in self.admins)

    def user_left(self, line):
        """ Handles PARTs """
        words = line.split()
        nick = Address(words[0]).nick
        channel = words[2].lower()
        if nick.lower() == self.nick.lower():
            del self.channels[channel]
        else:
            self.channels[channel].remove(nick)

    def user_quit(self, line):
        """ Handles QUITs"""
        words = line.split()
        nick = Address(words[0]).nick
        for i in self.channels:
            if nick in self.channels[i]:
                self.channels[i].remove(nick)

    def user_join(self, line):
        """ Handles JOINs """
        words = line.split()
        nick = Address(words[0]).nick
        channel = words[2][1:].lower()
        if nick.lower() == self.nick.lower():
            self.channels[channel] = set()
            self.sendline("WHO %s" % words[2]) # TODO: replace with connection object shit.
        else:
            self.channels[channel].add(nick)

    def joined_channel(self, line):
        """ Handles 352s (WHOs) """
        words = line.split()
        self.channels[words[3].lower()].add(words[7])

    def user_nickchange(self, line):
        """ Handles NICKs """
        words = line.split()
        nick = Address(words[0]).nick
        newnick = words[2][1:]
        for i in self.channels:
            if nick in self.channels[i]:
                self.channels[i].remove(nick)
                self.channels[i].add(newnick)
        if nick.lower() == self.nick.lower():
            self.nick = newnick

    def user_kicked(self, line):
        """ Handles KICKs """
        words = line.split()
        nick = words[3]
        channel = words[2].lower()
        self.channels[channel].remove(nick)

#! /usr/bin/python3
# -*- coding: utf-8 -*-
"""
Usage: %(name)s [options] <config> [plugin]...

Options:
    -h --help               Show this screen.
    --version               Show version.
    -v N, --verbosity=N     Set verbosity [default: 1]
"""

"""
Defining a Karkat plugin.

The following can optionally be defined to hook into karkat:
__callbacks__: A mapping of callbacks.
__icallbacks__:  A mapping of inline callbacks.
__initialise__(name, botobj, printer) : A function to initialise the module.
"""


import collections
import functools
import inspect
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time

import yaml
import docopt

from threads import ColourPrinter, Caller
from irc import Address, Callback, Message, Command
from text import Buffer, TimerBuffer, average

__version__ = 2.0

socket.setdefaulttimeout(1800)

GP_CALLERS = 2

#TODO: Move connection object and subclasses
# TODO: Turn subclasses into objects owned by the connection thread.
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
        while self.buff.append(self.sock.recv(1).decode("utf-8")):
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

    def sendline(self, line):
        self.sock.send(("%s\r\n" % line).encode("utf-8"))

    def dispatch(self, line):
        """
        Dispatch and process a line of IRC.
        """
        return

    def cleanup(self):
            # TODO: decouple printer and connection.
            printer.terminate()
            print("Terminating threads...")

            printer.join()
            if "-d" in sys.argv and self.buff.log:
                print("%d high latency events recorded, max=%r, avg=%r" % (len(self.buff.log), max(self.buff.log), average(self.buff.log)))

    def run(self):
        try:
            while self.connected and self.buff.append(self.sock.recv(1024).decode("utf-8")):
                for line in self.buff:
                    self.dispatch(line)               

        finally:
            self.sock.close()
            print("Connection closed.")
            self.cleanup()            

            self.connected = False


class ServerState(Connection):
    """ Beware of thread safety when manipulating server state. If a callback
    interacts with this class, it must either be inlined, or be
    okay with the fact the state can change under your feet. """

    # TODO: Store own state
    # TODO: Interact with connection threads
    # TODO: Extend interface to search for users and return lists and things.
    #       See xchat docs for interface ideas.
    # TODO: Fix nickname case rules and do sanity checking

    def __init__(self, conf):
        super(ServerState, self).__init__(conf)
        self.channels = {}

    def user_left(self, words, line):
        """ Handles PARTs """
        nick = Address(words[0]).nick
        channel = words[2].lower()
        if nick.lower() == self.nick.lower():
            del self.channels[channel]
        else:
            self.channels[channel].remove(nick)

    def user_quit(self, words, line):
        """ Handles QUITs"""
        nick = Address(words[0]).nick
        for i in self.channels:
            if nick in self.channels[i]:
                self.channels[i].remove(nick)

    def user_join(self, words, line):
        """ Handles JOINs """
        nick = Address(words[0]).nick
        channel = words[2][1:].lower()
        if nick.lower() == self.nick.lower():
            self.channels[channel] = set()
            self.sendline("WHO %s" % words[2]) # TODO: replace with connection object shit.
        else:
            self.channels[channel].add(nick)

    def joined_channel(self, words, line):
        """ Handles 352s (WHOs) """
        self.channels[words[3].lower()].add(words[7])

    def user_nickchange(self, words, line):
        """ Handles NICKs """
        nick = Address(words[0]).nick
        newnick = words[2][1:]
        for i in self.channels:
            if nick in self.channels[i]:
                self.channels[i].remove(nick)
                self.channels[i].add(newnick)
        if nick.lower() == self.nick.lower():
            self.nick = newnick

    def user_kicked(self, words, line):
        """ Handles KICKs """
        nick = words[3]
        channel = words[2].lower()
        self.channels[channel].remove(nick)

class Bot(ServerState):
    def __init__(self, conf, cbs=None, icbs=None):
        super(Bot, self).__init__(conf)
        self.callbacks = cbs or {"ALL":[]}
        self.inline_cbs = icbs or {"ALL":[], "DIE":[]}

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
            self.caller.queue(funct, (line,))

        # Inline functions: execute immediately.
        for funct in self.inline_cbs.get(msgType.lower(), []):
            try:
                funct(words, line)
            except BaseException:
                print("Error in inline function " + funct.__name__)
                sys.excepthook(*sys.exc_info())

        for funct in self.callbacks.get(msgType.lower(), []):
            if Callback.isBackground(funct):
                self.bg_caller.queue(funct, (words, line))
            elif Callback.isThreadsafe(funct):
                min(self.callers, key=lambda x: x.work.qsize()).queue(funct, (words, line))
            else:
                self.caller.queue(funct, (words, line))




try:
    server = Bot(sys.argv[1])
except (OSError, IndexError):
    print("Usage: %s <config>" % sys.argv[0])
    sys.exit(1)
server.connect()
printer = server.printer

class AutoJoin(object):
    try:
        chans = open("autojoin.txt").read().strip() if "-t" not in sys.argv else "#karkat"
    except OSError:
        open("autojoin.txt", "w")
        chans = ""
    @Callback.threadsafe
    def join(self, x, y):
        if self.chans:
            bot.join(self.chans)
    @Callback.threadsafe
    def onInvite(self, words, line):
        if Address(words[0]).mask in server.admins or words[3][1:].lower() in self.chans.lower().split(","):
            bot.join(words[3])
    def trigger(self, x, y):
        if x[3].lower() == "::autojoin" and x[2].startswith("#"):
            if x[2].lower() in self.chans.split(","):
                chans = self.chans.split(",")
                chans.remove(x[2].lower())
                self.chans = ",".join(chans)
                with open("./autojoin.txt", "w") as chanfile:
                    chanfile.write(self.chans)
                server.printer.message("Channel removed from autojoin.", x[2])
            else:
                self.chans = ",".join(self.chans.split(",") + [x[2].lower()])
                with open("./autojoin.txt", "w") as chanfile:
                    chanfile.write(self.chans)
                server.printer.message("Channel added to autojoin.", x[2])

aj = AutoJoin()

class Allbots:
    def __init__(self, bots, args = ""):
        self.bots = bots
        self.args = args
    def __call__(self, *data):
        pref = self.args + (" " * bool(self.args))
        for i in self.bots:
            i.sendline(pref + (" ".join(data)))
    def __getattr__(self, d):
        return Allbots(self.bots, self.args + " " + d)
bot = Allbots([server])

# 1010100100100010001011000001000011100000110010111000101100000100100110100111000001000001100000100110010010011000101
        

class Shell(threading.Thread):

    activeShell = False
    shellThread = None
    target = None

    def __init__(self, shell):
        self.shell = shell
        self.stdout = shell.stdout
        self.stdin = shell.stdin
        threading.Thread.__init__(self)
    def run(self):
        started = time.time()
        for line in iter(self.stdout.readline, b""):
            line = line.decode('utf-8')
            server.printer.message(line, Shell.target)
        Shell.activeShell = False
        if time.time() - started > 2:
            server.printer.message("[Shell] Program exited with code %s"%(self.shell.poll()), Shell.target)

    @classmethod
    def trigger(cls, words, line):
        if Address(words[0]).mask in server.admins and words[3] == ":$":
            args = line.split(" ", 4)[-1]
            cls.target = Message(line).context

            if not cls.activeShell:
                try:
                    shell = subprocess.Popen(args, 
                                             stdin=subprocess.PIPE, 
                                             stdout=subprocess.PIPE, 
                                             stderr=subprocess.STDOUT, 
                                             shell=True, 
                                             preexec_fn=os.setsid)
                except OSError:
                    server.printer.message("「 Shell Error 」 Command failed.", cls.target)
                    return
                cls.activeShell = True
                cls.shellThread = cls(shell)
                cls.shellThread.start()
            else:
                cls.shellThread.stdin.write(args + "\n")

    @classmethod
    def terminate(cls):
        if cls.activeShell:
            os.killpg(cls.shellThread.shell.pid, signal.SIGTERM)

def authenticate(words, line):
    if "-i" in sys.argv:
        try:
            password = sys.argv[sys.argv.index("-i")+1]
        except IndexError:
            return
        else:
            server.sendline("msg nickserv identify %s" % password)
       

class Interpretter(object):
    def __init__(self):
        self.curcmd = []
        self.codeReact = 0

    def trigger(self, words, line):
        if Address(words[0]).mask in server.admins:
            # TODO: modify passed in namespace's stdout.
            data = line.split(" ", 3)[-1]
            msgdata = Message(line)
            evaluate = False
            if data == (":%s, undo" % server.nick):
                # Delete the last command off the buffer
                self.curcmd.pop()
                printer.message("oh, sure", Message(line).context)
            elif self.codeReact:
                # Code is being added to the buffer.
                # Keep building
                if '"""' in data:
                    # Is the end of the input somewhere in the text?
                    self.codeReact = 0
                    evaluate = True
                self.curcmd.append(data[1:].split('"""', 1)[0])
                
            elif ':"""' in data:
                # Enable code building.
                self.codeReact = 1
                act = data.split(':"""', 1)[-1]
                if act:
                    self.curcmd = [act]

            elif words[3] == ":>>>":
                try:
                    act = line.split(" ", 4)[4]
                except IndexError:
                    act = ""
                if act and (act[-1] in "\\:" or act[0] in " \t@"):
                    self.curcmd += [act[:-1]] if act[-1] == "\\" else [act]
                else:
                    self.curcmd.append(act)
                    evaluate = True
            if evaluate:
                code = "\n".join([re.sub("\x02(.+?)(\x02|\x0f|$)", "printer.message(\\1, %r)" % msgdata.context, i) for i in self.curcmd])
                print("-------- Executing code --------")
                print(code)
                print("--------------------------------")
                try: 
                    assert "\n" not in code
                    output = eval(code, globals())
                    if output != None: 
                        printer.message(str(output))
                except:
                    try:
                        exec(code, globals())
                    except BaseException as e:
                        printer.message("\x02「\x02\x0305 oh wow\x0307 \x0315%s \x03\x02」\x02 "%(repr(e)[:repr(e).find("(")]) + str(e))
                self.curcmd = []


def log(line):
    if "-d" in sys.argv:
        print("[%s] %s" % (server.server[0], line))

flist = {
         "privmsg" : [aj.trigger],
         "kick" : [lambda x, y: bot.join(x[2]) if x[3].lower() == server.nick.lower() else None],
         "invite" : [aj.onInvite],
         "376" : [aj.join,
                  authenticate,
                  lambda *x: printer.start(),
                  lambda x, y: bot.mode(server.nick, "+B")],
         "ALL" : [],
        }

inline = {
         "privmsg" : [Shell.trigger, 
                      lambda x, y: printer.set_target(Message(y).context), 
                      Interpretter().trigger],
         "ping"    : [lambda x, y: server.sendline("PONG " + x[1])],
         "quit"    : [server.user_quit],
         "part"    : [server.user_left],
         "join"    : [server.user_join],
         "nick"    : [server.user_nickchange],
         "kick"    : [server.user_kicked],
         "352"     : [server.joined_channel],
         "ALL"     : [log],
         "DIE"     : []
}


if __name__ == "__main__":
    #args = docopt.docopt()
    if "-f" in sys.argv:
        exec(open("features.py").read())
        # Temporary.
    plugins = __import__("plugins") # temporary

    for mod in plugins.__all__:
        if "__initialise__" in dir(mod):
            mod.__initialise__(server.server[0], server, printer)
            print("Initialising %s" % mod.__name__)
        else:
            print("Warning: No initialiser for %s" % mod.__name__)
        if "__callbacks__" in dir(mod):
            for trigger in mod.__callbacks__:
                flist.setdefault(trigger, []).extend(mod.__callbacks__[trigger])
                print("    Registered callbacks: %s" % ", ".join(i.__name__ for i in mod.__callbacks__[trigger]))
        if "__icallbacks__" in dir(mod):
            for trigger in mod.__icallbacks__:
                flist.setdefault(trigger, []).extend(mod.__icallbacks__[trigger])
                print("    Registered inlines: %s" % ", ".join(i.__name__ for i in mod.__icallbacks__[trigger]))

        print("Loaded %s" % mod.__name__)

    server.register_all(flist)
    server.register_alli(inline)

    print("Running...")
    server.start()

    while server.connected:
        try:
            exec(input())
        except KeyboardInterrupt:
            print("Terminating...")
            server.connected = False
            server.sock.send("QUIT\r\n".encode("utf-8"))
        except BaseException:
            sys.excepthook(*sys.exc_info())

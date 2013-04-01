#! /usr/bin/python
# -*- coding: utf-8 -*-

import collections
import functools
import inspect
import os
import re
import shlex
import signal
import socket
import subprocess
import sys
import threading
import time
import yaml

from threads import ColourPrinter, Caller
from irc import Address, Callback, Message, Command
from text import Buffer

socket.setdefaulttimeout(1800)

GP_CALLERS = 2
connected = True

class Connection(object):
    def __init__(self, conf):
        config = yaml.safe_load(open(conf))
        self.sock = None
        self.server = tuple(config["Server"])
        self.username = config["Username"]
        self.realname = config["Real Name"]
        self.mode = config.get("Mode", 0)
        
        self.nick = None
        self.nicks = config["Nick"]

        self.admins = config["Admins"]

    def connect(self):
        self.sock = socket.socket()
        self.sock.connect(self.server)

        # Try our first nickname.
        nicks = collections.deque(self.nicks)
        self.nick = nicks.popleft()
        self.sendline("NICK %s" % self.nick)
        # Create a temporary buffer while we find a working nickname
        buff = Buffer()
        while buff.append(self.sock.recv(1)):
            for line in buff:
                if line.startswith("PING"):
                    # We're done here.
                    self.sendline("PONG %s" % line.split()[-1])
                    break
                words = line.split()
                errdict = {"433": "Invalid nickname, retrying.", "436": "Nickname in use, retrying."}
                if words[1] == "432":
                    raise ValueError("Arguments sent to server are invalid; are you sure the configuration file is correct?")
                elif words[1] in errdict:
                    print >> sys.stderr, errdict[words[1]]
                    self.nick = nicks.popleft()
                    self.sendline("NICK %s" % self.nick)
            else:
                # If we haven't broken out of the loop, our nickname is not valid.
                continue
            break
        self.sendline("USER %s %s * :%s\r\n" % (self.username, self.mode, self.realname))

    def sendline(self, line):
        self.sock.send("%s\r\n" % line)


class ServerState(Connection):
    """ Beware of thread safety when manipulating server state. If a callback
    interacts with this class, it must either not be marked threadsafe, or be
    okay with the fact the state can change under your feet. """

    # TODO: Store own state
    # TODO: Interact with connection threads
    # TODO: Extend interface to search for users and return lists and things.
    #       See xchat docs for interface ideas.
    # TODO: Fix nickname case rules and do sanity checking

    def __init__(self, conf):
        super(ServerState, self).__init__(conf)
        self.channels = {}

    def userLeft(self, words, line):
        """ Handles PARTs """
        nick = Address(words[0]).nick
        channel = words[2].lower()
        if nick.lower() == self.nick.lower():
            del self.channels[channel]
        else:
            self.channels[channel].remove(nick)

    def userQuit(self, words, line):
        """ Handles QUITs"""
        nick = Address(words[0]).nick
        for i in self.channels:
            if nick in self.channels[i]:
                self.channels[i].remove(nick)

    def userJoin(self, words, line):
        """ Handles JOINs """
        nick = Address(words[0]).nick
        channel = words[2][1:].lower()
        if nick.lower() == self.nick.lower():
            self.channels[channel] = []
            bot.who(words[2]) # TODO: replace with connection object shit.
        else:
            self.channels[channel].append(nick)

    def joinedChannel(self, words, line):
        """ Handles 352s (WHOs) """
        self.channels[words[3].lower()].append(words[7])

    def userNickchange(self, words, line):
        """ Handles NICKs """
        nick = Address(words[0]).nick
        newnick = words[2][1:]
        for i in self.channels:
            if nick in self.channels[i]:
                self.channels[i][self.channels[i].index(nick)] = newnick
        if nick.lower() == self.nick.lower():
            self.nick = newnick

    def userKicked(self, words, line):
        """ Handles KICKs """
        nick = words[3]
        channel = words[2].lower()
        self.channels[channel].remove(nick)

try:
    server = ServerState(sys.argv[1])
except (OSError, IndexError):
    print "Usage: %s <config>" % sys.argv[0]
    sys.exit(1)
server.connect()
s = server.sock


printer = ColourPrinter(server)
callers   = [Caller() for _ in range(GP_CALLERS + 2)] # Make 4 general purpose callers.
caller    = callers[1] # second caller is the general caller
bg_caller = callers[0] # first caller is the background caller
for c in callers: 
    c.start()
                                
# Decorators!
def command(triggers, args=None, key=str.lower, help=None):
    private = "!"
    public = "@"
    if type(triggers) == str:
        triggers = [triggers]
    triggers = map(key, triggers)
    def decorator(funct):
        @functools.wraps(funct)
        def _(*argv):
            try:
                message = Command(argv[-1])
                user = message.address

                if len(argv) == 3:
                    fargs = [argv[0], message]
                else:
                    fargs = [message]
            except IndexError:
                return
            else:
                if message.prefix in [private, public] and key(message.command) in triggers:
                    # Triggered.
                    # Set up output
                    if message.prefix == private:
                        output = printer.buffer(user.nick, "NOTICE")
                    else:
                        output = printer.buffer(message.context, "PRIVMSG")

                    # Check arguments
                    if args is not None:
                        try:
                            argument = message.text.split(" ", 1)[1]
                            fargs.extend(list(re.match(args, argument).groups()))
                        except (AttributeError, IndexError):
                            if help is not None:
                                with output as out:
                                    out += help
                            return
                    if inspect.isgeneratorfunction(funct):
                        with output as out:
                            for line in funct(*fargs):
                                out += line
                    else:
                        rval = funct(*fargs)
                        if rval is not None:
                            with output as out:
                                out += rval
        return _
    return decorator


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
                printer.message("Channel removed from autojoin.", x[2])
            else:
                self.chans = ",".join(self.chans.split(",") + [x[2].lower()])
                with open("./autojoin.txt", "w") as chanfile:
                    chanfile.write(self.chans)
                printer.message("Channel added to autojoin.", x[2])

aj = AutoJoin()

class Allbots:
    def __init__(self, bots, args = ""):
        self.bots = bots
        self.args = args
    def __call__(self, *data):
        pref = self.args + (" " * bool(self.args))
        for i in self.bots:
            i.send(pref + (" ".join(data)) + "\n")
    def __getattr__(self, d):
        return Allbots(self.bots, self.args + " " + d)
bot = Allbots([s])

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
        for line in iter(self.stdout.readline, ""):
            printer.message(line, Shell.target)
        Shell.activeShell = False
        if time.time() - started > 2:
            printer.message("[Shell] Program exited with code %s"%(self.shell.poll()), Shell.target)

    @classmethod
    def trigger(cls, words, line):
        if Address(words[0]).mask in server.admins and words[3] == ":$":
            args = line.split(" ", 4)[-1]
            cls.target = Message(line).context

            if not cls.activeShell:
                try:
                    shell = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, preexec_fn=os.setsid)
                except OSError:
                    printer.message("「 Shell Error 」 Command failed.", cls.target)
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

def authenticate(x, y):
    if "-i" in sys.argv:
        flag = sys.argv.index("-i")
        try:
            password = sys.argv[flag+1]
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
            if words[3][1:-1] == server.nick and words[3][-1] == "," and words[4] == "undo":
                # Delete the last command off the buffer
                self.curcmd.pop()
                printer.message("oh, sure", Message(line).context)
            elif self.codeReact:
                # Code is being added to the buffer.
                do = False
                if words[3] == ':"""':
                    # We've finished a multiline input, evaluate.
                    self.codeReact = 0
                    do = True
                else:
                    # Keep building
                    act = line.split(" ", 3)[-1]
                    if '"""' in act:
                        # Is the end of the input somewhere in the text?
                        act = act[:act.find('"""')]
                        self.codeReact = 0
                        do = True
                    self.curcmd += [act[1:]]
                if do:
                    # Do we execute yet?
                    try:
                        printer.message(eval(chr(10).join(self.curcmd), globals()))
                    except:
                        try:
                            exec(chr(10).join(self.curcmd), globals())
                        except BaseException, e:
                            printer.message("\x02「\x02\x0305 hah error \x0307 \x0315%s\x03\x02」\x02 "%(repr(e)[:repr(e).find("(")]) + str(e))
                    self.curcmd = []
                return
                
            elif words[3] == ':"""':
                # Enable code building.
                self.codeReact = 1
                return

            elif words[3] == ":>>>":

                act = line.split(" ", 3)[-1]
                ret = ""
                try:
                    act = str(act[act.index(" ")+1:]) # What the fuck?
                except ValueError:
                    act = ""
                if act and (act[-1] in "\\:" or act[0] in " \t@"):
                    self.curcmd += [act[:-1]] if act[-1] == "\\" else [act] #NTS add pre-evaluation syntax checking
                    return
                elif act and (act[0] + act[-1] == "\x02\x02"):
                    ret = str(act)[1:-1]
                    act = chr(10).join(self.curcmd)
                    self.curcmd = []
                elif self.curcmd:
                    act = chr(10).join(self.curcmd) + "\n" + act
                    self.curcmd = []
                try: 
                    assert "\n" not in act and not ret
                    output = eval(act, globals())
                    if output != None: 
                        printer.message(repr(output))
                except:
                    try:
                        exec(act, globals())
                        if ret: 
                            printer.message(repr(eval(ret, globals())))
                    except BaseException, e:
                        printer.message("\x02「\x02\x0305 oh wow\x0307 \x0315%s \x03\x02」\x02 "%(repr(e)[:repr(e).find("(")]) + str(e))      


class CallbackSystem(object):
    def __init__(self, config="callbacks.yaml"):
        pass

flist = {
         "privmsg" : [aj.trigger],
         "kick" : [
                    lambda x, y: bot.join(x[2]) if x[3].lower() == server.nick.lower() else None,
                  ],
         "invite" : [
                     aj.onInvite
                    ],
         "376" : [aj.join,
                  authenticate,
                  lambda *x: printer.start(),
                  lambda x, y: bot.mode(server.nick, "+B")
                  ],
         "ALL" : [],
        }

inline = {
         "privmsg" : [Shell.trigger, lambda x, y: printer.setTarget(Message(y).context), Interpretter().trigger],
         "ping" : [lambda x, y: bot.PONG(x[1])], # refactor pls.
         "quit" : [server.userQuit],
         "part" : [server.userLeft],
         "join" : [server.userJoin],
         "nick" : [server.userNickchange],
         "kick" : [server.userKicked],
         "352" : [server.joinedChannel],
         "ALL" : [],
         "DIE" : []
}

if "-f" in sys.argv:
    execfile("features.py")
    # Temporary.

class Pipeline(object):
    def __init__(self, descriptor=None):
        self.steps = []
        if descriptor:
            for step in descriptor.split("|"):
                self.add(step.strip())

    def __repr__(self):
        return " | ".join(self.steps)

    def add(self, step, pos=None):
        if pos:
            self.steps.insert(pos, step)
        else:
            self.steps.append(step)
            pos = len(self.steps) - 1
        return pos

    # syntactic sugar
    def __or__(self, step):
        self.add(step)
        return self

    def remove(self, pos):
        del self.steps[pos]

    def run(self):
        procs = {}
        procs[0] = subprocess.Popen(shlex.split(self.steps[0]), stdout=subprocess.PIPE)
        if len(self.steps) > 1:
            i = 1
            for p in self.steps[1:]:
                procs[i] = subprocess.Popen(shlex.split(p), stdin=procs[i-1].stdout, stdout=subprocess.PIPE)
                procs[i-1].stdout.close()
        output = procs[len(procs) - 1].communicate()[0]
        return output


class PipelineWithSubstitutions(Pipeline):
    def __init__(self, descriptor=None, substitutions=None):
        Pipeline.__init__(self, descriptor)
        self.substitutions = substitutions

    def add(self, step, pos=None):
        for sub in self.substitutions:
            step = re.sub(sub, self.substitutions[sub], step)
        Pipeline.add(self, step, pos)
        

class VolatilePipeline(Pipeline):
    def __repr__(self):
        return self.run()
        
class PipeWrapper(object):
    def __sub__(self, thing):
        pipe = VolatilePipeline()
        pipe.add(thing)
        return pipe
        
run = PipeWrapper()

buff = Buffer()

try:
    while connected and buff.append(s.recv(1024)):
        for line_w_spaces in buff:
            line_w_spaces = line_w_spaces.rstrip()
            line = line_w_spaces.split()

            if line[0] == "PING":
                msgType = line[0]
            else:
                msgType = line[1]

            callertimeout = [_.last for _ in callers[2:]]
            longestqueue = max(callers[2:], key=lambda x: x.work.qsize())
            if all(callertimeout) and longestqueue.work.qsize() > 50:
                print "All queues backed up: expanding."
                callers.append(Caller())
                callers[-1].start()
                callers.remove(longestqueue)
                longestqueue.terminate()
            for c in callers[2:]:
                ltime = c.last
                if ltime and time.time() - ltime > 8:
                    print "Caller is taking too long: forking."
                    callers.remove(c)
                    callers.append(Caller(c.dump()))
                    callers[-1].start()
                    print "Caller added."

            # TODO: add a guard on inline functions
            for funct in inline["ALL"]:
                funct(line_w_spaces)
            for funct in flist["ALL"]:
                caller.queue(funct, (line_w_spaces,))

            # Inline functions: execute immediately.
            for funct in inline.get(msgType.lower(), []):
                funct(line, line_w_spaces)

            for funct in flist.get(msgType.lower(), []):
                if Callback.isBackground(funct):
                    bg_caller.queue(funct, (line, line_w_spaces))
                elif Callback.isThreadsafe(funct):
                    min(callers, key=lambda x: x.work.qsize()).queue(funct, (line, line_w_spaces))
                else:
                    caller.queue(funct, (line, line_w_spaces))                    


finally:
    print "Bot ended; terminating threads."

    s.close()
    connected = 0
    print "Connection closed."

    for funct in inline["DIE"]:
        funct()
    print "Cleaned up."

    for c in callers: c.terminate()
    printer.terminate()
    print "Terminating threads..."

    printer.join()
    for c in callers: c.join()
    print "Threads terminated."
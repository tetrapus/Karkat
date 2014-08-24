import os
import signal
import subprocess
import threading
import time
import tempfile

from util.irc import Callback
from util.irc import Message
from bot.events import command

class Process(threading.Thread):
    def __init__(self, shell, target, invocator):
        self.shell = shell
        self.stdout = shell.stdout
        self.stdin = shell.stdin
        self.parent = invocator
        self.target = target
        threading.Thread.__init__(self)

    def run(self):
        started = time.time()
        lines = 0
        line_buffer = []
        outfile = None
        for line in iter(self.stdout.readline, b""):
            line_buffer.append(line)
            if lines < 25:
                line = line.decode('utf-8')
                self.parent.stream.message(line, self.target)
            elif lines == 25:
                outfile = tempfile.NamedTemporaryFile(delete=False)
                for i in line_buffer:
                    outfile.write(i)
                self.parent.stream.message("12bash│ Output truncated. Data written to %s" % outfile, self.target)
            else:
                outfile.write(line)
            lines += 1
        if outfile is not None:
            outfile.close()
        self.parent.activeShell = False
        if time.time() - started > 2:
            exitcode = self.shell.poll()
            self.parent.stream.message("%.2dbash│ Program exited with code %s"%(5 if exitcode else 12, exitcode), self.target)

class Shell(object):

    def __init__(self, server):
        self.stream = server.printer
        self.activeShell = False
        self.shellThread = None

        server.register("privmsg", self.trigger)
        server.register("privmsg", self.terminate)

    @Callback.inline
    def trigger(self, server, line):
        message = Message(line)
        user, target, text = message.address, message.context, message.text
        if server.is_admin(user.hostmask) and message.text.split()[0] == "$":
            args = text.split(" ", 1)[-1]

            if not self.activeShell:
                try:
                    shell = subprocess.Popen(args, 
                                             stdin=subprocess.PIPE, 
                                             stdout=subprocess.PIPE, 
                                             stderr=subprocess.STDOUT, 
                                             shell=True, 
                                             preexec_fn=os.setsid)
                except OSError:
                    server.printer.message("05bash│ Command failed.", target)
                    return
                self.activeShell = True
                self.shellThread = Process(shell, target, self)
                self.shellThread.start()
            else:
                self.shellThread.stdin.write((args + "\n").encode("utf-8"))
                self.shellThread.stdin.flush()

    @command("terminate", admin=True)
    def terminate(self, server, msg):
        if self.activeShell:
            os.killpg(self.shellThread.shell.pid, signal.SIGTERM)

__initialise__ = Shell
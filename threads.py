"""
This module contains the worker threads for Karkat's system.
"""

import sys
import threading
import time
import Queue
import re

from irc import Address, Callback
from text import lineify


class Work(Queue.Queue):
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
        Queue.Queue.__init__(self)

    def __iter__(self):
        """
        The object itself is iterable. Returns self.
        """
        return self

    def next(self):
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
        self.bot = connection.sock
        self.last = "#homestuck"

    def send(self, message):
        """
        Send data through the underlying socket.
        """
        self.bot.send(message)

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
        for message in [i for i in mesg.split("\n") if i]:
            self.work.put((method, recipient, message))

    def run(self):
        while True:
            for data in self.work:
                if not self.flush:
                    try:
                        self.send("%s %s :%s\r\n" % data)
                    except BaseException as err:
                        print >> sys.__stdout__, "Shit, error: %r\n" % err
                    else:
                        sys.__stdout__.write(">>> %s sent." % data[0])
                        if self.work.qsize():
                            sys.__stdout__.write(" %d items queued." %
                                                 self.work.qsize())
                        sys.__stdout__.write("\n")
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
            msg = self.defaultcolor(msg)
        Printer.message(self, msg, recipient, method)


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
        for funct, args in self.work:
            self.last = time.time()
            try:
                funct(*args)
            except BaseException:
                sys.__stdout__.write("Error in function %s%s\n" %
                                                            (funct.func_name,
                                                             args))
                sys.excepthook(*sys.exc_info())
            self.last = None
        assert self.work.qsize() == 0

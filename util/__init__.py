import threading

from . import services
from . import irc
from . import text
from . import dcc
from . import images
from . import files
from . import throttle
from . import database

# Taken straight from the xchat source. Thanks, xchat!
rfc_tolowertab = {'A': 'a', 'G': 'g', '\\': '|', '^': '~', 'D': 'd', 'C': 'c', 'T': 't', 'M': 'm', 'I': 'i', 'B': 'b', 'N': 'n', 'R': 'r', 'W': 'w', 'L': 'l', 'F': 'f', 'Y': 'y', '[': '{', 'P': 'p', 'S': 's', 'H': 'h', ']': '}', 'O': 'o', 'Q': 'q', 'U': 'u', 'V': 'v', 'J': 'j', 'K': 'k', 'E': 'e', 'Z': 'z', 'X': 'x'}

def cmp(a, b):
    return (a > b) - (a < b)

def rfc_nickkey(nick: str) -> str:
    return "".join(rfc_tolowertab.get(i, i) for i in nick)

def average(x):
    return float(sum(x))/len(x) if x else 0.00

# TODO: Move to submodule

class Job(threading.Thread):
    def __init__(self, job):
        threading.Thread.__init__(self)
        self.job = job
        self.answer = None

    def run(self):
        self.answer = self.job()

def parallelise(jobs):
    # Do all jobs in parallel and return their results.
    threads = [Job(i) for i in jobs]
    # Start all threads
    for i in threads: i.start()
    # Join all threads
    for i in threads: i.join()
    return [i.answer for i in threads]

__all__ = ["services", "irc", "text", "parallelise", "cmp", "rfc_nickkey", "average", "dcc", "images", "files", "throttle"]
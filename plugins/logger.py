import time

from bot.events import Callback
from threading import Thread


class Logger(Callback):
    def __init__(self, server):
        self.logs = []
        self.logpath = server.get_config_dir("log.txt")
        with open(self.logpath) as logfile:
            for line in logfile:
                try:
                    timestamp, text = line.split(" ", 1)
                    self.logs.append(float(timestamp), line.rstrip("\n"))
                except:
                    print("[Logger] Warning: Could not parse %s" % line)
        super().__init__(server)

    @Callback.inline
    def log(self, server, line) -> "ALL":
        timestamp = time.time()
        with open(self.logpath, "a") as logfile:
            logfile.write("%f %s\n" % (timestamp, line))
        self.logs.append((timestamp, line))
    

"""
    @command("scrollback", "\d+")
    def scrollback(self, server, message, lines:int):
        lines = int(lines)

"""
__initialise__ = Logger
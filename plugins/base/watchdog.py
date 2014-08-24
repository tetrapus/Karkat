import time
import threading

from bot.events import Callback
from util import scheduler


class Watchdog(Callback):
    
    def __init__(self, server):
        self.server = server
        self.last = time.time()
        self.lastcheck = time.time()
        self.watchdog = scheduler.schedule_after(90, self.check, stop_after=None)
        super().__init__(server)    

    @Callback.inline
    def reset_timer(self, server, line) -> "ALL":
        self.last = time.time()
        t = time.time() - self.last
        if t > 180:
            print("!!! Warning: Watchdog failure detected, spawning a fallback thread.")
            self.watchdog = FallbackWatchdog(self)
            self.watchdog.start()

    def check(self):
        self.lastcheck = time.time()
        t = time.time() - self.last
        if t > 270:
            self.server.restart = True
            self.server.connected = False
        elif t > 180:
            self.server.printer.raw_message("PING :♥")

class FallbackWatchdog(threading.Thread, object):
    def __init__(self, watchdog):
        self.watchdog = watchdog
        super().__init__()

    def run(self):
        while self.watchdog.server.connected:
            self.watchdog.check()
            time.sleep(90)


__initialise__ = Watchdog
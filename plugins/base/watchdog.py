"""
Checks that the connection to the server is still active.
"""

import time
import threading

from bot.events import Callback
from util.scheduler import schedule_after


class Watchdog(Callback):
    """
    Periodically test whether the connection is active, using the scheduler.
    """

    def __init__(self, server):
        self.server = server
        self.last = time.time()
        self.lastcheck = time.time()
        self.watchdog = schedule_after(90, self.check, stop_after=None)
        super().__init__(server)

    @Callback.inline
    def reset_timer(self, *_) -> "ALL":
        """
        Update last-heard time, and check whether the scheduler is alive.
        """
        self.last = time.time()
        delta = time.time() - self.last
        if delta > 180:
            print(
                "!!! Warning: Watchdog failure detected, spawning a fallback "
                "thread."
            )
            self.watchdog = FallbackWatchdog(self)
            self.watchdog.start()

    def check(self):
        """ Check whether we've heard from the server in the last 270s """
        self.lastcheck = time.time()
        delta = time.time() - self.last
        if delta > 270:
            self.server.restart = True
            self.server.connected = False
        elif delta > 180:
            self.server.printer.raw_message("PING :♥")


class FallbackWatchdog(threading.Thread, object):
    """ Use a separate thread to trigger the watchdog """
    def __init__(self, watchdog):
        self.watchdog = watchdog
        super().__init__()

    def run(self):
        while self.watchdog.server.connected:
            self.watchdog.check()
            time.sleep(90)


__initialise__ = Watchdog

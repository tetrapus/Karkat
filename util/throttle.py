""" Monitor resource usage and prevent overuse by waiting 
until it is no longer throttled. """

import time

class ThrottledResource(object):
    def __init__(self, limit, period=60, safety=2):
        self.history = []
        self.period = period
        self.limit = limit
        self.safety = safety

    def acquire(self):
        now = time.time()
        self.history = [i for i in self.history if i >= now - self.period]
        if len(self.history) + 1 > self.limit:
            time.sleep(self.history[0] + self.period - now + self.safety)
        self.history.append(time.time())
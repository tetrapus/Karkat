import time
import threading
import queue


class Scheduler(threading.Thread):
    _scheduler = None
    _schedlock = threading.Lock()

    def __new__(cls):
        if cls._scheduler is None:
            lock = cls._schedlock.acquire(blocking=False)
            if not lock:
                # We're not the new thread, so wait for it to be made
                with cls._schedlock:
                    pass
            else:
                # We're the new thread: make the scheduler.
                cls._scheduler = getattr(threading.Thread, "__new__")(cls) 
                threading.Thread.__init__(cls._scheduler)
                cls._scheduler.incoming = queue.PriorityQueue()
                cls._scheduler.start()
                cls._schedlock.release()
        return cls._scheduler
        
    def __init__(self):
        self.incoming = getattr(self, "incoming")

    def run(self):
        waiting = queue.PriorityQueue()

        while True:
            try:
                nextjob = waiting.get(block=False)
                wait = nextjob[0] - time.time()
            except queue.Empty:
                wait, nextjob = None, None
            try:
                if wait is not None and wait <= 0:
                    raise queue.Empty
                job = self.incoming.get(timeout=wait)
            except queue.Empty:
                # We've a job to run!
                nextjob[1](*nextjob[2], **nextjob[3])
            else:
                if job is None:
                    self.__class__._scheduler = None
                    return
                waiting.put(job)
                if nextjob is not None:
                    waiting.put(nextjob)

    def schedule(self, time, job, args, kwargs):
        self.incoming.put((time, job, args, kwargs))

    def stop(self):
        self.incoming.put(None)

class Job(object):
    def __init__(self, job, seconds=0, stop_after=1):
        self.job = job
        self.interval = seconds
        self.stop_after = stop_after
        self.stop = False

    def __call__(self, *args, **kwargs):
        if self.stop: 
            return
        scheduler = Scheduler()

        if self.stop_after != 1:
            scheduler.schedule(time.time() + self.interval, self, args, kwargs)
            if self.stop_after is not None:
                self.stop_after -= 1
        self.job(*args, **kwargs)

    def cancel(self):
        self.stop = True


def schedule(time, job, args=(), kwargs={}):
    scheduler = Scheduler()
    job = Job(job)
    scheduler.schedule(time, job, args, kwargs)
    return job

def schedule_after(seconds, job, args=(), kwargs={}, stop_after=1):
    scheduler = Scheduler()
    job = Job(job, seconds, stop_after)
    scheduler.schedule(time.time() + seconds, job, args, kwargs)
    return job

def stop():
    if Scheduler._scheduler:
        Scheduler().stop()
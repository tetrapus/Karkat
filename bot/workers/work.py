"""
Represents a work queue
"""
import queue
import threading


class Work(object):
    """
    This object is an iterable work queue.
    """

    TERM = object()

    def __init__(self):
        """
        Create a new Work Queue.
        """

        self._lock = threading.Lock()
        self.last = None
        self._queue = queue.Queue()

    def empty(self):
        """ Returns true if probably empty. """
        return self._queue.empty()

    def flush(self):
        """ Locks the queue and flushes all items from it. """
        jobs = []

        with self._lock:
            while not self.empty():
                jobs.append(self._queue.get())

        return jobs

    def get(self, *args, **kwargs):
        """ See queue.Queue.get """
        with self._lock:
            value = self._queue.get(*args, **kwargs)
            self.last = value
            return value

    def put(self, *args, **kwargs):
        """ See queue.Queue.put """
        with self._lock:
            self._queue.put(*args, **kwargs)

    def terminate(self):
        """ Queues the TERM sentinel, which breaks out of the iterator. """
        self.put(Work.TERM)

    def __iter__(self):
        """
        The object itself is iterable. Returns self.
        """
        return self

    def __next__(self):
        """
        Tells the queue a task is done and deques a new one.
        """
        with self._lock:
            value = self._queue.get()
            if value == Work.TERM:
                raise StopIteration
            else:
                self.last = value
                return value

    def __len__(self):
        return self._queue.qsize()

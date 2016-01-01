"""
Represents a work queue
"""
import queue
import threading


class Work(queue.Queue):
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
        queue.Queue.__init__(self)

    def flush(self):
        """ Locks the queue and flushes all items from it. """
        jobs = []

        with self._lock:
            while not self.empty():
                jobs.append(super().get())

        return jobs

    def get(self, *args, **kwargs):
        """ See queue.Queue.get """
        with self._lock:
            super().get(*args, **kwargs)

    def put(self, *args, **kwargs):
        """ See queue.Queue.put """
        with self._lock:
            super().put(*args, **kwargs)

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
            try:
                self.task_done()
            except ValueError:
                # This means first iteration. We don't really care.
                pass
            value = super().get()
            if value == Work.TERM:
                self.task_done()
                raise StopIteration
            else:
                self.last = value
                return value

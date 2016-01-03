"""
Workers work on work queues.
"""
from abc import ABCMeta, abstractmethod

import threading

from .work import Work


class JobNotAccepted(Exception):
    """ Raised if a worker cannot process a job and wishes to requeue it. """
    pass


class Worker(threading.Thread):
    """
    A thread which feeds tasks off of a queue.
    """
    __metaclass__ = ABCMeta

    def __init__(self, work=None):
        super().__init__()
        self.work = work or Work()
        self.flush = False

    @abstractmethod
    def process(self, job):
        """ Process a job on the work queue. """
        pass

    def run(self):
        """ Event loop. Use Worker.process to implement event handling. """

        for job in self.work:
            if self.flush:
                break

            try:
                self.process(job)
            except JobNotAccepted:
                # Requeue unaccepted job
                self.put(job)

        else:
            # Queue terminated normally
            return

        # Flush requested, reset state
        self.work.flush()

        # Restart queue
        return self.run()

    def clear(self):
        """
        Tell the worker to remove rather than process all the queued data.
        """
        self.flush = True

    def put(self, job):
        """
        Insert a job into the underlying queue.

        May not be processed by this worker.
        """
        self.work.put(job)

    def terminate(self):
        """
        Send a terminate signal to the underlying queue, which will terminate
        a worker process using this queue nondeterministically.

        No method is currently provided to directly terminate a thread; to
        implement this use case, manually ensure workers are 1:1 with work
        queues.
        """
        self.work.terminate()

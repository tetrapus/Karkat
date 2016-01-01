""" A Worker for executing arbitrary functions """
import sys
import time

from abc import ABC, abstractmethod

from ..events import Callback

from .work import Work
from .worker import Worker


def repr_call(funct, *args, **kwargs):
    """ Return the string that represents the value of this call. """
    # Positional args
    call_args = [repr(i) for i in args]
    # Keyword args
    call_args += ["%s=%r" % (key, value) for key, value in kwargs.items()]
    # Find name
    if hasattr(funct, 'name'):
        name = funct.name
    else:
        name = funct.__name__
    return "%s(%s)" % (name, ", ".join(call_args))


class Executor(ABC):
    """
    An executor has a single function, call, which dispatches function calls
    in a customised way.
    """
    @abstractmethod
    def call(self, funct, *args, **kwargs):
        """ Execute a function with the given parameters. """
        pass


class InlineExecutor(Executor):
    """
    Executes functions in the current thread synchronously, catching and
    reporting any exceptions.
    """
    def call(self, funct, *args, **kwargs):
        try:
            funct(*args, **kwargs)
        except BaseException:
            print(
                "Error in inline function %s" % repr_call(
                    funct, *args, **kwargs
                ),
                file=sys.stderr
            )
            sys.excepthook(*sys.exc_info())


class AsyncExecutor(Worker, Executor):
    """
    A worker thread for executing jobs asynchronously.
    """

    forklimit = 10

    def __init__(self, work=None):
        super().__init__(self, work=work)
        self.last = None
        self.lastf = (None, None)

    def call(self, funct, *args, **kwargs):
        """
        Queue a job.
        """
        # TODO: Integrate forking
        self.put((funct, args, kwargs))

    def dump(self):
        """
        Terminate the thread, returning a new queue containing the unprocessed
        jobs.
        Assumes 1:1 map between worker and work queue.
        """
        queue = Work()
        old_jobs = self.work.flush()
        for job in old_jobs:
            if Callback.isThreadsafe(job[0]):
                queue.put(job)
            else:
                # These functions aren't threadsafe, so we can't safely fork
                # off a queue with these tasks or we may end up with
                # time travel bugs.
                # FIXME: Make sure that new calls to this function are
                # redirected appropriately.
                self.put(job)

        self.terminate()
        return queue

    def process(self, job):
        """ Call a function in this worker thread. """
        funct, args, kwargs = job
        self.last = time.time()
        self.lastf = job
        try:
            funct(*args, **kwargs)
        except BaseException:
            print("Error in function %s" % repr_call(funct, *args, **kwargs))
            sys.excepthook(*sys.exc_info())
        self.last = None

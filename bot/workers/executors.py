"""
Objects for dispatching function calls.
"""

import sys
import time

from abc import ABC, abstractmethod
from functools import wraps
from threading import Lock

from .worker import Worker
from .work import Work

# TODO: Tests
# TODO: Types
# TODO: Define properties of start and terminate concretely
# TODO: Logging
# TODO: Implement Executor.join()
# TODO: Documentation


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

    @abstractmethod
    def start(self):
        """ Activate the executor. """
        pass

    @abstractmethod
    def terminate(self):
        """ Deactivate the executor. """
        pass

    @abstractmethod
    def join(self):
        """ Block until the executor has cleaned up. """
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

    def start(self):
        pass

    def terminate(self):
        pass

    def join(self):
        pass


class AsyncExecutor(Worker, Executor):
    """
    A worker thread for executing jobs asynchronously.
    """

    def call(self, funct, *args, **kwargs):
        """
        Queue a job.
        """
        self.put((funct, args, kwargs))

    @staticmethod
    def process(job):
        """ Call a function in this worker thread. """
        funct, args, kwargs = job
        try:
            funct(*args, **kwargs)
        except BaseException:
            print("Error in function %s" % repr_call(funct, *args, **kwargs))
            sys.excepthook(*sys.exc_info())

    # These methods are defined here to shut up pylint.

    def start(self):
        super().start()

    def terminate(self):
        super().terminate()

    def join(self):
        super().join()


class Flexicutor(AsyncExecutor):
    """
    An asynchronous executor which can be dumped mid-execution.

    This class implements threaded execution for callbacks with a defined
    mutual exclusion set. This is the default operating mode for callbacks,
    where calls are guaranteed to be executed synchronously within the class
    it is defined, but not relative to anything else.

    An attempt to add to the queue in a blocked state triggers a dump event if
    the worker has been executing for DUMP_THRESHHOLD seconds.
    """

    DUMP_THRESHHOLD = 45

    def __init__(self):
        super().__init__(self)
        self.last = None
        self.dump_lock = Lock()
        self.__mutex__ = set()
        self.next_thread = None

    def call(self, funct, *args, **kwargs):
        # Check we're blocked
        if self.last is not None:
            if time.time() - self.last > self.DUMP_THRESHHOLD:
                self.dump()

        # Route job to correct queue
        with self.dump_lock:
            if self.next_thread is None:
                # We have no thread to defer to, so weaken the mutex.
                self.__mutex__ = set()
            if funct not in self.__mutex__ and self.next_thread is not None:
                self.next_thread.call(self, funct, *args, **kwargs)
            else:
                self.put((funct, args, kwargs))

    def dump(self):
        """
        Terminate the worker and spawn a new one with the queue elements that
        are safe.

        Assumes 1:1 map between worker and work queue.
        """
        with self.dump_lock:
            self.next_thread = Flexicutor()
            old_jobs = self.work.flush()
            # Clearing the queue is atomic. This gives us two cases:
            # 1. The worker is executing a job, or blocked on us, in which case
            #    we must leave the mutex set of the last dequed job untouched.
            # 2. The worker has cleared the dump lock and is waiting for a job.
            #    However, we cannot detect the difference between this and the
            #    prior case! As it is idle, we let it retain jobs from the last
            #    mutex set, as this is probably not harmful.
            last_job = self.work.last
            self.__mutex__ = getattr(last_job, '__mutex__', {last_job})
            for job in old_jobs:
                # FIXME: EventHandler __mutex__ support
                if job[0] in self.__mutex__:
                    # We aren't assuming thread safety, so we must requeue
                    # the functions in the mutex set.
                    self.work.put(job)
                else:
                    self.next_thread.put(job)
            self.next_thread.start()
            # Once the blockage is clear, we can revive this worker.
            self.work.put((self.revive, (), {}))

    def revive(self):
        """ Kill the child and start accepting jobs. """
        with self.dump_lock:
            if self.next_thread is not None:
                # Kill off the thread
                self.next_thread.terminate()
                self.next_thread = None
            self.__mutex__ = set()

    def process(self, job):
        """ Call a function in this worker thread. """
        self.last = time.time()

        super().process(job)

        with self.dump_lock:
            self.last = None

    def terminate(self):
        if self.next_thread is not None:
            self.next_thread.terminate()
        super().terminate()

    def join(self):
        if self.next_thread is not None:
            self.next_thread.join()
        super().join()


class FlexicutorPool(Executor):
    """
    A statically sized pool of flexicutors.

    Sends calls to the least loaded pool. This Executor assumes that calls are
    threadsafe.
    """
    # TODO: Expand on demand. Currently does not attempt to guarantee
    # any queue-to-execution latency properties.

    def __init__(self, workers=2):
        super().__init__(self)
        self.executors = [Flexicutor() for _ in range(workers)]
        # NOTE: This is not threadsafe for multiple callers, but as it is just
        # a heuristic, we don't really care.
        self.serviced = [0 for i in range(workers)]
        self.waiting = [0 for i in range(workers)]

    def tracked(self, funct, worker_num):
        """
        Marks the function as threadsafe for the flexicutor, and updates our
        statistics once the function is serviced.
        """
        @wraps(funct)
        def tracked_function(*args, **kwargs):
            """ Wraps a function call with tracking information """
            funct(*args, **kwargs)
            self.serviced[worker_num] += 1
        tracked_function.__mutex__ = set()
        return tracked_function

    def call(self, funct, *args, **kwargs):
        # Calculate most timely worker thread
        worker_num, worker = min(
            enumerate(self.executors),
            key=lambda i, w: self.waiting[i] - self.serviced[i]
        )

        # Queue and track function
        self.waiting[worker_num] += 1
        worker.call(self.tracked(funct, worker_num), *args, **kwargs)

    def start(self):
        for executor in self.executors:
            executor.start()

    def terminate(self):
        for executor in self.executors:
            executor.terminate()

    def join(self):
        for executor in self.executors:
            executor.join()


class AsyncExecutorPool(Executor):
    """
    A dynamic pool of executors sharing a work pool.
    """
    # TODO: Finish this class.
    def __init__(self, min_size=2, max_size=4, queue=None):
        if queue is None:
            self.queue = Work()
        else:
            self.queue = queue

        self.executors = [AsyncExecutor(self.queue) for i in range(min_size)]
        self.min_size = min_size
        self.max_size = max_size
        raise NotImplementedError

    def call(self, funct, *args, **kwargs):
        pass

    def start(self):
        for executor in self.executors:
            executor.start()

    def terminate(self):
        for executor in self.executors:
            executor.terminate()

    def join(self):
        for executor in self.executors:
            executor.join()


class ExecutorMap(Executor):
    """
    Map functions with given properties to an associated executor.
    """

    def __init__(self, executor_map, key=id):
        self.executors = executor_map
        self.key = key

    def call(self, funct, *args, **kwargs):
        self.executors[self.key(funct)].call(funct, *args, **kwargs)

    def start(self):
        for executor in self.executors.values():
            executor.start()

    def terminate(self):
        for executor in self.executors.values():
            executor.terminate()

    def join(self):
        for executor in self.executors.values():
            executor.join()

from hypothesis import given
from hypothesis.strategies import lists, integers

from bot.workers.worker import Worker
from .test_work import list_to_queue


class MockWorker(Worker):
    """ Mock worker which saves the jobs it processes. """
    def __init__(self, queue):
        super().__init__(work=queue)
        self.processed = []

    def process(self, job):
        self.processed.append(job)

@given(lists(integers()))
def test_worker_empties_queue(jobs):
    """ A worker should empty a terminated queue. """
    queue = list_to_queue(jobs)
    worker = MockWorker(queue)
    worker.terminate()
    worker.run()
    assert worker.processed == jobs

# TODO: test more things

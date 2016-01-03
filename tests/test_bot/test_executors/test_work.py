""" Hypotheses and tests about work queues. """
from hypothesis import given
from hypothesis.strategies import lists, integers

from bot.workers.work import Work


def list_to_queue(lst):
    """ Turns a list into a queue """
    work = Work()
    for elem in lst:
        work.put(elem)
    return work


def work_queues(strategy=integers):
    """ Strategy for generating work queues. """
    return lists(strategy()).map(list_to_queue)


def test_default_work_empty():
    """ Work is empty by default """
    assert Work().empty()


@given(work_queues())
def test_get_len_returns_empty(queue):
    """ A queue length |q| big can be emptied with |q| get()s """
    for _ in range(len(queue)):
        queue.get()
    assert queue.empty()


@given(work_queues(), integers())
def test_put_not_empty(queue, i):
    """ Inserting an element into a queue makes it non-empty. """
    queue.put(i)
    assert not queue.empty()


@given(work_queues())
def test_flush_empties(queue):
    """ .flush() always results in an empty queue. """
    queue.flush()
    assert queue.empty()


@given(lists(integers()))
def test_flush_returns_all(ints):
    """ .flush() returns all the values in the queue. """
    queue = list_to_queue(ints)
    assert queue.flush() == ints


@given(work_queues())
def test_iterator_terminate(queue):
    """ Test that a terminated iterator runs |q| times. """
    length = len(queue)
    queue.terminate()
    for _ in queue:
        length -= 1
    assert length == 0
    assert queue.empty()

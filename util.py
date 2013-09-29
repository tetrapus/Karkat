import threading

class Job(threading.Thread):
    def __init__(self, job):
        threading.Thread.__init__(self)
        self.job = job
        self.answer = None

    def run(self):
        self.answer = self.job()

def parallelise(jobs):
    # Do all jobs in parallel and return their results.
    threads = [Job(i) for i in jobs]
    # Start all threads
    for i in threads: i.start()
    # Join all threads
    for i in threads: i.join()
    return [i.answer for i in threads]

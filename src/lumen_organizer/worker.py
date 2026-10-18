"""One worker, a completion queue, and explicit owner-thread result delivery."""

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Any

from .controller import Job
from .models import LumenError


@dataclass(frozen=True)
class Completion:
    job: Job
    value: Any = field(default=None, repr=False)
    error_code: str | None = None


class Worker:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lumen-worker")
        self.results = Queue()
        self.closed = False

    def submit(self, job: Job):
        if self.closed:
            raise LumenError("worker_closed")
        context = copy_context()
        def run():
            try:
                value = context.run(job.work)
                completion = Completion(job, value)
            except LumenError as exc:
                completion = Completion(job, error_code=exc.code)
            except BaseException:
                # Do not propagate note-bearing reprs, parser excerpts, or
                # arbitrary exception messages into Tk or persistent logs.
                completion = Completion(job, error_code="unexpected_error")
            self.results.put(completion)
        self.executor.submit(run)

    def drain(self):
        while True:
            try:
                yield self.results.get_nowait()
            except Empty:
                return

    def close(self):
        self.closed = True
        self.executor.shutdown(wait=False, cancel_futures=True)

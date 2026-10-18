import threading
import time
import unittest

from lumen_organizer.controller import Controller, Job
from lumen_organizer.worker import Worker
from .support import FictionalWorkspace, bounded_writes


class WorkerTests(unittest.TestCase):
    def test_work_is_background_and_state_acceptance_is_main_thread(self):
        with FictionalWorkspace() as w, bounded_writes(w.root):
            c, worker = Controller(w.state), Worker()
            owner = threading.get_ident()
            threads = []
            job = c._job("validation", lambda: threads.append(threading.get_ident()),
                         lambda value: threads.append(threading.get_ident()))
            worker.submit(job)
            try:
                completion = self.wait(worker)
                self.assertEqual(len(threads), 1)
                self.assertNotEqual(threads[0], owner)
                c.complete(completion.job, completion.value, completion.error_code)
                self.assertEqual(threads[-1], owner)
            finally:
                worker.close()

    def wait(self, worker):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            for completion in worker.drain():
                return completion
            time.sleep(0.01)
        self.fail("Worker did not complete.")

    def test_arbitrary_exception_text_not_forwarded(self):
        worker = Worker()
        def fail():
            raise RuntimeError("PRIVATE-FICTITIOUS-NOTE-MARKER")
        try:
            worker.submit(Job("validation", 0, fail, lambda value: None))
            result = self.wait(worker)
            self.assertEqual(result.error_code, "unexpected_error")
            self.assertNotIn("PRIVATE-FICTITIOUS", repr(result))
        finally:
            worker.close()

    def test_fictional_write_audit_context_propagates_to_worker(self):
        with FictionalWorkspace() as w, bounded_writes(w.root):
            worker = Worker()
            try:
                job = Job("validation", 0, lambda: (w.root.parent / "prohibited-worker.tmp").write_bytes(b"fictional"), lambda value: None)
                worker.submit(job)
                result = self.wait(worker)
                self.assertEqual(result.error_code, "unexpected_error")
                self.assertFalse((w.root.parent / "prohibited-worker.tmp").exists())
            finally:
                worker.close()

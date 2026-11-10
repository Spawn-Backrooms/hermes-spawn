import unittest
import threading
from unittest.mock import Mock, patch

from tests.support import load

lease = load("lease")
State = load("state").State
SpawnError = load("spawn_client").SpawnError


class FakeStop:
    def __init__(self):
        self.stopped = False
        self.delays = []
    def is_set(self):
        return self.stopped
    def set(self):
        self.stopped = True
    def wait(self, delay):
        self.delays.append(delay)
        if len(self.delays) > 10:
            raise AssertionError("Lease did not stop promptly")
        return self.stopped


class LeaseTests(unittest.TestCase):
    def setUp(self):
        self.jobs = Mock()
        self.jobs.state = State()
        self.jobs.config = lambda key, default=None: default
        self.jobs.state.set("active", "chat", {"job_id": "job", "lease_expires_at_ms": 2000000})
        self.keeper = lease.LeaseKeeper(self.jobs)

    def run_loop(self):
        stop = FakeStop()
        self.keeper.workers["job"] = (stop, Mock())
        with patch.object(lease.time, "time", return_value=1000):
            self.keeper._run("job", "chat", stop)
        self.assertNotIn("job", self.keeper.workers)
        return stop

    def test_interval_is_bounded_and_requires_known_future_expiry(self):
        self.assertEqual(15, lease.LeaseKeeper.interval({"lease_expires_at_ms": 1001000}, now=1000))
        self.assertEqual(300, lease.LeaseKeeper.interval({"lease_expires_at_ms": 3000000}, now=1000))
        for active in ({}, {"lease_expires_at_ms": 999000}):
            with self.subTest(active=active), self.assertRaises(SpawnError):
                lease.LeaseKeeper.interval(active, now=1000)

    def test_three_failures_stop_without_resume(self):
        self.jobs.heartbeat.side_effect = SpawnError("transport_error", uncertain=True)
        stop = self.run_loop()
        self.assertEqual(3, self.jobs.heartbeat.call_count)
        self.assertEqual(3, len(stop.delays))
        self.jobs.heartbeat.assert_called_with("job", "chat", background=True)
        self.jobs.progress.assert_not_called()
        self.jobs.accept.assert_not_called()
        self.assertIn("transport_error", self.jobs.state.get("active", "chat")["warning"])

    def test_expired_or_pending_stops_after_first_failure(self):
        for code in ("LEASE_EXPIRED", "pending_outcome", "not_signed_in", "BETA_TOKEN_REQUIRED"):
            with self.subTest(code=code):
                self.jobs.heartbeat.reset_mock()
                self.jobs.heartbeat.side_effect = SpawnError(code)
                self.run_loop()
                self.assertEqual(1, self.jobs.heartbeat.call_count)
                self.jobs.progress.assert_not_called()

    def test_no_active_job_does_no_work(self):
        self.jobs.state.set("active", "chat", None)
        self.run_loop()
        self.jobs.heartbeat.assert_not_called()

    def test_disabled_keeper_does_no_work(self):
        self.jobs.config = lambda key, default=None: False
        self.run_loop()
        self.jobs.heartbeat.assert_not_called()

    def test_start_is_idempotent_and_stop_signals_worker(self):
        with patch.object(lease.threading, "Thread") as thread:
            self.keeper.start("job", "chat")
            stop = self.keeper.workers["job"][0]
            self.keeper.start("job", "chat")
            thread.assert_called_once()
            thread.return_value.start.assert_called_once()
            self.assertTrue(thread.call_args.kwargs["daemon"])
            self.keeper.stop("job")
            self.assertTrue(stop.is_set())
            self.assertNotIn("job", self.keeper.workers)

    def test_start_after_close_creates_no_thread(self):
        self.keeper.close()
        self.assertTrue(self.keeper.closed)
        self.assertTrue(self.jobs.background_stopped)
        with patch.object(lease.threading, "Thread") as thread:
            self.keeper.start("job", "chat")
            thread.assert_not_called()
        self.assertEqual({}, self.keeper.workers)

    def test_close_during_blocked_snapshot_prevents_renewal(self):
        from tests.fake_jobs import FakeSpawn
        server = FakeSpawn()
        jobs = load("jobs").Jobs(client=server, config=lambda key, default=None: False if key == "lease_keeper" else default)
        jobs.accept({"job_id": "job-123"}, "chat", load("envelopes").terms(server.job))
        keeper = lease.LeaseKeeper(jobs)
        jobs.keeper = keeper
        entered, release = threading.Event(), threading.Event()
        original_snapshot = jobs.snapshot
        errors = []
        def blocked_snapshot(job_id):
            entered.set()
            if not release.wait(timeout=3):
                raise AssertionError("Test did not release snapshot")
            return original_snapshot(job_id)
        def renew():
            try:
                jobs.heartbeat("job-123", "chat", background=True)
            except Exception as exc:
                errors.append(exc)
        before = len(server.mutations())
        with patch.object(jobs, "snapshot", side_effect=blocked_snapshot):
            worker = threading.Thread(target=renew, daemon=True)
            worker.start()
            try:
                self.assertTrue(entered.wait(timeout=3))
                keeper.close()
                self.assertTrue(jobs.background_stopped)
            finally:
                release.set()
                worker.join(timeout=3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(before, len(server.mutations()))
        self.assertEqual(1, len(errors))
        self.assertIsInstance(errors[0], SpawnError)
        self.assertEqual("plugin_unloaded", errors[0].code)
        self.assertIsNone(jobs.state.get("pending", "job-123"))

    def test_close_signals_and_joins_workers(self):
        first, second = FakeStop(), FakeStop()
        thread1, thread2 = Mock(), Mock()
        self.keeper.workers = {"a": (first, thread1), "b": (second, thread2)}
        self.keeper.close()
        self.assertTrue(first.is_set())
        self.assertTrue(second.is_set())
        self.assertEqual({}, self.keeper.workers)
        thread1.join.assert_called_once_with(timeout=0.1)
        thread2.join.assert_called_once_with(timeout=0.1)
        self.jobs.progress.assert_not_called()


if __name__ == "__main__":
    unittest.main()

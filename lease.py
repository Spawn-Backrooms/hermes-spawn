"""Scoped, stoppable lease renewal. Never accepts or resumes a job in background."""
import contextvars
import threading
import time
from .spawn_client import SpawnError


class LeaseKeeper:
    def __init__(self, jobs):
        self.jobs = jobs
        self.lock = threading.RLock()
        self.workers = {}
        self.closed = False

    @staticmethod
    def interval(active, now=None):
        now = time.time() if now is None else now
        expires = active.get("lease_expires_at_ms") if active else None
        if not isinstance(expires, (int, float)):
            raise SpawnError("lease_ttl_unknown", "No lease expiry returned; automatic renewal is paused.")
        remaining = expires / 1000 - now
        if remaining <= 0:
            raise SpawnError("LEASE_EXPIRED", "Lease expired; explicit progress is required to resume.")
        return max(15, min(300, remaining / 3))

    def start(self, job_id, conversation):
        with self.lock:
            if self.closed or job_id in self.workers:
                return
            stop = threading.Event()
            # Preserve Hermes's request/profile/secret scope in the renewal thread.
            context = contextvars.copy_context()
            thread = threading.Thread(target=context.run, args=(self._run, job_id, conversation, stop), name="spawn-lease", daemon=True)
            self.workers[job_id] = (stop, thread)
            thread.start()

    def _run(self, job_id, conversation, stop):
        failures = 0
        try:
            while not stop.is_set():
                active = self.jobs.state.get("active", conversation)
                if not active or active["job_id"] != job_id:
                    break
                if not self.jobs.config("lease_keeper", True):
                    break
                try:
                    delay = self.interval(active)
                except SpawnError as exc:
                    self._warn(conversation, job_id, exc.code)
                    break
                if stop.wait(delay):
                    break
                try:
                    self.jobs.heartbeat(job_id, conversation, background=True)
                    failures = 0
                except SpawnError as exc:
                    failures += 1
                    if failures >= 3 or exc.code in {"LEASE_EXPIRED", "lease_changed", "not_signed_in", "BETA_TOKEN_REQUIRED", "pending_outcome"}:
                        self._warn(conversation, job_id, exc.code)
                        break
                except Exception:
                    failures += 1
                    if failures >= 3:
                        self._warn(conversation, job_id, "lease_refresh_failed")
                        break
        finally:
            with self.lock:
                if self.workers.get(job_id, (None,))[0] is stop:
                    self.workers.pop(job_id, None)

    def _warn(self, conversation, job_id, code):
        active = self.jobs.state.get("active", conversation)
        if active and active["job_id"] == job_id:
            self.jobs.state.set("active", conversation, {**active, "warning": "Lease renewal stopped: " + code})
        self.jobs.notify(job_id, warning=code)

    def stop(self, job_id):
        with self.lock:
            worker = self.workers.pop(job_id, None)
            if worker:
                worker[0].set()

    def close(self):
        self.jobs.background_stopped = True
        with self.lock:
            self.closed = True
            workers = list(self.workers.values())
            self.workers.clear()
        for stop, _ in workers:
            stop.set()
        for _, thread in workers:
            if thread is not threading.current_thread():
                thread.join(timeout=0.1)

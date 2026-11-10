"""Conversation-separated state plus serialization shared with the lease keeper."""
import copy
import threading

from .envelopes import digest
from .spawn_client import SpawnError


def conversation_key(kwargs, *, required=False):
    value = kwargs.get("conversation_id") or kwargs.get("session_id")
    if not value and required:
        raise SpawnError("session_required", "Run this action in a Hermes conversation.")
    return str(value or "read-only")


class State:
    def __init__(self, backend=None):
        self.backend = backend
        self.memory = {}
        self.lock = threading.RLock()
        self.job_locks = {}
        self.preflights = {}

    def get(self, kind, key, default=None):
        with self.lock:
            name = kind + ":" + digest(key)
            value = self.backend.get(name, default) if self.backend else self.memory.get(name, default)
            return copy.deepcopy(value)

    def set(self, kind, key, value):
        with self.lock:
            name = kind + ":" + digest(key)
            if self.backend:
                self.backend.set(name, value)
            else:
                self.memory[name] = copy.deepcopy(value)

    def for_job(self, job_id):
        with self.lock:
            return self.job_locks.setdefault(job_id, threading.RLock())

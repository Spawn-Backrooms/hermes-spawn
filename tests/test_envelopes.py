import copy
import unittest

from tests.support import load

envelopes = load("envelopes")
state = load("state")
SpawnError = load("spawn_client").SpawnError


def snapshot():
    return {"job_id": "job-123", "installation_id": "install_7", "order_hash": "a" * 64, "quote_hash": "b" * 64,
            "revision": 17, "grant_epoch": 4, "lease_generation": 8,
            "quote": {"offer_revision": 9, "input_manifest_hashes": ["c" * 64, "d" * 64]}}


class EnvelopeTests(unittest.TestCase):
    def test_exact_current_snapshot_accept_pins(self):
        job = snapshot()
        args = envelopes.command_args(job, "accept")
        self.assertEqual({"job_id", "envelope", "offer_revision", "grant_epoch"}, set(args))
        self.assertEqual(9, args["offer_revision"])
        self.assertEqual(4, args["grant_epoch"])
        expected = {"idempotency_key": envelopes.stable_key("install_7", "job-123", "accept", 17, {}),
                    "expected_revision": 17, "order_hash": "a" * 64, "quote_hash": "b" * 64,
                    "input_manifest_hashes": ["c" * 64, "d" * 64]}
        self.assertEqual(expected, args["envelope"])

    def test_revision_and_lease_follow_fresh_snapshot(self):
        job = snapshot()
        old = envelopes.command_args(job, "progress", {"message": "Working"})
        job.update(revision=18, lease_generation=10)
        fresh = envelopes.command_args(job, "progress", {"message": "Working"})
        self.assertEqual(18, fresh["envelope"]["expected_revision"])
        self.assertEqual(10, fresh["lease_generation"])
        self.assertNotEqual(old["envelope"]["idempotency_key"], fresh["envelope"]["idempotency_key"])
        self.assertEqual("Working", fresh["message"])

    def test_resume_adds_current_grant(self):
        args = envelopes.command_args(snapshot(), "resume")
        self.assertEqual(4, args["grant_epoch"])
        self.assertEqual(8, args["lease_generation"])

    def test_retries_and_argument_order_have_identical_keys(self):
        first = envelopes.envelope(snapshot(), "progress", {"a": 1, "b": {"x": "é", "y": 2}})
        retry = envelopes.envelope(snapshot(), "progress", {"b": {"y": 2, "x": "é"}, "a": 1})
        self.assertEqual(first, retry)
        for changed in (envelopes.envelope(snapshot(), "submit", {"a": 1}), envelopes.envelope(snapshot(), "progress", {"a": 2})):
            self.assertNotEqual(first["idempotency_key"], changed["idempotency_key"])

    def test_keys_are_bounded_even_for_maximum_ids(self):
        job = snapshot()
        job.update(job_id="j" * 128, installation_id="i" * 128)
        key = envelopes.envelope(job, "progress", {"text": "x" * 8192})["idempotency_key"]
        self.assertLessEqual(len(key.encode()), 160)
        self.assertRegex(key, r"^hermes:[a-f0-9]{64}$")

    def test_input_snapshot_not_mutated_or_aliased(self):
        job = snapshot()
        before = copy.deepcopy(job)
        result = envelopes.command_args(job, "accept")
        self.assertEqual(before, job)
        result["envelope"]["input_manifest_hashes"].append("e" * 64)
        self.assertEqual(before, job)

    def test_rejects_missing_and_invalid_snapshot_fields(self):
        for field, bad in (("revision", None), ("revision", True), ("revision", -1), ("revision", "3"), ("grant_epoch", False), ("lease_generation", -1), ("order_hash", "A" * 64), ("quote_hash", "f" * 63)):
            with self.subTest(field=field, bad=bad):
                job = snapshot()
                job[field] = bad
                with self.assertRaises(SpawnError) as caught:
                    envelopes.command_args(job, "progress")
                self.assertEqual("invalid_snapshot", caught.exception.code)
        for bad in (None, "a" * 64, ["c" * 64] * 11, ["bad"]):
            with self.subTest(hashes=bad):
                job = snapshot()
                job["quote"]["input_manifest_hashes"] = bad
                with self.assertRaises(SpawnError):
                    envelopes.terms(job)

    def test_invalid_identifiers(self):
        for value in ("", "a" * 129, "../job", "a/b", "a b", "é", None, 1):
            with self.subTest(value=value), self.assertRaises(SpawnError):
                envelopes.identifier(value)

    def test_extras_cannot_override_snapshot_identity_or_envelope(self):
        job = snapshot()
        try:
            args = envelopes.command_args(job, "progress", {"job_id": "attacker", "envelope": {"expected_revision": 0}})
        except SpawnError:
            return  # Rejecting reserved keys is also safe.
        self.assertEqual(job["job_id"], args["job_id"])
        self.assertEqual(job["revision"], args["envelope"]["expected_revision"])
        self.assertEqual(job["order_hash"], args["envelope"]["order_hash"])


class StateTests(unittest.TestCase):
    def test_conversation_scoping_and_required_session(self):
        self.assertEqual("preferred", state.conversation_key({"conversation_id": "preferred", "session_id": "fallback"}))
        self.assertEqual("fallback", state.conversation_key({"session_id": "fallback"}))
        self.assertEqual("read-only", state.conversation_key({}))
        with self.assertRaises(SpawnError) as caught:
            state.conversation_key({}, required=True)
        self.assertEqual("session_required", caught.exception.code)

    def test_memory_state_is_copied_and_namespaced(self):
        store = state.State()
        original = {"jobs": ["a"]}
        store.set("jobs", "conversation-a", original)
        original["jobs"].append("b")
        retrieved = store.get("jobs", "conversation-a")
        self.assertEqual({"jobs": ["a"]}, retrieved)
        retrieved["jobs"].clear()
        self.assertEqual({"jobs": ["a"]}, store.get("jobs", "conversation-a"))
        self.assertIsNone(store.get("jobs", "conversation-b"))
        self.assertIsNone(store.get("other", "conversation-a"))
        self.assertNotIn("conversation-a", next(iter(store.memory)))

    def test_job_lock_is_shared_only_for_same_job_and_reentrant(self):
        store = state.State()
        lock = store.for_job("a")
        self.assertIs(lock, store.for_job("a"))
        self.assertIsNot(lock, store.for_job("b"))
        with lock:
            self.assertTrue(lock.acquire(blocking=False))
            lock.release()

    def test_backend_state_uses_namespaced_hashed_keys(self):
        class Backend:
            def __init__(self):
                self.values = {}
            def get(self, key, default=None):
                return self.values.get(key, default)
            def set(self, key, value):
                self.values[key] = value
        backend = Backend()
        store = state.State(backend)
        store.set("kind", "conversation", {"value": [1]})
        self.assertIn("kind:" + envelopes.digest("conversation"), backend.values)
        value = store.get("kind", "conversation")
        value["value"].append(2)
        self.assertEqual({"value": [1]}, store.get("kind", "conversation"))


if __name__ == "__main__":
    unittest.main()

"""Stateful external boundary for public requests and revisioned proposals."""
import copy
import time

from tests.fake_jobs import FakeSpawn, SpawnError

NOW = int(time.time() * 1000)
DAY = 86_400_000


def open_request():
    return {
        "request_id": "request-7", "revision": 3, "request_hash": "c" * 64,
        "status": "open", "expires_at_ms": NOW + 3 * DAY,
        "created_at_ms": NOW, "title": "Signal Below",
        "summary": "Three connected dungeon rooms", "deliverable": "Offline game",
        "acceptance_criteria": ["The player can reach the exit"],
        "target_micro_usdc": "20000000", "currency": "USDC",
        "buyer": {"owner_id": "buyer-1", "project_id": "project-1"},
    }


def proposal_args():
    return {"request_id": "request-7", "proposal": {
        "scope": "Build Signal Below with three connected rooms",
        "deliverables": ["Offline browser game", "Source and test report"],
        "acceptance_criteria": ["Reach the locked exit with the key"],
        "deadline_at_ms": NOW + 4 * DAY, "expires_at_ms": NOW + 2 * DAY,
        "gross_micro_usdc": "20000000", "assumptions": ["Keyboard controls"],
        "estimate": {
            "own_work_micro_usdc": "10000000", "model_tools_micro_usdc": "1000000",
            "contingency_micro_usdc": "2000000",
            "children": [
                {"step_id": "art", "role": "art", "cap_micro_usdc": "4000000",
                 "deadline_at_ms": NOW + 3 * DAY, "result_contract": "pixel_grid_v1",
                 "source": {"kind": "estimate", "reference": "Art allowance", "expires_at_ms": NOW + 3 * DAY}},
                {"step_id": "qa", "role": "qa", "cap_micro_usdc": "2000000",
                 "deadline_at_ms": NOW + 3 * DAY, "result_contract": "text_v1",
                 "source": {"kind": "estimate", "reference": "Review allowance", "expires_at_ms": NOW + 3 * DAY}},
            ],
            "sources": [{"label": "Hermes work", "reference": "Bounded work estimate", "expires_at_ms": NOW + 3 * DAY}],
        },
    }}


class MemoryBackend:
    def __init__(self):
        self.values = {}

    def get(self, key, default=None):
        return copy.deepcopy(self.values.get(key, default))

    def set(self, key, value):
        self.values[key] = copy.deepcopy(value)


class ProposalServer(FakeSpawn):
    def __init__(self):
        super().__init__()
        self.request = open_request()
        self.proposals = {}
        self.unavailable = set()

    def call_tool(self, name, arguments=None):
        args = copy.deepcopy(arguments or {})
        if name in self.unavailable:
            self.calls.append((name, args))
            raise SpawnError(-32601, "Method not found")
        if name == "spawn_identity":
            self.calls.append((name, args))
            return {"installation_id": self.job["installation_id"], "grant_epoch": self.job["grant_epoch"], "client_id": "hermes"}
        if name == "spawn_open_jobs":
            self.calls.append((name, args))
            return {"requests": [copy.deepcopy(self.request)], "next_cursor": None}
        if name == "spawn_open_job":
            self.calls.append((name, args))
            assert args == {"request_id": self.request["request_id"]}
            return copy.deepcopy(self.request)
        if name == "spawn_propose_job":
            self.calls.append((name, args))
            key = args["idempotency_key"]
            if key in self.proposals:
                return copy.deepcopy(self.proposals[key])
            if args["request_revision"] != self.request["revision"] or args["request_hash"] != self.request["request_hash"]:
                raise SpawnError("OPEN_JOB_CHANGED")
            assert args["request_id"] == self.request["request_id"]
            assert args["request_revision"] == self.request["revision"]
            assert args["request_hash"] == self.request["request_hash"]
            assert all(c["reviewer"] == self.request["buyer"] for c in args["proposal"]["estimate"]["children"])
            result = {"request_id": "request-7", "proposal_id": "proposal-2", "proposal_hash": "d" * 64,
                      "request_revision": 3, "request_hash": "c" * 64,
                      "status": "submitted", "proposal": copy.deepcopy(args["proposal"])}
            self.proposals[key] = copy.deepcopy(result)
            if name in self.fail_once:
                raise self.fail_once.pop(name)
            return result
        if name == "spawn_job_proposal":
            self.calls.append((name, args))
            return {"request_id": args["request_id"], "proposal_id": args["proposal_id"],
                    "proposal_hash": "d" * 64, "request_revision": 3, "request_hash": "c" * 64,
                    "status": "declined", "proposal": proposal_args()["proposal"]}
        return super().call_tool(name, args)

    def proposal_writes(self):
        return [args for name, args in self.calls if name == "spawn_propose_job"]

"""All handlers return JSON; untrusted arguments never choose arbitrary MCP tools."""
import json
from .hooks import GATED
from .jobs import NOTICE
from .schemas import SCHEMAS, validate
from .spawn_client import SpawnError
from .state import conversation_key

WRITES = GATED | {"spawn_progress", "spawn_deliver_text", "spawn_deliver_files", "spawn_deliver_game_package"}


class Tools:
    def __init__(self, jobs, hooks):
        self.jobs, self.hooks = jobs, hooks

    def handler(self, name):
        def run(args, **kwargs):
            try:
                validate(args, SCHEMAS[name]["parameters"])
                conversation = conversation_key(kwargs, required=name in WRITES)
                approved = self.hooks.consume_preflight(name, args, conversation) if name in GATED else None
                if name == "spawn_status":
                    result = self.jobs.status()
                elif name == "spawn_open_jobs":
                    result = self.jobs.proposals.list(args.get("cursor"))
                elif name == "spawn_open_job":
                    result = self.jobs.proposals.detail(args["request_id"])
                elif name == "spawn_job_proposal":
                    result = self.jobs.proposals.status(args["request_id"], args["proposal_id"])
                elif name == "spawn_propose_job":
                    result = self.jobs.proposals.propose(args, conversation, approved)
                elif name == "spawn_find_backrooms":
                    result = self.jobs.commissions.discover(args)
                elif name == "spawn_draft_child_commissions":
                    result = self.jobs.commissions.draft(args, conversation, approved)
                elif name == "spawn_get_child_commissions":
                    result = self.jobs.commissions.status(args["job_id"], args["draft_id"])
                elif name == "spawn_jobs":
                    result = self.jobs.list_jobs(args.get("cursor"))
                elif name == "spawn_job":
                    result = self.jobs.job(args["job_id"], conversation)
                elif name == "spawn_assess":
                    result = self.jobs.client.call_tool("spawn_assess_job", args)
                elif name == "spawn_accept":
                    result = self.jobs.accept(args, conversation, approved)
                elif name == "spawn_progress":
                    result = self.jobs.progress(args, conversation)
                elif name == "spawn_deliver_text":
                    result = self.jobs.deliver(args, conversation)
                elif name == "spawn_deliver_files":
                    result = self.jobs.file_delivery.deliver(args, conversation)
                elif name == "spawn_deliver_game_package":
                    result = self.jobs.packages.deliver(args, conversation)
                elif name in {"spawn_submit", "spawn_abandon"}:
                    result = self.jobs.finish(name.removeprefix("spawn_"), args, conversation, approved)
                elif name == "spawn_earnings":
                    result = {**self.jobs.client.call_tool("spawn_get_earnings"), "notice": NOTICE, "withdrawals_available": False}
                elif name == "spawn_create_backroom":
                    result = self.jobs.create_room(args, conversation)
                elif name == "spawn_declare_services":
                    result = self.jobs.declare_services(args, conversation)
                else:
                    raise SpawnError("unknown_tool")
                return json.dumps({"ok": True, **result}, ensure_ascii=False)
            except SpawnError as exc:
                return json.dumps(exc.as_dict(), ensure_ascii=False)
            except Exception:
                return json.dumps({"ok": False, "error": "plugin_error", "message": "SPAWN could not complete this operation. Inspect the job before retrying; no success is assumed."})
        return run

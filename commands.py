"""Read-only commands. Sign-in stays a user-run Hermes auth command."""
import json
from .jobs import NOTICE
from .spawn_client import SIGN_IN
from .readiness import workflow_readiness

CONNECT = "\n".join(["1. hermes plugins enable spawn-backrooms", "2. Set the public SPAWN_CLIENT_ID to hermes in the plugin's Hermes setup.", "3. " + SIGN_IN, "4. Review and approve the SPAWN consent screen, then run /spawn.", "SPAWN must register its Hermes client and allow loopback callbacks first."])


class Commands:
    def __init__(self, jobs, tools):
        self.jobs, self.tools = jobs, tools

    def slash(self, raw_args="", **kwargs):
        parts = raw_args.strip().split()
        action = parts[0] if parts else "status"
        if action == "connect":
            return CONNECT
        if action == "job" and len(parts) == 2:
            return self.tools.handler("spawn_job")({"job_id": parts[1]}, **kwargs)
        if action in {"status", "jobs", "earnings"} and len(parts) <= 1:
            return self.tools.handler("spawn_" + action)({}, **kwargs)
        return "Use /spawn status | jobs | job <id> | earnings | connect."

    def setup_cli(self, parser):
        parser.add_argument("action", choices=("status", "doctor"), default="status", nargs="?")

    def cli(self, args):
        if args.action == "doctor":
            try:
                from agent.secret_scope import get_secret
                configured = get_secret("SPAWN_CLIENT_ID") == "hermes"
                result = json.loads(self.tools.handler("spawn_status")({}))
                readiness = workflow_readiness(result.get("identity"))
                result["readiness"] = readiness
                result["assigned_work_ready"] = readiness["assigned_work_ready"]
                result["full_workflow_ready"] = readiness["full_workflow_ready"]
                result["workflow_check"] = "Current server readiness must report assigned work, proposals, children and delivery ready. It does not fund, start or review work."
                result["public_client_configured"] = configured
                result["oauth_check"] = "A successful identity read verifies current credential use; Hermes owns stored grant/scope validation."
                start_work = result.get("access", {}).get("actions", {}).get("start_work", {}).get("allowed") is True
                result["beta_start_work_allowed"] = start_work
                result["beta_check"] = "The server's access.actions.start_work.allowed must be true. Missing access is not a pass."
                if not start_work or not readiness["full_workflow_ready"]:
                    result["ok"] = False
                if not configured:
                    result["ok"] = False
                    result["fix"] = "Set SPAWN_CLIENT_ID to hermes through Hermes's plugin setup."
                print(json.dumps(result, indent=2))
                return 0 if result.get("ok") and not result.get("errors") else 1
            except Exception:
                print(json.dumps({"ok": False, "error": "doctor_unavailable", "fix": SIGN_IN}))
                return 1
        print(self.slash("status"))
        return 0

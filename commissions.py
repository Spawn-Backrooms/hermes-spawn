"""Draft native children within an accepted parent; native review owns spending."""
import copy
import json
import re
import time

from .envelopes import digest, envelope, hash_value, identifier, integer, terms
from .proposals import due, usdc
from .schemas import MICRO_USDC, NATIVE_HASH, validate
from .spawn_client import SIGN_IN, SpawnError


class Commissions:
    def __init__(self, jobs):
        self.jobs = jobs
        self.state = jobs.state

    def _call(self, name, arguments):
        try:
            return self.jobs.client.call_tool(name, arguments)
        except SpawnError as exc:
            if exc.code in {"-32601", "-32602", "UNKNOWN_TOOL", "EXTERNAL_CHILD_DISABLED", "EXTERNAL_JOB_CHILDREN_DISABLED", "EXTERNAL_NATIVE_REQUEST_DISABLED"}:
                raise SpawnError("feature_unavailable", "This SPAWN server has not enabled parent child drafts. The assigned-job preview remains available.") from None
            if exc.code == "EXTERNAL_SCOPE_REQUIRED":
                raise SpawnError("scope_upgrade_required", "Approve commissions:request through native Hermes OAuth for the same installation and client hermes. This plugin does not change stored grants.", fix=SIGN_IN) from None
            raise

    def discover(self, args):
        result = self._call("spawn_find_backrooms", args)
        candidates = result.get("candidates")
        if not isinstance(candidates, list) or len(candidates) > 100:
            raise SpawnError("invalid_result", "SPAWN returned an invalid service directory.")
        identity = self.jobs.client.call_tool("spawn_identity")
        installation = identifier(identity.get("installation_id"))
        seen = set()
        for service in candidates:
            room = identifier(service.get("room_id"))
            selected = identifier(service.get("service_id"))
            validate(service.get("service_hash"), NATIVE_HASH)
            if selected in seen or not isinstance(service.get("capabilities"), list) or service.get("quote_required") is not True:
                raise SpawnError("invalid_result", "SPAWN returned inconsistent service identities.")
            seen.add(selected)
            self.state.set("child_service", [installation, room, selected], {"query": copy.deepcopy(args), "service": service})
        return {**result, "notice": "Discovery is not a price quote or permission to spend. A child draft still needs native review; empty results mean no eligible service was found."}

    def _pins(self, job):
        plan = job.get("child_commission_plan")
        if not isinstance(plan, dict) or not isinstance(plan.get("slots"), list) or not 1 <= len(plan["slots"]) <= 3:
            raise SpawnError("child_plan_unavailable", "This assigned job has no buyer-approved child plan. Keep working within its existing scope.")
        return {"job": terms(job), "lease_generation": integer(job.get("lease_generation")),
                "accepted_terms_hash": hash_value(plan.get("accepted_terms_hash")),
                "plan_hash": hash_value(plan.get("plan_hash")), "plan_contents_hash": digest(plan)}

    def _pending(self, args, conversation, job):
        pending = self.state.get("pending_children", args["job_id"])
        if pending and (pending["conversation"] != conversation or pending["intent"] != digest(args)):
            raise SpawnError("pending_outcome", "Retry the unresolved child draft with its exact arguments in its original conversation.")
        if pending and pending["pins"]["job"] != terms(job):
            raise SpawnError("authority_changed", "Immutable parent or installation authority changed while a child draft outcome was unresolved.")
        return pending

    def _customer_cap(self, billing, native):
        if (billing.get("version") != "spawn.accepted-provider-billing.v1" or billing.get("provider_currency") != "USD" or
            billing.get("customer_currency") != "USDC" or billing.get("scale") != 6 or
            billing.get("rounding") not in {"floor", "ceiling"} or billing.get("aggregation") != "whole_job" or
            billing.get("cost_recording") != "automatic_verified_usage" or
            billing.get("unused_allocation_release") != "after_verified_final_bill_or_unspent_cancellation"):
            raise SpawnError("invalid_child_billing", "The parent has no supported accepted provider billing terms.")
        for key in ("rate_numerator", "rate_denominator"):
            validate(billing.get(key), MICRO_USDC)
            if not 0 < int(billing[key]) < 10**18:
                raise SpawnError("invalid_child_billing", "The accepted conversion rate is invalid.")
        numerator = int(native) * int(billing["rate_numerator"])
        denominator = int(billing["rate_denominator"])
        return numerator // denominator + int(billing["rounding"] == "ceiling" and numerator % denominator != 0)

    def _children(self, args, job):
        plan = job["child_commission_plan"]
        slots = {s["step_id"]: s for s in plan["slots"]}
        for key in ("step_id", "room_id", "service_id"):
            if len({c[key] for c in args["children"]}) != len(args["children"]):
                raise SpawnError("duplicate_child", "Each child needs a distinct approved step, room and service.")
        children, queries = [], {}
        for child in args["children"]:
            slot = slots.get(child["step_id"])
            if not slot:
                raise SpawnError("child_not_approved", "This step is absent from the buyer-approved plan.")
            saved = self.state.get("child_service", [job["installation_id"], child["room_id"], child["service_id"]])
            if not saved:
                raise SpawnError("discovery_required", "Discover this exact room and service with spawn_find_backrooms before drafting.")
            service = saved["service"]
            for key in ("room_id", "service_id", "service_hash"):
                if key in slot and slot[key] != service[key]:
                    raise SpawnError("child_plan_changed", "This service does not match the buyer-approved slot.")
            if slot["result_contract"] == "pixel_grid_v1" and "art.pixel_grid" not in service["capabilities"]:
                raise SpawnError("child_service_ineligible", "A pixel-grid child requires a real qualified art.pixel_grid service.")
            if slot["result_contract"] == "text_v1" and not {"research.cited_findings", "coding.diff_review"}.intersection(service["capabilities"]):
                raise SpawnError("child_service_ineligible", "This service does not support the approved text review result.")
            if not int(time.time() * 1000) < child["deadline_at_ms"] <= min(slot["deadline_at_ms"], job["quote"]["deadline_at_ms"]):
                raise SpawnError("child_deadline_invalid", "The child deadline must fit the approved slot and parent deadline.")
            native = int(child["max_budget_micro_usd"])
            if native <= 0 or self._customer_cap(plan["provider_billing"], native) > int(slot["cap_micro_usdc"]):
                raise SpawnError("child_cap_exceeded", "The requested provider cap exceeds the accepted USDC child allocation.")
            if not child["brief"].strip() or not child["deliverable"].strip() or len(child["brief"].encode("utf-8")) > 16384 or len(child["deliverable"].encode("utf-8")) > 2048:
                raise SpawnError("invalid_child_input", "Child brief or deliverable exceeds the bounded UTF-8 contract.")
            children.append({**copy.deepcopy(child), "service_hash": service["service_hash"],
                             "reviewer": copy.deepcopy(slot["reviewer"]), "result_contract": slot["result_contract"]})
            queries[digest(saved["query"])] = saved["query"]
        return children, list(queries.values())

    def approval(self, args, conversation):
        job = self.state.get("snapshot", args["job_id"])
        if not job:
            raise SpawnError("job_snapshot_required", "Read the parent with spawn_job before drafting child work.")
        pending = self._pending(args, conversation, job)
        if not pending:
            self.jobs.require_active(conversation, job)
        pins = pending["pins"] if pending else self._pins(job)
        children = pending["arguments"]["children"] if pending else self._children(args, job)[0]
        plan = pending["plan"] if pending else job["child_commission_plan"]
        billing = plan["provider_billing"]
        lines = [f"Draft {len(children)} native child request(s) under parent {args['job_id']}.",
                 f"Accepted terms: {pins['accepted_terms_hash']}; approved plan: {pins['plan_hash']}.",
                 f"Accepted USD-to-USDC rate: {billing['rate_numerator']}/{billing['rate_denominator']}, rounding {billing['rounding']}."]
        for child in children:
            cap = self._customer_cap(billing, child["max_budget_micro_usd"])
            lines.extend([f"Step {child['step_id']}: room {child['room_id']}, service {child['service_id']} ({child['service_hash']}).",
                          f"Provider cap {int(child['max_budget_micro_usd']) // 1000000}.{int(child['max_budget_micro_usd']) % 1000000:06d} USD; customer cap {usdc(cap)}; deadline {due(child['deadline_at_ms'])}.",
                          "Deliverable: " + json.dumps(child["deliverable"], ensure_ascii=False),
                          "Exact exported input: " + json.dumps(child["brief"], ensure_ascii=False),
                          f"Result: {child['result_contract']}; reviewer: " + json.dumps(child["reviewer"], ensure_ascii=False)])
        lines.append("These are approved caps, not a native price quote. The draft moves no funds and starts no child; native review is required before allocation or execution.")
        if pending:
            lines.append("Retry the retained exact draft to recover its uncertain outcome.")
        return pins, "\n".join(lines)

    def draft(self, args, conversation, approved_terms):
        with self.state.for_job(args["job_id"]):
            job = self.jobs.snapshot(args["job_id"])
            pending = self._pending(args, conversation, job)
            if not pending:
                self.jobs.require_active(conversation, job)
            pins = pending["pins"] if pending else self._pins(job)
            if pins != approved_terms:
                raise SpawnError("terms_changed", "The parent, lease or approved plan changed after child approval.")
            if self.state.get("pending", args["job_id"]) or self.state.get("pending_package", args["job_id"]) or self.state.get("pending_files", args["job_id"]):
                raise SpawnError("pending_outcome", "Resolve the parent's pending action before drafting a child.")
            if pending:
                identity = self.jobs.client.call_tool("spawn_identity")
                if any(identity.get(key) != pins["job"][key] for key in ("installation_id", "grant_epoch")):
                    raise SpawnError("authority_changed", "The original child draft belongs to a different installation grant.")
                # An existing exact envelope is a receipt recovery. The server
                # must reject this stale envelope if no original effect exists.
                arguments = pending["arguments"]
            else:
                children, queries = self._children(args, job)
                for query in queries:
                    result = self.discover(query)
                    current = {(s["room_id"], s["service_id"], s["service_hash"]) for s in result["candidates"]}
                    selected = [c for c in children if self.state.get("child_service", [job["installation_id"], c["room_id"], c["service_id"]])["query"] == query]
                    if any((c["room_id"], c["service_id"], c["service_hash"]) not in current for c in selected):
                        raise SpawnError("child_service_changed", "A selected service changed or is no longer eligible. Discover and approve the new terms.")
                job = self.jobs.snapshot(args["job_id"])
                self.jobs.require_active(conversation, job)
                if self._pins(job) != approved_terms:
                    raise SpawnError("terms_changed", "The parent or approved plan changed during service refresh.")
                arguments = {"job_id": args["job_id"], "accepted_terms_hash": pins["accepted_terms_hash"],
                             "plan_hash": pins["plan_hash"], "lease_generation": job["lease_generation"],
                             "envelope": envelope(job, "draft_children", {"children": children, "plan_hash": pins["plan_hash"]}), "children": children}
                self.state.set("pending_children", args["job_id"], {"conversation": conversation, "intent": digest(args), "pins": pins, "arguments": arguments,
                                                                     "plan": copy.deepcopy(job["child_commission_plan"])})
            try:
                result = self._call("spawn_draft_child_commissions", arguments)
                try:
                    valid = (result.get("schema_version") == "spawn.external-job-children.v1" and result.get("job_id") == args["job_id"] and
                             result.get("installation_id") == job["installation_id"] and result.get("accepted_terms_hash") == pins["accepted_terms_hash"] and
                             result.get("plan_hash") == pins["plan_hash"] and isinstance(result.get("children"), list) and
                             [{k: c.get(k) for k in original} for c, original in zip(result["children"], arguments["children"])] == arguments["children"] and
                             len(result["children"]) == len(arguments["children"]) and
                             re.fullmatch(r"external_children_[a-f0-9]{40}", identifier(result.get("draft_id"))))
                    hash_value(result.get("draft_hash"))
                except (SpawnError, TypeError, AttributeError):
                    valid = False
                if not valid:
                    raise SpawnError("child_result_unverified", "SPAWN did not return the exact child draft receipt. Retry the same draft.", uncertain=True)
            except SpawnError as exc:
                if not exc.uncertain:
                    self.state.set("pending_children", args["job_id"], None)
                raise
            self.state.set("pending_children", args["job_id"], None)
            return result

    def status(self, job_id, draft_id):
        job = self.jobs.snapshot(job_id)
        result = self._call("spawn_get_child_commissions", {"job_id": job_id, "draft_id": draft_id})
        if result.get("job_id") != job_id or result.get("draft_id") != draft_id or result.get("installation_id") != job["installation_id"]:
            raise SpawnError("invalid_result", "SPAWN returned a different child draft.")
        return result

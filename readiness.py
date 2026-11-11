"""Read-only workflow readiness from the authenticated server identity."""
from .envelopes import identifier, integer
from .spawn_client import SpawnError

FEATURES = ("assigned_work", "proposals", "children", "delivery")
STATES = {"ready", "disabled", "scope_required", "unavailable"}
LIMITS = ("max_artifacts", "max_file_bytes", "max_game_package_bytes", "max_child_brief_bytes")


def workflow_readiness(identity):
    unavailable = {"available": False, "assigned_work_ready": False, "full_workflow_ready": False}
    if not isinstance(identity, dict) or "workflow_readiness" not in identity:
        return {**unavailable, "error": "readiness_unavailable",
                "message": "This server did not report workflow readiness. Identity alone does not establish proposal, child or delivery support."}
    try:
        value = identity["workflow_readiness"]
        if (not isinstance(value, dict) or value.get("schema_version") != "spawn.external-work-readiness.v1" or
            identifier(value.get("installation_id")) != identifier(identity.get("installation_id")) or
            integer(value.get("grant_epoch")) != integer(identity.get("grant_epoch")) or
            integer(value.get("observed_at_ms")) == 0):
            raise ValueError("readiness authority")
        features = {}
        for name in FEATURES:
            feature = value["features"][name]
            if not isinstance(feature, dict) or feature.get("state") not in STATES:
                raise ValueError("readiness state")
            for field in ("reasons", "required_scopes", "missing_scopes"):
                items = feature[field]
                if not isinstance(items, list) or any(not isinstance(item, str) or not item for item in items):
                    raise ValueError("readiness reasons or scopes")
            if (not set(feature["missing_scopes"]).issubset(feature["required_scopes"]) or
                feature["state"] == "ready" and feature["missing_scopes"]):
                raise ValueError("readiness scope contradiction")
            features[name] = {key: feature[key] for key in ("state", "reasons", "required_scopes", "missing_scopes")}
        limits = {name: integer(value["limits"][name]) for name in LIMITS}
        if not all(limits.values()):
            raise ValueError("readiness limits")
        return {"available": True, "schema_version": value["schema_version"],
                "observed_at_ms": value["observed_at_ms"], "installation_id": value["installation_id"],
                "grant_epoch": value["grant_epoch"], "features": features, "limits": limits,
                "assigned_work_ready": features["assigned_work"]["state"] == "ready",
                "full_workflow_ready": all(feature["state"] == "ready" for feature in features.values())}
    except (KeyError, TypeError, ValueError, SpawnError):
        return {**unavailable, "error": "readiness_invalid",
                "message": "The server readiness response did not match the current installation, grant or supported contract."}

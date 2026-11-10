"""SPAWN MCP transport. Credentials always stay in Hermes-owned code."""
from __future__ import annotations

import itertools
import base64
import json
import re
import threading

MCP_URL = "https://spawnbackrooms.com/api/v1/external-work/mcp"
SIGN_IN = "hermes auth add spawn-backrooms:spawn"
MAX_RESPONSE_BYTES = 6 * 1024 * 1024


class SpawnError(Exception):
    def __init__(self, code, message=None, *, uncertain=False, **details):
        self.code = str(code)
        self.message = message or self.code
        self.uncertain = uncertain
        self.details = details
        super().__init__(self.message)

    def as_dict(self):
        result = {"ok": False, "error": self.code, "message": self.message, **self.details}
        if self.uncertain:
            result["outcome_uncertain"] = True
            result["next_step"] = "Check job state. Retry only this same action and arguments to reuse its idempotency key."
        return result


def mapped_error(value, *, status=None, uncertain=None):
    error = value.get("error", value) if isinstance(value, dict) else {}
    if not isinstance(error, dict):
        error = {"code": str(error)}
    code = error.get("code", "remote_error")
    if uncertain is None:
        # HTTP-200 MCP tool errors can wrap a server failure after commit.
        # Only explicit, known precondition/schema denials are definitive.
        definitive = {
            -32700, -32600, -32601, -32602,
            "LEASE_EXPIRED", "LEASE_GENERATION_STALE", "JOB_LEASE_STATE_CONFLICT",
            "ARTIFACT_LEASE_STALE", "JOB_REVISION_CONFLICT", "EXTERNAL_ORDER_CHANGED",
            "EXTERNAL_SCOPE_REQUIRED", "OFFER_EXPIRED", "JOB_NOT_FOUND",
            "ARTIFACT_FENCE_MISMATCH", "ARTIFACT_HASH_MISMATCH", "ARTIFACT_NOT_VERIFIED",
            "INVALID_ARTIFACT_MANIFEST", "INVALID_LEASE_COMMAND", "UPLOAD_EXPIRED",
            "ROOM_CREATION_NOT_AUTHORIZED", "DELEGATED_TOKEN_NOT_AUTHORIZED",
            "INVALID_REQUEST", "INVALID_ARGUMENTS", "INVALID_MCP_BODY",
            "OPEN_JOB_CHANGED", "OPEN_JOB_NOT_FOUND", "OPEN_JOB_NOT_OPEN", "OPEN_JOB_EXPIRED",
            "OPEN_JOB_PROPOSAL_CONFLICT", "OPEN_JOB_PROPOSAL_EXISTS", "OPEN_JOB_PLAN_OVER_CAP",
            "OPEN_JOB_STALE_ESTIMATE", "OPEN_JOB_SELF_COMMISSION", "OPEN_JOB_SCOPE_REQUIRED",
            "EXTERNAL_JOB_AUTHORITY_MISMATCH", "EXTERNAL_CHILD_PARENT_CHANGED", "EXTERNAL_CHILD_LEASE_STALE",
            "EXTERNAL_CHILD_PLAN_CHANGED", "EXTERNAL_CHILD_CAP_EXCEEDED", "EXTERNAL_CHILD_SERVICE_UNAVAILABLE",
            "EXTERNAL_CHILD_SLOT_RESERVED", "EXTERNAL_CHILD_BILLING_REQUIRED", "EXTERNAL_CHILD_DRAFT_NOT_FOUND",
            "IDEMPOTENCY_CONFLICT", "ARTIFACT_INVALID_GAME_PACKAGE",
        }
        uncertain = code not in definitive
    # Do not echo arbitrary responses, headers, credentials, or HTML into chat/logs.
    allowed = ("action", "balance", "balance_raw", "shortfall", "shortfall_raw", "required", "required_amount", "current_amount", "balance_checked_at", "recover_url")
    public = error.get("details") if isinstance(error.get("details"), dict) else error
    details = {k: public[k] for k in allowed if k in public}
    if "recover_url" in details:
        from urllib.parse import urlparse
        parsed = urlparse(str(details["recover_url"]))
        if parsed.scheme != "https" or parsed.hostname != "spawnbackrooms.com" or parsed.username or parsed.password:
            details.pop("recover_url")
    if status == 401 or code in {"INVALID_TOKEN", "EXTERNAL_AUTHORITY_DENIED", "EXTERNAL_GRANT_EXPIRED"}:
        return SpawnError("not_signed_in", "Not signed in, or this grant expired.", fix=SIGN_IN)
    if code == "BETA_TOKEN_REQUIRED":
        return SpawnError(code, "SPAWN beta access is required. Show the balance and shortfall; stop until the user confirms access is restored.", **details)
    if code == "BETA_TOKEN_CHECK_UNAVAILABLE":
        return SpawnError(code, "SPAWN could not check the balance. Try later; do not suggest buying tokens.")
    if code == "EXTERNAL_AUTHORITY_UNAVAILABLE" or status == 503:
        return SpawnError(code, "SPAWN authority is temporarily unavailable. Try later.", uncertain=uncertain)
    return SpawnError(code, "SPAWN rejected the request." if not uncertain else "SPAWN did not confirm the outcome.", uncertain=uncertain, **details)


def credentialed_request(*args, **kwargs):
    """Own plugin frame must stay on the stack for Hermes's caller attribution."""
    from hermes_cli.auth_constants import AuthError
    from hermes_cli.plugin_provider_requests import ProviderNotSignedIn, credentialed_provider_request
    try:
        return credentialed_provider_request(*args, **kwargs)
    except ProviderNotSignedIn:
        raise SpawnError("not_signed_in", "Sign in to SPAWN through Hermes.", fix=SIGN_IN) from None
    except AuthError as exc:
        raise SpawnError(getattr(exc, "code", "oauth_error"), "Hermes could not use the SPAWN grant.", fix=SIGN_IN) from None
    except PermissionError:
        raise SpawnError("provider_permission_denied", "Enable the installed plugin and use its declared SPAWN OAuth grant.") from None


class SpawnClient:
    def __init__(self, request=None):
        self._request = request or credentialed_request
        self._ids = itertools.count(1)
        self._lock = threading.RLock()
        self.protocol = "2025-06-18"
        self.session_id = None
        self._initialized = False

    def upload_game_package(self, upload_id, content):
        """Use native JSON credentials for one exact, already reserved package."""
        if not isinstance(upload_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", upload_id):
            raise SpawnError("invalid_id", "Expected a SPAWN upload identifier.")
        if not isinstance(content, bytes) or not 0 < len(content) <= 2 * 1024 * 1024:
            raise SpawnError("request_too_large", "Game packages must contain at most 2 MiB of bytes.")
        url = "https://spawnbackrooms.com/api/v1/external-work/uploads/" + upload_id + "/game-package"
        try:
            response = self._request("spawn", "PUT", url, json={"content_base64": base64.b64encode(content).decode("ascii")},
                                     headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=30.0)
        except SpawnError:
            raise
        except Exception:
            raise SpawnError("transport_error", "SPAWN did not confirm the package upload.", uncertain=True) from None
        status = response.status
        if 300 <= status < 400:
            raise SpawnError("redirect_refused", "SPAWN redirected the upload. No redirect was followed.", uncertain=True)
        if status == 401:
            raise mapped_error({}, status=status)
        if len(response.text.encode("utf-8")) > MAX_RESPONSE_BYTES:
            raise SpawnError("response_too_large", "SPAWN returned too much package metadata.", uncertain=True)
        try:
            payload = json.loads(response.text)
        except (ValueError, TypeError):
            raise SpawnError("invalid_response", "SPAWN did not confirm the uploaded package.", uncertain=True) from None
        if not 200 <= status < 300:
            raise mapped_error(payload, status=status, uncertain=status >= 500)
        if not isinstance(payload, dict):
            raise SpawnError("invalid_result", uncertain=True)
        if "error" in payload or payload.get("ok") is False:
            raise mapped_error(payload)
        result = payload.get("data", payload)
        if not isinstance(result, dict):
            raise SpawnError("invalid_result", uncertain=True)
        return result

    def _rpc(self, method, params=None, *, notification=False):
        with self._lock:
            request_id = next(self._ids)
        body = {"jsonrpc": "2.0", "method": method}
        if not notification:
            body["id"] = request_id
        if params is not None:
            body["params"] = params
        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json", "MCP-Protocol-Version": self.protocol}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        # Bound the exact encoded request below SPAWN's 64 KiB MCP request cap.
        if len(json.dumps(body, ensure_ascii=False).encode("utf-8")) > 64000:
            raise SpawnError("request_too_large", "This text is too large for SPAWN's MCP request limit.")
        try:
            response = self._request("spawn", "POST", MCP_URL, json=body, headers=headers, timeout=30.0)
        except SpawnError:
            raise
        except Exception:
            raise SpawnError("transport_error", "No response from SPAWN.", uncertain=True) from None
        status = response.status
        response_headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
        if 300 <= status < 400:
            raise SpawnError("redirect_refused", "SPAWN redirected the request. No redirect was followed.", uncertain=True)
        raw = response.text
        if len(raw.encode("utf-8")) > MAX_RESPONSE_BYTES:
            raise SpawnError("response_too_large", "SPAWN returned too much data.", uncertain=True)
        if status == 401:
            raise mapped_error({}, status=status)
        if notification and status in (200, 202, 204) and not raw.strip():
            return {}
        try:
            if "text/event-stream" in response_headers.get("content-type", ""):
                matches = []
                for frame in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n\n"):
                    payload = "\n".join(line[5:].lstrip(" ") for line in frame.splitlines() if line.startswith("data:"))
                    if payload:
                        event = json.loads(payload)
                        if isinstance(event, dict) and event.get("id") == request_id:
                            matches.append(event)
                value = matches[-1] if matches else None
            else:
                value = json.loads(raw)
        except (ValueError, TypeError):
            raise SpawnError("invalid_response", "SPAWN returned an invalid JSON/SSE response.", uncertain=True) from None
        if status < 200 or status >= 300:
            raise mapped_error(value, status=status, uncertain=status >= 500)
        if not isinstance(value, dict) or value.get("id") != request_id or value.get("jsonrpc") != "2.0":
            raise SpawnError("response_id_mismatch", "SPAWN did not return a matching JSON-RPC response.", uncertain=True)
        if "error" in value:
            error = value["error"]
            if not isinstance(error, dict):
                raise SpawnError("invalid_response", uncertain=True)
            if error.get("code") == -32000 and "initializ" in str(error.get("message", "")).lower():
                raise SpawnError("not_initialized")
            raise mapped_error({"error": error})
        session_id = response_headers.get("mcp-session-id")
        if session_id:
            self.session_id = session_id
        return value.get("result", {})

    def call_tool(self, name, arguments=None):
        params = {"name": name, "arguments": arguments or {}}
        try:
            result = self._rpc("tools/call", params)
        except SpawnError as exc:
            if exc.code != "not_initialized" or self._initialized:
                raise
            with self._lock:
                if not self._initialized:
                    info = self._rpc("initialize", {"protocolVersion": self.protocol, "capabilities": {}, "clientInfo": {"name": "spawn-backrooms", "version": "0.1.0"}})
                    if not isinstance(info, dict):
                        raise SpawnError("invalid_response", uncertain=True)
                    version = info.get("protocolVersion")
                    if version not in {"2025-06-18", "2025-03-26", "2024-11-05"}:
                        raise SpawnError("unsupported_protocol", "SPAWN negotiated an unsupported MCP version.")
                    self.protocol = version
                    self._rpc("notifications/initialized", notification=True)
                    self._initialized = True
            result = self._rpc("tools/call", params)
        if not isinstance(result, dict):
            raise SpawnError("invalid_result", uncertain=True)
        payload = result.get("structuredContent")
        if payload is None:
            try:
                text = next(item["text"] for item in result.get("content", []) if isinstance(item, dict) and item.get("type") == "text")
                payload = json.loads(text)
            except (StopIteration, KeyError, ValueError, TypeError):
                raise SpawnError("invalid_result", "SPAWN did not return structured tool data.", uncertain=True) from None
        if not isinstance(payload, dict):
            raise SpawnError("invalid_result", uncertain=True)
        if result.get("isError") or payload.get("ok") is False or "error" in payload:
            raise mapped_error(payload)
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise SpawnError("invalid_result", uncertain=True)
        return data

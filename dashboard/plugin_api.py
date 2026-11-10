"""Read-only Hermes Desktop routes; credentials remain inside Hermes.

Hermes imports dashboard APIs as standalone modules, not package children.
Load only our adjacent, fixed client module without altering import paths.
"""
from __future__ import annotations

import asyncio
import importlib.util
import re
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from hermes_cli.config import load_config
from hermes_constants import get_hermes_home

_CLIENT_PATH = Path(__file__).resolve().parent.parent / "spawn_client.py"
_spec = importlib.util.spec_from_file_location("spawn_backrooms_dashboard_client", _CLIENT_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError("SPAWN client module is missing")
_client_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_client_module)
SpawnClient = _client_module.SpawnClient
SpawnError = _client_module.SpawnError

router = APIRouter()
_CACHE_SECONDS = 20
_cache: dict[tuple[str, str, str], tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()
_READS = frozenset({"spawn_identity", "spawn_access_status", "spawn_list_rooms", "spawn_list_jobs", "spawn_get_job", "spawn_get_earnings"})


def _read(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Keep a plugin-owned frame on the executor stack for credential attribution."""
    if name not in _READS:
        raise ValueError("Dashboard routes permit read-only SPAWN tools only")
    return SpawnClient().call_tool(name, arguments or {})


def _cached(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    # The home follows Hermes's request-local profile scope. Never share results
    # between profiles, even when the plugin module is mounted only once.
    args = arguments or {}
    key = (str(get_hermes_home()), name, repr(sorted(args.items())))
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if cached and now - cached[0] < _CACHE_SECONDS:
            return cached[1]
    value = _read(name, args)
    with _cache_lock:
        if len(_cache) >= 128:
            _cache.clear()
        _cache[key] = (time.monotonic(), value)
    return value


def _settings() -> dict[str, Any]:
    config = load_config()
    entry = config.get("plugins", {}).get("entries", {}).get("spawn-backrooms", {})
    return {**entry.get("config", {}), **entry.get("settings", {})}


def _poll_seconds() -> int:
    try:
        return max(20, min(3600, int(_settings().get("poll_seconds", 60))))
    except (TypeError, ValueError):
        return 60


def _error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, SpawnError):
        return exc.as_dict()
    # Do not expose exception reprs, HTTP headers, filesystem paths, or secrets.
    return {"ok": False, "error": "dashboard_unavailable", "message": "SPAWN could not be read. Check the agent plugin and sign-in."}


async def _status() -> dict[str, Any]:
    # Identity fails closed first; independent remaining reads run concurrently.
    # asyncio.to_thread copies Hermes's request/profile context into each worker.
    identity = await asyncio.to_thread(_one, "spawn_identity")
    if identity.get("ok") is False:
        return identity
    response: dict[str, Any] = {"ok": True, "identity": identity, "poll_seconds": await asyncio.to_thread(_poll_seconds), "errors": []}
    sections = (("access", "spawn_access_status"), ("rooms", "spawn_list_rooms"), ("jobs", "spawn_list_jobs"), ("earnings", "spawn_get_earnings"))
    results = await asyncio.gather(*(asyncio.to_thread(_one, tool) for _, tool in sections))
    for (section, _), value in zip(sections, results):
        if value.get("ok") is False:
            response["errors"].append({"section": section, **value})
        else:
            response[section] = value
    return response


def _one(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return _cached(name, args)
    except Exception as exc:
        return _error(exc)


@router.get("/status")
async def status() -> dict[str, Any]:
    return await _status()


@router.get("/jobs")
async def jobs(cursor: str | None = None) -> dict[str, Any]:
    if cursor is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", cursor):
        return {"ok": False, "error": "invalid_cursor", "message": "Invalid jobs cursor."}
    return await asyncio.to_thread(_one, "spawn_list_jobs", {"cursor": cursor} if cursor else {})


@router.get("/jobs/{job_id}")
async def job(job_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", job_id):
        return {"ok": False, "error": "invalid_job_id", "message": "Invalid job ID."}
    return await asyncio.to_thread(_one, "spawn_get_job", {"job_id": job_id})


@router.get("/earnings")
async def earnings() -> dict[str, Any]:
    result = await asyncio.to_thread(_one, "spawn_get_earnings")
    return {**result, "withdrawals_available": False, "notice": "Recorded amounts only; withdrawals are not available."}

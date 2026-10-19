"""Projects live in one JSON file each. Versions are immutable; approval is a human click."""
import json
import time
from pathlib import Path

from . import config


def _path(pid: str) -> Path:
    return config.DATA_DIR / f"{''.join(c for c in pid if c.isalnum() or c in '-_')}.json"


def load(pid: str) -> dict:
    p = _path(pid)
    return json.loads(p.read_text()) if p.exists() else {"id": pid, "versions": []}


def save(proj: dict) -> None:
    _path(proj["id"]).write_text(json.dumps(proj, indent=2))


def add_version(pid: str, result: dict, transcripts: list[str]) -> dict:
    proj = load(pid)
    v = {"n": len(proj["versions"]) + 1, "created": time.time(), "status": "draft", "approved_by": None,
         "transcript_chars": sum(map(len, transcripts)), **result}
    proj["versions"].append(v)
    save(proj)
    return v


def approved_baseline(pid: str) -> dict | None:
    ok = [v for v in load(pid)["versions"] if v["status"] == "approved"]
    return ok[-1]["scope"] if ok else None


def _version(proj: dict, n: int) -> dict:
    if n < 1 or n > len(proj["versions"]):
        raise IndexError(f"version {n} does not exist")
    return proj["versions"][n - 1]


def approve(pid: str, n: int, who: str) -> dict:
    proj = load(pid)
    v = _version(proj, n)
    v.update(status="approved", approved_by=who, approved_at=time.time())
    save(proj)
    return v


def client_view(pid: str, n: int) -> dict:
    v = _version(load(pid), n)
    if v["status"] != "approved":
        raise PermissionError("Not approved by a human yet - nothing may reach the client.")
    return {"proposal_markdown": v["proposal_markdown"], "price": v["price"]}

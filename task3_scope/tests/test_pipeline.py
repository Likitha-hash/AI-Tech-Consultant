"""pytest -q   (no network / no API key: LLM calls are faked)"""
import asyncio
import json

import pytest

from app import config, pipeline, store
from app.models import Estimate, EstTask, Fit, Scope


def test_schema_has_no_refs():
    assert "$ref" not in json.dumps(pipeline.schema_of(Scope))


def test_windows_cover_everything_with_overlap():
    text = "\n".join(f"Client: line {i} " + "x" * 40 for i in range(400))
    parts = pipeline.windows(text, size=1000)
    assert len(parts) > 5 and all(len(p) < 1300 for p in parts)
    joined = "\n".join(parts)
    assert all(f"line {i} " in joined for i in range(400))


def test_price_math_is_deterministic():
    est = Estimate(tasks=[EstTask(scope_item_id="S1", title="t", role="backend", hours_low=10, hours_high=20, risk="low")])
    p = pipeline.price(est)
    assert p["price_low"] == round(10 * config.RATE_PER_HOUR * (1 + config.CONTINGENCY))


def test_nothing_reaches_client_before_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    store.add_version("p1", {"scope": {"items": []}, "proposal_markdown": "hi", "price": {}}, ["t"])
    with pytest.raises(PermissionError):
        store.client_view("p1", 1)
    store.approve("p1", 1, "me")
    assert store.client_view("p1", 1)["proposal_markdown"] == "hi"
    assert store.approved_baseline("p1") == {"items": []}


def test_followup_prices_only_changed_and_flags_extra(monkeypatch):
    item = lambda i, st: {"id": i, "title": i, "description": "d", "acceptance_criteria": ["a"], "evidence": "q", "status": st, "change_summary": "c"}
    async def fake_call(model, system, content, schema=None, **kw):
        label = kw.get("label")
        if label == "extract":
            return {"notes": [{"kind": "requirement", "text": "map", "quote": "q" + str(hash(content) % 99), "speaker": "c"}]}
        if label == "scope":
            return {"items": [item("S1", "unchanged"), item("S2", "new")], "questions_for_client": []}
        if label == "estimate":
            tasks = json.loads(content)["items"]
            assert [t["id"] for t in tasks] == ["S2"]                       # S1 was already quoted
            return {"tasks": [{"scope_item_id": "S2", "title": "map", "role": "frontend", "hours_low": 4, "hours_high": 6, "risk": "low", "notes": ""}]}
        if label == "review":
            return {"ok": True, "issues": []}
        return "# Change Request"
    async def fake_fit(it):
        return Fit(item_id=it["id"], solution="custom_dev", how="x")
    monkeypatch.setattr(pipeline.llm, "call", fake_call)
    monkeypatch.setattr(pipeline, "check_fit", fake_fit)
    out = asyncio.run(pipeline.run(["Client: add a map"], baseline={"items": [item("S1", "new")]}))
    assert [e["id"] for e in out["quote_extra"]] == ["S2"]
    assert out["proposal_markdown"].startswith("# Change")


def test_bad_version_numbers_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    store.add_version("p2", {"scope": {"items": []}, "proposal_markdown": "x", "price": {}}, ["t"])
    for bad in (0, -1, 5):
        with pytest.raises(IndexError):
            store.approve("p2", bad, "me")
        with pytest.raises(IndexError):
            store.client_view("p2", bad)

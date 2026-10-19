"""API + tiny UI on :8003. CLI: python -m app.main run project1 transcripts/meeting1.txt [more.txt]"""
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import pipeline, store

app = FastAPI(title="Meeting to Scope of Work", version="1.0")


class RunIn(BaseModel):
    project_id: str = Field(min_length=1, max_length=60)
    transcripts: list[str] = Field(min_length=1)
    follow_up: bool = Field(False, description="True = compare against the last APPROVED version")


@app.post("/projects/run")
async def run(body: RunIn) -> dict:
    base = store.approved_baseline(body.project_id) if body.follow_up else None
    if body.follow_up and base is None:
        raise HTTPException(409, "Approve the first version before uploading a follow-up meeting.")
    try:
        res = await pipeline.run(body.transcripts, base)
    except Exception as e:
        raise HTTPException(502, f"Pipeline failed: {e}") from e
    return store.add_version(body.project_id, res, body.transcripts)


@app.get("/projects/{pid}")
def get(pid: str) -> dict:
    return store.load(pid)


@app.post("/projects/{pid}/versions/{n}/approve")
def approve(pid: str, n: int, who: str = "human") -> dict:
    try:
        return store.approve(pid, n, who)
    except IndexError:
        raise HTTPException(404, "no such version")


@app.get("/projects/{pid}/versions/{n}/client")
def client(pid: str, n: int) -> dict:
    try:
        return store.client_view(pid, n)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except IndexError:
        raise HTTPException(404, "no such version")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return (Path(__file__).parent / "ui.html").read_text()


if __name__ == "__main__" and len(sys.argv) > 3 and sys.argv[1] == "run":
    import asyncio
    import json
    pid, files = sys.argv[2], sys.argv[3:]
    texts = [Path(f).read_text() for f in files]
    base = store.approved_baseline(pid) if "followup" in files[0] else None
    out = asyncio.run(pipeline.run(texts, base))
    v = store.add_version(pid, out, texts)
    print(json.dumps({"version": v["n"], "price": v["price"], "cost": v["cost"]}, indent=2))
    print(v["proposal_markdown"])

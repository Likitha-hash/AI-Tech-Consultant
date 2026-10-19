"""Knowledge Brain API. Docs: http://localhost:8001/docs (auto-generated, also see README)."""
import asyncio
import contextlib
import logging
import time
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import config, db, ingest, qa

logging.basicConfig(level=logging.INFO)
_lock = asyncio.Lock()


async def _refresh_job() -> None:
    if _lock.locked():
        return
    async with _lock:
        try:
            await ingest.refresh()
        except Exception:
            logging.exception("refresh failed")  # next scheduled run retries


async def _daily_loop() -> None:
    while True:
        await asyncio.sleep(config.REFRESH_EVERY_HOURS * 3600)
        await _refresh_job()


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    db.conn()
    task = asyncio.create_task(_daily_loop())
    yield
    task.cancel()


app = FastAPI(title="Knowledge Brain", version="1.0", lifespan=lifespan,
              description="Ask questions about a help center. Answers always cite articles or say 'I don't know'.")


def auth(x_api_key: str = Header(default="")) -> None:
    if config.BRAIN_API_KEY and x_api_key != config.BRAIN_API_KEY:
        raise HTTPException(401, "bad or missing X-API-Key")


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000, examples=["How do I change the checkout currency?"])


class Source(BaseModel):
    n: int
    url: str
    title: str
    kind: str = Field(description="text | image | expert")


class AskOut(BaseModel):
    question: str
    answer: str
    confident: bool
    sources: list[Source]
    task_id: int | None = Field(description="Set when a human expert has been asked")
    cost: dict


class ExpertIn(BaseModel):
    answer: str = Field(min_length=3, max_length=5000)
    expert: str = "expert"


@app.post("/ask", response_model=AskOut, dependencies=[Depends(auth)])
async def ask(body: AskIn) -> dict:
    return await qa.ask(body.question)


@app.get("/search", dependencies=[Depends(auth)])
def search(q: str, k: int = 5) -> list[dict]:
    """Raw retrieval, no LLM. Useful for debugging and for agents that want the passages."""
    return [{"url": h["url"], "title": h["title"], "kind": h["kind"], "snippet": h["body"][:400]}
            for h in qa.retrieve(q, min(k, 20))]


@app.get("/tasks", dependencies=[Depends(auth)])
def tasks(status: str = "open") -> list[dict]:
    return [dict(r) for r in db.q("SELECT * FROM tasks WHERE status=? ORDER BY created_at DESC", (status,))]


@app.post("/tasks/{task_id}/answer", dependencies=[Depends(auth)])
def answer_task(task_id: int, body: ExpertIn) -> dict:
    rows = db.q("SELECT * FROM tasks WHERE id=?", (task_id,))
    if not rows:
        raise HTTPException(404, "no such task")
    db.x("UPDATE tasks SET status='answered', answer=?, expert=?, answered_at=? WHERE id=?",
         (body.answer, body.expert, time.time(), task_id))
    ingest.add_expert_answer(task_id, rows[0]["question"], body.answer)
    return {"ok": True, "message": "Answer saved and searchable now."}


@app.post("/admin/refresh", dependencies=[Depends(auth)])
async def refresh(bg: BackgroundTasks) -> dict:
    if _lock.locked():
        return {"started": False, "reason": "a refresh is already running"}
    bg.add_task(_refresh_job)
    return {"started": True}


@app.get("/health")
def health() -> dict:
    pages = {r["status"]: r["n"] for r in db.q("SELECT status, COUNT(*) n FROM pages GROUP BY status")}
    last = db.q("SELECT * FROM runs ORDER BY id DESC LIMIT 1")
    return {"ok": True, "pages": pages, "refreshing": _lock.locked(),
            "images": db.q("SELECT COUNT(*) n FROM images")[0]["n"],
            "open_tasks": db.q("SELECT COUNT(*) n FROM tasks WHERE status='open'")[0]["n"],
            "last_run": dict(last[0]) if last else None}


@app.get("/")
def home() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")

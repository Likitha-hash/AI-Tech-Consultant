"""Sitemap sync (add / update / remove) and page processing. Safe to stop and re-run at any time."""
import hashlib
import logging
from typing import Awaitable, Callable

from . import config, db
from .crawler import Fetcher, chunk_text, parse_article, read_sitemap
from .vision import describe_image

log = logging.getLogger("brain.ingest")
Describer = Callable[[str, str, str], Awaitable[str]]


def _drop_chunks(url: str) -> None:
    db.x("DELETE FROM chunks WHERE url=?", (url,))


async def sync_sitemap(fetcher: Fetcher, sitemap_url: str | None = None) -> dict:
    """Compare sitemap with our records. New -> pending. lastmod changed -> pending. Gone -> removed."""
    entries = await read_sitemap(fetcher, sitemap_url or config.SITEMAP_URL)
    live = {u: lm for u, lm in entries}
    known = {r["url"]: r for r in db.q("SELECT url,lastmod,status FROM pages WHERE url NOT LIKE 'expert://%'")}
    added = updated = removed = 0
    for url, lm in live.items():
        row = known.get(url)
        if row is None:
            db.x("INSERT INTO pages(url,lastmod,status) VALUES(?,?, 'pending')", (url, lm))
            added += 1
        elif row["status"] == "removed":          # page came back
            db.x("UPDATE pages SET status='pending', lastmod=?, tries=0 WHERE url=?", (lm, url))
            added += 1
        elif lm and lm != row["lastmod"]:
            db.x("UPDATE pages SET status='pending', lastmod=?, tries=0 WHERE url=?", (lm, url))
            updated += 1
    for url, row in known.items():
        if url not in live and row["status"] != "removed":
            db.x("UPDATE pages SET status='removed' WHERE url=?", (url,))
            _drop_chunks(url)
            removed += 1
    return {"added": added, "updated": updated, "removed": removed, "in_sitemap": len(live)}


async def process_page(fetcher: Fetcher, url: str, describe: Describer = describe_image) -> str:
    r = await fetcher.get(url)
    if r is None:
        tries = db.q("SELECT tries FROM pages WHERE url=?", (url,))[0]["tries"] + 1
        db.x("UPDATE pages SET tries=?, status=?, error='fetch failed' WHERE url=?",
             (tries, "error" if tries >= 3 else "pending", url))
        return "failed"
    if r.status_code in (404, 410):
        db.x("UPDATE pages SET status='removed' WHERE url=?", (url,))
        _drop_chunks(url)
        return "removed"
    if r.status_code != 200:
        db.x("UPDATE pages SET status='error', error=? WHERE url=?", (f"http {r.status_code}", url))
        return "failed"
    art = parse_article(r.text, url)
    if len(art["text"]) < 40:
        db.x("UPDATE pages SET status='error', error='empty article' WHERE url=?", (url,))
        return "failed"
    h = hashlib.sha1((art["text"] + "|".join(i["src"] for i in art["images"])).encode()).hexdigest()
    old = db.q("SELECT content_hash,status FROM pages WHERE url=?", (url,))[0]
    if old["content_hash"] == h and old["status"] in ("active", "pending"):
        db.x("UPDATE pages SET status='active', fetched_at=? WHERE url=?", (db.now(), url))
        return "unchanged"
    _drop_chunks(url)
    for i, ch in enumerate(chunk_text(art["text"])):
        db.x("INSERT INTO chunks(url,kind,title,body) VALUES(?,?,?,?)", (url, "text", art["title"], ch))
    db.x("DELETE FROM page_images WHERE page_url=?", (url,))
    for im in art["images"]:
        db.x("INSERT OR REPLACE INTO page_images VALUES(?,?,?)", (url, im["src"], im["alt"]))
        row = db.q("SELECT description FROM images WHERE src=?", (im["src"],))
        if row:
            desc = row[0]["description"]
        else:
            try:
                desc = await describe(im["src"], im["alt"], art["title"])
                db.x("INSERT OR REPLACE INTO images VALUES(?,?,?)", (im["src"], desc, db.now()))
            except Exception as e:  # one bad image must not lose the whole article
                log.warning("image failed %s: %s", im["src"], e)
                continue
        db.x("INSERT INTO chunks(url,kind,title,body) VALUES(?,?,?,?)",
             (url, "image", art["title"], f"Screenshot in article '{art['title']}'. {im['alt']} {desc}"))
    db.x("UPDATE pages SET title=?,category=?,folder=?,content_hash=?,status='active',error=NULL,fetched_at=? WHERE url=?",
         (art["title"], art["category"], art["folder"], h, db.now(), url))
    return "updated"


async def process_pending(fetcher: Fetcher, describe: Describer = describe_image, limit: int = 0) -> dict:
    limit = limit or config.MAX_PAGES
    counts = {"updated": 0, "unchanged": 0, "removed": 0, "failed": 0}
    todo = [r["url"] for r in db.q("SELECT url FROM pages WHERE status='pending' AND url NOT LIKE 'expert://%'")]
    if limit:
        todo = todo[:limit]
    for i in range(0, len(todo), config.BATCH_SIZE):
        for url in todo[i:i + config.BATCH_SIZE]:
            counts[await process_page(fetcher, url, describe)] += 1
        log.info("progress %d/%d %s", min(i + config.BATCH_SIZE, len(todo)), len(todo), counts)
    return counts


async def refresh(fetcher: Fetcher | None = None, describe: Describer = describe_image, limit: int = 0) -> dict:
    """The one function used for both first crawl and the daily refresh."""
    f = fetcher or Fetcher()
    run = db.x("INSERT INTO runs(kind,started) VALUES('refresh',?)", (db.now(),))
    await f.load_robots(config.SITEMAP_URL)
    diff = await sync_sitemap(f)
    done = await process_pending(f, describe, limit)
    summary = {"sitemap": diff, "processed": done}
    db.x("UPDATE runs SET finished=?, summary=? WHERE id=?", (db.now(), str(summary), run))
    return summary


def add_expert_answer(task_id: int, question: str, answer: str) -> None:
    """Expert answers become first-class knowledge, searchable like any article."""
    url = f"expert://task/{task_id}"
    db.x("INSERT OR REPLACE INTO pages(url,title,category,status,fetched_at) VALUES(?,?,?, 'active', ?)",
         (url, f"Expert answer: {question[:80]}", "Expert", db.now()))
    _drop_chunks(url)
    db.x("INSERT INTO chunks(url,kind,title,body) VALUES(?,?,?,?)",
         (url, "expert", f"Expert answer: {question[:80]}", f"Question: {question}\nExpert answer: {answer}"))

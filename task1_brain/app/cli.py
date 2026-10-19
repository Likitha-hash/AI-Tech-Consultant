"""python -m app.cli crawl [--max N] | refresh | inspect URL | ask "question" | stats"""
import argparse
import asyncio
import json
import logging

from . import config, db, ingest, qa
from .crawler import Fetcher, parse_article


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["crawl", "refresh", "inspect", "ask", "stats"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--max", type=int, default=0)
    a = ap.parse_args()
    if a.cmd in ("crawl", "refresh"):
        print(await ingest.refresh(limit=a.max))
    elif a.cmd == "inspect":  # check that the HTML selectors work on a real page
        f = Fetcher()
        r = await f.get(a.arg)
        art = parse_article(r.text, a.arg)
        art["text"] = art["text"][:600] + "..."
        print(json.dumps(art, indent=2))
    elif a.cmd == "ask":
        print(json.dumps(await qa.ask(a.arg), indent=2))
    else:
        print({r["status"]: r["n"] for r in db.q("SELECT status, COUNT(*) n FROM pages GROUP BY status")})


if __name__ == "__main__":
    asyncio.run(main())

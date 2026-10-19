"""SQLite storage. FTS5 gives us BM25 keyword search with zero extra infrastructure."""
import sqlite3
import time
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages(
  url TEXT PRIMARY KEY, lastmod TEXT, content_hash TEXT, title TEXT, category TEXT, folder TEXT,
  status TEXT NOT NULL DEFAULT 'pending',   -- pending | active | removed | error
  error TEXT, fetched_at REAL, tries INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS images(src TEXT PRIMARY KEY, description TEXT, described_at REAL);
CREATE TABLE IF NOT EXISTS page_images(page_url TEXT, src TEXT, alt TEXT, PRIMARY KEY(page_url, src));
CREATE TABLE IF NOT EXISTS tasks(
  id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT UNIQUE, status TEXT DEFAULT 'open',
  answer TEXT, expert TEXT, created_at REAL, answered_at REAL);
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, started REAL, finished REAL, summary TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
  url UNINDEXED, kind UNINDEXED, title, body, tokenize='porter unicode61');
"""
_db: sqlite3.Connection | None = None


def init(path: str) -> sqlite3.Connection:
    global _db
    _db = sqlite3.connect(path, check_same_thread=False)
    _db.row_factory = sqlite3.Row
    _db.executescript(SCHEMA)
    _db.commit()
    return _db


def conn() -> sqlite3.Connection:
    if _db is None:
        from . import config
        init(config.DB_PATH)
    assert _db is not None
    return _db


def q(sql: str, args: Iterable[Any] = ()) -> list[sqlite3.Row]:
    return conn().execute(sql, tuple(args)).fetchall()


def x(sql: str, args: Iterable[Any] = ()) -> int:
    c = conn()
    cur = c.execute(sql, tuple(args))
    c.commit()
    return cur.lastrowid or 0


def now() -> float:
    return time.time()

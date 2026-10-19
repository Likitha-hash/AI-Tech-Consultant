"""Polite fetching + parsing. Nothing here talks to the database."""
import asyncio
import random
import re
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from . import config


class Fetcher:
    """Max N requests in flight, a pause before each one, robots.txt respected,
    Retry-After honoured, exponential back-off on 429/5xx."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client or httpx.AsyncClient(
            headers={"User-Agent": config.USER_AGENT}, timeout=30, follow_redirects=True)
        self.sem = asyncio.Semaphore(config.CONCURRENCY)
        self.robots: robotparser.RobotFileParser | None = None
        self.delay = config.DELAY_SECONDS

    async def load_robots(self, base_url: str) -> None:
        p = urlparse(base_url)
        rp = robotparser.RobotFileParser()
        try:
            r = await self.client.get(f"{p.scheme}://{p.netloc}/robots.txt")
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            cd = rp.crawl_delay(config.USER_AGENT)
            if cd:
                self.delay = max(self.delay, float(cd))
        except httpx.HTTPError:
            rp.parse([])
        self.robots = rp

    def allowed(self, url: str) -> bool:
        return True if self.robots is None else self.robots.can_fetch(config.USER_AGENT, url)

    async def get(self, url: str) -> httpx.Response | None:
        if not self.allowed(url):
            return None
        async with self.sem:
            for attempt in range(5):
                await asyncio.sleep(self.delay + random.random() * 0.5)
                try:
                    r = await self.client.get(url)
                except httpx.HTTPError:
                    await asyncio.sleep(2 ** attempt)
                    continue
                if r.status_code == 429 or r.status_code >= 500:
                    wait = r.headers.get("Retry-After", "")
                    await asyncio.sleep(float(wait) if wait.isdigit() else 2 ** (attempt + 1))
                    continue
                return r
        return None


def parse_sitemap(xml: str) -> tuple[list[tuple[str, str | None]], list[str]]:
    """Returns (pages as (url, lastmod), child sitemap urls)."""
    soup = BeautifulSoup(xml, "xml")
    children = [s.find("loc").text.strip() for s in soup.find_all("sitemap") if s.find("loc")]
    pages = []
    for u in soup.find_all("url"):
        loc = u.find("loc")
        if loc:
            lm = u.find("lastmod")
            pages.append((loc.text.strip(), lm.text.strip() if lm else None))
    return pages, children


async def read_sitemap(fetcher: Fetcher, url: str, depth: int = 0) -> list[tuple[str, str | None]]:
    r = await fetcher.get(url)
    if r is None or r.status_code != 200 or depth > 3:
        raise RuntimeError(f"cannot read sitemap {url}")
    pages, children = parse_sitemap(r.text)
    for c in children:
        pages += await read_sitemap(fetcher, c, depth + 1)
    return pages


BODY_SELECTORS = [".article-body", "#article-body", "article", ".article-content", "main", "body"]
SKIP_IMG = re.compile(r"(logo|avatar|icon|sprite|pixel|badge|emoji)", re.I)


def parse_article(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "nav", "footer", "header", "noscript", "form"]):
        t.decompose()
    h1 = soup.find("h1")
    title = (h1.get_text(" ", strip=True) if h1 else (soup.title.get_text(strip=True) if soup.title else url))
    crumbs = [a.get_text(" ", strip=True) for a in soup.select(".breadcrumb a, .breadcrumbs a, nav.breadcrumb a")]
    crumbs = [c for c in crumbs if c and c.lower() not in ("home", "support", "solution home")]
    body = next((soup.select_one(s) for s in BODY_SELECTORS if soup.select_one(s)), soup)
    images = []
    for img in body.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src or src.startswith("data:") or src.lower().endswith((".svg", ".ico")):
            continue
        if SKIP_IMG.search(src) or SKIP_IMG.search(" ".join(img.get("class", []))):
            continue
        w = str(img.get("width", "")).replace("px", "")
        if w.isdigit() and int(w) < 60:
            continue
        images.append({"src": urljoin(url, src), "alt": (img.get("alt") or "").strip()})
    text = "\n".join(ln.strip() for ln in body.get_text("\n").splitlines() if ln.strip())
    seen, uniq = set(), []
    for im in images:
        if im["src"] not in seen:
            seen.add(im["src"])
            uniq.append(im)
    return {"title": title, "category": crumbs[0] if crumbs else "", "folder": crumbs[1] if len(crumbs) > 1 else "",
            "text": text, "images": uniq[: config.MAX_IMAGES_PER_PAGE]}


def chunk_text(text: str, size: int = 1200) -> list[str]:
    chunks, cur = [], ""
    for para in text.split("\n"):
        if len(cur) + len(para) + 1 > size and cur:
            chunks.append(cur)
            cur = cur[-150:]  # small overlap so a step is not cut from its heading
        cur += para + "\n"
    if cur.strip():
        chunks.append(cur)
    return chunks

import asyncio
import httpx
import pytest

from app import db, ingest, qa, config
from app.crawler import Fetcher, chunk_text, parse_article, parse_sitemap

SITEMAP = """<?xml version="1.0"?><urlset>
<url><loc>https://h.test/a1</loc><lastmod>2026-01-01</lastmod></url>
<url><loc>https://h.test/a2</loc><lastmod>2026-01-01</lastmod></url></urlset>"""
PAGES = {
    "https://h.test/a1": """<html><body><nav>menu</nav><ol class="breadcrumb"><a>Home</a><a>Payments</a><a>Stripe</a></ol>
      <h1>Change checkout currency</h1><div class="article-body"><p>Go to Settings, then Payments, then Currency and pick EUR.
      Refunds are processed within five business days.</p><img src="/img/currency.png" alt="currency screen"><img src="/img/logo.png"></div></body></html>""",
    "https://h.test/a2": """<html><body><h1>Email templates</h1><div class="article-body"><p>Open Design, Email Templates to edit the welcome email text shown to members.</p></div></body></html>""",
}


def make_fetcher(state):
    def handler(req: httpx.Request) -> httpx.Response:
        u = str(req.url)
        if u.endswith("robots.txt"):
            return httpx.Response(404)
        if u.endswith("sitemap.xml"):
            return httpx.Response(200, text=state["sitemap"])
        if u in state["pages"]:
            return httpx.Response(200, text=state["pages"][u])
        return httpx.Response(404)
    f = Fetcher(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    f.delay = 0
    return f


async def fake_describe(src, alt, title):
    return "Screenshot showing Currency dropdown set to EUR in Payments settings."


@pytest.fixture(autouse=True)
def fresh_db():
    db.init(":memory:")
    config.SITEMAP_URL = "https://h.test/sitemap.xml"


def run(c):
    return asyncio.run(c)


def test_parse_article_and_images():
    art = parse_article(PAGES["https://h.test/a1"], "https://h.test/a1")
    assert art["title"] == "Change checkout currency"
    assert art["category"] == "Payments" and art["folder"] == "Stripe"
    assert [i["src"] for i in art["images"]] == ["https://h.test/img/currency.png"]  # logo skipped


def test_sitemap_parse_and_chunk():
    pages, children = parse_sitemap(SITEMAP)
    assert len(pages) == 2 and children == []
    assert all(len(c) < 1500 for c in chunk_text("line\n" * 1000))


def test_first_crawl_then_search_finds_image_text():
    state = {"sitemap": SITEMAP, "pages": dict(PAGES)}
    out = run(ingest.refresh(make_fetcher(state), fake_describe))
    assert out["sitemap"]["added"] == 2 and out["processed"]["updated"] == 2
    hits = qa.retrieve("which currency dropdown EUR")
    assert any(h["kind"] == "image" for h in hits)


def test_update_only_changes_what_changed_and_removed_disappears():
    state = {"sitemap": SITEMAP, "pages": dict(PAGES)}
    run(ingest.refresh(make_fetcher(state), fake_describe))
    # a2 is edited, a1 is removed from the sitemap
    state["sitemap"] = SITEMAP.replace("<url><loc>https://h.test/a1</loc><lastmod>2026-01-01</lastmod></url>", "") \
        .replace("a2</loc><lastmod>2026-01-01", "a2</loc><lastmod>2026-02-01")
    state["pages"]["https://h.test/a2"] = state["pages"]["https://h.test/a2"].replace("welcome", "goodbye")
    out = run(ingest.refresh(make_fetcher(state), fake_describe))
    assert out["sitemap"]["removed"] == 1 and out["processed"]["updated"] == 1 and out["processed"]["unchanged"] == 0
    assert qa.retrieve("checkout currency EUR") == []             # removed article never appears
    assert qa.retrieve("goodbye email template")                  # updated one does


def test_resume_after_crash():
    state = {"sitemap": SITEMAP, "pages": dict(PAGES)}
    f = make_fetcher(state)
    run(ingest.sync_sitemap(f))
    run(ingest.process_pending(f, fake_describe, limit=1))        # "crash" after one page
    assert len(db.q("SELECT 1 FROM pages WHERE status='pending'")) == 1
    run(ingest.process_pending(f, fake_describe))                 # restart
    assert len(db.q("SELECT 1 FROM pages WHERE status='active'")) == 2


def test_expert_answer_flows_back(monkeypatch):
    async def fake_call(*a, **k):
        return {"answer": "x", "source_numbers": [], "confident": False}
    monkeypatch.setattr(qa.llm, "call", fake_call)
    r = run(qa.ask("Do you offer lifetime discounts for nonprofits?"))
    assert r["task_id"] and not r["confident"]
    ingest.add_expert_answer(r["task_id"], "Do you offer lifetime discounts for nonprofits?", "Yes, nonprofits get 20 percent off.")
    assert qa.retrieve("nonprofits discount")[0]["kind"] == "expert"

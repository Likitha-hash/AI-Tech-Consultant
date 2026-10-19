# DESIGN (REWRITE IN YOUR OWN WORDS - this is a starting skeleton; the live review will test that you understand it)

## 1. The problem, in my words
AI makes code cheap. A $2,000 website change now sells for $200, so a consultancy must handle 10-20x more clients with the same people.
The slow parts are not coding: they are (a) knowing the product, (b) answering email fast and correctly, (c) turning meetings into a clear scope.
I built one system that attacks all three, and each part gets better with use.

## 2. How the three tasks connect  (redraw this as an image if you like)
```
 Help center --daily--> [Task 1 Knowledge Brain] <--HTTP /ask-- [Task 2 Inbox Agent]  <-- customer emails
   (text+images)         |  FTS5 index, vision,                      ^ human edits -> lessons -> better drafts
                         |  expert queue -> memory                   |
                         +<---------HTTP /ask---- [Task 3 Scope team] <-- meeting transcripts
                                                   "can an existing setting do this?"   -> human approves -> client
```

## 3. Features I chose, and why
- Task 1: polite resumable crawl (2 at a time, 1s gap, robots.txt, Retry-After) - because overloading a real server is rude and a crash must not restart a 400-page crawl.
- Task 1: screenshots described by a cheap vision model and stored as searchable text tied to their article - the answer is often in the picture.
- Task 1: daily sitemap diff by `lastmod`; removed pages are deleted from the index in the same step - a removed article must never be cited.
- Task 1: "I don't know" creates an expert task; the expert's answer becomes a searchable document - the memory grows from real gaps.
- Task 2: risk flag (money, anger, legal, cancellation) forces a human, always - the cost of one wrong auto-reply is bigger than the gain of many right ones.
- Task 2: "same kind" = same category + low risk + Brain was confident. "Unchanged" = 98% text similarity. 20 in a row unlocks autopilot; any human edit, or a failed spot-check (1 in 10 auto-replies is shown to a human), takes it away.
- Task 2: every edit becomes a short general rule (a "lesson") that can be switched off with one click; each draft records a prompt version so improvement is measured per version.
- Task 3: six single-purpose agents; transcripts are cut into overlapping windows and processed in parallel (map), then merged (reduce); every note keeps its quote as evidence.
- Task 3: Fit Checker calls Task 1 to find existing settings that replace custom code (cheaper for the client).
- Task 3: money is computed in Python, never by the model. Follow-up meeting: baseline = last approved version; items marked unchanged / changed / new / removed; only changed + new are priced, as a Change Request.
- Task 3: nothing is client-visible until a human approves (enforced in the API, not only in the UI).

## 4. Features I dropped, and why (EDIT: be honest)
- Vector embeddings: BM25 over SQLite FTS5 was enough for a few hundred articles and needs no extra service. Next step if recall evals show misses: hybrid search.
- Real email (IMAP/Gmail): the agent takes emails through an API/UI. Connectors are plumbing, not thinking.
- Multi-tenant auth and billing: out of scope for 4 days.

## 5. Model choices (fill from EVALS.md)
Vision + triage + extraction: Haiku-class (many cheap calls). Answers, scoping, estimating, proposals, learning: Sonnet-class.
Proof: see the tables in EVALS.md. Change a choice only if your numbers say so.

## 6. What breaks (EDIT with what YOU observe)
- HTML selectors may not match every article layout (use `python -m app.cli inspect <url>` to check).
- BM25 misses when customers use different words than the docs.
- Autopilot threshold of 20 is a business choice, not a statistical guarantee.
- Estimates are ranges from an LLM; compare them with real past projects before trusting them.

## 7. What I would build next
Hybrid vector search, a Gmail connector, per-customer memory, estimate calibration from real finished projects.

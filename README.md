# AI Tech Consultant

One system for a software/service business: it **knows the product** (Task 1), **answers the inbox** (Task 2), and **turns client meetings into a scope, estimate and proposal** (Task 3).

| Task | Language | Port | What it does |
|---|---|---|---|
| `task1_brain` | Python | 8001 | Reads a public help center (text + screenshots), refreshes daily, answers with citations, asks a human expert when unsure |
| `task2_inbox` | TypeScript | 3002 | Drafts email replies from Task 1's facts, learns from every human edit, earns autopilot after 20 unchanged drafts |
| `task3_scope` | Python | 8003 | Meeting transcript -> scope, hour estimates, proposal. Follow-up meeting -> what changed + what to quote extra |

Task 2 and Task 3 call Task 1 **only over HTTP** (`POST /ask`).

## Run it (3 commands)
```bash
cp .env.example .env        # then put your ANTHROPIC_API_KEY inside
./run.sh crawl              # one-time: read the help center (add MAX_PAGES=30 in .env for a quick trial)
./run.sh                    # starts all three apps
```
Other: `./run.sh test` (all tests, no key needed), `./run.sh eval` (writes the numbers for EVALS.md).

## Requirements
Python 3.11+, Node 20+, an Anthropic API key.

Docs: `DESIGN.md`, `EVALS.md`, `AI_LOG.md`. API docs for Task 1: http://localhost:8001/docs

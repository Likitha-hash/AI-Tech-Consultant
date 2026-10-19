# EVALS (fill in from `./run.sh eval`; paste the real numbers - never invent them)

## Task 1 - Knowledge Brain (20 cases: 15 in-scope, 5 out-of-scope)  -> task1_brain/evals/results.md
(paste table)  What I conclude + which model I chose and why:

## Task 2 - Inbox Agent (52 labelled emails)  -> task2_inbox/evals/results.md and simulation.md
(paste triage table + learning-curve table)  Did similarity rise after lessons? What did autopilot do?

## Task 3 - Meeting to Scope (20 snippets)  -> task3_scope/evals/results.md
(paste table)  Plus: one long transcript run: time, cost, and whether a follow-up meeting flagged the map as "quote extra".

## Failure cases I saw (required - hiding failures costs marks)
1.
2.

## Safety checks I ran
- Prompt injection email (e52 in task2 data) -> expected: no refund promise. Result:
- Injection line in transcript 3 -> expected: ignored. Result:

"""python -m evals.run_evals  -> writes evals/results.md. Needs a crawled DB and ANTHROPIC_API_KEY.
Compares answer models on: grounded answers (LLM judge), citations, honest 'I don't know', cost, speed."""
import asyncio
import json
import statistics
from pathlib import Path

from app import config, llm, qa

MODELS = ["claude-haiku-5-5", "claude-sonnet-5-5"]
JUDGE = "claude-sonnet-5-5"
JSCHEMA = {"type": "object", "properties": {"supported": {"type": "boolean"}, "reason": {"type": "string"}},
           "required": ["supported", "reason"]}


async def judge(question: str, answer: str, context: str) -> bool:
    out = await llm.call(JUDGE, "You are a strict grader. Say supported=true only if EVERY factual claim in the answer "
                         "is backed by the sources.", f"<sources>{context}</sources>\n<question>{question}</question>\n<answer>{answer}</answer>",
                         schema=JSCHEMA, label="judge")
    return out["supported"]


async def main() -> None:
    cases = json.loads((Path(__file__).parent / "cases.json").read_text())
    rows = []
    for model in MODELS:
        config.MODEL_ANSWER = model
        start = len(llm.LEDGER)
        res = {"model": model, "grounded": 0, "cited": 0, "confident": 0, "refused_ok": 0, "lat": []}
        for qn in cases["in_scope"]:
            r = await qa.ask(qn, create_missing_task=False, with_context=True)
            res["lat"].append(r["cost"]["ms"])
            res["confident"] += r["confident"]
            res["cited"] += bool(r["sources"])
            if r["confident"] and await judge(qn, r["answer"], r.get("_context", "")):
                res["grounded"] += 1
        for qn in cases["out_of_scope"]:
            r = await qa.ask(qn, create_missing_task=False)
            res["refused_ok"] += (not r["confident"])
        answer_cost = sum(e["usd"] for e in llm.LEDGER[start:] if e["label"] == "answer")
        res["usd_per_q"] = answer_cost / (len(cases["in_scope"]) + len(cases["out_of_scope"]))
        rows.append(res)
    n_in, n_out = len(cases["in_scope"]), len(cases["out_of_scope"])
    lines = ["| Model | Answered | Grounded (judge) | Has citation | Refused out-of-scope | Median latency ms | $ per question |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['model']} | {r['confident']}/{n_in} | {r['grounded']}/{n_in} | {r['cited']}/{n_in} | "
                     f"{r['refused_ok']}/{n_out} | {int(statistics.median(r['lat']))} | {r['usd_per_q']:.4f} |")
    Path(__file__).with_name("results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())

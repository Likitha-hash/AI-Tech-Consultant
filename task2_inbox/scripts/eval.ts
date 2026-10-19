// npm run eval  -> triage accuracy on the 50 labelled emails for two models, plus cost and speed.
import { readFileSync, writeFileSync } from "node:fs";
import { triage } from "../src/agent.js";
import { LEDGER } from "../src/llm.js";
import type { Email } from "../src/types.js";

const emails = JSON.parse(readFileSync("data/emails.json", "utf8")) as (Email & { label: string })[];
const rows: string[] = [];
for (const model of ["claude-haiku-5-5", "claude-sonnet-5-5"]) {
  let ok = 0, riskOk = 0;
  const start = LEDGER.length, t0 = Date.now();
  for (const e of emails) {
    const t = await triage(e, model);
    ok += t.category === e.label ? 1 : 0;
    // every refund / complaint / cancellation / legal-threat email must be marked high risk
    const mustBeHigh = ["refund", "complaint", "cancellation"].includes(e.label) || e.subject.includes("Refund + legal");
    riskOk += mustBeHigh ? (t.risk === "high" ? 1 : 0) : 1;
  }
  const usd = LEDGER.slice(start).reduce((a, r) => a + r.usd, 0);
  rows.push(`| ${model} | ${ok}/${emails.length} | ${riskOk}/${emails.length} | ${Math.round((Date.now() - t0) / emails.length)} | ${(usd / emails.length).toFixed(5)} |`);
}
const table = "| Triage model | Category correct | Risk rule satisfied | ms per email | $ per email |\n|---|---|---|---|---|\n" + rows.join("\n") + "\n";
writeFileSync("evals/results.md", table);
console.log(table);

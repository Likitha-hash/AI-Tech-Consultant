// npm run simulate -> shows the agent LEARNING. A fake "human" always rewrites the greeting and sign-off.
// Needs ANTHROPIC_API_KEY. Uses a throw-away state file so your real data is untouched.
process.env["STATE_FILE"] = "data/sim-state.json";
import { readFileSync, writeFileSync } from "node:fs";
import { processEmail } from "../src/agent.js";
import { resolve, stats } from "../src/learn.js";
import type { Email, State } from "../src/types.js";

const emails = (JSON.parse(readFileSync("data/emails.json", "utf8")) as (Email & { label: string })[]).filter((e) => e.label === "how_to");
const s: State = { emails: [], records: {}, lessons: [], autopilot: {}, examples: {}, outbox: [], autoCount: 0 };
// The fake human's style: "Hello <first name>," at the top, "Warm regards, Priya" at the bottom, never "Best, The Support Team".
const humanize = (body: string, name: string): string =>
  `Hello ${name.split(" ")[0]},\n` + body.replace(/^(Hi|Hello|Dear)[^\n]*\n+/i, "").replace(/\n+Best,?[\s\S]*$/i, "").trim() + "\n\nWarm regards,\nPriya";
const lines: string[] = ["| # | prompt version | similarity of draft to human's final |", "|---|---|---|"];
let i = 0;
for (const e of emails) {
  s.emails.push(e);
  const rec = await processEmail(s, e);
  const done = await resolve(s, e.id, "send", humanize(rec.draft.body, e.name));
  lines.push(`| ${++i} | ${done.promptVersion} | ${done.similarity} |`);
}
const out = lines.join("\n") + `\n\nLessons learned: ${s.lessons.length}\n` + s.lessons.map((l) => `- [${l.scope}] ${l.rule}`).join("\n") +
  "\n\nBy version: " + JSON.stringify(stats(s));
writeFileSync("evals/simulation.md", out + "\n");
console.log(out);

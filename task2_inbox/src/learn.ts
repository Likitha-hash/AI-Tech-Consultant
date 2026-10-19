import { activeLessons, newId } from "./agent.js";
import { MODELS, callJson } from "./llm.js";
import { UNCHANGED_THRESHOLD, similarity } from "./similarity.js";
import { CATEGORIES, type Category, type DraftRecord, type Email, type Lesson, type State } from "./types.js";

export const STREAK_TO_AUTOPILOT = 20;

export type Learner = (rec: DraftRecord, email: Email, finalBody: string, s: State) => Promise<{ scope: Category | "global"; rule: string }[]>;

const SCHEMA = {
  type: "object",
  properties: {
    lessons: {
      type: "array", maxItems: 3,
      items: { type: "object", properties: { scope: { type: "string", enum: [...CATEGORIES, "global"] }, rule: { type: "string" } }, required: ["scope", "rule"] },
    },
  },
  required: ["lessons"],
};

/** Ask Claude what the human changed. Rules must be general (tone, structure, policy) and never contain customer details. */
export const llmLearner: Learner = async (rec, email, finalBody, s) => {
  const existing = activeLessons(s, rec.triage.category).map((l) => `- ${l.rule}`).join("\n") || "(none)";
  const { data } = await callJson<{ lessons: { scope: Category | "global"; rule: string }[] }>({
    model: MODELS.learn, schema: SCHEMA, label: "learn", maxTokens: 600,
    system: `A human edited an AI-written email reply. Compare DRAFT and FINAL and return up to 3 short, general rules that would make the next draft match FINAL (tone, length, structure, wording, what to always/never say).
Rules must NOT contain customer names, emails or one-off facts. If the change is only a one-off fact for this customer, return an empty list.
Do not repeat existing rules. Scope "global" only if it applies to every kind of email.`,
    user: `<category>${rec.triage.category}</category>\n<existing_rules>\n${existing}\n</existing_rules>\n<customer_email>\n${email.body.slice(0, 3000)}\n</customer_email>\n<draft>\n${rec.draft.body}\n</draft>\n<final>\n${finalBody}\n</final>`,
  });
  return data.lessons;
};

export function revoke(s: State, cat: Category, reason: string): void {
  const ap = (s.autopilot[cat] ??= { streak: 0, enabled: false, reason: "" });
  ap.streak = 0; ap.enabled = false; ap.reason = reason;
}

export async function resolve(s: State, emailId: string, action: "send" | "own_reply", finalBody: string, learner: Learner = llmLearner): Promise<DraftRecord> {
  const rec = s.records[emailId], email = s.emails.find((e) => e.id === emailId);
  if (!rec || !email) throw new Error("unknown email");
  if (rec.status !== "pending") throw new Error("already resolved");
  const sim = similarity(rec.draft.body, finalBody);
  const unchanged = action === "send" && sim >= UNCHANGED_THRESHOLD;
  rec.finalBody = finalBody; rec.similarity = Number(sim.toFixed(3));
  rec.status = action === "own_reply" ? "own_reply" : unchanged ? "sent_as_is" : "edited";
  s.outbox.push({ emailId, body: finalBody, auto: false, at: new Date().toISOString() });

  const cat = rec.triage.category;
  const ap = (s.autopilot[cat] ??= { streak: 0, enabled: false, reason: "" });
  const eligible = rec.triage.risk === "low" && rec.brain.confident;   // "same kind" = category + low risk + Brain was sure
  if (unchanged) {
    if (eligible) ap.streak += 1;
    if (!ap.enabled && ap.streak >= STREAK_TO_AUTOPILOT) { ap.enabled = true; ap.reason = `${STREAK_TO_AUTOPILOT} unchanged drafts in a row`; }
  } else {
    if (ap.enabled) revoke(s, cat, "a human changed a draft"); else ap.streak = 0;
    const learned = await learner(rec, email, finalBody, s);
    for (const l of learned) {
      if (s.lessons.some((x) => x.rule.toLowerCase() === l.rule.toLowerCase())) continue;
      const lesson: Lesson = { id: newId(), scope: l.scope, rule: l.rule, evidence: emailId, createdAt: new Date().toISOString(), active: true };
      s.lessons.push(lesson);
    }
  }
  (s.examples[cat] ??= []).push(finalBody);
  s.examples[cat] = s.examples[cat]!.slice(-5);
  return rec;
}

/** Spot-check of an auto-sent email. A failed check takes the freedom away immediately. */
export async function audit(s: State, emailId: string, ok: boolean, corrected: string | undefined, learner: Learner = llmLearner): Promise<void> {
  const rec = s.records[emailId], email = s.emails.find((e) => e.id === emailId);
  if (!rec || !email || !rec.audit) throw new Error("not an audit item");
  rec.auditResult = ok ? "ok" : "bad"; rec.audit = false;
  if (ok) return;
  revoke(s, rec.triage.category, "spot-check of an automatic reply failed");
  if (corrected) {
    for (const l of await learner(rec, email, corrected, s)) {
      s.lessons.push({ id: newId(), scope: l.scope, rule: l.rule, evidence: emailId, createdAt: new Date().toISOString(), active: true });
    }
  }
}

export function stats(s: State) {
  const by: Record<string, { n: number; sim: number; unchanged: number }> = {};
  for (const r of Object.values(s.records)) {
    if (r.similarity === undefined) continue;
    const b = (by[r.promptVersion] ??= { n: 0, sim: 0, unchanged: 0 });
    b.n++; b.sim += r.similarity; b.unchanged += r.status === "sent_as_is" ? 1 : 0;
  }
  return Object.entries(by).map(([version, b]) => ({ version, n: b.n, avgSimilarity: +(b.sim / b.n).toFixed(3), unchangedRate: +(b.unchanged / b.n).toFixed(2) }));
}

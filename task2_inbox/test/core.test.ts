import { test } from "node:test";
import assert from "node:assert/strict";
import { similarity } from "../src/similarity.js";
import { resolve, audit, STREAK_TO_AUTOPILOT, type Learner } from "../src/learn.js";
import { canAutoSend } from "../src/agent.js";
import type { DraftRecord, State } from "../src/types.js";

const noLearn: Learner = async () => [];
const mk = (id: string, risk: "low" | "high" = "low", confident = true): DraftRecord => ({
  emailId: id, triage: { category: "how_to", risk, urgency: "normal", key_question: "q", sentiment: "neutral" },
  draft: { subject: "s", body: "Hi Sam,\nGo to Settings.\nBest", confidence: 0.9, needs_human_reason: "" },
  brain: { confident, answer: "a", sources: [], taskId: null }, promptVersion: "v1", createdAt: "", status: "pending", audit: false, costUsd: 0,
});
const stateWith = (n: number): State => {
  const s: State = { emails: [], records: {}, lessons: [], autopilot: {}, examples: {}, outbox: [], autoCount: 0 };
  for (let i = 0; i < n; i++) { s.emails.push({ id: `e${i}`, name: "A", from: "a@x", subject: "s", body: "b", receivedAt: "" }); s.records[`e${i}`] = mk(`e${i}`); }
  return s;
};

test("whitespace is not a change, typos are", () => {
  assert.equal(similarity("Hello  world\n", "Hello world"), 1);
  assert.ok(similarity("Please reset your password now", "Please reset your pasword now") < 1);
  assert.ok(similarity("abc", "xyz") < 0.2);
});

test("20 unchanged drafts in a row unlock autopilot; one edit takes it away", async () => {
  const s = stateWith(22);
  for (let i = 0; i < STREAK_TO_AUTOPILOT; i++) await resolve(s, `e${i}`, "send", s.records[`e${i}`]!.draft.body, noLearn);
  assert.equal(s.autopilot.how_to?.enabled, true);
  assert.equal(canAutoSend(s, mk("x")), true);
  assert.equal(canAutoSend(s, mk("x", "high")), false);           // risky mail never goes automatically
  assert.equal(canAutoSend(s, mk("x", "low", false)), false);     // Brain unsure -> human
  await resolve(s, "e20", "send", "Totally different reply that a human wrote", noLearn);
  assert.equal(s.autopilot.how_to?.enabled, false);
  assert.equal(s.autopilot.how_to?.streak, 0);
});

test("an edit in the middle resets the streak", async () => {
  const s = stateWith(21);
  for (let i = 0; i < 10; i++) await resolve(s, `e${i}`, "send", s.records[`e${i}`]!.draft.body, noLearn);
  await resolve(s, "e10", "send", "Edited text here", noLearn);
  for (let i = 11; i < 21; i++) await resolve(s, `e${i}`, "send", s.records[`e${i}`]!.draft.body, noLearn);
  assert.equal(s.autopilot.how_to?.enabled, false);               // only 10 in a row since the edit
});

test("learned rules are stored and duplicates are ignored", async () => {
  const s = stateWith(2);
  const learner: Learner = async () => [{ scope: "global", rule: "Sign off with 'Warm regards'." }];
  await resolve(s, "e0", "send", "Changed text", learner);
  await resolve(s, "e1", "send", "Changed again", learner);
  assert.equal(s.lessons.length, 1);
});

test("failed spot-check revokes autopilot", async () => {
  const s = stateWith(1);
  s.autopilot.how_to = { streak: 20, enabled: true, reason: "x" };
  s.records["e0"]!.audit = true; s.records["e0"]!.status = "auto_sent";
  await audit(s, "e0", false, undefined, noLearn);
  assert.equal(s.autopilot.how_to?.enabled, false);
});

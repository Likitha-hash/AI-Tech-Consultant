import type { BrainResult } from "./types.js";

const BRAIN_URL = process.env["BRAIN_URL"] ?? "http://localhost:8001";
const KEY = process.env["BRAIN_API_KEY"] ?? "";

interface AskOut { answer: string; confident: boolean; sources: { url: string }[]; task_id: number | null }

/** Calls Task 1 over HTTP only. If the Brain is down we say "not confident" so a human handles it. */
export async function askBrain(question: string): Promise<BrainResult> {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const r = await fetch(`${BRAIN_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(KEY ? { "X-API-Key": KEY } : {}) },
        body: JSON.stringify({ question: question.slice(0, 900) }),
        signal: AbortSignal.timeout(45_000),
      });
      if (!r.ok) throw new Error(`brain ${r.status}`);
      const j = (await r.json()) as AskOut;
      return { confident: j.confident, answer: j.answer, sources: j.sources.map((s) => s.url), taskId: j.task_id };
    } catch {
      await new Promise((res) => setTimeout(res, 500 * 2 ** attempt));
    }
  }
  return { confident: false, answer: "", sources: [], taskId: null };
}

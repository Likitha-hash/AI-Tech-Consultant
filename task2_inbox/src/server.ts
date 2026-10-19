import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { readFileSync } from "node:fs";
import { newId, processEmail } from "./agent.js";
import { LEDGER } from "./llm.js";
import { audit, resolve, stats, STREAK_TO_AUTOPILOT } from "./learn.js";
import { load, save } from "./store.js";
import type { Email } from "./types.js";

const PORT = Number(process.env["PORT"] ?? 3002);
const state = load();
let busy: Promise<unknown> = Promise.resolve();            // one writer at a time: simple and safe
const serial = <T>(fn: () => Promise<T>): Promise<T> => { const p = busy.then(fn, fn); busy = p.catch(() => undefined); return p; };

const send = (res: ServerResponse, code: number, body: unknown): void => {
  res.writeHead(code, { "Content-Type": typeof body === "string" ? "text/html" : "application/json" });
  res.end(typeof body === "string" ? body : JSON.stringify(body));
};
async function readJson(req: IncomingMessage): Promise<Record<string, unknown>> {
  let raw = "";
  for await (const c of req) { raw += c; if (raw.length > 200_000) throw new Error("body too large"); }
  return raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
}
const str = (v: unknown, max: number): string => (typeof v === "string" ? v.slice(0, max) : "");

async function ingest(e: Omit<Email, "id" | "receivedAt"> & { id?: string }): Promise<void> {
  const email: Email = { ...e, id: e.id ?? newId(), receivedAt: new Date().toISOString() };
  if (state.emails.some((x) => x.id === email.id)) return;
  state.emails.push(email);
  try { await processEmail(state, email); }
  catch (err) { state.emails.pop(); throw err; }            // no half-created emails
  save(state);
}

createServer((req, res) => {
  void (async () => {
    try {
      const url = new URL(req.url ?? "/", "http://x");
      const m = req.method ?? "GET";
      if (m === "GET" && url.pathname === "/") return send(res, 200, readFileSync("public/index.html", "utf8"));
      if (m === "GET" && url.pathname === "/api/state")
        return send(res, 200, { ...state, stats: stats(state), streakNeeded: STREAK_TO_AUTOPILOT,
          spend: +LEDGER.reduce((a, r) => a + r.usd, 0).toFixed(4) });
      if (m === "POST" && url.pathname === "/api/emails") {
        const b = await readJson(req);
        const body = str(b["body"], 8000), subject = str(b["subject"], 300);
        if (!body || !subject) return send(res, 400, { error: "subject and body are required" });
        await serial(() => ingest({ name: str(b["name"], 100) || "Customer", from: str(b["from"], 200), subject, body }));
        return send(res, 200, { ok: true });
      }
      if (m === "POST" && url.pathname === "/api/seed") {
        const n = Math.min(Number(url.searchParams.get("n") ?? 5), 50);
        const all = JSON.parse(readFileSync("data/emails.json", "utf8")) as Email[];
        const todo = all.filter((e) => !state.emails.some((x) => x.id === e.id)).slice(0, n);
        for (const e of todo) await serial(() => ingest(e));
        return send(res, 200, { added: todo.length });
      }
      const rm = url.pathname.match(/^\/api\/records\/([\w-]+)\/(resolve|audit)$/);
      if (m === "POST" && rm) {
        const b = await readJson(req), id = rm[1] as string;
        await serial(async () => {
          if (rm[2] === "resolve") await resolve(state, id, b["action"] === "own_reply" ? "own_reply" : "send", str(b["finalBody"], 8000));
          else await audit(state, id, b["ok"] === true, str(b["corrected"], 8000) || undefined);
          save(state);
        });
        return send(res, 200, { ok: true });
      }
      const lm = url.pathname.match(/^\/api\/lessons\/([\w-]+)\/toggle$/);
      if (m === "POST" && lm) {
        const l = state.lessons.find((x) => x.id === lm[1]);
        if (!l) return send(res, 404, { error: "no such lesson" });
        l.active = !l.active; save(state);                  // undo a bad lesson with one click
        return send(res, 200, { active: l.active });
      }
      send(res, 404, { error: "not found" });
    } catch (err) {
      send(res, 500, { error: err instanceof Error ? err.message : "failed" });
    }
  })();
}).listen(PORT, () => console.log(`Inbox Agent on http://localhost:${PORT}`));

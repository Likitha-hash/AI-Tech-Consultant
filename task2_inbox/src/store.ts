import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import type { State } from "./types.js";

const FILE = process.env["STATE_FILE"] ?? "data/state.json";
const empty = (): State => ({ emails: [], records: {}, lessons: [], autopilot: {}, examples: {}, outbox: [], autoCount: 0 });

export function load(): State {
  if (!existsSync(FILE)) return empty();
  try { return { ...empty(), ...(JSON.parse(readFileSync(FILE, "utf8")) as State) }; }
  catch { return empty(); }   // corrupted file: start clean rather than crash
}
export function save(s: State): void {
  mkdirSync(dirname(FILE), { recursive: true });
  writeFileSync(FILE, JSON.stringify(s, null, 2));
}

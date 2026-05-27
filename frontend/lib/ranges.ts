// Postgres range string helpers. PostgREST returns/accepts inclusive/exclusive
// bounds like "[2026-07-10,2026-07-21)"; we normalize to closed `[a,b]`.

export type DateRange = { start: string; end: string };
export type IntRange = { min: number; max: number };

const RE = /^([\[\(])([^,]*),([^\]\)]*)([\]\)])$/;

function shiftDate(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function parseDateRange(raw: string | null | undefined): DateRange | null {
  if (!raw) return null;
  const m = RE.exec(raw);
  if (!m) return null;
  const [, lo, a, b, hi] = m;
  return {
    start: lo === "(" ? shiftDate(a, 1) : a,
    end: hi === ")" ? shiftDate(b, -1) : b,
  };
}

export function parseIntRange(raw: string | null | undefined): IntRange | null {
  if (!raw) return null;
  const m = RE.exec(raw);
  if (!m) return null;
  const [, lo, a, b, hi] = m;
  return {
    min: parseInt(a, 10) + (lo === "(" ? 1 : 0),
    max: parseInt(b, 10) - (hi === ")" ? 1 : 0),
  };
}

export function fmtDateRange(r: DateRange): string {
  return `[${r.start},${r.end}]`;
}

export function fmtIntRange(r: IntRange): string {
  return `[${r.min},${r.max}]`;
}

// Data accessors used by the App Router pages.
//
// When `DEMO_MODE=1`, returns deterministic fixture data and skips Supabase
// entirely — useful to preview the UI without backend setup.

import { DEMO_RESULTS, DEMO_SEARCHES } from "./demo-fixtures";
import { serverClient, type FlightResult, type Search } from "./supabase";

export type SearchWithStats = Search & {
  min_price: number | null;
  last_captured_at: string | null;
};

const DEMO = process.env.DEMO_MODE === "1";

export async function listSearchesWithStats(): Promise<SearchWithStats[]> {
  if (DEMO) return demoSearchesWithStats();
  const supabase = serverClient();
  const { data: searches } = await supabase
    .from("searches")
    .select("*")
    .order("created_at", { ascending: false });
  if (!searches?.length) return [];

  const ids = searches.map((s) => s.id);
  const { data: results } = await supabase
    .from("flight_results")
    .select("search_id, price_eur, captured_at")
    .in("search_id", ids);

  const byId: Record<string, { min: number | null; last: string | null }> = {};
  for (const id of ids) byId[id] = { min: null, last: null };
  for (const r of (results ?? []) as Pick<FlightResult, "search_id" | "price_eur" | "captured_at">[]) {
    const acc = byId[r.search_id];
    if (acc.min === null || r.price_eur < acc.min) acc.min = r.price_eur;
    if (acc.last === null || r.captured_at > acc.last) acc.last = r.captured_at;
  }
  return (searches as Search[]).map((s) => ({
    ...s,
    min_price: byId[s.id].min,
    last_captured_at: byId[s.id].last,
  }));
}

export async function getSearchAndResults(
  id: string,
): Promise<{ search: Search; results: FlightResult[] } | null> {
  if (DEMO) return demoSearchAndResults(id);
  const supabase = serverClient();
  const { data: search } = await supabase.from("searches").select("*").eq("id", id).maybeSingle();
  if (!search) return null;
  const { data: results } = await supabase
    .from("flight_results")
    .select("*")
    .eq("search_id", id)
    .order("captured_at", { ascending: false })
    .limit(200);
  return { search: search as Search, results: (results as FlightResult[]) ?? [] };
}

function demoSearchesWithStats(): SearchWithStats[] {
  return DEMO_SEARCHES.map((s) => {
    const stats = DEMO_RESULTS.filter((r) => r.search_id === s.id);
    const min = stats.length ? Math.min(...stats.map((r) => r.price_eur)) : null;
    const last = stats.length
      ? stats.map((r) => r.captured_at).sort().slice(-1)[0]
      : null;
    return { ...s, min_price: min, last_captured_at: last };
  });
}

function demoSearchAndResults(id: string) {
  const search = DEMO_SEARCHES.find((s) => s.id === id);
  if (!search) return null;
  const results = DEMO_RESULTS.filter((r) => r.search_id === id).sort(
    (a, b) => b.captured_at.localeCompare(a.captured_at),
  );
  return { search, results };
}

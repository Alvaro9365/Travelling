import Link from "next/link";
import { serverClient, type Search, type FlightResult } from "@/lib/supabase";
import { parseDateRange } from "@/lib/ranges";

export const dynamic = "force-dynamic";

type SearchWithStats = Search & {
  min_price: number | null;
  last_captured_at: string | null;
};

async function loadSearches(): Promise<SearchWithStats[]> {
  const supabase = serverClient();
  const { data: searches } = await supabase
    .from("searches")
    .select("*")
    .order("created_at", { ascending: false });
  if (!searches?.length) return [];

  // One round-trip to fetch latest + min per search; small N so we just
  // hit flight_results twice.
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
  return searches.map((s) => ({
    ...(s as Search),
    min_price: byId[s.id].min,
    last_captured_at: byId[s.id].last,
  }));
}

export default async function Home() {
  const searches = await loadSearches();
  if (!searches.length) {
    return (
      <div className="rounded border bg-white p-8 text-center text-neutral-600">
        Aún no hay búsquedas.{" "}
        <Link href="/searches/new" className="text-blue-600 underline">
          Crea la primera
        </Link>
        .
      </div>
    );
  }
  return (
    <ul className="space-y-3">
      {searches.map((s) => {
        const window = parseDateRange(s.outbound_window);
        return (
          <li key={s.id} className="rounded border bg-white p-4 hover:shadow-sm">
            <Link href={`/searches/${s.id}`} className="block">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold">{s.name}</div>
                  <div className="text-sm text-neutral-600">
                    {s.origin_iata} → {destLabel(s)} ·{" "}
                    {window ? `${window.start} → ${window.end}` : "sin fechas"}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm text-neutral-500">
                    {s.active ? "Activa" : "Pausada"}
                  </div>
                  <div className="text-lg font-medium">
                    {s.min_price !== null ? `${s.min_price.toFixed(2)} €` : "—"}
                  </div>
                  <div className="text-xs text-neutral-500">
                    {s.last_captured_at
                      ? new Date(s.last_captured_at).toLocaleString()
                      : "sin datos aún"}
                  </div>
                </div>
              </div>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function destLabel(s: Search): string {
  const d = s.destinations;
  if (d.mode === "any") return d.region ? `cualquier ${d.region}` : "cualquier destino";
  if (d.mode === "include") return d.iatas.join(", ");
  return `cualquiera salvo ${d.iatas.join(", ") || "—"}`;
}

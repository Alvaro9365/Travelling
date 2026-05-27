import Link from "next/link";
import { notFound } from "next/navigation";

import PriceHistoryChart, { type PricePoint } from "@/components/PriceHistoryChart";
import { getSearchAndResults } from "@/lib/data";
import type { FlightResult, Search } from "@/lib/supabase";
import { parseDateRange, parseIntRange } from "@/lib/ranges";
import { deleteSearch, toggleActive } from "../actions";

export const dynamic = "force-dynamic";

export default async function SearchDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const loaded = await getSearchAndResults(id);
  if (!loaded) notFound();
  const { search, results } = loaded;

  const history = aggregateMinPerDay(results);
  const recent = results.slice(0, 20);

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{search.name}</h1>
          <p className="text-sm text-neutral-600">{summary(search)}</p>
        </div>
        <div className="flex gap-2">
          <form action={async () => { "use server"; await toggleActive(id, !search.active); }}>
            <button className="rounded border px-3 py-1.5 text-sm hover:bg-neutral-100">
              {search.active ? "Pausar" : "Reactivar"}
            </button>
          </form>
          <form action={async () => { "use server"; await deleteSearch(id); }}>
            <button className="rounded border border-red-300 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50">
              Borrar
            </button>
          </form>
        </div>
      </header>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-neutral-700">Evolución del precio mínimo</h2>
        <PriceHistoryChart data={history} />
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-neutral-700">Últimas ofertas</h2>
        {recent.length === 0 ? (
          <div className="rounded border bg-white p-6 text-sm text-neutral-500">Aún sin resultados.</div>
        ) : (
          <table className="w-full overflow-hidden rounded border bg-white text-sm">
            <thead className="bg-neutral-100 text-left">
              <tr>
                <th className="px-3 py-2">Capturada</th>
                <th className="px-3 py-2">Destino</th>
                <th className="px-3 py-2">Fechas</th>
                <th className="px-3 py-2 text-right">Precio</th>
                <th className="px-3 py-2">Reservar</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((r) => (
                <tr key={r.id} className="border-t">
                  <td className="px-3 py-2 text-neutral-500">{new Date(r.captured_at).toLocaleString()}</td>
                  <td className="px-3 py-2">{r.origin_iata} → {r.destination_iata}</td>
                  <td className="px-3 py-2">
                    {r.departure_date}{r.return_date ? ` → ${r.return_date}` : ""}
                  </td>
                  <td className="px-3 py-2 text-right font-medium">{r.price_eur.toFixed(2)} €</td>
                  <td className="px-3 py-2">
                    {r.deep_link ? (
                      <a className="text-blue-600 underline" href={r.deep_link} target="_blank" rel="noreferrer">
                        Ver
                      </a>
                    ) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <Link href="/" className="inline-block text-sm text-neutral-600 hover:underline">← Volver</Link>
    </div>
  );
}

function aggregateMinPerDay(results: FlightResult[]): PricePoint[] {
  const byDay = new Map<string, number>();
  for (const r of results) {
    const day = r.captured_at.slice(0, 10);
    const cur = byDay.get(day);
    if (cur === undefined || r.price_eur < cur) byDay.set(day, r.price_eur);
  }
  return [...byDay.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, min_price]) => ({ day, min_price }));
}

function summary(s: Search): string {
  const window = parseDateRange(s.outbound_window);
  const dur = parseIntRange(s.duration_days);
  const dest =
    s.destinations.mode === "any" ? "cualquier destino" :
    s.destinations.mode === "include" ? `solo ${s.destinations.iatas.join(", ")}` :
    `cualquiera salvo ${s.destinations.iatas.join(", ") || "—"}`;
  const dates = window ? `${window.start} → ${window.end}` : "fechas sin definir";
  const duration = dur ? ` · ${dur.min}–${dur.max} días` : "";
  const price = s.price_range?.max ? ` · hasta ${s.price_range.max} €` : "";
  return `${s.origin_iata} → ${dest} · ${dates}${duration}${price}`;
}

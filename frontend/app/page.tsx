import Link from "next/link";
import { listSearchesWithStats } from "@/lib/data";
import type { Search } from "@/lib/supabase";
import { parseDateRange } from "@/lib/ranges";

export const dynamic = "force-dynamic";

export default async function Home() {
  const searches = await listSearchesWithStats();
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

// Sample data for DEMO_MODE — used by `lib/data.ts` so reviewers can boot
// the UI without configuring Supabase.

import type { FlightResult, Search } from "./supabase";

export const DEMO_SEARCHES: Search[] = [
  {
    id: "demo-europe",
    name: "Escapada verano (cualquier destino)",
    active: true,
    origin_iata: "MAD",
    trip_type: "round_trip",
    outbound_window: "[2026-07-10,2026-07-25]",
    duration_days: "[5,10]",
    destinations: { mode: "any", region: "EUROPE" },
    price_range: { min: 0, max: 250, currency: "EUR" },
    filters: { max_stops: 1, max_duration_minutes: 480, excluded_airlines: [] },
    notify_on: { price_under: 180, new_lowest: true },
    created_at: "2026-05-01T10:00:00Z",
    updated_at: "2026-05-01T10:00:00Z",
  },
  {
    id: "demo-lis-cdg",
    name: "Puente de mayo Lisboa o París",
    active: true,
    origin_iata: "MAD",
    trip_type: "round_trip",
    outbound_window: "[2026-05-01,2026-05-03]",
    duration_days: "[3,4]",
    destinations: { mode: "include", iatas: ["LIS", "CDG"] },
    price_range: { min: 0, max: 200, currency: "EUR" },
    filters: { max_stops: 0, excluded_airlines: ["RYR"] },
    notify_on: { price_under: 150, new_lowest: false },
    created_at: "2026-04-10T09:00:00Z",
    updated_at: "2026-04-10T09:00:00Z",
  },
  {
    id: "demo-paused",
    name: "Viaje a Japón (en pausa)",
    active: false,
    origin_iata: "MAD",
    trip_type: "round_trip",
    outbound_window: "[2026-10-01,2026-10-31]",
    duration_days: "[12,21]",
    destinations: { mode: "include", iatas: ["NRT", "HND", "KIX"] },
    price_range: null,
    filters: {},
    notify_on: { new_lowest: true },
    created_at: "2026-03-20T08:00:00Z",
    updated_at: "2026-03-20T08:00:00Z",
  },
];

export const DEMO_RESULTS: FlightResult[] = (() => {
  const out: FlightResult[] = [];
  const start = new Date("2026-05-13T08:00:00Z");
  for (let i = 0; i < 14; i++) {
    const day = new Date(start);
    day.setUTCDate(day.getUTCDate() + i);
    const captured = day.toISOString();
    const base = 240 - i * 4 + (i % 3) * 7;
    out.push({
      id: `er-${i}-lis`,
      search_id: "demo-europe",
      captured_at: captured,
      origin_iata: "MAD",
      destination_iata: "LIS",
      departure_date: "2026-07-12",
      return_date: "2026-07-19",
      price_eur: base,
      airline: null,
      stops: null,
      duration_minutes: null,
      deep_link: "https://test.api.amadeus.com/v2/shopping/flight-offers?demo=1",
    });
    out.push({
      id: `er-${i}-fco`,
      search_id: "demo-europe",
      captured_at: captured,
      origin_iata: "MAD",
      destination_iata: "FCO",
      departure_date: "2026-07-15",
      return_date: "2026-07-22",
      price_eur: base + 20,
      airline: null,
      stops: null,
      duration_minutes: null,
      deep_link: null,
    });
  }
  for (let i = 0; i < 5; i++) {
    const day = new Date("2026-05-21T10:00:00Z");
    day.setUTCDate(day.getUTCDate() + i);
    out.push({
      id: `il-${i}`,
      search_id: "demo-lis-cdg",
      captured_at: day.toISOString(),
      origin_iata: "MAD",
      destination_iata: i % 2 ? "CDG" : "LIS",
      departure_date: "2026-05-02",
      return_date: "2026-05-05",
      price_eur: 175 - i * 6,
      airline: null,
      stops: null,
      duration_minutes: null,
      deep_link: null,
    });
  }
  return out;
})();

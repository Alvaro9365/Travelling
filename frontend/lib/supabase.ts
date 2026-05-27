import { createClient, SupabaseClient } from "@supabase/supabase-js";

export type Search = {
  id: string;
  name: string;
  active: boolean;
  origin_iata: string;
  trip_type: "round_trip" | "one_way";
  outbound_window: string;
  duration_days: string | null;
  destinations:
    | { mode: "include"; iatas: string[] }
    | { mode: "exclude"; iatas: string[] }
    | { mode: "any"; region?: string | null };
  price_range: { min?: number; max?: number; currency?: string } | null;
  filters: {
    max_stops?: number;
    max_duration_minutes?: number;
    excluded_airlines?: string[];
  };
  notify_on: { price_under?: number; new_lowest?: boolean };
  created_at: string;
  updated_at: string;
};

export type FlightResult = {
  id: string;
  search_id: string;
  captured_at: string;
  origin_iata: string;
  destination_iata: string;
  departure_date: string;
  return_date: string | null;
  price_eur: number;
  airline: string | null;
  stops: number | null;
  duration_minutes: number | null;
  deep_link: string | null;
};

// Server-side client uses the service key so it bypasses RLS. Never import
// this module from a Client Component — keep it in server actions / RSCs.
export function serverClient(): SupabaseClient {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !key) throw new Error("Missing SUPABASE_URL / SUPABASE_SERVICE_KEY");
  return createClient(url, key, { auth: { persistSession: false } });
}

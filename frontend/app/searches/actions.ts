"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { z } from "zod";

import { serverClient } from "@/lib/supabase";
import { fmtDateRange, fmtIntRange } from "@/lib/ranges";

const iatas = z
  .string()
  .optional()
  .transform((s) =>
    (s ?? "")
      .split(/[,\s]+/)
      .map((x) => x.trim().toUpperCase())
      .filter((x) => x.length === 3),
  );

const Form = z.object({
  name: z.string().min(1),
  active: z.preprocess((v) => v === "on" || v === true, z.boolean()).optional(),
  origin_iata: z.string().length(3).transform((s) => s.toUpperCase()),
  trip_type: z.enum(["round_trip", "one_way"]),
  outbound_start: z.string().min(10),
  outbound_end: z.string().min(10),
  duration_min: z.coerce.number().int().min(1).optional(),
  duration_max: z.coerce.number().int().min(1).optional(),
  dest_mode: z.enum(["include", "exclude", "any"]),
  dest_iatas: iatas,
  dest_region: z.string().optional(),
  price_min: z.coerce.number().min(0).optional().or(z.literal("")),
  price_max: z.coerce.number().min(0).optional().or(z.literal("")),
  max_stops: z.coerce.number().int().min(0).optional().or(z.literal("")),
  max_duration_minutes: z.coerce.number().int().min(0).optional().or(z.literal("")),
  excluded_airlines: iatas,
  notify_price_under: z.coerce.number().min(0).optional().or(z.literal("")),
  notify_new_lowest: z.preprocess((v) => v === "on" || v === true, z.boolean()).optional(),
});

function num(v: unknown): number | undefined {
  return typeof v === "number" && !Number.isNaN(v) ? v : undefined;
}

const DEMO = process.env.DEMO_MODE === "1";

export async function createSearch(formData: FormData) {
  if (DEMO) {
    // In demo mode just bounce back to the home page — no Supabase available.
    revalidatePath("/");
    redirect("/");
  }
  const raw: Record<string, FormDataEntryValue> = {};
  formData.forEach((v, k) => {
    raw[k] = v;
  });
  const data = Form.parse(raw);

  const destinations =
    data.dest_mode === "any"
      ? { mode: "any" as const, region: data.dest_region || null }
      : data.dest_mode === "include"
      ? { mode: "include" as const, iatas: data.dest_iatas }
      : { mode: "exclude" as const, iatas: data.dest_iatas };

  const priceMin = num(data.price_min);
  const priceMax = num(data.price_max);
  const price_range =
    priceMin === undefined && priceMax === undefined
      ? null
      : { min: priceMin, max: priceMax, currency: "EUR" };

  const filters = {
    max_stops: num(data.max_stops),
    max_duration_minutes: num(data.max_duration_minutes),
    excluded_airlines: data.excluded_airlines,
  };

  const notify_on = {
    price_under: num(data.notify_price_under),
    new_lowest: !!data.notify_new_lowest,
  };

  const payload: Record<string, unknown> = {
    name: data.name,
    active: data.active ?? true,
    origin_iata: data.origin_iata,
    trip_type: data.trip_type,
    outbound_window: fmtDateRange({ start: data.outbound_start, end: data.outbound_end }),
    duration_days:
      data.trip_type === "round_trip" && data.duration_min && data.duration_max
        ? fmtIntRange({ min: data.duration_min, max: data.duration_max })
        : null,
    destinations,
    price_range,
    filters,
    notify_on,
  };

  const supabase = serverClient();
  const { data: inserted, error } = await supabase
    .from("searches")
    .insert(payload)
    .select("id")
    .single();
  if (error) throw new Error(error.message);

  revalidatePath("/");
  redirect(`/searches/${inserted.id}`);
}

export async function deleteSearch(id: string) {
  if (DEMO) {
    revalidatePath("/");
    redirect("/");
  }
  const supabase = serverClient();
  const { error } = await supabase.from("searches").delete().eq("id", id);
  if (error) throw new Error(error.message);
  revalidatePath("/");
  redirect("/");
}

export async function toggleActive(id: string, active: boolean) {
  if (DEMO) {
    revalidatePath(`/searches/${id}`);
    return;
  }
  const supabase = serverClient();
  const { error } = await supabase.from("searches").update({ active }).eq("id", id);
  if (error) throw new Error(error.message);
  revalidatePath("/");
  revalidatePath(`/searches/${id}`);
}

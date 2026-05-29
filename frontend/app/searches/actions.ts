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

// Empty form fields arrive as "" — coerce.number would silently turn that
// into 0, so an empty `max_stops` field would mean "direct flights only".
// Treat blanks as `undefined` before coercing.
const optionalNumber = (extra?: (n: z.ZodNumber) => z.ZodNumber) =>
  z.preprocess(
    (v) => (v === "" || v === null || v === undefined ? undefined : v),
    extra ? extra(z.coerce.number()).optional() : z.coerce.number().optional(),
  );

const checkbox = z.preprocess((v) => v === "on" || v === true, z.boolean()).optional();

const Form = z.object({
  name: z.string().min(1),
  active: checkbox,
  origin_iata: z.string().length(3).transform((s) => s.toUpperCase()),
  trip_type: z.enum(["round_trip", "one_way"]),
  outbound_start: z.string().min(10),
  outbound_end: z.string().min(10),
  duration_min: optionalNumber((n) => n.int().min(1)),
  duration_max: optionalNumber((n) => n.int().min(1)),
  dest_mode: z.enum(["include", "exclude", "any"]),
  dest_iatas: iatas,
  dest_region: z.string().optional(),
  price_min: optionalNumber((n) => n.min(0)),
  price_max: optionalNumber((n) => n.min(0)),
  max_stops: optionalNumber((n) => n.int().min(0)),
  max_duration_minutes: optionalNumber((n) => n.int().min(0)),
  excluded_airlines: iatas,
  notify_price_under: optionalNumber((n) => n.min(0)),
  notify_new_lowest: checkbox,
});

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

  const price_range =
    data.price_min === undefined && data.price_max === undefined
      ? null
      : { min: data.price_min, max: data.price_max, currency: "EUR" };

  const filters = {
    max_stops: data.max_stops,
    max_duration_minutes: data.max_duration_minutes,
    excluded_airlines: data.excluded_airlines,
  };

  const notify_on = {
    price_under: data.notify_price_under,
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

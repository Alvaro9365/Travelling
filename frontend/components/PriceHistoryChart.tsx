"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type PricePoint = { day: string; min_price: number };

export default function PriceHistoryChart({ data }: { data: PricePoint[] }) {
  if (!data.length) {
    return (
      <div className="rounded border bg-white p-6 text-sm text-neutral-500">
        Sin datos suficientes todavía. Se irá rellenando cada vez que se ejecute el cron.
      </div>
    );
  }
  return (
    <div className="h-72 w-full rounded border bg-white p-4">
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="day" />
          <YAxis tickFormatter={(v) => `${v} €`} />
          <Tooltip formatter={(v: number) => `${v.toFixed(2)} €`} />
          <Line
            type="monotone"
            dataKey="min_price"
            stroke="#171717"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

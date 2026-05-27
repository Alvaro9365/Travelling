import "./globals.css";
import Link from "next/link";
import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Flight Monitor",
  description: "Monitor de vuelos con búsquedas flexibles.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body>
        <header className="border-b bg-white">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
            <Link href="/" className="text-lg font-semibold">Flight Monitor</Link>
            <Link
              href="/searches/new"
              className="rounded bg-neutral-900 px-3 py-1.5 text-sm text-white hover:bg-neutral-700"
            >
              Nueva búsqueda
            </Link>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}

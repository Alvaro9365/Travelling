import { createSearch } from "@/app/searches/actions";

export default function SearchForm() {
  return (
    <form action={createSearch} className="space-y-6">
      <Section title="Identificación">
        <Field label="Nombre">
          <input name="name" required className={input} placeholder="Escapada verano" />
        </Field>
      </Section>

      <Section title="Origen y tipo de viaje">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Aeropuerto origen (IATA)">
            <input name="origin_iata" required minLength={3} maxLength={3}
                   className={input} placeholder="MAD" />
          </Field>
          <Field label="Tipo de viaje">
            <select name="trip_type" className={input} defaultValue="round_trip">
              <option value="round_trip">Ida y vuelta</option>
              <option value="one_way">Solo ida</option>
            </select>
          </Field>
        </div>
      </Section>

      <Section title="Fechas">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Salida desde"><input name="outbound_start" type="date" required className={input} /></Field>
          <Field label="Salida hasta"><input name="outbound_end" type="date" required className={input} /></Field>
          <Field label="Duración mín. (días)"><input name="duration_min" type="number" min={1} className={input} placeholder="5" /></Field>
          <Field label="Duración máx. (días)"><input name="duration_max" type="number" min={1} className={input} placeholder="10" /></Field>
        </div>
        <p className="text-xs text-neutral-500">
          Para fecha fija, pon el mismo día en ambos campos. La duración solo aplica a ida y vuelta.
        </p>
      </Section>

      <Section title="Destinos">
        <Field label="Modo">
          <select name="dest_mode" className={input} defaultValue="any">
            <option value="any">Cualquier destino</option>
            <option value="include">Solo estos destinos</option>
            <option value="exclude">Cualquiera salvo estos</option>
          </select>
        </Field>
        <Field label="IATAs (separados por coma)">
          <input name="dest_iatas" className={input} placeholder="LIS, CDG, FCO" />
        </Field>
        <Field label="Región (opcional, solo modo cualquiera)">
          <input name="dest_region" className={input} placeholder="EUROPE" />
        </Field>
      </Section>

      <Section title="Rango de precios">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Mín (€)"><input name="price_min" type="number" min={0} step="0.01" className={input} /></Field>
          <Field label="Máx (€)"><input name="price_max" type="number" min={0} step="0.01" className={input} placeholder="250" /></Field>
        </div>
      </Section>

      <Section title="Filtros avanzados">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Máx. escalas"><input name="max_stops" type="number" min={0} className={input} placeholder="1" /></Field>
          <Field label="Máx. duración vuelo (min)"><input name="max_duration_minutes" type="number" min={0} className={input} placeholder="480" /></Field>
        </div>
        <Field label="Aerolíneas excluidas (códigos IATA, separados por coma)">
          <input name="excluded_airlines" className={input} placeholder="RYR, W6" />
        </Field>
      </Section>

      <Section title="Notificaciones">
        <Field label="Avisar cuando el precio sea ≤ (€)">
          <input name="notify_price_under" type="number" min={0} step="0.01" className={input} placeholder="200" />
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input name="notify_new_lowest" type="checkbox" />
          Avisar cuando aparezca un nuevo mínimo histórico
        </label>
      </Section>

      <button
        type="submit"
        className="rounded bg-neutral-900 px-4 py-2 text-white hover:bg-neutral-700"
      >
        Crear búsqueda
      </button>
    </form>
  );
}

const input = "w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-neutral-900 focus:outline-none";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <fieldset className="space-y-3 rounded border bg-white p-4">
      <legend className="px-2 text-sm font-semibold text-neutral-700">{title}</legend>
      {children}
    </fieldset>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium text-neutral-700">{label}</span>
      {children}
    </label>
  );
}

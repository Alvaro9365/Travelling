# Flight Monitor

Automatización que consulta cada 2 h vuelos en Amadeus para un conjunto
configurable de búsquedas (orígenes, ventanas de fechas, destinos y
precios) y notifica por Telegram cuando aparece una oferta interesante.

```
GitHub Actions (cron) ──► Python runner ──► Amadeus API
                                │
                                ▼
                      Supabase Postgres ◄──── Next.js (Vercel)
                                │
                                ▼
                         Telegram Bot
```

## Estructura

- `backend/` — runner Python (cron + Amadeus + Telegram).
- `frontend/` — Next.js (App Router) en Vercel para crear y visualizar búsquedas.
- `supabase/migrations/` — esquema SQL.
- `.github/workflows/flight-monitor.yml` — cron `0 */2 * * *`.

## Setup

### 1. Supabase

Crear proyecto en https://supabase.com, abrir el SQL Editor y ejecutar
`supabase/migrations/0001_initial.sql`. Anotar `SUPABASE_URL` y
`SUPABASE_SERVICE_KEY` (Project Settings → API).

### 2. Amadeus

Registrarse en https://developers.amadeus.com, crear una app self-service
(modo `test`) y anotar `AMADEUS_CLIENT_ID` y `AMADEUS_CLIENT_SECRET`.

### 3. Telegram

Hablar con `@BotFather` para crear un bot, anotar `TELEGRAM_BOT_TOKEN`.
Hablar con `@userinfobot` y anotar el `TELEGRAM_CHAT_ID` propio.

### 4. Secrets en GitHub

En Repo → Settings → Secrets and variables → Actions añadir:
`AMADEUS_CLIENT_ID`, `AMADEUS_CLIENT_SECRET`, `SUPABASE_URL`,
`SUPABASE_SERVICE_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

### 5. Vercel

Importar el repo, root directory `frontend/`. Variables de entorno:
`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`. Deploy.

## Desarrollo local

```bash
# Backend
cd backend
uv sync --dev
uv run pytest                  # tests unitarios
cp ../.env.example .env && $EDITOR .env
set -a && source .env && set +a
uv run python -m flightmon run --search-id <uuid>

# Frontend
cd ../frontend
npm install
SUPABASE_URL=... SUPABASE_SERVICE_KEY=... npm run dev
# abrir http://localhost:3000
```

## Verificación end-to-end

1. Crear una búsqueda desde `/searches/new` (ej. `MAD → cualquier destino`,
   próximos 60 días, precio máx 200 €).
2. Lanzar el workflow manualmente desde la pestaña "Actions" de GitHub.
3. Comprobar en Supabase Studio que `flight_results` tiene filas nuevas.
4. Si alguna oferta cumple el umbral configurado, llegará un mensaje al chat
   de Telegram.
5. Volver al detalle de la búsqueda y ver el histórico en el gráfico.

## Roadmap

- Enriquecimiento con `/v2/shopping/flight-offers` para airline/stops/duración.
- Edición de búsquedas desde la UI.
- Proveedores hoteles, transporte local y POIs (interfaz `Provider` ya está
  preparada en `backend/flightmon/providers/base.py`).
- Propuestas de viaje completas (vuelo + alojamiento + duración recomendada).

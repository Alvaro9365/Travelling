# Flight Monitor

Automatización que consulta cada 2 h vuelos en Amadeus para un conjunto
configurable de búsquedas y publica los resultados en un **dashboard
estático en GitHub Pages** que se puede consultar en cualquier momento.

Las alertas por Telegram (opcionales) siguen disponibles, pero el origen de
verdad para consultar gangas y evolución de precios es el dashboard.

```
┌─────────────────────────────────────────────────────────────────────┐
│ GitHub Actions cron (cada 2 h)                                      │
│   └── python -m flightmon run                                       │
│        ├── lee data/searches.yaml                                   │
│        ├── consulta Amadeus (inspiration / cheapest-dates)          │
│        ├── escribe data/results.json + data/history/<id>.jsonl      │
│        ├── construye data/dashboard.json                            │
│        ├── (opcional) avisa por Telegram                            │
│        ├── commit & push de data/ al repo                           │
│        └── deploy del dashboard a GitHub Pages                      │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
              https://alvaro9365.github.io/travelling/
```

## Setup (una sola vez)

### 1. Habilitar GitHub Pages

`Settings → Pages → Source → GitHub Actions`.

### 2. Configurar secretos

`Settings → Secrets and variables → Actions → New secret`:

| Secreto | Cómo conseguirlo |
|---|---|
| `AMADEUS_CLIENT_ID` / `AMADEUS_CLIENT_SECRET` | https://developers.amadeus.com → My Self-Service Workspace |
| `TELEGRAM_BOT_TOKEN` *(opcional)* | Bot creado con `@BotFather` |
| `TELEGRAM_CHAT_ID` *(opcional)* | Tu chat ID via `@userinfobot` |

Sin las dos variables de Telegram el cron sigue funcionando, solo se omiten
las notificaciones.

### 3. Editar `data/searches.yaml`

Es la única fuente de verdad de qué se monitoriza. Cualquier cambio se
recoge en la siguiente ejecución del cron. Ejemplo mínimo:

```yaml
searches:
  - id: verano-europa
    name: Escapada verano Europa
    active: true
    origin_iata: MAD
    trip_type: round_trip
    outbound_window: { start: 2026-07-10, end: 2026-07-25 }
    duration_days: { min: 5, max: 10 }
    destinations: { mode: any, region: EUROPE }
    price_range: { max: 250 }
    notify_on: { price_under: 180, new_lowest: true }
```

Modos de destino:
- `any` → cualquier destino (Amadeus Flight Inspiration). Soporta `price_range.max`.
- `include` → solo los IATAs listados.
- `exclude` → cualquiera menos los listados.

### 4. Lanzar el primer run

`Actions → flight-monitor → Run workflow`. Tras unos segundos:
- Aparece `data/dashboard.json` en el repo.
- El job de Pages despliega `https://<usuario>.github.io/<repo>/`.

## Desarrollo local

```bash
cd backend
uv sync --dev
uv run pytest               # 30 tests

# Smoke test contra Amadeus test (necesita credenciales):
AMADEUS_CLIENT_ID=... AMADEUS_CLIENT_SECRET=... \
  uv run python -m flightmon run

# Servir el dashboard estático con los datos generados:
python3 -m http.server -d dashboard 8000 &
ln -s "$PWD/data" dashboard/data        # solo para preview local
# abrir http://localhost:8000
```

## Estructura del repo

```
Travelling/
├── data/
│   ├── searches.yaml          # ← TÚ editas esto
│   ├── results.json           # snapshot última ejecución (cron)
│   ├── notifications.json     # dedup de alertas Telegram (cron)
│   ├── runs.jsonl             # log de ejecuciones (cron)
│   ├── dashboard.json         # JSON único que consume el front (cron)
│   └── history/<search>.jsonl # histórico append-only (cron)
├── backend/
│   └── flightmon/             # provider Amadeus, expander, runner, notifier, storage
├── dashboard/                 # estático HTML + CSS + vanilla JS (sin build)
└── .github/workflows/
    └── flight-monitor.yml     # cron + commit-back + deploy Pages
```

## Roadmap

- Múltiples búsquedas en `searches.yaml` (ya soportado, solo añadir entradas).
- Enriquecer con `/v2/shopping/flight-offers` para tener `airline`, `stops`, `duration` reales.
- Vistas de "alojamiento sugerido" y "rutas en destino" cuando llegue ese trabajo
  (la interfaz `FlightProvider` deja preparada la extensión a otros providers).

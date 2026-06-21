# Flight Monitor

Automatización que consulta cada 2 h vuelos en **Google Flights** (vía la
librería [`fast-flights`](https://github.com/AWeirdDev/flights), gratuita y
sin credenciales) para un conjunto configurable de búsquedas y publica
los resultados en un **dashboard estático en GitHub Pages** que se puede
consultar en cualquier momento.

Las alertas por Telegram (opcionales) siguen disponibles, pero el origen de
verdad para consultar gangas y evolución de precios es el dashboard.

```
┌─────────────────────────────────────────────────────────────────────┐
│ GitHub Actions cron (cada 2 h)                                      │
│   └── python -m flightmon run                                       │
│        ├── lee data/searches.yaml                                   │
│        ├── consulta Google Flights (fast-flights, sin credenciales) │
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

### 2. Configurar secretos (opcionales)

`fast-flights` no necesita credenciales: el cron funciona sin tocar
secretos. Si quieres que además te lleguen alertas a Telegram, añade en
`Settings → Secrets and variables → Actions → New secret`:

| Secreto | Cómo conseguirlo |
|---|---|
| `TELEGRAM_BOT_TOKEN` *(opcional)* | Bot creado con `@BotFather` |
| `TELEGRAM_CHAT_ID` *(opcional)* | Tu chat ID via `@userinfobot` |

Sin esas dos variables el cron sigue funcionando, solo se omiten las
notificaciones — el dashboard es la fuente principal.

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
- `include` → solo los IATAs listados (**recomendado** con fast-flights).
- `exclude` → cualquiera menos los listados.
- `any` → muestrea un pool curado de ~25 hubs europeos (LIS, CDG, FCO, AMS,
  BER, LHR, DUB, OPO, MXP, BCN, VLC, AGP, PMI, ATH, VIE, PRG, BUD, CPH,
  ARN, OSL, ZRH, BRU, MUC, HEL, NAP). Soporta `price_range.max` para
  filtrar offers.

Coste de llamadas:
fast-flights hace 1 query a Google Flights por (destino × fecha muestreada
× duración muestreada). Por defecto muestrea 2 fechas × 2 duraciones = 4
queries por destino y run, con throttle de 1 s. Para `mode: include` con 3
destinos = 12 queries/run ≈ 144/día (asumible). Para `mode: any` con el
pool por defecto = ~100 queries/run ≈ 1200/día (margen ajustado: si Google
te empieza a bloquear, baja la cadencia del cron o usa `include`).

### 4. Lanzar el primer run

`Actions → flight-monitor → Run workflow`. Tras unos segundos:
- Aparece `data/dashboard.json` en el repo.
- El job de Pages despliega `https://<usuario>.github.io/<repo>/`.

## Desarrollo local

```bash
cd backend
uv sync --dev
uv run pytest               # 40 tests

# Smoke test contra Google Flights (sin credenciales):
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

## Proveedores alternativos

`FlightProvider` (`backend/flightmon/providers/base.py`) es una interfaz
abstracta. Hoy hay dos implementaciones disponibles:

- `fastflights.py` — **default**, Google Flights, gratis.
- `amadeus.py` — Amadeus Self-Service (necesita credenciales y, para
  datos reales, suscripción de pago). Se queda en el repo como fallback
  si Google rompe la API interna.

Para forzar Amadeus, modifica `cli.py` para instanciar `AmadeusProvider`
en vez de `FastFlightsProvider` y añade los secretos `AMADEUS_CLIENT_ID`,
`AMADEUS_CLIENT_SECRET`, `AMADEUS_HOSTNAME` (`test` o `production`).

## Roadmap

- Múltiples búsquedas en `searches.yaml` (ya soportado, solo añadir entradas).
- Selector de provider por búsqueda en el YAML (cuando se necesite hibridar).
- Vistas de "alojamiento sugerido" y "rutas en destino" cuando llegue ese trabajo.

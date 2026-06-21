# Flight Monitor

Automatización que consulta cada 2 h vuelos vía **Travelpayouts**
(agregador del buscador Aviasales, gratuito tras registro como afiliado
sin tarjeta) para un conjunto configurable de búsquedas y publica los
resultados en un **dashboard estático en GitHub Pages** que se puede
consultar en cualquier momento.

> **Nota sobre la fuente de datos:** Travelpayouts sirve precios cacheados
> de búsquedas reales que han hecho otros usuarios en Aviasales /
> Jetradar en las últimas ~48 h. Cobertura excelente para rutas populares
> (MAD-LIS, MAD-CDG, etc.) y patchier para rutas raras. El enlace de
> reserva lleva a Aviasales, que confirma el precio en vivo al pinchar.

Las alertas por Telegram (opcionales) siguen disponibles, pero el origen de
verdad para consultar gangas y evolución de precios es el dashboard.

```
┌─────────────────────────────────────────────────────────────────────┐
│ GitHub Actions cron (cada 2 h)                                      │
│   └── python -m flightmon run                                       │
│        ├── lee data/searches.yaml                                   │
│        ├── consulta Travelpayouts /v1/prices/cheap                  │
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

### 2. Crear cuenta Travelpayouts y obtener token

1. Regístrate (gratis, sin tarjeta) en https://www.travelpayouts.com/programs/100/.
2. En tu panel, `Tools → Data Access API`, copia el **API Token**.
3. (Opcional) Copia también tu **Marker** (ID de afiliado) — solo se usa
   para que Aviasales atribuya las reservas que hagas tú; no afecta a la
   funcionalidad.

### 3. Configurar secretos en GitHub

`Settings → Secrets and variables → Actions → New secret`:

| Secreto | Obligatorio | Cómo conseguirlo |
|---|---|---|
| `TRAVELPAYOUTS_TOKEN` | sí | Panel Travelpayouts → Tools → Data Access API |
| `TRAVELPAYOUTS_MARKER` | no | Panel Travelpayouts → tu ID de afiliado |
| `TELEGRAM_BOT_TOKEN` | no | Bot creado con `@BotFather` |
| `TELEGRAM_CHAT_ID` | no | Tu chat ID via `@userinfobot` |

Sin Telegram el cron sigue funcionando; el dashboard es la fuente
principal de consulta.

### 4. Editar `data/searches.yaml`

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
- `include` → solo los IATAs listados.
- `exclude` → cualquiera salvo los listados (consulta endpoint open-ended y filtra).
- `any` → cualquier destino que aparezca en la cache de Aviasales para tu origen.

Llamadas por run:
Travelpayouts agrupa los precios por mes, así que cada destino son
~1 llamada/mes-de-ventana, lo cual es muy ligero (típicamente 1-3
llamadas por búsqueda). No hay riesgo de rate-limit con cron cada 2 h.

### 5. Lanzar el primer run

`Actions → flight-monitor → Run workflow`. Tras unos segundos:
- Aparece `data/dashboard.json` en el repo.
- El job de Pages despliega `https://<usuario>.github.io/<repo>/`.

## Desarrollo local

```bash
cd backend
uv sync --dev
uv run pytest               # 40 tests

# Smoke test contra Travelpayouts (necesita token):
TRAVELPAYOUTS_TOKEN=xxxxx uv run python -m flightmon run

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
abstracta. Implementaciones disponibles:

- `travelpayouts.py` — **default**, Aviasales cache, gratis.
- `amadeus.py` — Amadeus Self-Service (test gratis con datos sintéticos;
  producción de pago con datos reales). Para usarlo modifica `cli.py`
  para instanciar `AmadeusProvider` y añade secretos `AMADEUS_CLIENT_ID`,
  `AMADEUS_CLIENT_SECRET`, `AMADEUS_HOSTNAME`.

En el historial git puedes encontrar también una implementación
`fastflights.py` (Google Flights via la librería `fast-flights`); se
retiró porque Google dejó de pre-renderizar resultados en SSR y la
librería sin JS-runtime devuelve `payload[3][0] is None` → 0 ofertas.

## Roadmap

- Múltiples búsquedas en `searches.yaml` (ya soportado, solo añadir entradas).
- Selector de provider por búsqueda en el YAML (cuando se necesite hibridar).
- Vistas de "alojamiento sugerido" y "rutas en destino" cuando llegue ese trabajo.

// Static dashboard for Flight Monitor — fetches a single JSON snapshot
// produced by the cron and renders KPIs, deals, per-search history charts
// and a recent-runs feed. Zero external runtime dependencies.

const DATA_URL = "./data/dashboard.json";
const REPO_URL = "https://github.com/alvaro9365/travelling/blob/main/data/searches.yaml";

document.getElementById("repo-link").href = REPO_URL;

const fmtEur = (n) => (n == null ? "—" : new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n));
const fmtEur2 = (n) => (n == null ? "—" : new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" }).format(n));
const fmtDateTime = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(+d) ? iso : d.toLocaleString("es-ES", { dateStyle: "medium", timeStyle: "short" });
};
const fmtRelative = (iso) => {
  if (!iso) return "—";
  const diff = Date.now() - +new Date(iso);
  if (diff < 60_000) return "hace segundos";
  if (diff < 3_600_000) return `hace ${Math.round(diff / 60_000)} min`;
  if (diff < 86_400_000) return `hace ${Math.round(diff / 3_600_000)} h`;
  return `hace ${Math.round(diff / 86_400_000)} d`;
};
const esc = (s) => String(s ?? "").replace(/[&<>'"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[c]));

(async () => {
  try {
    const res = await fetch(DATA_URL, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    render(data);
  } catch (e) {
    document.getElementById("generated-at").textContent = "Sin datos todavía";
    document.getElementById("banner-slot").innerHTML = `
      <div class="card banner">
        No hay <code>data/dashboard.json</code> disponible (${esc(e.message)}). La primera ejecución del cron lo generará.
      </div>`;
    console.error(e);
  }
})();

function render(d) {
  document.getElementById("generated-at").textContent =
    `Actualizado ${fmtDateTime(d.generated_at)} · ${fmtRelative(d.generated_at)}`;
  renderKpis(d);
  renderDeals(d.deals || []);
  renderSearches(d.searches || []);
  renderRuns(d.recent_runs || []);
}

function renderKpis(d) {
  const cheapest = (d.deals || [])[0]?.price_eur ?? null;
  const t = d.totals || {};
  const kpis = [
    { label: "Búsquedas activas", value: `${t.active_searches ?? 0} / ${t.searches ?? 0}`, cls: "accent" },
    { label: "Ofertas en snapshot", value: t.offers ?? 0, cls: "" },
    { label: "Gangas detectadas", value: t.deals ?? 0, cls: "warn" },
    { label: "Mejor precio ahora", value: fmtEur(cheapest), cls: "accent" },
  ];
  document.getElementById("kpis").innerHTML = kpis
    .map((k) => `<div class="card kpi"><div class="label">${k.label}</div><div class="value ${k.cls}">${k.value}</div></div>`)
    .join("");
}

function renderDeals(deals) {
  document.getElementById("deals-count").textContent = `${deals.length} oferta(s)`;
  const el = document.getElementById("deals");
  if (!deals.length) {
    el.innerHTML = `<div class="banner empty">No hay ofertas por debajo de los umbrales configurados todavía.</div>`;
    return;
  }
  el.innerHTML = `
    <table>
      <thead><tr>
        <th>Búsqueda</th><th>Ruta</th><th>Fechas</th><th>Motivo</th><th class="right">Precio</th><th></th>
      </tr></thead>
      <tbody>
        ${deals.map((d) => `
          <tr class="deal-row">
            <td><a href="#search-${esc(d.search_id)}">${esc(d.search_name)}</a></td>
            <td class="muted">${esc(d.origin_iata)} → ${esc(d.destination_iata)}</td>
            <td class="muted">${d.departure_date}${d.return_date ? ` → ${d.return_date}` : ""}</td>
            <td><span class="pill warn">${esc(d.reason)}</span></td>
            <td class="right bold accent">${fmtEur2(d.price_eur)}</td>
            <td class="right">${d.deep_link ? `<a class="dim" target="_blank" rel="noreferrer" href="${esc(d.deep_link)}">Reservar →</a>` : ""}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

function renderSearches(searches) {
  document.getElementById("searches-count").textContent = `${searches.length} búsqueda(s)`;
  const el = document.getElementById("searches");
  if (!searches.length) {
    el.innerHTML = `<div class="card banner">Sin búsquedas configuradas. Añade entradas a <code>data/searches.yaml</code>.</div>`;
    return;
  }
  el.innerHTML = searches.map(searchCard).join("");
  for (const s of searches) attachSparkInteractions(s);
}

function searchCard(s) {
  const cfg = s.config || {};
  const offers = (s.offers || []).slice(0, 8);
  const dur = cfg.duration_days ? ` · ${esc(cfg.duration_days)}` : "";
  const price = cfg.price_max ? ` · hasta ${fmtEur(cfg.price_max)}` : "";
  const alert = cfg.price_under_alert ? ` · alerta ≤ ${fmtEur(cfg.price_under_alert)}` : "";
  const active = s.active
    ? `<span class="pill accent">Activa</span>`
    : `<span class="pill dim">Pausada</span>`;

  return `
    <div id="search-${esc(s.id)}" class="card search-card" style="margin-top:16px">
      <div class="search-head">
        <div>
          <div class="title"><h3>${esc(s.name)}</h3>${active}</div>
          <p class="meta">${esc(cfg.origin_iata || "")} → ${esc(cfg.destinations_label || "—")} · ${esc(cfg.outbound_window || "—")}${dur}${price}${alert}</p>
        </div>
        <div class="price-now">
          <div class="label">Mejor ahora</div>
          <div class="value">${fmtEur2(s.stats?.last_min ?? null)}</div>
          <div class="when">${fmtRelative(s.captured_at)}</div>
        </div>
      </div>
      <div class="search-body">
        <div class="chart-cell">
          <div class="cell-label">Histórico (min/día)</div>
          ${renderSpark(s)}
        </div>
        <div class="offers-cell">
          <div class="cell-label">Ofertas más baratas</div>
          ${offers.length
            ? `<table class="offers-list"><tbody>${offers.map((o) => `
                <tr>
                  <td class="muted">${esc(o.origin_iata)} → ${esc(o.destination_iata)}</td>
                  <td class="dim">${o.departure_date}${o.return_date ? ` → ${o.return_date}` : ""}</td>
                  <td class="right bold">${fmtEur2(o.price_eur)}</td>
                  <td class="right">${o.deep_link ? `<a class="dim" target="_blank" rel="noreferrer" href="${esc(o.deep_link)}">Reservar →</a>` : ""}</td>
                </tr>`).join("")}</tbody></table>`
            : `<p class="dim" style="margin:8px 0 0">Sin ofertas todavía.</p>`}
        </div>
      </div>
    </div>`;
}

// --- inline SVG sparkline -------------------------------------------------

function renderSpark(s) {
  const h = s.history || [];
  if (!h.length) return `<div class="no-history">Sin histórico aún</div>`;
  const W = 480, H = 176, PAD_L = 36, PAD_R = 8, PAD_T = 14, PAD_B = 22;
  const xs = h.map((p, i) => i);
  const ys = h.map((p) => p.min_price);
  const yMin = Math.min(...ys), yMax = Math.max(...ys);
  const ySpan = Math.max(yMax - yMin, 1);
  const xToPx = (i) => PAD_L + (i / Math.max(xs.length - 1, 1)) * (W - PAD_L - PAD_R);
  const yToPx = (v) => H - PAD_B - ((v - yMin) / ySpan) * (H - PAD_T - PAD_B);

  const linePoints = h.map((p, i) => `${xToPx(i)},${yToPx(p.min_price)}`).join(" ");
  const areaPath = `M${xToPx(0)},${H - PAD_B} L${linePoints.split(" ").join(" L")} L${xToPx(h.length - 1)},${H - PAD_B} Z`;
  const yTicks = [yMin, (yMin + yMax) / 2, yMax];
  const xTicks = pickTicks(h.length, 4);

  return `
    <div style="position:relative">
      <svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"
           data-points='${JSON.stringify(h.map((p, i) => ({ x: xToPx(i), y: yToPx(p.min_price), day: p.day, price: p.min_price })))}'>
        <line class="axis" x1="${PAD_L}" y1="${H - PAD_B}" x2="${W - PAD_R}" y2="${H - PAD_B}" />
        <line class="axis" x1="${PAD_L}" y1="${PAD_T}" x2="${PAD_L}" y2="${H - PAD_B}" />
        ${yTicks.map((v) => `
          <line class="axis" x1="${PAD_L}" y1="${yToPx(v)}" x2="${W - PAD_R}" y2="${yToPx(v)}" stroke-dasharray="2 4" stroke-opacity="0.5"/>
          <text x="${PAD_L - 6}" y="${yToPx(v) + 3}" text-anchor="end">${Math.round(v)} €</text>
        `).join("")}
        ${xTicks.map((i) => `<text x="${xToPx(i)}" y="${H - 6}" text-anchor="middle">${h[i].day.slice(5)}</text>`).join("")}
        <path class="area" d="${areaPath}" />
        <polyline class="line" points="${linePoints}" />
        <line class="hover-line" x1="0" y1="${PAD_T}" x2="0" y2="${H - PAD_B}" />
        <circle class="hover-dot" r="4" cx="0" cy="0" />
      </svg>
      <div class="spark-tooltip" style="display:none"></div>
    </div>`;
}

function pickTicks(n, maxTicks) {
  if (n <= maxTicks) return Array.from({ length: n }, (_, i) => i);
  const step = Math.max(1, Math.round((n - 1) / (maxTicks - 1)));
  const out = [];
  for (let i = 0; i < n; i += step) out.push(i);
  if (out[out.length - 1] !== n - 1) out.push(n - 1);
  return out;
}

function attachSparkInteractions(s) {
  const card = document.getElementById(`search-${s.id}`);
  if (!card) return;
  const svg = card.querySelector("svg.spark");
  if (!svg) return;
  const tooltip = card.querySelector(".spark-tooltip");
  const hoverLine = svg.querySelector(".hover-line");
  const hoverDot = svg.querySelector(".hover-dot");
  let points;
  try { points = JSON.parse(svg.dataset.points); } catch { return; }

  svg.addEventListener("mousemove", (ev) => {
    const rect = svg.getBoundingClientRect();
    const xRatio = (ev.clientX - rect.left) / rect.width;
    const viewX = xRatio * svg.viewBox.baseVal.width;
    let nearest = points[0];
    let bestDist = Math.abs(points[0].x - viewX);
    for (const p of points) {
      const d = Math.abs(p.x - viewX);
      if (d < bestDist) { nearest = p; bestDist = d; }
    }
    svg.classList.add("hovered");
    hoverLine.setAttribute("x1", nearest.x);
    hoverLine.setAttribute("x2", nearest.x);
    hoverDot.setAttribute("cx", nearest.x);
    hoverDot.setAttribute("cy", nearest.y);
    const pxX = (nearest.x / svg.viewBox.baseVal.width) * rect.width;
    const pxY = (nearest.y / svg.viewBox.baseVal.height) * rect.height;
    tooltip.style.display = "block";
    tooltip.style.left = `${pxX}px`;
    tooltip.style.top = `${pxY}px`;
    tooltip.innerHTML = `<strong>${fmtEur2(nearest.price)}</strong><br><span class="dim">${nearest.day}</span>`;
  });
  svg.addEventListener("mouseleave", () => {
    svg.classList.remove("hovered");
    tooltip.style.display = "none";
  });
}

function renderRuns(runs) {
  const el = document.getElementById("runs");
  if (!runs.length) { el.innerHTML = `<div class="banner empty">Sin ejecuciones registradas.</div>`; return; }
  el.innerHTML = `
    <table>
      <thead><tr>
        <th>Cuándo</th><th class="right">Búsquedas</th><th class="right">Ofertas</th>
        <th class="right">Notificadas</th><th class="right">Errores</th><th class="right">Duración</th>
      </tr></thead>
      <tbody>
        ${runs.map((r) => {
          const errs = (r.totals?.provider_errors ?? 0) + (r.totals?.failed_searches ?? 0);
          return `
            <tr>
              <td>${fmtDateTime(r.started_at)} <span class="dim">(${fmtRelative(r.started_at)})</span></td>
              <td class="right">${r.totals?.searches ?? 0}</td>
              <td class="right">${r.totals?.offers_kept ?? 0} / ${r.totals?.offers_returned ?? 0}</td>
              <td class="right">${r.totals?.notifications ?? 0}</td>
              <td class="right ${errs > 0 ? "warn" : "dim"}">${errs}</td>
              <td class="right dim">${r.duration_seconds ?? "—"}s</td>
            </tr>`;
        }).join("")}
      </tbody>
    </table>`;
}

/*
 * Eni Plenitude cards for Home Assistant.
 *
 *   custom:plenitude-consumption-card  consumption chart: default period chosen in the card settings, then
 *                                      day / week / month / year and back and forth on the card
 *   custom:plenitude-billing-card      current billing period (two months from a chosen day): kWh and cost
 *                                      so far, bands, estimate at the end of the period
 *
 * Costs: the cost statistic is kWh x (price of the band + costs per kWh). The periodic costs entered in the
 * integration (monthly, two-monthly, yearly, per kW per month) count in full, as entered: every month carries
 * 1/12 of their euro per year, split among its days; a billing period carries its months in full, also before
 * it is over (9 euro a month: 18 euro in a two-month bill).
 * Texts in Italian and English, following the language of the user's profile.
 *
 * The statistics change about once a day, when the integration imports new days: what the cards read is kept
 * until the integration's data version changes (plenitude/info), in memory for all the cards of the page (Home
 * Assistant re-creates the cards on every reconnection) and in the browser's localStorage (reloads of the page).
 *
 * Served by the integration (custom_components/plenitude) and loaded by the frontend on every dashboard.
 * Values come from the long-term statistics (recorder/statistics_during_period); the integration's
 * plenitude/info command only says which statistics exist. No external dependencies: plain custom elements
 * and hand-drawn SVG. Text that comes from outside (category names) is always set with textContent.
 */

const CARD_VERSION = "0.4.1";

// ------------------------------------------------------------------------------------------- language

const STRINGS = {
  it: {
    consumption_card: "Plenitude: consumi",
    consumption_card_desc: "Grafico dei consumi di luce con periodo a scelta, per fascia o per categoria.",
    billing_card: "Plenitude: bolletta in corso",
    billing_card_desc: "Consumi e costo del periodo di fatturazione in corso (bimestre da un giorno a scelta).",
    title: "Titolo",
    entry: "Fornitura",
    period: "Periodo di default",
    view: "Vista di default",
    unit: "Unità di default",
    view_label: "Vista",
    unit_label: "Unità",
    start_date: "Primo giorno di un periodo di fatturazione",
    months: "Durata del periodo",
    day: "Giorno",
    week: "Settimana",
    month: "Mese",
    year: "Anno",
    total: "Totale",
    bands: "Fasce",
    categories: "Categorie",
    kwh: "kWh",
    eur: "€",
    one_month: "1 mese",
    two_months: "2 mesi (bimestre)",
    consumption: "Consumo",
    cost: "Costo",
    default_title: "Consumi luce",
    default_billing_title: "Bolletta in corso",
    previous: "Periodo precedente",
    next: "Periodo successivo",
    latest: "Ultimi dati",
    table: "Tabella",
    chart: "Grafico",
    no_data: "Nessun dato",
    not_configured: "Integrazione Eni Plenitude non configurata o non ancora caricata.",
    loading: "Caricamento…",
    error: "Errore nel leggere le statistiche",
    data_until: "Dati fino al",
    categories_daily: "Le categorie sono stime giornaliere: scegli settimana, mese o anno.",
    categories_kwh_only: "Le categorie sono solo in kWh.",
    no_price: "Per vedere il costo imposta il prezzo nelle opzioni dell'integrazione.",
    period_label: "Periodo",
    so_far: "finora",
    day_of: "giorno {x} di {n}",
    estimate: "Stima a fine periodo",
    estimate_note: "media dei giorni con dati × durata del periodo",
    choose_start: "Scegli nelle impostazioni della card il primo giorno di un periodo di fatturazione.",
    cost_note:
      "Il costo è kWh × (prezzo della fascia + costi per kWh), più i costi periodici (mensili, bimestrali, annuali, €/kW al mese) per intero, come impostati nell'integrazione: quelli di tutto il periodo, anche se non è finito. È una stima: la bolletta può contenere anche conguagli e letture stimate.",
    future: "periodo futuro",
    period_total: "Totale del periodo",
    when: "Quando",
    fixed_costs: "Costi fissi",
    usage_cost: "Consumi",
    energy_cost: "Energia",
    with_fixed: "di cui costi fissi {x}",
    cost_breakdown: "Composizione del costo",
    kind_monthly: "mensile",
    kind_bimonthly: "bimestrale",
    kind_yearly: "annuale",
    kind_per_kw_monthly: "€/kW al mese",
    kind_per_kwh: "per kWh",
    cat_comfort_ambientale: "Comfort ambientale (HVAC)",
    cat_standby: "Standby",
    cat_lavare: "Lavare",
    cat_elettronica_luci: "Elettronica e luci",
    cat_refrigerare: "Refrigerare",
    cat_cucinare: "Cucinare",
    cat_ricarica_elettrica: "Ricarica elettrica",
    cat_altro: "Altro",
  },
  en: {
    consumption_card: "Plenitude: consumption",
    consumption_card_desc: "Electricity consumption chart with a chosen period, by band or by category.",
    billing_card: "Plenitude: current bill",
    billing_card_desc: "Consumption and cost of the current billing period (two months from a chosen day).",
    title: "Title",
    entry: "Supply",
    period: "Default period",
    view: "Default view",
    unit: "Default unit",
    view_label: "View",
    unit_label: "Unit",
    start_date: "First day of a billing period",
    months: "Length of the period",
    day: "Day",
    week: "Week",
    month: "Month",
    year: "Year",
    total: "Total",
    bands: "Bands",
    categories: "Categories",
    kwh: "kWh",
    eur: "€",
    one_month: "1 month",
    two_months: "2 months",
    consumption: "Consumption",
    cost: "Cost",
    default_title: "Electricity consumption",
    default_billing_title: "Current bill",
    previous: "Previous period",
    next: "Next period",
    latest: "Latest data",
    table: "Table",
    chart: "Chart",
    no_data: "No data",
    not_configured: "Eni Plenitude integration not configured or not loaded yet.",
    loading: "Loading…",
    error: "Error reading the statistics",
    data_until: "Data until",
    categories_daily: "Categories are daily estimates: choose week, month or year.",
    categories_kwh_only: "Categories are in kWh only.",
    no_price: "Set the price in the integration options to see the cost.",
    period_label: "Period",
    so_far: "so far",
    day_of: "day {x} of {n}",
    estimate: "Estimate at the end of the period",
    estimate_note: "average of the days with data × length of the period",
    choose_start: "Choose the first day of a billing period in the card settings.",
    cost_note:
      "The cost is kWh × (price of the band + costs per kWh), plus the periodic costs (monthly, two-monthly, yearly, per kW per month) in full, as set in the integration: those of the whole period, also while it is not over. It is an estimate: the bill may also contain adjustments and estimated readings.",
    future: "future period",
    period_total: "Period total",
    when: "When",
    fixed_costs: "Fixed costs",
    usage_cost: "Consumption",
    energy_cost: "Energy",
    with_fixed: "of which fixed costs {x}",
    cost_breakdown: "Cost breakdown",
    kind_monthly: "monthly",
    kind_bimonthly: "every two months",
    kind_yearly: "yearly",
    kind_per_kw_monthly: "per kW per month",
    kind_per_kwh: "per kWh",
    cat_comfort_ambientale: "Heating and cooling (HVAC)",
    cat_standby: "Standby",
    cat_lavare: "Washing",
    cat_elettronica_luci: "Electronics and lighting",
    cat_refrigerare: "Refrigeration",
    cat_cucinare: "Cooking",
    cat_ricarica_elettrica: "EV charging",
    cat_altro: "Other",
  },
};

/** Language of the user's profile where there is no ``hass`` (card picker, editor): the frontend's own, then the
 * page's (set by the frontend once its translations are loaded), then the one saved by the profile, then the
 * browser's. */
function pageLang() {
  let saved = null;
  try {
    saved = JSON.parse(window.localStorage?.getItem("selectedLanguage") || "null");
  } catch (err) {
    saved = null;
  }
  const hass = document.querySelector?.("home-assistant")?.hass;
  const code = hass?.locale?.language || hass?.language || document.documentElement.lang || saved || navigator.language || "en";
  return String(code).startsWith("it") ? "it" : "en";
}
const hassLang = (hass) => (((hass && (hass.locale?.language || hass.language)) || pageLang()).startsWith("it") ? "it" : "en");
const tr = (lang, key, vars = {}) =>
  (STRINGS[lang][key] ?? STRINGS.en[key] ?? key).replace(/\{(\w+)\}/g, (_, name) => String(vars[name] ?? ""));
/** In Italian the portal's own name of a category; in English ours, by key (the portal speaks Italian only). */
function categoryName(lang, category) {
  const ours = STRINGS[lang][`cat_${category.key}`];
  return (lang === "it" ? category.name || ours : ours || category.name) || category.key;
}

// --------------------------------------------------------------------------------------------- colors

// Categorical palette validated for CVD separation (adjacent pairs; the first three on all pairs) on the
// Home Assistant card surfaces, light #ffffff and dark #1c1c1c. Slots are assigned in fixed order.
// Slot 8 is a neutral gray for the fixed costs: not an entity hue, always labelled (3.4:1 and 5.3:1 contrast).
const PALETTE = {
  light: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948", "#8a8a8a"],
  dark: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9", "#e66767", "#8f8f8f"],
};
const FIXED_COLOR = 8;

// ---------------------------------------------------------------------------------------------- dates

const HOUR = 3600000;
const parseDay = (text) => {
  const [y, m, d] = text.split("-").map(Number);
  return new Date(y, m - 1, d);
};
const addDays = (date, n) => new Date(date.getFullYear(), date.getMonth(), date.getDate() + n);
const daysInMonth = (y, m) => new Date(y, m + 1, 0).getDate();
/** Same day of the month ``n`` months later, clamped to the length of that month (31 Jan + 1 = 28/29 Feb). */
const addMonths = (date, n, dayOfMonth = date.getDate()) => {
  const first = new Date(date.getFullYear(), date.getMonth() + n, 1);
  return new Date(first.getFullYear(), first.getMonth(), Math.min(dayOfMonth, daysInMonth(first.getFullYear(), first.getMonth())));
};
const startOfWeek = (date) => addDays(date, -((date.getDay() + 6) % 7)); // weeks start on Monday
const startOfDay = (date) => new Date(date.getFullYear(), date.getMonth(), date.getDate());
const daysBetween = (a, b) => Math.round((startOfDay(b) - startOfDay(a)) / 86400000);
const daysInYear = (y) => (new Date(y, 1, 29).getMonth() === 1 ? 366 : 365);

// Euro per year of a periodic cost, as computed by the integration (``yearly``; null for the costs per kWh).
const yearlyOf = (cost) => (cost.yearly === null || cost.yearly === undefined ? null : Number(cost.yearly));
const periodicCosts = (entry) => (entry.costs || []).filter((c) => yearlyOf(c) !== null);
const perKwhCosts = (entry) => (entry.costs || []).filter((c) => c.kind === "per_kwh");
const perKwhExtra = (entry) => perKwhCosts(entry).reduce((a, c) => a + Number(c.amount), 0);

/** Euro a month of the periodic costs (all of them, or ``items``): 1/12 of their euro per year. */
const monthlyFixed = (entry, items = periodicCosts(entry)) => items.reduce((a, c) => a + (yearlyOf(c) || 0), 0) / 12;

/**
 * Periodic costs in each bucket, as entered: every calendar month from the month of the first day of the history
 * to the month of the last day with data carries 1/12 of the euro per year, split evenly among its days (and among
 * the real hours of a day: 23, 24 or 25). A month gets exactly its amount, also while it is not over; a year the
 * sum of its months; a week the share of its days. ``null`` where nothing applies, like the statistics.
 */
function fixedShares(entry, buckets, items = periodicCosts(entry)) {
  const monthly = monthlyFixed(entry, items);
  if (!monthly || !entry.prices || !entry.last_day) return buckets.map(() => null);
  const last = parseDay(entry.last_day);
  const first = entry.first_day ? parseDay(entry.first_day) : null;
  const from = first ? new Date(first.getFullYear(), first.getMonth(), 1).getTime() : -Infinity;
  const to = new Date(last.getFullYear(), last.getMonth() + 1, 1).getTime();
  return buckets.map((bucket) => {
    let total = null;
    for (let day = startOfDay(new Date(bucket.start)); day.getTime() < bucket.end; day = addDays(day, 1)) {
      const dayStart = day.getTime();
      const dayEnd = addDays(day, 1).getTime();
      if (dayStart < from || dayStart >= to) continue;
      const overlap = Math.min(bucket.end, dayEnd) - Math.max(bucket.start, dayStart);
      const perDay = monthly / daysInMonth(day.getFullYear(), day.getMonth());
      if (overlap > 0) total = (total || 0) + perDay * (overlap / (dayEnd - dayStart));
    }
    return total;
  });
}

/**
 * Periodic costs of a billing period of ``months`` months, as entered: the euro a month times the months of the
 * period, also while the period is not over. Nothing for a period that ends before the history starts.
 */
function billingFixed(entry, period, months, items = periodicCosts(entry)) {
  if (!entry.prices) return 0;
  if (entry.first_day && period.end <= parseDay(entry.first_day)) return 0;
  return monthlyFixed(entry, items) * months;
}
const sumValues = (values) => (values || []).reduce((a, v) => a + (v || 0), 0);

/** Range of a period around ``anchor``: start, end (exclusive), statistics period and buckets. */
function periodRange(period, anchor) {
  let start;
  let end;
  if (period === "day") {
    start = startOfDay(anchor);
    end = addDays(start, 1);
    const buckets = [];
    for (let t = start.getTime(); t < end.getTime(); t += HOUR) buckets.push({ start: t, end: t + HOUR });
    return { start, end, stat: "hour", buckets }; // 23, 24 or 25 hours: real time, not wall-clock time
  }
  if (period === "year") {
    start = new Date(anchor.getFullYear(), 0, 1);
    end = new Date(anchor.getFullYear() + 1, 0, 1);
    const buckets = [];
    for (let m = 0; m < 12; m++) {
      buckets.push({ start: new Date(start.getFullYear(), m, 1).getTime(), end: new Date(start.getFullYear(), m + 1, 1).getTime() });
    }
    return { start, end, stat: "month", buckets };
  }
  if (period === "week") {
    start = startOfWeek(anchor);
    end = addDays(start, 7);
  } else {
    start = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    end = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 1);
  }
  return { start, end, stat: "day", buckets: dayBuckets(start, end) };
}

function dayBuckets(start, end) {
  const buckets = [];
  for (let d = start; d < end; d = addDays(d, 1)) buckets.push({ start: d.getTime(), end: addDays(d, 1).getTime() });
  return buckets;
}

function shiftAnchor(period, anchor, direction) {
  if (period === "day") return addDays(anchor, direction);
  if (period === "week") return addDays(anchor, 7 * direction);
  if (period === "month") return new Date(anchor.getFullYear(), anchor.getMonth() + direction, 1);
  return new Date(anchor.getFullYear() + direction, 0, 1);
}

// ----------------------------------------------------------------------------------------- formatting

const fmt = (lang) => {
  const locale = lang === "it" ? "it-IT" : "en-GB";
  const number = (max) => new Intl.NumberFormat(locale, { maximumFractionDigits: max, minimumFractionDigits: 0 });
  const euro = new Intl.NumberFormat(locale, { style: "currency", currency: "EUR" });
  const date = (value, options) => new Intl.DateTimeFormat(locale, options).format(value);
  return {
    kwh: (v) => `${number(v < 1 ? 3 : v < 10 ? 2 : v < 100 ? 1 : 0).format(v)} kWh`,
    eur: (v) => euro.format(v),
    number: (v) => number(3).format(v),
    tick: (v, unit) => (unit === "eur" ? euro.format(v).replace(/[,.]00(?=\D|$)/, "") : number(v < 10 ? 1 : 0).format(v)),
    date,
    dayLong: (d) => date(d, { weekday: "long", day: "numeric", month: "long", year: "numeric" }),
    dayShort: (d) => date(d, { weekday: "short", day: "numeric", month: "short" }),
    dayMonth: (d) => date(d, { day: "numeric", month: "short" }),
    dayMonthYear: (d) => date(d, { day: "numeric", month: "short", year: "numeric" }),
    monthYear: (d) => date(d, { month: "long", year: "numeric" }),
    monthShort: (d) => date(d, { month: "short" }),
    hour: (t) => String(new Date(t).getHours()).padStart(2, "0"),
  };
};

// ------------------------------------------------------------------------------------------ data access

const INFO_MAX_AGE = 5 * 60000; // the integration's description is asked again at most every 5 minutes...
const CHECK_EVERY = 60000; // ...and each card looks at it at most once a minute, on the updates of hass
const infoCache = new WeakMap();

/**
 * The integration's description of its supplies (statistics, prices, costs, data version), one request at a time
 * for all the cards of a connection. ``maxAge`` Infinity: whatever is known, without waiting for the network.
 */
async function getInfo(hass, maxAge = INFO_MAX_AGE) {
  const key = hass.connection || hass;
  const cached = infoCache.get(key);
  if (cached && Date.now() - cached.time < maxAge) return cached.promise;
  const promise = hass.callWS({ type: "plenitude/info" }).catch((err) => {
    if (infoCache.get(key)?.promise === promise) infoCache.delete(key);
    throw err;
  });
  infoCache.set(key, { promise, time: Date.now() });
  return promise;
}

const pickEntry = (info, entryId) =>
  (info.entries || []).find((e) => e.entry_id === entryId) || (info.entries || [])[0] || null;

/** Every statistic of a supply: what is read for a period serves all the views and units of the cards. */
function statisticIds(entry) {
  const s = entry.statistics;
  return [s.consumo, s.f1, s.f2, s.f3, s.costo, ...(entry.categories || []).map((c) => c.statistic_id)].filter(Boolean);
}

const STORE_PREFIX = "plenitude-cards:";
const STORE_MAX = 40; // periods kept in the browser's storage (a few kB each)
const MEMORY_MAX = 80;
const memory = new Map(); // key -> promise of the changes, shared by all the cards of the page

/** Periods already read, in the browser's localStorage. Best effort: blocked or full storage means memory only. */
const browserStore = {
  get(key) {
    try {
      const raw = window.localStorage?.getItem(STORE_PREFIX + key);
      return raw ? JSON.parse(raw).changes : null;
    } catch (err) {
      return null;
    }
  },
  set(key, supply, version, changes) {
    try {
      const storage = window.localStorage;
      if (!storage) return;
      const ours = [];
      for (let i = 0; i < storage.length; i++) {
        const name = storage.key(i);
        if (name?.startsWith(STORE_PREFIX)) ours.push(name);
      }
      const kept = [];
      for (const name of ours) {
        // Other versions of the same supply are of no use any more.
        if (name.startsWith(`${STORE_PREFIX}${supply}|`) && !name.startsWith(`${STORE_PREFIX}${supply}|${version}|`)) storage.removeItem(name);
        else kept.push(name);
      }
      if (kept.length >= STORE_MAX) {
        const saved = (name) => {
          try {
            return JSON.parse(storage.getItem(name)).saved || 0;
          } catch (err) {
            return 0;
          }
        };
        kept.sort((a, b) => saved(a) - saved(b));
        for (const name of kept.slice(0, kept.length - STORE_MAX + 1)) storage.removeItem(name);
      }
      storage.setItem(STORE_PREFIX + key, JSON.stringify({ saved: Date.now(), changes }));
    } catch (err) {
      // Storage blocked or full: the data stay in memory.
    }
  },
};

/**
 * Change per bucket of every statistic of the supply in ``range``: ``{id: [number | null, ...]}``, read once per
 * data version of the integration, then from memory or from the browser's storage. The result is shared: read only.
 */
function getChanges(hass, entry, range) {
  const version = entry.version ?? "none";
  const key = `${entry.entry_id}|${version}|${range.stat}|${range.start.getTime()}|${range.end.getTime()}`;
  if (memory.has(key)) return memory.get(key);
  const stored = browserStore.get(key);
  const promise = stored
    ? Promise.resolve(stored)
    : fetchChanges(hass, statisticIds(entry), range).then((changes) => {
        browserStore.set(key, entry.entry_id, version, changes);
        return changes;
      });
  memory.set(key, promise);
  promise.catch(() => memory.delete(key));
  while (memory.size > MEMORY_MAX) memory.delete(memory.keys().next().value);
  return promise;
}

/** Change per bucket of each statistic: ``{id: [number | null, ...]}``. */
async function fetchChanges(hass, ids, range) {
  const wanted = ids.filter(Boolean);
  const result = Object.fromEntries(wanted.map((id) => [id, range.buckets.map(() => null)]));
  if (!wanted.length) return result;
  const rows = await hass.callWS({
    type: "recorder/statistics_during_period",
    start_time: range.start.toISOString(),
    end_time: range.end.toISOString(),
    statistic_ids: wanted,
    period: range.stat,
    types: ["change"],
  });
  for (const id of wanted) {
    for (const row of rows[id] || []) {
      const index = range.buckets.findIndex((b) => row.start >= b.start && row.start < b.end);
      if (index >= 0) result[id][index] = (result[id][index] || 0) + (row.change || 0);
    }
  }
  return result;
}

/**
 * Series to draw for a view and a unit. Each series sums some statistics, each times a factor (the price,
 * for costs by band). Colors are fixed per entity: F1 is always slot 1, a category always its own slot.
 */
function buildSeries(entry, view, unit, lang) {
  const s = entry.statistics;
  const price = entry.prices || {};
  if (view === "categories") {
    return entry.categories.map((c, i) => ({ key: c.key, name: categoryName(lang, c), color: i, parts: [{ id: c.statistic_id, factor: 1 }] }));
  }
  if (view === "bands") {
    const extra = unit === "eur" ? perKwhExtra(entry) : 0;
    const factor = (band) => (unit === "eur" ? (price[band] ?? 0) + extra : 1);
    if (entry.price_mode === "two") {
      return [
        { key: "f1", name: "F1", color: 0, parts: [{ id: s.f1, factor: factor("f1") }] },
        { key: "f23", name: "F23", color: 1, parts: [{ id: s.f2, factor: factor("f2") }, { id: s.f3, factor: factor("f3") }] },
      ];
    }
    return ["f1", "f2", "f3"].map((band, i) => ({
      key: band,
      name: band.toUpperCase(),
      color: i,
      parts: [{ id: s[band], factor: factor(band) }],
    }));
  }
  if (unit === "eur") return [{ key: "cost", name: tr(lang, "cost"), color: 0, parts: [{ id: s.costo, factor: 1 }] }];
  return [{ key: "total", name: tr(lang, "consumption"), color: 0, parts: [{ id: s.consumo, factor: 1 }] }];
}

function seriesValues(series, changes, count) {
  return series.map((serie) => {
    const values = [];
    for (let i = 0; i < count; i++) {
      let value = null;
      for (const part of serie.parts) {
        const change = changes[part.id]?.[i];
        if (change !== null && change !== undefined) value = (value || 0) + change * part.factor;
      }
      values.push(value);
    }
    return { ...serie, values, total: values.reduce((a, v) => a + (v || 0), 0) };
  });
}

// ------------------------------------------------------------------------------------------------ DOM

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (value === false || value === null || value === undefined) continue;
    if (name.startsWith("on")) node.addEventListener(name.slice(2), value);
    else if (name === "text") node.textContent = value;
    else node.setAttribute(name, value === true ? "" : value);
  }
  for (const child of [].concat(children)) if (child) node.append(child);
  return node;
}

const SVG = "http://www.w3.org/2000/svg";
function svg(tag, attrs = {}, children = []) {
  const node = document.createElementNS(SVG, tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (name.startsWith("on")) node.addEventListener(name.slice(2), value);
    else if (name === "text") node.textContent = value;
    else if (value !== null && value !== undefined) node.setAttribute(name, value);
  }
  for (const child of [].concat(children)) if (child) node.append(child);
  return node;
}

function niceTicks(max) {
  if (!(max > 0)) return [0, 1];
  const rough = max / 3;
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= rough) || 10 * power;
  const ticks = [];
  for (let v = 0; v <= max + step * 0.001; v += step) ticks.push(v);
  if (ticks[ticks.length - 1] < max) ticks.push(ticks[ticks.length - 1] + step);
  return ticks;
}

/** Rounded data-end (4px) at the top, square at the baseline. */
function topRoundedBar(x, y, w, h, r) {
  const radius = Math.min(r, w / 2, h);
  return `M${x},${y + h}V${y + radius}Q${x},${y} ${x + radius},${y}H${x + w - radius}Q${x + w},${y} ${x + w},${y + radius}V${y + h}Z`;
}

/**
 * Stacked column chart. ``series``: [{name, color, values}], ``labels``: x labels (sparse ones are skipped),
 * ``onHover(index, x, y)`` / ``onLeave()`` drive the tooltip. Every column is a focusable hit target.
 */
function columnChart({ width, height, series, labels, colors, unit, format, onHover, onLeave, ariaLabel }) {
  const margin = { top: 8, right: 4, bottom: 22, left: 44 };
  const plotW = Math.max(40, width - margin.left - margin.right);
  const plotH = height - margin.top - margin.bottom;
  const count = labels.length;
  const totals = labels.map((_, i) => series.reduce((a, s) => a + Math.max(0, s.values[i] || 0), 0));
  const ticks = niceTicks(Math.max(...totals, 0));
  const top = ticks[ticks.length - 1] || 1;
  const y = (v) => margin.top + plotH - (v / top) * plotH;
  const slot = plotW / count;
  const barW = Math.max(2, Math.min(24, slot * 0.7));

  const root = svg("svg", { width, height, viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": ariaLabel });
  const grid = svg("g", { class: "grid" });
  for (const tick of ticks) {
    grid.append(svg("line", { x1: margin.left, x2: margin.left + plotW, y1: y(tick), y2: y(tick) }));
    grid.append(svg("text", { x: margin.left - 6, y: y(tick) + 4, "text-anchor": "end", text: format.tick(tick, unit) }));
  }
  root.append(grid);

  const every = Math.ceil(count / Math.max(1, Math.floor(plotW / 34)));
  const axis = svg("g", { class: "axis" });
  labels.forEach((label, i) => {
    if (i % every === 0) {
      axis.append(svg("text", { x: margin.left + slot * i + slot / 2, y: height - 6, "text-anchor": "middle", text: label }));
    }
  });
  axis.append(svg("line", { class: "baseline", x1: margin.left, x2: margin.left + plotW, y1: y(0), y2: y(0) }));
  root.append(axis);

  const bars = svg("g", { class: "bars" });
  const columns = [];
  for (let i = 0; i < count; i++) {
    const column = svg("g", { class: "column" });
    const x = margin.left + slot * i + (slot - barW) / 2;
    const segments = series.map((s, k) => ({ value: Math.max(0, s.values[i] || 0), color: colors[s.color], k })).filter((s) => s.value > 0);
    let base = 0;
    segments.forEach((segment, n) => {
      const y0 = y(base);
      const y1 = y(base + segment.value);
      base += segment.value;
      const gapBelow = n > 0 ? 1 : 0; // 2px surface gap between touching segments
      const gapAbove = n < segments.length - 1 ? 1 : 0;
      const h = y0 - y1 - gapBelow - gapAbove;
      if (h <= 0.4) return;
      const top = y1 + gapAbove;
      if (n === segments.length - 1) column.append(svg("path", { d: topRoundedBar(x, top, barW, h, 4), fill: segment.color }));
      else column.append(svg("rect", { x, y: top, width: barW, height: h, fill: segment.color }));
    });
    const hit = svg("rect", {
      class: "hit",
      x: margin.left + slot * i,
      y: margin.top,
      width: slot,
      height: plotH,
      tabindex: 0,
      "aria-label": labels[i],
    });
    const show = () => {
      root.classList.add("hovering");
      columns.forEach((c, j) => c.classList.toggle("active", j === i));
      onHover(i, margin.left + slot * i + slot / 2, y(totals[i]));
    };
    const hide = () => {
      root.classList.remove("hovering");
      columns.forEach((c) => c.classList.remove("active"));
      onLeave();
    };
    hit.addEventListener("pointerenter", show);
    hit.addEventListener("pointermove", show);
    hit.addEventListener("focus", show);
    hit.addEventListener("pointerleave", hide);
    hit.addEventListener("blur", hide);
    column.append(hit);
    columns.push(column);
    bars.append(column);
  }
  root.append(bars);
  return root;
}

const STYLE = `
  :host { display: block; }
  ha-card { padding: 16px; box-sizing: border-box; position: relative; overflow: visible; }
  ha-card.placeholder { min-height: 360px; }
  .head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
  h2 { margin: 0; font-size: 1.15rem; font-weight: 500; color: var(--primary-text-color); }
  .sub { color: var(--secondary-text-color); font-size: 0.9rem; }
  .controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 12px 0 8px; }
  .group { display: inline-flex; border: 1px solid var(--divider-color); border-radius: 8px; overflow: hidden; }
  .group button { border: 0; border-right: 1px solid var(--divider-color); }
  .group button:last-child { border-right: 0; }
  button {
    font: inherit; font-size: 0.85rem; color: var(--primary-text-color); background: transparent;
    padding: 4px 10px; cursor: pointer; min-height: 30px; border: 1px solid var(--divider-color); border-radius: 8px;
  }
  .group button { border-radius: 0; }
  button[aria-pressed="true"] { background: var(--primary-color); color: var(--text-primary-color, #fff); }
  button:disabled { opacity: 0.4; cursor: default; }
  button:focus-visible, .hit:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 1px; }
  .nav { display: inline-flex; gap: 4px; align-items: center; }
  .nav button { padding: 4px 8px; }
  .spacer { flex: 1; }
  .summary { display: flex; flex-wrap: wrap; gap: 4px 16px; align-items: baseline; margin: 4px 0 8px; }
  .big { font-size: 1.6rem; font-weight: 600; color: var(--primary-text-color); }
  .second { color: var(--secondary-text-color); }
  .legend { display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 4px 0 6px; font-size: 0.85rem; color: var(--secondary-text-color); }
  .legend span.key { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
  .legend b { color: var(--primary-text-color); font-weight: 500; margin-left: 4px; }
  .chart { position: relative; }
  .chart.loading { opacity: 0.5; }
  svg { display: block; overflow: visible; font-size: 11px; }
  svg .grid line { stroke: var(--divider-color); stroke-width: 1; }
  svg .grid text, svg .axis text { fill: var(--secondary-text-color); font-variant-numeric: tabular-nums; }
  svg .axis .baseline { stroke: var(--secondary-text-color); stroke-opacity: 0.5; }
  svg .hit { fill: transparent; outline: none; }
  svg.hovering .column:not(.active) path, svg.hovering .column:not(.active) rect:not(.hit) { opacity: 0.55; }
  .tooltip {
    position: absolute; pointer-events: none; z-index: 2; min-width: 120px; padding: 8px 10px; border-radius: 8px;
    background: var(--card-background-color, #fff); color: var(--primary-text-color);
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25); font-size: 0.82rem; transform: translate(-50%, calc(-100% - 10px));
    white-space: nowrap;
  }
  .tooltip .when { color: var(--secondary-text-color); margin-bottom: 4px; }
  .tooltip .row { display: flex; align-items: center; gap: 6px; }
  .tooltip .row b { font-weight: 600; }
  .tooltip .line { display: inline-block; width: 12px; height: 2px; border-radius: 1px; }
  .tooltip .row.sum { border-top: 1px solid var(--divider-color); margin-top: 4px; padding-top: 4px; }
  .note { color: var(--secondary-text-color); font-size: 0.85rem; margin: 6px 0; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; font-variant-numeric: tabular-nums; }
  th, td { text-align: right; padding: 3px 6px; border-bottom: 1px solid var(--divider-color); color: var(--primary-text-color); }
  th:first-child, td:first-child { text-align: left; }
  th { color: var(--secondary-text-color); font-weight: 500; }
  .tablewrap { max-height: 320px; overflow: auto; }
  .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; margin: 10px 0; }
  .tile .label { color: var(--secondary-text-color); font-size: 0.85rem; }
  .tile .value { font-size: 1.7rem; font-weight: 600; color: var(--primary-text-color); }
  .meter { height: 8px; border-radius: 4px; background: var(--divider-color); overflow: hidden; margin: 6px 0 2px; }
  .meter div { height: 100%; background: var(--primary-color); border-radius: 4px; }
  .segbar { display: flex; gap: 2px; height: 8px; margin: 10px 0 6px; }
  .segbar div { height: 100%; border-radius: 4px; }
  .breakdown { margin: 6px 0 8px; font-size: 0.85rem; }
  .breakdown summary { cursor: pointer; color: var(--secondary-text-color); margin-bottom: 4px; }
  .breakdown .kind { color: var(--secondary-text-color); }
  .breakdown tfoot th { color: var(--primary-text-color); font-weight: 600; text-align: right; }
  .breakdown tfoot th:first-child { text-align: left; }
  .footer { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 6px; }
`;

/** Common machinery: config, hass, loading, tooltip, resize. */
class PlenitudeBase extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._loadedAt = 0;
    this._checkedAt = 0;
    this._token = 0;
    this._width = 360;
  }

  set hass(hass) {
    const first = !this._hass;
    const darkChanged = this._hass && !!this._hass.themes?.darkMode !== !!hass.themes?.darkMode;
    this._hass = hass;
    if (first) {
      this._load();
      return;
    }
    if (darkChanged) this._render();
    if (Date.now() - this._checkedAt > CHECK_EVERY) this._check();
  }

  /** Has the integration written new data, or changed prices or costs? Then read again (from the cache if possible). */
  async _check() {
    this._checkedAt = Date.now();
    if (!this._config) return;
    if (this._entry === undefined) {
      if (this._error) this._load(); // the first reading failed: try again
      return;
    }
    try {
      // Integration not loaded yet (Home Assistant starting): look again every minute, not every five.
      const info = await getInfo(this._hass, this._entry ? INFO_MAX_AGE : CHECK_EVERY);
      const entry = pickEntry(info, this._config.entry);
      if (JSON.stringify(entry) !== JSON.stringify(this._entry)) this._load();
    } catch (err) {
      // Not reachable now: the card keeps what it shows and looks again later.
    }
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    this._resize = new ResizeObserver(() => {
      const width = Math.round(this.clientWidth || 360);
      if (Math.abs(width - this._width) > 4) {
        this._width = width;
        this._render();
      }
    });
    this._resize.observe(this);
  }

  disconnectedCallback() {
    this._resize?.disconnect();
  }

  get _lang() {
    return hassLang(this._hass);
  }

  get _colors() {
    return this._hass?.themes?.darkMode ? PALETTE.dark : PALETTE.light;
  }

  _shell(children, placeholder = false) {
    // While loading the first time, the card keeps about its final height: the dashboard does not jump.
    const card = el("ha-card", { class: placeholder ? "placeholder" : null }, children);
    this.shadowRoot.replaceChildren(el("style", { text: STYLE }), card);
    return card;
  }

  _tooltip(container, chartWidth, index, x, y, build) {
    container.querySelector(".tooltip")?.remove();
    const tip = el("div", { class: "tooltip" }, build(index));
    const left = Math.min(Math.max(x, 70), chartWidth - 70);
    tip.style.left = `${left}px`;
    tip.style.top = `${Math.max(y, 40)}px`;
    container.append(tip);
  }

  _hideTooltip(container) {
    container.querySelector(".tooltip")?.remove();
  }

  /**
   * Read the data of the card. What is in the cache arrives within the same task, so a card that Home Assistant
   * re-creates shows its data at once; the description of the integration is the last one known (``_check``
   * looks for a newer one right after). Real requests show the loading state only if they take a while.
   */
  async _load() {
    if (!this._hass || !this._config) return;
    const token = ++this._token;
    if (!this._data) this._render();
    const slow = setTimeout(() => {
      if (token !== this._token) return;
      this._loading = true;
      this._render();
    }, 150);
    try {
      const info = await getInfo(this._hass, Infinity);
      const entry = pickEntry(info, this._config.entry);
      const data = entry ? await this._fetch(entry) : null;
      if (token !== this._token) return;
      this._entry = entry;
      this._data = data;
      this._error = null;
      this._loadedAt = Date.now();
    } catch (err) {
      if (token !== this._token) return;
      this._error = err?.message || String(err);
    } finally {
      clearTimeout(slow);
    }
    this._loading = false;
    this._render();
  }

  _toolbarButton(label, pressed, onclick, disabled = false, title = null) {
    return el("button", { "aria-pressed": pressed ? "true" : "false", onclick, disabled, title, text: label });
  }

  getCardSize() {
    return 6;
  }
}

// ------------------------------------------------------------------------------------ consumption card

const PERIODS = ["day", "week", "month", "year"];
const VIEWS = ["total", "bands", "categories"];

class PlenitudeConsumptionCard extends PlenitudeBase {
  static getConfigForm() {
    const lang = pageLang();
    const options = (values) => values.map((value) => ({ value, label: tr(lang, value) }));
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        { name: "entry", selector: { config_entry: { integration: "plenitude" } } },
        { name: "period", selector: { select: { mode: "dropdown", options: options(PERIODS) } } },
        { name: "view", selector: { select: { mode: "dropdown", options: options(VIEWS) } } },
        { name: "unit", selector: { select: { mode: "dropdown", options: options(["kwh", "eur"]) } } },
      ],
      computeLabel: (schema) => tr(lang, schema.name),
    };
  }

  static getStubConfig() {
    return { period: "month", view: "bands", unit: "kwh" };
  }

  setConfig(config) {
    const period = PERIODS.includes(config.period) ? config.period : "month";
    const view = VIEWS.includes(config.view) ? config.view : "bands";
    const unit = config.unit === "eur" ? "eur" : "kwh";
    this._config = { ...config, period, view, unit };
    this._period = period;
    this._view = view;
    this._unit = unit;
    this._anchor = null;
    this._showTable = false;
    this._load();
  }

  _effective(entry) {
    // Categories exist per day: not in the day view, and only in kWh.
    let view = this._view;
    let unit = this._unit;
    if (!entry?.prices && unit === "eur") unit = "kwh";
    if (view === "categories") unit = "kwh";
    return { view, unit, categoriesBlocked: view === "categories" && this._period === "day" };
  }

  async _fetch(entry) {
    if (!this._anchor) this._anchor = entry.last_day ? parseDay(entry.last_day) : addDays(new Date(), -2);
    const range = periodRange(this._period, this._anchor);
    const { view, unit, categoriesBlocked } = this._effective(entry);
    const series = categoriesBlocked ? [] : buildSeries(entry, view, unit, this._lang);
    // Every statistic of the period at once (one request, then the cache): views and units switch at once.
    const changes = await getChanges(this._hass, entry, range);
    const values = seriesValues(series, changes, range.buckets.length);
    // Fixed costs: in the totals always, in the chart as the bottom segment of the columns in euro.
    const fixed = fixedShares(entry, range.buckets);
    const fixedTotal = sumValues(fixed);
    if (unit === "eur" && fixedTotal > 0 && !categoriesBlocked) {
      if (view === "total") values[0].name = tr(this._lang, "usage_cost");
      values.unshift({ key: "fixed", name: tr(this._lang, "fixed_costs"), color: FIXED_COLOR, parts: [], values: fixed, total: fixedTotal });
    }
    return { range, series: values, changes, view, unit, categoriesBlocked, fixedTotal };
  }

  _go(direction) {
    this._anchor = shiftAnchor(this._period, this._anchor || new Date(), direction);
    this._load();
  }

  _render() {
    const lang = this._lang;
    const f = fmt(lang);
    const title = this._config?.title || tr(lang, "default_title");
    if (!this._config) return;
    if (!this._data && !this._error) {
      const missing = this._entry === null;
      this._shell([el("h2", { text: title }), el("p", { class: "note", text: missing ? tr(lang, "not_configured") : tr(lang, "loading") })], !missing);
      return;
    }
    if (this._error && !this._data) {
      this._shell([el("h2", { text: title }), el("p", { class: "note", text: `${tr(lang, "error")}: ${this._error}` })]);
      return;
    }
    const entry = this._entry;
    if (!entry) {
      this._shell([el("h2", { text: title }), el("p", { class: "note", text: tr(lang, "not_configured") })]);
      return;
    }
    const { range, series, changes, view, unit, categoriesBlocked } = this._data;
    const start = range.start;
    const subtitle = {
      day: () => f.dayLong(start),
      week: () => `${f.dayMonth(start)} – ${f.dayMonthYear(addDays(range.end, -1))}`,
      month: () => f.monthYear(start),
      year: () => String(start.getFullYear()),
    }[this._period]();

    const sumOf = (id) => (id ? (changes[id] || []).reduce((a, v) => a + (v || 0), 0) : null);
    const hasAny = (id) => id && (changes[id] || []).some((v) => v !== null);
    const kwhTotal = sumOf(entry.statistics.consumo);
    const fixedTotal = this._data.fixedTotal || 0;
    const eurTotal = entry.statistics.costo ? sumOf(entry.statistics.costo) + fixedTotal : null;

    const periodButtons = el(
      "div",
      { class: "group", role: "group", "aria-label": tr(lang, "period_label") },
      PERIODS.map((p) =>
        this._toolbarButton(tr(lang, p), this._period === p, () => {
          this._period = p;
          this._load();
        }),
      ),
    );
    const nav = el("div", { class: "nav" }, [
      el("button", { title: tr(lang, "previous"), "aria-label": tr(lang, "previous"), onclick: () => this._go(-1), text: "‹" }),
      el("button", { title: tr(lang, "next"), "aria-label": tr(lang, "next"), onclick: () => this._go(1), text: "›" }),
      el("button", {
        onclick: () => {
          this._anchor = entry.last_day ? parseDay(entry.last_day) : new Date();
          this._load();
        },
        text: tr(lang, "latest"),
      }),
    ]);
    const viewButtons = el(
      "div",
      { class: "group", role: "group", "aria-label": tr(lang, "view_label") },
      VIEWS.map((v) =>
        this._toolbarButton(tr(lang, v), this._view === v, () => {
          this._view = v;
          this._load();
        }),
      ),
    );
    const unitButtons = el(
      "div",
      { class: "group", role: "group", "aria-label": tr(lang, "unit_label") },
      ["kwh", "eur"].map((u) =>
        this._toolbarButton(
          tr(lang, u),
          unit === u,
          () => {
            this._unit = u;
            this._load();
          },
          u === "eur" && (!entry.prices || view === "categories"),
          u === "eur" && !entry.prices ? tr(lang, "no_price") : u === "eur" && view === "categories" ? tr(lang, "categories_kwh_only") : null,
        ),
      ),
    );

    const summary = el("div", { class: "summary" }, [
      el("span", { class: "big", text: hasAny(entry.statistics.consumo) ? (unit === "eur" && eurTotal !== null ? f.eur(eurTotal) : f.kwh(kwhTotal)) : tr(lang, "no_data") }),
      hasAny(entry.statistics.consumo) && eurTotal !== null
        ? el("span", { class: "second", text: unit === "eur" ? f.kwh(kwhTotal) : f.eur(eurTotal) })
        : null,
      hasAny(entry.statistics.consumo) && eurTotal !== null && fixedTotal > 0
        ? el("span", { class: "second", text: tr(lang, "with_fixed", { x: f.eur(fixedTotal) }) })
        : null,
    ]);

    const children = [
      el("div", { class: "head" }, [el("h2", { text: title }), el("span", { class: "sub", text: subtitle })]),
      el("div", { class: "controls" }, [periodButtons, nav]),
      el("div", { class: "controls" }, [viewButtons, unitButtons]),
      summary,
    ];

    if (categoriesBlocked) {
      children.push(el("p", { class: "note", text: tr(lang, "categories_daily") }));
    } else {
      const format = unit === "eur" ? f.eur : f.kwh;
      if (series.length > 1) {
        children.push(
          el(
            "div",
            { class: "legend" },
            series.map((s) => el("span", {}, [el("span", { class: "key", style: `background:${this._colors[s.color]}` }), s.name, el("b", { text: format(s.total) })])),
          ),
        );
      }
      const labels = range.buckets.map((b) => {
        const d = new Date(b.start);
        if (this._period === "day") return f.hour(b.start);
        if (this._period === "week") return f.date(d, { weekday: "short" });
        if (this._period === "month") return String(d.getDate());
        return f.monthShort(d);
      });
      const when = (i) => {
        const b = range.buckets[i];
        const d = new Date(b.start);
        if (this._period === "day") return `${f.dayMonth(d)}, ${f.hour(b.start)}:00–${f.hour(b.end)}:00`;
        if (this._period === "year") return f.monthYear(d);
        return f.dayShort(d);
      };
      const chartBox = el("div", { class: `chart${this._loading ? " loading" : ""}` });
      if (this._showTable) {
        chartBox.append(this._table(series, range, when, format, lang));
      } else {
        const width = Math.max(220, this._width - 32);
        chartBox.append(
          columnChart({
            width,
            height: 200,
            series,
            labels,
            colors: this._colors,
            unit,
            format: f,
            ariaLabel: `${title}, ${subtitle}`,
            onHover: (i, x, y) =>
              this._tooltip(chartBox, width, i, x, y, (index) => {
                const rows = [el("div", { class: "when", text: when(index) })];
                const present = series.filter((s) => s.values[index] !== null);
                if (!present.length) rows.push(el("div", { text: tr(lang, "no_data") }));
                for (const s of [...series].reverse()) {
                  if (s.values[index] === null) continue;
                  rows.push(el("div", { class: "row" }, [el("span", { class: "line", style: `background:${this._colors[s.color]}` }), el("b", { text: format(s.values[index]) }), s.name]));
                }
                if (present.length > 1) {
                  const total = present.reduce((a, s) => a + s.values[index], 0);
                  rows.push(el("div", { class: "row sum" }, [el("b", { text: format(total) }), tr(lang, "total")]));
                }
                return rows;
              }),
            onLeave: () => this._hideTooltip(chartBox),
          }),
        );
      }
      children.push(chartBox);
    }

    children.push(
      el("div", { class: "footer" }, [
        el("span", { class: "note", text: entry.last_day ? `${tr(lang, "data_until")} ${f.dayMonthYear(parseDay(entry.last_day))}` : "" }),
        categoriesBlocked
          ? null
          : el("button", {
              onclick: () => {
                this._showTable = !this._showTable;
                this._render();
              },
              text: this._showTable ? tr(lang, "chart") : tr(lang, "table"),
            }),
      ]),
    );
    this._shell(children);
  }

  _table(series, range, when, format, lang) {
    const head = el("tr", {}, [el("th", { text: tr(lang, "when") }), ...series.map((s) => el("th", { text: s.name })), series.length > 1 ? el("th", { text: tr(lang, "total") }) : null]);
    const rows = range.buckets.map((_, i) => {
      const values = series.map((s) => s.values[i]);
      const any = values.some((v) => v !== null);
      return el("tr", {}, [
        el("td", { text: when(i) }),
        ...values.map((v) => el("td", { text: v === null ? "–" : format(v) })),
        series.length > 1 ? el("td", { text: any ? format(values.reduce((a, v) => a + (v || 0), 0)) : "–" }) : null,
      ]);
    });
    return el("div", { class: "tablewrap" }, [el("table", {}, [el("thead", {}, [head]), el("tbody", {}, rows)])]);
  }
}

// -------------------------------------------------------------------------------------- billing card

/** Billing periods repeat every ``months`` months from ``start``; return the one containing ``day``. */
function billingPeriod(start, months, day, offset = 0) {
  const dayOfMonth = start.getDate();
  let k = Math.floor(((day.getFullYear() - start.getFullYear()) * 12 + (day.getMonth() - start.getMonth())) / months);
  if (addMonths(start, k * months, dayOfMonth) > day) k -= 1;
  if (addMonths(start, (k + 1) * months, dayOfMonth) <= day) k += 1;
  k += offset;
  return { start: addMonths(start, k * months, dayOfMonth), end: addMonths(start, (k + 1) * months, dayOfMonth), index: k };
}

class PlenitudeBillingCard extends PlenitudeBase {
  static getConfigForm() {
    const lang = pageLang();
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        { name: "entry", selector: { config_entry: { integration: "plenitude" } } },
        { name: "start_date", required: true, selector: { date: {} } },
        {
          name: "months",
          selector: {
            select: {
              mode: "dropdown",
              options: [
                { value: "2", label: tr(lang, "two_months") },
                { value: "1", label: tr(lang, "one_month") },
              ],
            },
          },
        },
      ],
      computeLabel: (schema) => tr(lang, schema.name),
    };
  }

  static getStubConfig() {
    const today = new Date();
    const first = new Date(today.getFullYear(), today.getMonth() - (today.getMonth() % 2), 1);
    const pad = (n) => String(n).padStart(2, "0");
    return { start_date: `${first.getFullYear()}-${pad(first.getMonth() + 1)}-01`, months: "2" };
  }

  setConfig(config) {
    const months = Number(config.months) === 1 ? 1 : 2;
    this._config = { ...config, months };
    this._offset = 0;
    this._showTable = false;
    this._load();
  }

  async _fetch(entry) {
    if (!this._config.start_date) return { missingStart: true };
    const today = startOfDay(new Date());
    const period = billingPeriod(parseDay(this._config.start_date), this._config.months, today, this._offset);
    const range = { start: period.start, end: period.end, stat: "day", buckets: dayBuckets(period.start, period.end) };
    const changes = await getChanges(this._hass, entry, range);
    return { period, range, changes, isCurrent: this._offset === 0 };
  }

  _render() {
    const lang = this._lang;
    const f = fmt(lang);
    if (!this._config) return;
    const title = this._config.title || tr(lang, "default_billing_title");
    const entry = this._entry;
    if (this._error && !this._data) {
      this._shell([el("h2", { text: title }), el("p", { class: "note", text: `${tr(lang, "error")}: ${this._error}` })]);
      return;
    }
    if (this._loadedAt && !entry) {
      this._shell([el("h2", { text: title }), el("p", { class: "note", text: tr(lang, "not_configured") })]);
      return;
    }
    if (!this._data) {
      this._shell([el("h2", { text: title }), el("p", { class: "note", text: tr(lang, "loading") })], true);
      return;
    }
    if (this._data.missingStart) {
      this._shell([el("h2", { text: title }), el("p", { class: "note", text: tr(lang, "choose_start") })]);
      return;
    }
    const { period, range, changes, isCurrent } = this._data;
    const s = entry.statistics;
    const kwhDaily = changes[s.consumo];
    const sum = sumValues;
    const kwh = sum(kwhDaily);
    // Cost of the consumption so far (energy + costs per kWh, the cost statistic), plus the periodic costs of the
    // whole period as entered: the bill charges them in full (split evenly among the days for the columns).
    const usageEur = s.costo ? sum(changes[s.costo]) : null;
    const fixedPeriod = billingFixed(entry, period, this._config.months);
    const fixedDaily = range.buckets.map(() => (fixedPeriod ? fixedPeriod / range.buckets.length : null));
    const eur = usageEur !== null ? usageEur + fixedPeriod : null;
    const costOfDay = (i) => {
      const energy = s.costo ? changes[s.costo][i] : null;
      return energy === null && fixedDaily[i] === null ? null : (energy || 0) + (fixedDaily[i] || 0);
    };
    const periodDays = range.buckets.length;
    const dataDays = kwhDaily.filter((v) => v !== null).length;
    const lastDay = entry.last_day ? parseDay(entry.last_day) : null;
    const last = new Date(period.end.getTime() - 86400000);
    const future = startOfDay(new Date()) < period.start;
    const reached = lastDay ? Math.min(Math.max(daysBetween(period.start, lastDay) + 1, 0), periodDays) : 0;

    const nav = el("div", { class: "nav" }, [
      el("button", { title: tr(lang, "previous"), "aria-label": tr(lang, "previous"), onclick: () => { this._offset -= 1; this._load(); }, text: "‹" }),
      el("button", { title: tr(lang, "next"), "aria-label": tr(lang, "next"), disabled: this._offset >= 0, onclick: () => { this._offset += 1; this._load(); }, text: "›" }),
    ]);

    const tiles = el("div", { class: "tiles" }, [
      el("div", { class: "tile" }, [el("div", { class: "label", text: `${tr(lang, "consumption")}${isCurrent ? ` ${tr(lang, "so_far")}` : ""}` }), el("div", { class: "value", text: dataDays ? f.kwh(kwh) : "–" })]),
      eur !== null
        ? el("div", { class: "tile" }, [
            el("div", { class: "label", text: `${tr(lang, "cost")}${isCurrent ? ` ${tr(lang, "so_far")}` : ""}` }),
            el("div", { class: "value", text: dataDays ? f.eur(eur) : "–" }),
          ])
        : null,
    ]);

    const children = [
      el("div", { class: "head" }, [el("h2", { text: title }), nav]),
      el("div", { class: "sub", text: `${f.dayMonth(period.start)} – ${f.dayMonthYear(last)}${future ? ` (${tr(lang, "future")})` : ""}` }),
      tiles,
    ];
    if (eur === null) children.push(el("p", { class: "note", text: tr(lang, "no_price") }));

    // Progress through the period, by the last day with data.
    if (isCurrent && lastDay) {
      children.push(el("div", { class: "note", text: `${tr(lang, "data_until")} ${f.dayMonthYear(lastDay)} · ${tr(lang, "day_of", { x: reached, n: periodDays })}` }));
      const meter = el("div", { class: "meter", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": periodDays, "aria-valuenow": reached });
      meter.append(el("div", { style: `width:${(100 * reached) / periodDays}%` }));
      children.push(meter);
      if (dataDays >= 3 && reached < periodDays) {
        const projectedKwh = (kwh / dataDays) * periodDays;
        const projectedEur = usageEur !== null ? (usageEur / dataDays) * periodDays + fixedPeriod : null;
        children.push(
          el("p", { class: "note" }, [
            `${tr(lang, "estimate")}: `,
            el("b", { text: `≈ ${f.kwh(projectedKwh)}${projectedEur !== null ? ` · ≈ ${f.eur(projectedEur)}` : ""}` }),
            ` (${tr(lang, "estimate_note")})`,
          ]),
        );
      }
    }

    // Bands: one whole split into parts (thin segmented bar) plus a legend with kWh and EUR.
    const bands = buildSeries(entry, "bands", "kwh", lang);
    const bandValues = seriesValues(bands, changes, periodDays);
    const bandCosts = entry.prices ? seriesValues(buildSeries(entry, "bands", "eur", lang), changes, periodDays) : null;
    if (kwh > 0) {
      const bar = el("div", { class: "segbar", role: "img", "aria-label": bandValues.map((b) => `${b.name} ${Math.round((100 * b.total) / kwh)}%`).join(", ") });
      for (const b of bandValues) if (b.total > 0) bar.append(el("div", { style: `flex:${b.total};background:${this._colors[b.color]}` }));
      children.push(bar);
      children.push(
        el(
          "div",
          { class: "legend" },
          bandValues.map((b, i) =>
            el("span", {}, [
              el("span", { class: "key", style: `background:${this._colors[b.color]}` }),
              `${b.name} ${Math.round((100 * b.total) / kwh)}%`,
              el("b", { text: f.kwh(b.total) + (bandCosts ? ` · ${f.eur(bandCosts[i].total)}` : "") }),
            ]),
          ),
        ),
      );
    }
    // Cost breakdown, item by item, when there are costs besides the energy.
    if (eur !== null && dataDays && (entry.costs || []).length) {
      const kind = (c) => tr(lang, `kind_${c.kind}`) + (c.kind === "per_kw_monthly" && c.power ? `, ${f.number(c.power)} kW` : "");
      const rows = [[tr(lang, "energy_cost"), null, usageEur - kwh * perKwhExtra(entry)]];
      for (const c of perKwhCosts(entry)) rows.push([c.name, kind(c), kwh * Number(c.amount)]);
      for (const c of periodicCosts(entry)) rows.push([c.name, kind(c), billingFixed(entry, period, this._config.months, [c])]);
      const line = ([name, kindText, value]) =>
        el("tr", {}, [el("td", {}, [name, kindText ? el("span", { class: "kind", text: ` · ${kindText}` }) : null]), el("td", { text: f.eur(value) })]);
      children.push(
        el("details", { class: "breakdown", open: true }, [
          el("summary", { text: tr(lang, "cost_breakdown") }),
          el("table", {}, [
            el("tbody", {}, rows.map(line)),
            el("tfoot", {}, [el("tr", {}, [el("th", { text: tr(lang, "total") }), el("th", { text: f.eur(eur) })])]),
          ]),
        ]),
      );
    }

    // Daily columns of the period, by band.
    const chartBox = el("div", { class: `chart${this._loading ? " loading" : ""}` });
    const when = (i) => f.dayShort(new Date(range.buckets[i].start));
    if (this._showTable) {
      const head = el("tr", {}, [el("th", { text: tr(lang, "when") }), ...bandValues.map((b) => el("th", { text: b.name })), el("th", { text: tr(lang, "total") }), s.costo ? el("th", { text: tr(lang, "cost") }) : null]);
      const rows = range.buckets.map((_, i) =>
        el("tr", {}, [
          el("td", { text: when(i) }),
          ...bandValues.map((b) => el("td", { text: b.values[i] === null ? "–" : f.kwh(b.values[i]) })),
          el("td", { text: kwhDaily[i] === null ? "–" : f.kwh(kwhDaily[i]) }),
          s.costo ? el("td", { text: costOfDay(i) === null ? "–" : f.eur(costOfDay(i)) }) : null,
        ]),
      );
      chartBox.append(el("div", { class: "tablewrap" }, [el("table", {}, [el("thead", {}, [head]), el("tbody", {}, rows)])]));
    } else {
      const width = Math.max(220, this._width - 32);
      const labels = range.buckets.map((b) => String(new Date(b.start).getDate()));
      chartBox.append(
        columnChart({
          width,
          height: 150,
          series: bandValues,
          labels,
          colors: this._colors,
          unit: "kwh",
          format: f,
          ariaLabel: `${title}: ${f.dayMonth(period.start)} – ${f.dayMonthYear(last)}`,
          onHover: (i, x, y) =>
            this._tooltip(chartBox, width, i, x, y, (index) => {
              const rows = [el("div", { class: "when", text: when(index) })];
              if (kwhDaily[index] === null) {
                rows.push(el("div", { text: tr(lang, "no_data") }));
                return rows;
              }
              for (const b of [...bandValues].reverse()) {
                if (b.values[index] === null) continue;
                rows.push(el("div", { class: "row" }, [el("span", { class: "line", style: `background:${this._colors[b.color]}` }), el("b", { text: f.kwh(b.values[index]) }), b.name]));
              }
              rows.push(el("div", { class: "row sum" }, [el("b", { text: f.kwh(kwhDaily[index]) }), s.costo && costOfDay(index) !== null ? `· ${f.eur(costOfDay(index))}` : tr(lang, "total")]));
              return rows;
            }),
          onLeave: () => this._hideTooltip(chartBox),
        }),
      );
    }
    children.push(chartBox);
    children.push(
      el("div", { class: "footer" }, [
        eur !== null ? el("span", { class: "note", text: tr(lang, "cost_note") }) : el("span"),
        el("button", {
          onclick: () => {
            this._showTable = !this._showTable;
            this._render();
          },
          text: this._showTable ? tr(lang, "chart") : tr(lang, "table"),
        }),
      ]),
    );
    this._shell(children);
  }
}

if (!customElements.get("plenitude-consumption-card")) {
  customElements.define("plenitude-consumption-card", PlenitudeConsumptionCard);
}
if (!customElements.get("plenitude-billing-card")) {
  customElements.define("plenitude-billing-card", PlenitudeBillingCard);
}

// Names and descriptions for the card picker. Getters: this file is loaded before the frontend knows the language
// of the user, and the picker reads them only when it opens.
window.customCards = window.customCards || [];
for (const [type, name, description] of [
  ["plenitude-consumption-card", "consumption_card", "consumption_card_desc"],
  ["plenitude-billing-card", "billing_card", "billing_card_desc"],
]) {
  if (!window.customCards.some((card) => card.type === type)) {
    window.customCards.push({
      type,
      get name() {
        return tr(pageLang(), name);
      },
      get description() {
        return tr(pageLang(), description);
      },
      preview: false,
      documentationURL: "https://github.com/paoloaq/ha-plenitude",
    });
  }
}

console.info(`%c PLENITUDE-CARDS %c ${CARD_VERSION} `, "background:#2a78d6;color:#fff", "");

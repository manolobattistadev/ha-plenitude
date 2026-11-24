// Fake `hass` with SYNTHETIC data for the pages that show the cards (harness.html, dashboard.html): a
// deterministic hourly profile, bands as in the ARERA table (no holidays here), the prices and costs of a real
// contract.
// No real consumption. A classic script: it defines globals (makeHass, requests, ...) for the page.

const FIRST = new Date(2026, 0, 4).getTime();
const LAST_DAY = "2026-11-21";
const LAST = new Date(2026, 10, 22).getTime();
// A real contract (single price, 6 kW), so that the screenshots show realistic costs; the consumption is synthetic.
const PRICE = 0.2077;
const PRICES = { f1: PRICE, f2: PRICE, f3: PRICE };
// As plenitude/info sends them: ``yearly`` is euro per year (null for the costs per kWh and the percentages).
const COSTS = [
  { name: "Accise", kind: "per_kwh", amount: 0.0227, exempt: true, yearly: null },
  { name: "Quota fissa", kind: "monthly", amount: 6.92, exempt: false, yearly: 83.04 },
  { name: "Canone TV", kind: "bimonthly", amount: 18, exempt: true, yearly: 108 },
  { name: "Quota potenza 6 kW", kind: "per_kw_monthly", amount: 1.9767, power: 6, exempt: false, yearly: 142.3224 },
  { name: "IVA", kind: "percent", amount: 10, yearly: null },
];
const VAT = 1.1; // the percentage, on the energy and on the costs that are not excluded from it
const EXEMPT = 0.0227; // the costs per kWh excluded from the percentages
// Price of an hour of each band, as the integration computes it: (energy + costs per kWh) x VAT + excluded costs.
const HOUR_PRICES = Object.fromEntries(Object.entries(PRICES).map(([b, p]) => [b, p * VAT + EXEMPT]));
const CATS = ["comfort_ambientale", "standby", "lavare", "elettronica_luci", "refrigerare", "cucinare", "ricarica_elettrica", "altro"];
const NAMES = ["Comfort Ambientale (HVAC)", "Standby", "Lavare", "Elettronica e luci", "Refrigerare", "Cucinare", "Ricarica elettrica", "Altro"];
const SHARES = [0.22, 0.12, 0.1, 0.16, 0.14, 0.1, 0.06, 0.1];
const P = "plenitude:luce_demo";
function band(t) {
  const d = new Date(t), h = d.getHours(), w = d.getDay();
  if (w === 0 || h < 7 || h >= 23) return "f3";
  if (w === 6) return "f2";
  return h >= 8 && h < 19 ? "f1" : "f2";
}
function kwh(t) {
  const d = new Date(t), h = d.getHours(), w = d.getDay();
  const season = 1 + 0.35 * Math.cos(((d.getMonth() + 0.5) / 12) * 2 * Math.PI);
  const home = w === 0 || w === 6; // at home at the weekend: more during the day
  const shape = 0.18 + (home ? 0.4 : 0.25) * Math.exp(-((h - (home ? 12 : 8)) ** 2) / (home ? 10 : 4)) + 0.45 * Math.exp(-((h - 20) ** 2) / 5);
  const noise = 0.85 + 0.3 * Math.abs(Math.sin(t / 3.7e6));
  // A different day every day, always the same for the same date (washing machine, oven, guests...).
  const n = Math.floor(new Date(d.getFullYear(), d.getMonth(), d.getDate(), 12).getTime() / 86400000);
  const day = 0.7 + 0.6 * ((Math.sin(n * 12.9898) * 43758.5453) % 1 + 1) % 1;
  return shape * season * noise * day;
}
function valueOf(id, t) {
  if (t < FIRST || t >= LAST) return null;
  const key = id.slice(P.length + 1);
  const v = kwh(t);
  if (key === "consumo") return v;
  // ?nocost: the cost statistic has no rows (being rewritten, or never written), as on a server on 2026-11-23.
  if (key === "costo") return location.search.includes("nocost") ? null : v * HOUR_PRICES[band(t)];
  if (key === "f1" || key === "f2" || key === "f3") return band(t) === key ? v : 0;
  return null;
}
function stepStart(t, period) {
  const d = new Date(t);
  if (period === "hour") return t + 3600000;
  if (period === "day") return new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1).getTime();
  return new Date(d.getFullYear(), d.getMonth() + 1, 1).getTime();
}
function statistics(msg) {
  const out = {};
  const start = Date.parse(msg.start_time), end = Date.parse(msg.end_time);
  for (const id of msg.statistic_ids) {
    const rows = [];
    const cat = CATS.findIndex((c) => id.endsWith("_cat_" + c));
    for (let b = start; b < end; b = stepStart(b, msg.period)) {
      const e = Math.min(stepStart(b, msg.period), end);
      let sum = null;
      for (let t = b; t < e; t += 3600000) {
        const v = cat >= 0 ? (valueOf(P + "_consumo", t) ?? null) : valueOf(id, t);
        if (v !== null) sum = (sum || 0) + (cat >= 0 ? v * SHARES[cat] : v);
      }
      if (sum !== null) rows.push({ start: b, end: e, change: sum });
    }
    out[id] = rows;
  }
  return out;
}
const requests = { info: 0, statistics: 0 };
const connection = {}; // one connection for the page, as in Home Assistant
function makeHass(dark, lang = "it") {
  return {
    language: lang, locale: { language: lang }, themes: { darkMode: dark }, connection,
    async callWS(msg) {
      if (msg.type === "plenitude/info") {
        requests.info += 1;
        return { entries: [{
          entry_id: "demo", title: "Plenitude luce", version: "harness", first_day: "2026-01-04", last_day: LAST_DAY, price_mode: "single", prices: PRICES,
          hour_prices: HOUR_PRICES, costs: COSTS, currency: "EUR",
          statistics: { consumo: P + "_consumo", f1: P + "_f1", f2: P + "_f2", f3: P + "_f3", costo: P + "_costo" },
          categories: CATS.map((c, i) => ({ key: c, name: NAMES[i], statistic_id: P + "_cat_" + c })),
        }] };
      }
      if (msg.type === "recorder/statistics_during_period") {
        requests.statistics += 1;
        await new Promise((resolve) => setTimeout(resolve, 200)); // a recorder that takes its time
        return statistics(msg);
      }
      throw new Error("unexpected " + msg.type);
    },
  };
}

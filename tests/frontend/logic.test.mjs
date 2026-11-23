// Date logic of the cards. Run with: TZ=Europe/Rome node --test tests/frontend/
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

// Load the cards file in a sandbox with the few browser globals it touches at load time.
const source = readFileSync(new URL("../../custom_components/plenitude/frontend/plenitude-cards.js", import.meta.url), "utf8");
const sandbox = {
  HTMLElement: class {},
  customElements: { get: () => undefined, define: () => {} },
  window: {},
  document: { documentElement: { lang: "it" } },
  navigator: { language: "it-IT" },
  console: { info: () => {} },
  Intl,
  Date,
  Math,
};
vm.createContext(sandbox);
vm.runInContext(source, sandbox);
const { billingPeriod, periodRange, buildSeries, seriesValues, fixedShares, categoryName } = sandbox;

const day = (y, m, d) => new Date(y, m - 1, d);
const ymd = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

test("bimonthly periods from the 1st", () => {
  const p = billingPeriod(day(2026, 1, 1), 2, day(2026, 11, 22));
  assert.equal(ymd(p.start), "2026-11-01");
  assert.equal(ymd(p.end), "2027-01-01");
  const previous = billingPeriod(day(2026, 1, 1), 2, day(2026, 11, 22), -1);
  assert.equal(ymd(previous.start), "2026-09-01");
  assert.equal(ymd(previous.end), "2026-11-01");
});

test("periods from any day, also a start date in the future", () => {
  const p = billingPeriod(day(2027, 3, 15), 2, day(2026, 11, 22));
  assert.equal(ymd(p.start), "2026-11-15");
  assert.equal(ymd(p.end), "2027-01-15");
  const boundary = billingPeriod(day(2026, 3, 15), 2, day(2026, 11, 15));
  assert.equal(ymd(boundary.start), "2026-11-15"); // the first day belongs to the new period
  const before = billingPeriod(day(2026, 3, 15), 2, day(2026, 11, 14));
  assert.equal(ymd(before.start), "2026-09-15");
});

test("a start on the 31st is clamped to short months, without drifting", () => {
  const p = billingPeriod(day(2026, 1, 31), 1, day(2026, 2, 20));
  assert.equal(ymd(p.start), "2026-01-31");
  assert.equal(ymd(p.end), "2026-02-28");
  const next = billingPeriod(day(2026, 1, 31), 1, day(2026, 3, 5));
  assert.equal(ymd(next.start), "2026-02-28");
  assert.equal(ymd(next.end), "2026-03-31"); // back to the 31st
});

test("day view follows real time on DST days", () => {
  assert.equal(periodRange("day", day(2026, 3, 29)).buckets.length, 23);
  assert.equal(periodRange("day", day(2026, 10, 25)).buckets.length, 25);
  assert.equal(periodRange("day", day(2026, 11, 20)).buckets.length, 24);
});

test("week starts on Monday, month and year have their own length", () => {
  const week = periodRange("week", day(2026, 11, 22)); // a Sunday
  assert.equal(ymd(week.start), "2026-11-16");
  assert.equal(week.buckets.length, 7);
  assert.equal(periodRange("month", day(2026, 2, 10)).buckets.length, 28);
  const march = periodRange("month", day(2026, 3, 10)); // contains the DST change
  assert.equal(march.buckets.length, 31);
  assert.equal(new Date(march.buckets[30].start).getDate(), 31);
  assert.equal(periodRange("year", day(2026, 6, 1)).buckets.length, 12);
});

test("bands in EUR use the price of each band; two-band contracts show F1 and F23", () => {
  const entry = {
    statistics: { consumo: "c", f1: "a", f2: "b", f3: "d", costo: "e" },
    prices: { f1: 0.3, f2: 0.2, f3: 0.2 },
    price_mode: "two",
    categories: [],
  };
  const series = buildSeries(entry, "bands", "eur", "it");
  assert.deepEqual(Array.from(series, (s) => s.name), ["F1", "F23"]); // Array.from: the sandbox has its own Array
  const values = seriesValues(series, { a: [1, null], b: [2, null], d: [3, null] }, 2);
  assert.ok(Math.abs(values[0].values[0] - 0.3) < 1e-9);
  assert.ok(Math.abs(values[1].values[0] - 1.0) < 1e-9);
  assert.equal(values[0].values[1], null); // no data stays "no data", not zero
});

test("periodic costs: euro per year / days of the year, from the first to the last day with data", () => {
  // ``yearly`` as the integration sends it (plenitude/info): amount x times a year, x power for the costs per kW.
  const entry = {
    prices: { f1: 0.3, f2: 0.3, f3: 0.3 },
    costs: [
      { name: "Monthly", kind: "monthly", amount: 9.125, yearly: 109.5 },
      { name: "Two-monthly", kind: "bimonthly", amount: 18.25, yearly: 109.5 },
      { name: "Power", kind: "per_kw_monthly", amount: 1.825, power: 5, yearly: 109.5 },
      { name: "Yearly", kind: "yearly", amount: 36.5, yearly: 36.5 },
      { name: "Per kWh", kind: "per_kwh", amount: 0.05, yearly: null },
    ],
    first_day: "2026-01-04",
    last_day: "2026-11-20",
  };
  const perDay = (109.5 * 3 + 36.5) / 365; // 1.0 EUR a day in 2026; per kWh costs excluded
  const november = periodRange("month", day(2026, 11, 10));
  const shares = fixedShares(entry, november.buckets);
  assert.ok(Math.abs(shares[0] - perDay) < 1e-9);
  assert.ok(Math.abs(shares[19] - perDay) < 1e-9); // the 20th, last day with data
  assert.equal(shares[20], null); // nothing after the last day with data
  const january = fixedShares(entry, periodRange("month", day(2026, 1, 10)).buckets);
  assert.equal(january[2], null); // before the history
  assert.ok(Math.abs(january[3] - perDay) < 1e-9);
  // Whole period on request (estimate at the end of the period), and one item alone (cost breakdown).
  const full = fixedShares(entry, november.buckets, day(2026, 11, 30));
  assert.ok(Math.abs(full.reduce((a, v) => a + v, 0) - 30 * perDay) < 1e-9);
  const yearlyOnly = fixedShares(entry, november.buckets, undefined, [entry.costs[3]]);
  assert.ok(Math.abs(yearlyOnly[0] - 0.1) < 1e-9);
  // Day view: split by the real hours of the day, 25 on 25 October.
  const longDay = fixedShares(entry, periodRange("day", day(2026, 10, 25)).buckets);
  assert.equal(longDay.length, 25);
  assert.ok(Math.abs(longDay.reduce((a, v) => a + v, 0) - perDay) < 1e-9);
  // No cost at all: nothing.
  assert.equal(fixedShares({ ...entry, prices: null }, november.buckets)[0], null);
});

test("costs per kWh are added to the price of every band in euro", () => {
  const entry = {
    statistics: { consumo: "c", f1: "a", f2: "b", f3: "d", costo: "e" },
    prices: { f1: 0.3, f2: 0.2, f3: 0.1 },
    price_mode: "three",
    costs: [{ name: "Oneri", kind: "per_kwh", amount: 0.05 }, { name: "Quota", kind: "monthly", amount: 10 }],
    categories: [],
  };
  const series = seriesValues(buildSeries(entry, "bands", "eur", "it"), { a: [1], b: [1], d: [1] }, 1);
  assert.deepEqual(Array.from(series, (s) => Math.round(s.values[0] * 100) / 100), [0.35, 0.25, 0.15]);
});

test("category names: the portal's in Italian, translated in English", () => {
  const category = { key: "comfort_ambientale", name: "Comfort Ambientale (HVAC)" };
  assert.equal(categoryName("it", category), "Comfort Ambientale (HVAC)");
  assert.equal(categoryName("en", category), "Heating and cooling (HVAC)");
  assert.equal(categoryName("en", { key: "nuova", name: "Nuova" }), "Nuova"); // unknown key: the portal's name
});

// ----------------------------------------------------------------------------- cache and language

/** A fresh copy of the cards, as after a reload of the page, with the given browser storage and language. */
function freshCards({ storage = new Map(), lang = "it", selected = null } = {}) {
  if (selected !== null) storage.set("selectedLanguage", JSON.stringify(selected));
  const localStorage = {
    get length() {
      return storage.size;
    },
    key: (i) => [...storage.keys()][i] ?? null,
    getItem: (k) => (storage.has(k) ? storage.get(k) : null),
    setItem: (k, v) => storage.set(k, String(v)),
    removeItem: (k) => storage.delete(k),
  };
  const box = {
    HTMLElement: class {},
    customElements: { get: () => undefined, define: () => {} },
    window: { localStorage },
    document: { documentElement: { lang }, querySelector: () => null },
    navigator: { language: "en-US" },
    console: { info: () => {} },
    Intl,
    Date,
    Math,
    JSON,
    Promise,
  };
  box.window.customCards = [];
  vm.createContext(box);
  vm.runInContext(source, box);
  return { box, storage };
}

function fakeHass(calls) {
  return {
    connection: {},
    callWS: async (msg) => {
      calls.push(msg.type);
      const rows = Object.fromEntries(msg.statistic_ids.map((id) => [id, [{ start: new Date(msg.start_time).getTime(), change: 1 }]]));
      return rows;
    },
  };
}

const ENTRY = {
  entry_id: "e1",
  version: "v1",
  statistics: { consumo: "c", f1: "a", f2: "b", f3: "d", costo: null },
  categories: [{ key: "altro", statistic_id: "k" }],
};

test("a period is read once per data version, for every statistic, and kept across reloads of the page", async () => {
  const { box, storage } = freshCards();
  const calls = [];
  const hass = fakeHass(calls);
  const range = box.periodRange("month", day(2026, 11, 10));
  const first = await box.getChanges(hass, ENTRY, range);
  assert.deepEqual(Object.keys(first).sort(), ["a", "b", "c", "d", "k"]); // all of them: views switch at once
  await box.getChanges(hass, ENTRY, box.periodRange("month", day(2026, 11, 25)));
  assert.equal(calls.length, 1); // same month: from memory

  // Reload of the page: from the browser's storage, no request.
  const again = freshCards({ storage });
  const reloaded = await again.box.getChanges(hass, ENTRY, again.box.periodRange("month", day(2026, 11, 10)));
  assert.equal(calls.length, 1);
  assert.equal(reloaded.c[0], 1);
  assert.equal(reloaded.c[0], first.c[0]);

  // New data in the integration: read again, and the old version leaves the storage.
  await again.box.getChanges(hass, { ...ENTRY, version: "v2" }, again.box.periodRange("month", day(2026, 11, 10)));
  assert.equal(calls.length, 2);
  const names = [...storage.keys()].filter((k) => k.startsWith("plenitude-cards:"));
  assert.equal(names.length, 1);
  assert.ok(names[0].includes("|v2|"));
});

test("the browser's storage keeps a bounded number of periods", async () => {
  const { box, storage } = freshCards();
  const hass = fakeHass([]);
  for (let i = 0; i < 60; i++) await box.getChanges(hass, ENTRY, box.periodRange("day", new Date(2026, 0, 1 + i)));
  assert.equal([...storage.keys()].filter((k) => k.startsWith("plenitude-cards:")).length, 40);
});

test("blocked storage: the cards work from memory", async () => {
  const { box } = freshCards();
  box.window.localStorage.setItem = () => {
    throw new Error("QuotaExceededError");
  };
  const calls = [];
  const range = box.periodRange("week", day(2026, 11, 10));
  await box.getChanges(fakeHass(calls), ENTRY, range);
  await box.getChanges(fakeHass(calls), ENTRY, range);
  assert.equal(calls.length, 1);
});

test("card picker: names in the language of the profile, read when the picker opens", () => {
  const { box } = freshCards({ lang: "" });
  const card = box.window.customCards.find((c) => c.type === "plenitude-consumption-card");
  assert.equal(card.name, "Plenitude: consumption"); // nothing known yet: the browser's language
  box.document.documentElement.lang = "it"; // set by the frontend once its translations are loaded
  assert.equal(card.name, "Plenitude: consumi");
  assert.equal(freshCards({ lang: "", selected: "it" }).box.window.customCards[0].name, "Plenitude: consumi");
});

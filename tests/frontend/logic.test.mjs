// Date logic of the cards. Run with: TZ=Europe/Rome node --test tests/frontend/
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

// Load the cards file in a sandbox with the few browser globals it touches at load time.
const source = readFileSync(new URL("../../custom_components/plenitude/frontend/plenitude-cards.js", import.meta.url), "utf8");
const sandbox = {
  HTMLElement: class {},
  customElements: { get: () => undefined, define: () => {}, whenDefined: () => new Promise(() => {}) },
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
const { billingPeriod, periodRange, buildSeries, seriesValues, fixedShares, billingFixed, costBreakdown, categoryName, statisticIds } = sandbox;

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

test("periodic costs count in full: every month carries 1/12 of the euro per year, split among its days", () => {
  // ``yearly`` as the integration sends it (plenitude/info): amount x times a year, x power for the costs per kW.
  const entry = {
    prices: { f1: 0.3, f2: 0.3, f3: 0.3 },
    costs: [
      { name: "Canone TV", kind: "monthly", amount: 9, yearly: 108 },
      { name: "Bimestrale", kind: "bimonthly", amount: 12, yearly: 72 },
      { name: "Quota potenza", kind: "per_kw_monthly", amount: 2, power: 3, yearly: 72 },
      { name: "Annuale", kind: "yearly", amount: 36, yearly: 36 },
      { name: "Per kWh", kind: "per_kwh", amount: 0.05, yearly: null },
    ],
    first_day: "2026-01-04",
    last_day: "2026-11-20",
  };
  const monthly = (108 + 72 + 72 + 36) / 12; // 24 EUR a month; per kWh costs excluded
  const total = (values) => values.reduce((a, v) => a + (v || 0), 0);
  const close = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);
  // The current month in full, also its days after the last day with data.
  const november = fixedShares(entry, periodRange("month", day(2026, 11, 10)).buckets);
  close(total(november), monthly);
  close(november[29], monthly / 30);
  // February: the same amount over 28 days; the first month of the history in full.
  close(total(fixedShares(entry, periodRange("month", day(2026, 2, 10)).buckets)), monthly);
  close(total(fixedShares(entry, periodRange("month", day(2026, 1, 10)).buckets)), monthly);
  // Nothing after the month of the last day with data, nothing before the month of the first day.
  assert.equal(total(fixedShares(entry, periodRange("month", day(2026, 12, 10)).buckets)), 0);
  assert.equal(fixedShares(entry, periodRange("month", day(2025, 12, 10)).buckets)[0], null);
  // Year view: one column per month, January to November.
  const year = fixedShares(entry, periodRange("year", day(2026, 6, 1)).buckets);
  close(year[0], monthly);
  close(year[10], monthly);
  assert.equal(year[11], null);
  // One item alone (the monthly TV licence): 9 EUR in November.
  close(total(fixedShares(entry, periodRange("month", day(2026, 11, 10)).buckets, [entry.costs[0]])), 9);
  // Day view: the share of the day, split by its real hours, 25 on 25 October.
  const longDay = fixedShares(entry, periodRange("day", day(2026, 10, 25)).buckets);
  assert.equal(longDay.length, 25);
  close(total(longDay), monthly / 31);
  // No cost at all: nothing.
  assert.equal(fixedShares({ ...entry, prices: null }, periodRange("month", day(2026, 11, 10)).buckets)[0], null);
});

test("billing period: the periodic costs of all its months, also before it is over", () => {
  const entry = {
    prices: { f1: 0.3, f2: 0.3, f3: 0.3 },
    costs: [{ name: "Canone TV", kind: "monthly", amount: 9, yearly: 108 }],
    first_day: "2026-01-04",
    last_day: "2026-11-21",
  };
  const current = billingPeriod(day(2026, 1, 1), 2, day(2026, 11, 23)); // 1 November - 1 January
  assert.ok(Math.abs(billingFixed(entry, current, 2) - 18) < 1e-9); // 9 EUR a month, two months: 18 EUR
  const fromThe15th = billingPeriod(day(2026, 1, 15), 2, day(2026, 11, 23));
  assert.ok(Math.abs(billingFixed(entry, fromThe15th, 2) - 18) < 1e-9); // not aligned to the months: still 18
  assert.ok(Math.abs(billingFixed(entry, current, 1) - 9) < 1e-9);
  assert.equal(billingFixed(entry, billingPeriod(day(2025, 1, 1), 2, day(2025, 11, 23)), 2), 0); // before the history
  assert.equal(billingFixed({ ...entry, prices: null }, current, 2), 0);
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

const close = (a, b) => Math.abs(a - b) < 1e-9;
// VAT at 10 % on everything but the TV licence fee and a bonus per kWh excluded from it.
const WITH_VAT = {
  statistics: { consumo: "c", f1: "a", f2: "b", f3: "d", costo: "e" },
  prices: { f1: 0.2, f2: 0.2, f3: 0.2 },
  price_mode: "single",
  costs: [
    { name: "Oneri", kind: "per_kwh", amount: 0.05, exempt: false, yearly: null },
    { name: "Bonus", kind: "per_kwh", amount: -0.01, exempt: true, yearly: null },
    { name: "Quota fissa", kind: "monthly", amount: 10, exempt: false, yearly: 120 },
    { name: "Canone TV", kind: "monthly", amount: 9, exempt: true, yearly: 108 },
    { name: "IVA", kind: "percent", amount: 10, yearly: null },
  ],
  categories: [],
  first_day: "2026-01-04",
  last_day: "2026-11-21",
};

test("percentages apply to the periodic costs, except to those excluded", () => {
  const current = billingPeriod(day(2026, 1, 1), 2, day(2026, 11, 23));
  assert.ok(close(billingFixed(WITH_VAT, current, 2), (10 * 1.1 + 9) * 2)); // 40 EUR, not 38 nor 41.8
  assert.ok(close(billingFixed(WITH_VAT, current, 2, undefined, false), 38)); // as entered
  const november = fixedShares(WITH_VAT, periodRange("month", day(2026, 11, 10)).buckets);
  assert.ok(close(november.reduce((a, v) => a + (v || 0), 0), 10 * 1.1 + 9));
});

test("cost breakdown: the energy out of the cost statistic, every cost as entered, the percentage on its base", () => {
  const kwh = 100;
  const usageEur = kwh * ((0.2 + 0.05) * 1.1 - 0.01); // what the integration writes in the cost statistic
  const current = billingPeriod(day(2026, 1, 1), 2, day(2026, 11, 23));
  const fixedOf = (items, withPercent) => billingFixed(WITH_VAT, current, 2, items, withPercent);
  const rows = costBreakdown(WITH_VAT, usageEur, kwh, fixedOf);
  const byName = Object.fromEntries(rows.map((r) => [r.cost ? r.cost.name : "energy", Math.round(r.value * 1e6) / 1e6]));
  assert.deepEqual({ ...byName }, { energy: 20, Oneri: 5, Bonus: -1, "Quota fissa": 20, "Canone TV": 18, IVA: 4.5 });
  // The rows add up to the total of the card: the cost statistic plus the periodic costs with their VAT.
  assert.ok(close(rows.reduce((a, r) => a + r.value, 0), usageEur + billingFixed(WITH_VAT, current, 2)));
});

test("bands in euro: the price of an hour from the integration, with the percentages", () => {
  const changes = { a: [1], b: [1], d: [1] };
  const fromIntegration = { ...WITH_VAT, hour_prices: { f1: 0.5, f2: 0.4, f3: 0.3 } };
  const given = seriesValues(buildSeries({ ...fromIntegration, price_mode: "three" }, "bands", "eur", "it"), changes, 1);
  assert.deepEqual(Array.from(given, (s) => s.values[0]), [0.5, 0.4, 0.3]);
  // Older integration without hour_prices: the same formula as the cost statistic.
  const computed = seriesValues(buildSeries({ ...WITH_VAT, price_mode: "three" }, "bands", "eur", "it"), changes, 1);
  assert.ok(close(computed[0].values[0], (0.2 + 0.05) * 1.1 - 0.01));
});

test("the cost of the consumption comes from the bands, not from the cost statistic", () => {
  // The cost statistic is empty while the integration rewrites it (new prices or costs): the cards do not read it.
  const entry = { ...WITH_VAT, price_mode: "three", hour_prices: { f1: 0.5, f2: 0.4, f3: 0.3 } };
  assert.ok(!statisticIds(entry).includes("e"));
  const [cost] = seriesValues(buildSeries(entry, "total", "eur", "it"), { a: [2, null], b: [1, null], d: [0, null], e: [0, null] }, 2);
  assert.ok(close(cost.values[0], 2 * 0.5 + 1 * 0.4));
  assert.equal(cost.values[1], null); // no data, no cost
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
    customElements: { get: () => undefined, define: () => {}, whenDefined: () => new Promise(() => {}) },
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

// A registry with what the cards file uses; `onDefine` mimics the polyfill, which also defines a stand-in for every
// element in the native registry.
class FakeRegistry {
  constructor(onDefine = () => {}) {
    this.classes = new Map();
    this.waiting = new Map();
    this.onDefine = onDefine;
  }
  get(type) {
    return this.classes.get(type);
  }
  define(type, cls) {
    if (this.classes.has(type)) throw new Error(`${type} already defined`);
    this.classes.set(type, cls);
    this.onDefine(type);
    this.waiting.get(type)?.forEach((resolve) => resolve(cls));
  }
  whenDefined(type) {
    if (this.classes.has(type)) return Promise.resolve(this.classes.get(type));
    return new Promise((resolve) => this.waiting.set(type, [...(this.waiting.get(type) || []), resolve]));
  }
}

function cardsIn(registry, window = {}) {
  const box = {
    HTMLElement: class {},
    customElements: registry,
    window: { customCards: [], ...window },
    document: { documentElement: { lang: "it" }, querySelector: () => null },
    navigator: { language: "it-IT" },
    console: { info: () => {} },
    Intl,
    Date,
    Math,
    JSON,
    Promise,
  };
  vm.createContext(box);
  vm.runInContext(source, box);
  return box;
}

const CARD_TYPES = ["plenitude-consumption-card", "plenitude-billing-card"];

test("cards started before the frontend's polyfill are defined in the registry that replaces the native one", async () => {
  const native = new FakeRegistry();
  const box = cardsIn(native); // Home Assistant 2026.10 and older: this file can run first
  await Promise.resolve();
  assert.deepEqual(CARD_TYPES.map((t) => native.get(t)), [undefined, undefined]); // nothing in the old registry
  const scoped = new FakeRegistry((type) => native.get(type) || native.define(type, class {}));
  box.window.CustomElementRegistryPolyfill = {}; // the polyfill swaps window.customElements
  box.customElements = scoped;
  scoped.define("home-assistant", class {}); // then the frontend defines its root element
  await new Promise((resolve) => setImmediate(resolve));
  assert.ok(CARD_TYPES.every((t) => scoped.get(t)));
  assert.ok(CARD_TYPES.every((t) => native.get(t) !== scoped.get(t))); // only the polyfill's stand-ins there
});

test("cards started after the polyfill, or with the frontend already up, are defined at once", () => {
  const scoped = new FakeRegistry();
  cardsIn(scoped, { CustomElementRegistryPolyfill: {} }); // Home Assistant 2026.11: the polyfill comes first
  assert.ok(CARD_TYPES.every((t) => scoped.get(t)));
  const native = new FakeRegistry();
  native.define("home-assistant", class {}); // a frontend without the polyfill, already started
  cardsIn(native);
  assert.ok(CARD_TYPES.every((t) => native.get(t)));
});

test("without the polyfill the cards wait for the frontend's root element", async () => {
  const native = new FakeRegistry();
  cardsIn(native);
  assert.equal(native.get("plenitude-billing-card"), undefined);
  native.define("home-assistant", class {});
  await new Promise((resolve) => setImmediate(resolve));
  assert.ok(CARD_TYPES.every((t) => native.get(t)));
});

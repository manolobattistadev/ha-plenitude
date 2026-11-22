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
const { billingPeriod, periodRange, buildSeries, seriesValues } = sandbox;

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

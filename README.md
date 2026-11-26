# Eni Plenitude - Italian Electricity and Gas Energy Tracking for Home Assistant

[![Marketplace and HACS: custom repository](https://img.shields.io/badge/Marketplace%20%7C%20HACS-custom%20repository-41BDF5)](#installation)
[![Home Assistant 2026.9+](https://img.shields.io/badge/Home%20Assistant-2026.9%2B-18BCF2)](https://www.home-assistant.io/)
[![Tests](https://github.com/paoloaq/ha-plenitude/actions/workflows/tests.yml/badge.svg)](https://github.com/paoloaq/ha-plenitude/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**English** · [Italiano](README.it.md)

A Home Assistant integration that brings the electricity and gas consumption of your
[Eni Plenitude](https://eniplenitude.com) customer area into Home Assistant:

- hourly consumption as **long-term statistics**, with its real date, ready for the Energy dashboard;
- the same consumption split by **ARERA time band** (F1, F2, F3);
- the **estimated categories** of the customer area (heating and cooling, washing, cooking…), day by day;
- the **cost**, from the prices you enter (single price, two or three bands) plus **as many other costs as you
  want** (monthly, two-monthly, yearly, per kW, per kWh or a percentage: TV licence, fixed fee, power fee,
  system charges, VAT…);
- the **gas** consumption, month by month (day by day where the meter sends daily readings), in m³ for the gas
  section of the Energy dashboard, with its cost;
- two **dashboard cards**: a consumption chart with a period of your choice, and the **current bill** (kWh and
  euro of the billing period so far, with an estimate at the end of the period).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/paoloaq/ha-plenitude/main/docs/images/dashboard-dark-en.png">
  <img alt="The example dashboard: current bill and consumption of the week in euro, by band (synthetic consumption)" src="https://raw.githubusercontent.com/paoloaq/ha-plenitude/main/docs/images/dashboard-light-en.png">
</picture>

It is an integration, not an add-on: it works with every installation type (Home Assistant OS, Container, Core).

> [!IMPORTANT]
> **Unofficial.** This project is not affiliated with, endorsed or supported by Eni Plenitude or Eni. It uses
> the same web services as the customer area, which are not documented and can change without notice. It makes
> a few requests a day, like a person checking the customer area.

> [!NOTE]
> **Built with AI.** This software is developed with strong assistance from AI coding agents, with a human
> leading the ideas, the design decisions, the testing on a real customer area and the debugging. This is
> stated openly because it shaped how the project was built. If you are not comfortable with AI-developed
> code, this software is not for you.
>
> *— loosely quoting the great [antirez](https://github.com/antirez)*

## Contents
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [What you get](#what-you-get)
- [Cards](#cards)
- [How it works](#how-it-works)
- [Languages](#languages)
- [Privacy and security](#privacy-and-security)
- [Troubleshooting](#troubleshooting)
- [Removal](#removal)
- [Limitations](#limitations)
- [Development](#development)

## Requirements
- Home Assistant **2026.9** or later.
- An Eni Plenitude customer area account with **email and password** (sign-in with social accounts is not
  supported).
- An **electricity** supply for which the customer area shows the consumption analysis (consumption every
  15 minutes, usually available with second-generation smart meters), or a **gas** supply for which it shows the
  consumption (monthly, or daily with the meters that send daily readings).

## Installation

It depends on your version of Home Assistant: from **2026.11** HACS is part of Home Assistant as the
**Marketplace**; up to 2026.10 it is the HACS custom integration.

### With the Marketplace (Home Assistant 2026.11 and later, recommended)
1. Open **Settings → Marketplace**, tab **Add from link**. Or open [this link](https://my.home-assistant.io/redirect/marketplace_repository/?owner=paoloaq&repository=ha-plenitude&category=integration): it asks to add the repository
   to the Marketplace of your Home Assistant.
2. As **GitHub link** enter `https://github.com/paoloaq/ha-plenitude`, as **Type** choose **Integration**, then
   select **Add**. The first time the Marketplace asks you to **Connect GitHub**: you get a code to enter on GitHub,
   and the connection only reads public information.
3. Search for **Eni Plenitude**, open it and select **Install**.
4. Restart Home Assistant.

Installed with HACS before updating Home Assistant to 2026.11? There is nothing to do: at the first start the
Marketplace takes over HACS and the repositories added to it, Eni Plenitude included.

### With HACS (Home Assistant 2026.10 and earlier)
1. In Home Assistant open **HACS**, then the menu **⋮ → Custom repositories**.
2. Add `https://github.com/paoloaq/ha-plenitude` with type **Integration**.
3. Search for **Eni Plenitude**, open it and select **Download**.
4. Restart Home Assistant.

### Manually
1. Download the [latest release](https://github.com/paoloaq/ha-plenitude/releases/latest) and copy the folder
   `custom_components/plenitude` into the `custom_components` folder of your Home Assistant configuration (the
   folder that contains `configuration.yaml`; with Docker, the folder mounted on `/config`).
2. Restart Home Assistant.

## Configuration
1. Go to **Settings → Devices & services → Add integration** and search for **Eni Plenitude**.
2. Enter the email and password of the customer area.
3. If the account has more than one supply (electricity or gas), choose the one to import. To import another one,
   for example the gas after the electricity, add the integration again.

The first import starts right away, in the background: it reads the history going back from yesterday, three days
at a time, until it finds a month without data (at most three years). The last two weeks appear in a few seconds;
the whole history follows in a few minutes (about 6 minutes for three years).

### Prices and costs
Plenitude does not expose the price of your offer, so the cost is computed from prices and costs you enter.

**Price of the energy.** Open **Settings → Devices & services → Eni Plenitude → Configure**:

| Price type | Fields |
|---|---|
| No price | consumption only |
| Single price | one price per kWh for every hour |
| Two bands | F1 and F23 (F2 + F3) |
| Three bands | F1, F2 and F3 |

**Other costs.** In the same page select **Add cost**, as many times as you need. First the cost's:
- **Name**: free text, for example TV licence, fixed fee, power fee, system charges, VAT;
- **Type**: monthly, every two months, yearly, per kW per month, per kWh or percentage.

Then, in the unit of the type:
- **Amount**: euro, euro per kWh, euro per kW or percent, with a comma or a point for the decimals (`9,15` or
  `9.15`), at most 6 decimals, no thousands separators. Use a negative amount for a discount. Prices follow the
  same rule.
- **Power**, only for the costs per kW per month (the power fee of the bill, *quota potenza*): the power of the
  contract in kW, as in the bill (*potenza impegnata*). The value of the customer area is suggested when it is
  known.
- **Excluded from the percentages**, for every type but the percentages: turn it on for a cost that pays no VAT,
  such as the TV licence.

The costs are listed under the integration, where you can edit or delete them.

How they are counted:
- **Per kWh** costs are added to the price of every hour: they are in the cost statistic, in the Energy dashboard,
  in the sensor and in the cards. When prices, costs per kWh or percentages change, the cost of the whole history
  is recomputed.
- **Monthly, two-monthly, yearly and per kW per month** costs do not depend on the hours, so they are **not** in
  the cost statistic nor in the Energy dashboard. The cards count them **in full, as entered**: every month
  carries 1/12 of their euro a year (amount × 12 for monthly, × 6 for two-monthly, × 1 for yearly, × power × 12
  for the costs per kW per month), split among its days, from the month of the first day with data to the month
  of the last one. A month shows its whole amount also while it is not over. The current bill card counts all
  the months of the period, also before it ends (a TV licence of 9 euro a month is 18 euro in a two-month bill),
  and lists every cost.
- **Percentages** (VAT, for example) apply to the price of the energy and to every other cost not excluded from
  them: to the hours in the cost statistic, the Energy dashboard and the sensor, to the periodic costs in the
  cards. The current bill card shows each one on its own line. Several percentages add up and do not apply to each
  other (10 % and 2 % are 12 %).

**Getting close to the bill.** Use the energy price of your offer as the price, then add the other lines of a bill
as costs, without VAT: transport, system charges and excise duty per kWh; fixed fee and TV licence as periodic
costs; the power fee as a cost per kW per month. Then add VAT as a percentage (10 % for homes) and exclude the TV
licence from it.

## What you get

### Statistics
The integration imports long-term statistics with source `plenitude`. In the identifiers, `<p>` is
`plenitude:luce_<key>`, where the key is a short hash of the supply's POD.

| Statistic | Unit | Content |
|---|---|---|
| `<p>_consumo` | kWh | measured consumption, hour by hour |
| `<p>_f1`, `<p>_f2`, `<p>_f3` | kWh | the same consumption split by ARERA band (0 in the hours of the other bands) |
| `<p>_costo` | EUR | kWh × (price of the band + costs per kWh), with the percentages; with a price or a cost (periodic costs excluded) |
| `<p>_cat_<category>` | kWh | the **estimated** split of the customer area, one value per day |

Categories: `comfort_ambientale` (heating and cooling), `standby`, `lavare` (washing), `elettronica_luci`
(electronics and lighting), `refrigerare` (refrigeration), `cucinare` (cooking), `ricarica_elettrica`
(EV charging), `altro` (other).

The names of the statistics follow the language of the server, for example *Plenitude electricity consumption*
or *Plenitude luce consumo*.

### Sensors
| Sensor | Content |
|---|---|
| Last day available | the most recent day with data |
| Consumption of the last day | kWh of that day |
| Consumption cost of the last day | euro of that day: energy and costs per kWh with the percentages, no periodic costs |

They show how far the import has got. They have no `state_class` on purpose: the history is in the statistics,
with the right dates.

### Energy dashboard
1. **Settings → Dashboards → Energy → Electricity grid → Add consumption.**
2. As consumption choose the statistic *Plenitude electricity consumption* (*Plenitude luce consumo* on an Italian
   server).
3. With a price or costs, choose **Use an entity tracking the total costs** and the statistic *Plenitude electricity
   cost* (*Plenitude luce costo*).

Home Assistant cannot compute the cost of imported statistics from a price, so the integration computes it.
Data arrive about two days late: the last two days stay empty until Plenitude publishes them.

### Gas
A gas supply has its own entry, with the statistics `plenitude:gas_<key>_consumo` (m³) and, with a price or costs,
`plenitude:gas_<key>_costo` (EUR), where the key is a short hash of the PDR. A Smc is counted as a m³.

The customer area gives gas **one value per month** (the meter reading); the daily view exists only for the meters
that send daily readings. The integration writes one value per day: the real days where there are, otherwise the
value of the month spread evenly over its days, so that every month has its right total and the daily view has no
spike on the first day. A month read later, or with some real days, is rewritten. The last three months are checked
again at every sync.

**Price.** In **Configure**: no price or a single price in euro per Smc. Costs are added as for electricity; for a
gas supply the costs *per kWh* are per Smc.

**Sensors.** *Last month available* (its first day), *Gas consumption of the last month* (m³) and, with a price or
costs, *Gas cost of the last month*.

**Energy dashboard.** **Settings → Dashboards → Energy → Gas consumption → Add gas source**, statistic *Plenitude gas
consumption* (*Plenitude gas consumo* on an Italian server), and its cost statistic as total costs.

The cards show electricity only.

## Cards
The integration ships two cards and loads them on every dashboard by itself. You do not need to install them or
to add them as resources. In a dashboard select **Edit → Add card**, search for **Plenitude** and configure them
in the visual editor. The cards follow the language of your user profile (Italian or English) and the light or
dark theme.

### Example dashboard
[`examples/dashboard.yaml`](examples/dashboard.yaml) is a dashboard with both cards: the current bill of the
two-month period and the consumption of the week in euro, by band. In **Settings → Dashboards → Add dashboard**
choose **New dashboard from scratch**; open it, select **Edit dashboard** (the pencil), then **⋮ → Raw
configuration editor**, paste it and set `start_date` to the first day of one of your billing periods. The
screenshots show it with synthetic consumption and the prices and costs of a real contract (single price, 6 kW), in
the light and in the dark theme.

| Light | Dark |
|---|---|
| ![Example dashboard, light theme](https://raw.githubusercontent.com/paoloaq/ha-plenitude/main/docs/images/dashboard-light-en.png) | ![Example dashboard, dark theme](https://raw.githubusercontent.com/paoloaq/ha-plenitude/main/docs/images/dashboard-dark-en.png) |

The statistics change once a day, when new days are imported. The cards keep what they read until then: in
memory for all the cards of the page, and in the browser's storage across reloads of the page (a few kB per
period, at most 40 periods). Coming back to a dashboard, or switching view or unit on a card, does not read the
statistics again; new data appear within about 5 minutes of their import.

### Consumption
A column chart. In the settings you choose the default period, view and unit. On the card you can change them,
move back and forth, and go back to the latest data. Hover or tap a column to see its values; **Table** shows
them all.

```yaml
type: custom:plenitude-consumption-card
period: month      # day | week | month | year
view: bands        # total | bands | categories
unit: kwh          # kwh | eur
```

- **Categories** are daily estimates: they are not available in the day view, and only in kWh.
- **In euro**, the periodic costs (monthly, two-monthly, yearly, per kW per month), with their percentages, appear as
  the gray segment at the bottom of the columns.

### Current bill
Consumption and cost from the start of the current billing period to the last day with data. It also shows:
- the split by band;
- the progress through the period;
- the cost breakdown: energy, then every cost you entered, then every percentage;
- an estimate at the end of the period (average of the days with data × length of the period, plus the periodic
  costs of the whole period);
- the columns day by day.

Use the arrows to see past periods and compare them with your bills.

```yaml
type: custom:plenitude-billing-card
start_date: "2026-11-01"   # first day of any billing period (read it on a bill)
months: 2                  # 2 = two-month periods, 1 = monthly periods
```

Billing periods repeat every `months` months from `start_date`. If the start date is the 31st, shorter months
end on their last day.

Both cards also accept `title` and `entry` (the configuration entry, when you have more than one supply).

## How it works
- **Session.** At the first login the integration asks Plenitude for a 30-day session. The customer area session
  expires after less than an hour of inactivity and is reopened with the 30-day session, without the password.
  The password is used again only when the 30-day session is over. If Plenitude refuses it, Home Assistant asks
  you to sign in again in **Settings → Devices & services**.
- **Updates.** Every 6 hours the integration asks for the new days (data arrive about two days late). Once a day
  it also asks again for the days of the last two weeks that had no data, in case they arrived late.
- **Daylight saving time.** On the days the clock changes, the hours are rebuilt from the position of the values,
  because the server labels them wrongly. A day whose number of values does not match its length is skipped.
- **ARERA bands** ([deliberation 181/06](https://www.arera.it/atti-e-provvedimenti/dettaglio/06/181-06),
  table 1):
  - F1: Monday to Friday 8:00–19:00;
  - F2: Monday to Friday 7:00–8:00 and 19:00–23:00, Saturday 7:00–23:00;
  - F3: nights 23:00–7:00, Sundays and holidays.

  Holidays: 1 and 6 January, Easter Monday, 25 April, 1 May, 2 June, 15 August, 1 November, 8, 25 and
  26 December. 4 October (a national holiday again since 2026) is not in the ARERA table and is treated as a
  working day.

## Languages
Italian and English; every other language falls back to English.

| What | Follows |
|---|---|
| Configuration, options, costs, errors in the forms, states (*unknown*), number format | the language of each user's profile |
| Cards | the language of each user's profile |
| Names of the entities | the language of the server |
| Names of the statistics, title of the entry, device model | the language of the server when they are created |

If some texts are in Italian and others in English, the language of the server (**Settings → System → General**)
and the one of your profile (your name at the bottom of the sidebar → **Language**) differ: set both.

## Privacy and security
- **Credentials.** Email and password are kept in the configuration entry, like every integration that signs in
  to a service. They are sent only to the Plenitude sign-in service (`login.eniplenitude.com`).
- **Session.** Tokens and cookies are kept in `.storage/plenitude.<entry id>`, readable only by the owner of the
  file.
- **No other destinations.** The integration talks only to `eniplenitude.com` and `login.eniplenitude.com`, with
  no analytics or telemetry. The cards read the statistics from your Home Assistant only.
- **POD.** The supply's POD is not stored. Statistics and entities use a short hash of it. The hash is not a
  secret (the POD can be found again by trying), so do not publish your statistic identifiers.
- **Diagnostics.** *Download diagnostics* removes credentials, tokens, POD, supply key, address and consumption
  values, so you can attach it to an issue.

To report a vulnerability, see [SECURITY.md](SECURITY.md).

## Troubleshooting
- **Debug log.** In the integration's page select **Enable debug logging**, reproduce the problem, then disable
  it to download the log. Or in `configuration.yaml`:
  ```yaml
  logger:
    logs:
      custom_components.plenitude: debug
  ```
  The integration does not write credentials or tokens to the log; still, read the log before sharing it.

  If the problem happens while adding the integration (so there is no integration page yet), turn on the debug
  log from **Developer tools → Actions** with the action `logger.set_level` and the data
  `custom_components.plenitude: debug`, then try again. Each request is written with its HTTP status; the
  codes of the account are masked.
- **"Plenitude refused the login".** The password changed, or Plenitude asks for an additional verification. Sign
  in to the customer area with a browser, then open the request to sign in again in **Settings → Devices &
  services** and enter the password.
- **"The customer area refuses the data of the account".** Update to 0.3.5 or later: with Home Assistant
  2026.9 earlier versions lost the session cookies (see [docs/protocol.md](docs/protocol.md)). If it still
  happens, check that the customer area works in a browser, turn on the debug log and open an issue. Once
  configured, the integration signs in again by itself, at most every 15 minutes.
- **Some days are missing.** The customer area itself sometimes has no data for some days. The integration asks
  again for the missing days of the last two weeks, once a day.
- **The sensors stay *unknown* after the first configuration.** The first import is still running: the last two
  weeks appear within seconds, the rest in a few minutes (log: *Plenitude: first import, …*).
- **The cards do not appear** in *Add card*, or a dashboard shows *Custom element doesn't exist:
  plenitude-…-card*. The integration adds the cards when Home Assistant starts, and the frontend reads them only
  when the page loads: a page loaded while Home Assistant was starting does not have them. Reload the page once
  Home Assistant has started (without the cache, or clear the cache of the companion app). If they are still
  missing, open `/plenitude_static/plenitude-cards.js` on your Home Assistant: it must show the code of the cards
  with the version at the top. Do not add the cards as dashboard resources: the integration loads them.
  Versions before 0.5.2 could also miss the cards at random with Home Assistant 2026.10 and older, also hours
  after a restart (the frontend replaced its registry of elements after the cards were defined): update the
  integration. In the browser's console, `customElements.get("plenitude-billing-card")` must not be `undefined`.
- **The cost differs from the bill.** See [Prices and costs](#prices-and-costs): enter every line of the bill as a
  cost, without VAT, and VAT as a percentage. Bills may also contain adjustments and estimated readings.

## Removal
1. **Settings → Devices & services → Eni Plenitude → ⋮ → Delete.**
2. The imported statistics stay in the database. To delete them, go to **Developer tools → Statistics**, search
   for `plenitude` and delete them.
3. In the Marketplace (or in HACS up to Home Assistant 2026.10) open **Eni Plenitude** and select **Uninstall**,
   then restart Home Assistant.

## Limitations
- Home Assistant statistics are hourly: the 15-minute values are summed by hour.
- Categories are estimates of Plenitude and come only day by day.
- The monthly values by band of the customer area are not used: they do not match calendar months (they look
  like reading or billing periods).
- The cost is an estimate from the prices, costs and percentages you enter: bills also contain adjustments and
  estimated readings that the integration cannot know.
- Gas comes month by month: the days of a month without daily readings are an even split of its value, not a
  measure.
- The cards show electricity only; gas is in the Energy dashboard and in its sensors.

## Development
See [CONTRIBUTING.md](CONTRIBUTING.md): structure of the code, tests on the minimum and latest Home Assistant, the
cards' test page, and how to release. Notes on the customer area's web services are in
[docs/protocol.md](docs/protocol.md). Changes are listed in [CHANGELOG.md](CHANGELOG.md).

## License
[MIT](LICENSE). *Eni Plenitude* and *Plenitude* are trademarks of their owners and are used here only to say
which service the integration works with.

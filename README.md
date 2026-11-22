# Eni Plenitude for Home Assistant

[![HACS custom repository](https://img.shields.io/badge/HACS-custom%20repository-41BDF5)](https://hacs.xyz/docs/faq/custom_repositories/)
[![Home Assistant 2026.9+](https://img.shields.io/badge/Home%20Assistant-2026.9%2B-18BCF2)](https://www.home-assistant.io/)
[![Tests](https://github.com/paoloaq/ha-plenitude/actions/workflows/tests.yml/badge.svg)](https://github.com/paoloaq/ha-plenitude/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**English** · [Italiano](README.it.md)

A Home Assistant integration that brings the electricity consumption of your
[Eni Plenitude](https://eniplenitude.com) customer area into Home Assistant:

- hourly consumption as **long-term statistics**, with its real date, ready for the Energy dashboard;
- the same consumption split by **ARERA time band** (F1, F2, F3);
- the **estimated categories** of the customer area (heating and cooling, washing, cooking…), day by day;
- the **cost**, from the prices you enter (single price, two or three bands) plus **as many other costs as you
  want** (monthly, two-monthly, yearly or per kWh: TV licence, fixed fee, system charges…);
- two **dashboard cards**: a consumption chart with a period of your choice, and the **current bill** (kWh and
  euro of the billing period so far, with an estimate at the end of the period).

It is an integration, not an add-on: it works with every installation type (Home Assistant OS, Container, Core).

> [!IMPORTANT]
> **Unofficial.** This project is not affiliated with, endorsed or supported by Eni Plenitude or Eni. It uses
> the same web services as the customer area, which are not documented and can change without notice. It makes
> a few requests a day, like a person checking the customer area.

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
  15 minutes, usually available with second-generation smart meters). Gas is not supported yet.

## Installation

### With HACS (recommended)
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
3. If the account has more than one electricity supply, choose the one to import. To import another one, add
   the integration again.

The first import starts right away, in the background: it reads the history one day at a time, going back from
yesterday until it finds a month without data (at most three years). It takes a few minutes.

### Prices and costs
Plenitude does not expose the price of your offer, so the cost is computed from prices and costs you enter.

**Price of the energy.** Open **Settings → Devices & services → Eni Plenitude → Configure**:

| Price type | Fields |
|---|---|
| No price | consumption only |
| Single price | one price per kWh for every hour |
| Two bands | F1 and F23 (F2 + F3) |
| Three bands | F1, F2 and F3 |

**Other costs.** In the same page select **Add cost**, as many times as you need. Each cost has:
- **Name**: free text, for example TV licence, fixed fee, power, system charges;
- **Type**: monthly, every two months, yearly or per kWh;
- **Amount**: in euro (euro per kWh for the costs per kWh), at most 6 decimals. Use a negative amount for a
  discount.

The costs are listed under the integration, where you can edit or delete them.

How they are counted:
- **Per kWh** costs are added to the price of every hour: they are in the cost statistic, in the Energy dashboard,
  in the sensor and in the cards. When prices or costs per kWh change, the cost of the whole history is
  recomputed.
- **Monthly, two-monthly and yearly** costs do not depend on the hours, so they are **not** in the cost statistic
  nor in the Energy dashboard. The cards spread them over the days: `amount × times a year / days of the year`
  (12 times for monthly, 6 for two-monthly, once for yearly), from the first to the last day with data. The
  current bill card lists every cost.

**Getting close to the bill.** Use the energy price of your offer as the price, then add the other lines of a bill
as costs: transport, system charges and excise duty per kWh; fixed fee, power and TV licence as periodic costs.
Include VAT in every amount.

## What you get

### Statistics
The integration imports long-term statistics with source `plenitude`. In the identifiers, `<p>` is
`plenitude:luce_<key>`, where the key is a short hash of the supply's POD.

| Statistic | Unit | Content |
|---|---|---|
| `<p>_consumo` | kWh | measured consumption, hour by hour |
| `<p>_f1`, `<p>_f2`, `<p>_f3` | kWh | the same consumption split by ARERA band (0 in the hours of the other bands) |
| `<p>_costo` | EUR | kWh × (price of the band + costs per kWh), with a price or a cost (periodic costs excluded) |
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
| Consumption cost of the last day | euro of that day: energy and costs per kWh, no periodic costs |

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

## Cards
The integration ships two cards and loads them on every dashboard by itself. You do not need to install them or
to add them as resources. In a dashboard select **Edit → Add card**, search for **Plenitude** and configure them
in the visual editor. The cards follow the language of your user profile (Italian or English) and the light or
dark theme.

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
- **In euro**, the monthly, two-monthly and yearly costs appear as the gray segment at the bottom of the columns.

### Current bill
Consumption and cost from the start of the current billing period to the last day with data. It also shows:
- the split by band;
- the progress through the period;
- the cost breakdown: energy, then every cost you entered;
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
| Configuration, options, entity names, errors | the language of each user |
| Cards | the language of each user's profile |
| Names of the statistics, title of the entry, device model | the language of the server when they are created |

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
- **Some days are missing.** The customer area itself sometimes has no data for some days. The integration asks
  again for the missing days of the last two weeks, once a day.
- **The cards do not appear** in *Add card*. Make sure the integration is loaded, then reload the page without
  the cache (or clear the cache of the companion app). Do not add the cards as dashboard resources: the
  integration loads them.
- **The cost differs from the bill.** See [Prices and costs](#prices-and-costs): enter every line of the bill as a
  cost, VAT included. Bills may also contain adjustments and estimated readings.

## Removal
1. **Settings → Devices & services → Eni Plenitude → ⋮ → Delete.**
2. The imported statistics stay in the database. To delete them, go to **Developer tools → Statistics**, search
   for `plenitude` and delete them.
3. With HACS, remove the integration from HACS too, then restart Home Assistant.

## Limitations
- Home Assistant statistics are hourly: the 15-minute values are summed by hour.
- Categories are estimates of Plenitude and come only day by day.
- The monthly values by band of the customer area are not used: they do not match calendar months (they look
  like reading or billing periods).
- The cost is an estimate from your prices: bills also contain taxes, adjustments and estimated readings that the
  integration cannot know.
- Electricity only; gas is not supported yet.

## Development
See [CONTRIBUTING.md](CONTRIBUTING.md): structure of the code, tests on the minimum and latest Home Assistant, the
cards' test page, and how to release. Notes on the customer area's web services are in
[docs/protocol.md](docs/protocol.md). Changes are listed in [CHANGELOG.md](CHANGELOG.md).

## License
[MIT](LICENSE). *Eni Plenitude* and *Plenitude* are trademarks of their owners and are used here only to say
which service the integration works with.

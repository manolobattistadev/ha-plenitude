# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [0.3.2] - 2026-11-22

### Fixed
- New sign-ins: the customer area accepted the login but refused the data of the account (HTTP 401 from the
  account services, *portal refused* in the configuration). The client presented itself as Chrome 131; it now
  presents itself as a current Firefox, with the `Sec-Fetch-*` headers the browser sends and `Origin` only on
  POST requests. The Firefox version advances by itself over time.

## [0.3.1] - 2026-11-22

### Fixed
- Configuration: when Plenitude accepts the login but the customer area refuses the data of the account, the
  form now says so (*portal refused*) instead of *cannot connect*, and the reason is written to the log (with
  query strings and long numbers removed).

### Changed
- `manifest.json`: category `energy.meters_monitoring`.

## [0.3.0] - 2026-11-22

### Added
- **Costs**: as many as you want, each with a free name, a type (monthly, two-monthly, yearly, per kWh) and an
  amount in euro with at most 6 decimals (negative for discounts). They are configuration subentries, listed under
  the integration with buttons to add, edit and delete them.
  - Costs per kWh are added to the price of every hour: cost statistic, Energy dashboard, sensor and cards. The cost
    history is recomputed when they change.
  - Periodic costs are spread over the days by the cards: gray segment in the charts in euro, and in the totals.
- Current bill card: cost breakdown (energy, then every cost) and periodic costs in the estimate at the end of the
  period.
- Italian and English for the names of the statistics, the title of the entry and the device model (language of
  the server); translated error messages; descriptions of the fields; English names of the categories in the
  cards.
- Diagnostics, without credentials, tokens, POD, supply key, address or consumption values.
- Integration icon (`brand/`, Home Assistant 2026.3 and later).
- Repository files: README in English and Italian, changelog, contributing guide, security policy, license,
  issue templates, GitHub workflows (hassfest, HACS validation, tests on the minimum and latest Home Assistant,
  release).

### Changed
- The cost statistic exists when a price of the energy or at least one cost is configured.
- The cost sensor is now *Consumption cost of the last day* (energy and costs per kWh).
- Title of new entries in the language of the server (*Plenitude luce* or *Plenitude electricity*).
- `manifest.json`: keys in the order required by hassfest, code owner. `hacs.json`: country `IT`.

## [0.2.0] - 2026-11-22

### Added
- Consumption card (`custom:plenitude-consumption-card`): day, week, month or year; total, bands or categories;
  kWh or euro; navigation, tooltips and table.
- Current bill card (`custom:plenitude-billing-card`): billing period from a chosen day (two months or one),
  kWh and cost so far, bands, progress, estimate at the end of the period.
- Websocket command `plenitude/info` for the cards (which statistics and prices exist, no values).
- Compatibility with Home Assistant 2026.9.

## [0.1.0] - 2026-11-22

### Added
- Configuration flow with email and password, choice of the supply, re-authentication.
- Session kept alive without the password for 30 days.
- Long-term statistics: hourly consumption, ARERA bands F1/F2/F3, estimated categories (daily) and cost from a
  single price or prices by band.
- Sensors of the last day with data.

[0.3.1]: https://github.com/paoloaq/ha-plenitude/releases/tag/v0.3.1
[0.3.0]: https://github.com/paoloaq/ha-plenitude/releases/tag/v0.3.0
[0.2.0]: https://github.com/paoloaq/ha-plenitude/releases/tag/v0.2.0
[0.1.0]: https://github.com/paoloaq/ha-plenitude/releases/tag/v0.1.0

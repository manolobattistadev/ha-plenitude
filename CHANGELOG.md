# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [0.4.1] - 2026-11-23

### Changed
- Periodic costs count in full, as entered. Every month carries 1/12 of their euro per year, split among its days,
  also while it is not over; the current bill card counts all the months of the period before it ends (a TV
  licence of 9 euro a month is 18 euro in a two-month bill, not the share of the days so far). Before, they were
  spread over the days up to the last day with data.

### Fixed
- Prices, amounts and power accept a comma or a point for the decimals (`9,15` or `9.15`). They were number fields
  of the browser, which refused or lost the decimal comma depending on the browser; numbers with thousands
  separators (`1.234,56`) are now refused with a clear message instead of being guessed.
- README: what to do when a dashboard shows *Custom element doesn't exist* (page loaded while Home Assistant was
  starting).

## [0.4.0] - 2026-11-23

### Added
- Costs **per kW per month** (the power fee of the bill): amount in euro per kW and, in a second step, the power of
  the contract in kW, suggested from the customer area (`contractPower`). The cards spread them over the days
  like the monthly costs; the current bill card shows the power next to the cost.
- `plenitude/info` returns the data version (it changes when statistics are written) and the euro per year of
  every periodic cost.

### Changed
- Cards: what they read is kept until the integration writes new data, in memory for all the cards of the page
  and in the browser's localStorage across reloads (at most 40 periods). Before, every card read its statistics
  again every 15 minutes, and from scratch whenever Home Assistant re-created the cards: on every reconnection,
  for example when coming back to a tab hidden for more than 5 minutes. Measured in the cards harness, 6 cards
  re-created: 0.3.6 showed *Loading* on 6 and made 6 new requests to the recorder, 0.4.0 none.
- Cards: one request per period for every statistic of the supply, shared by the cards with the same period
  (6 requests instead of 17 in the harness); switching view or unit does not read again. While loading the
  first time a card keeps about its final height.
- Start without the network: the supply found once is stored, so starting Home Assistant and reloading the entry
  (after every change of prices or costs) no longer wait for the customer area. The first sync of each day checks
  the supply again.
- Regular syncs ask only the missing days; before, every day from the first missing one to yesterday.
- First import: three days at a time with a pause after each round (measured on the real customer area, same
  session, rounds interleaved: 15 days in 5-6 s instead of 15 s, same answers, no errors); the last two weeks are
  written at once, so sensors and cards show data in seconds, and the whole history follows. An interrupted first
  import starts again.

### Fixed
- Card picker: names and descriptions in the language of the user's profile. They were computed when the file
  loaded, before the frontend set the language, and could appear in English.
- README: the names of the entities follow the language of the server, not the one of each user.

## [0.3.6] - 2026-11-23

### Fixed
- First import: a day or a month that the customer area refuses with HTTP 400 no longer stops the whole import
  (seen on one account: nothing was imported and the sensors stayed unavailable). A refused day counts as a day
  without data, a refused month only loses its categories; if every day is refused it is still an error.

### Added
- One warning per sync lists the days and months refused with HTTP 400; the error of a sync where every day is
  refused names the first one.

## [0.3.5] - 2026-11-23

### Fixed
- The real cause of *portal refused* (HTTP 401 from the account services) with Home Assistant 2026.9: the portal
  writes `Expires` without the comma after the day, and aiohttp before 3.14.5 then loses the `Path=/` of the
  session cookies, which are no longer sent to the services of the account. The client brings the cookies of
  the portal back to `/`. Checked in the official image of Home Assistant 2026.9.4.
- The explanations of 0.3.2 (User-Agent) and 0.3.4 (too many open logins) were wrong; the sign-out, the pause
  between logins and the sign-out on removal of 0.3.4 stay, as good practice. Texts of the error updated.

## [0.3.4] - 2026-11-22

### Fixed
- The real cause of *portal refused* (HTTP 401 from the account services after a new login): the customer area
  refuses the data to new logins when too many are open on the account, and the integration never closed its
  logins. Version 0.3.2 attributed it to the User-Agent: it was a coincidence, the logins of the tests had just
  expired.
- The configuration closes its login (Gigya and portal, as the web app does on sign-out) also when the portal
  refuses the data.
- When the portal refuses the data also after renewing the session, the integration closes its login and signs
  in again on the next attempt, at most every 15 minutes, instead of keeping a refused login for 30 days.
- Removing the integration closes its login and deletes the stored session.

## [0.3.3] - 2026-11-22

### Added
- Debug log of every request to the customer area: method, host, path with the codes masked, HTTP status, type
  of the answer and, for errors only, the start of the answer. No query strings, no bodies of successful answers,
  nothing from Gigya but the status.
- The messages of the configuration in the log name the version of the integration.

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

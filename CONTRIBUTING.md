# Contributing

Thank you for helping. Bug reports, fixes and translations are welcome; for larger changes please open an issue
first, so we can agree on the approach.

## Ground rules
- **Never commit personal data**: no credentials, session files, HAR captures, POD, customer or contract codes,
  addresses or real consumption. Tests use synthetic data only (the fake POD is `IT001E99999999`). The
  `.gitignore` already excludes `*.har` and the prototype's session files.
- Error messages must not contain customer codes: the client masks long numbers in the paths
  (`api.safe_path`).
- Texts the user sees exist in **Italian and English**: `strings.json` (English source, copied to
  `translations/en.json`), `translations/it.json`, `texts.py` (names of statistics, title, device model) and the
  `STRINGS` of the cards. `tests/test_repository.py` checks that keys and placeholders match.

## Structure
```
custom_components/plenitude/
  api.py          client of the customer area (aiohttp only, no Home Assistant)
  bands.py        ARERA bands and prices (no Home Assistant)
  costs.py        additional costs and hourly price (no Home Assistant)
  texts.py        texts stored with the statistics, Italian and English (no Home Assistant)
  coordinator.py  session, choice of the days to download, import of the statistics
  config_flow.py  configuration, re-authentication, price options, cost subentries
  sensor.py       sensors of the last day
  websocket.py    plenitude/info command for the cards (which statistics, prices and costs; no values)
  diagnostics.py  diagnostics without personal data
  frontend/plenitude-cards.js   the two cards (plain JavaScript, no dependencies, hand-drawn SVG)
  brand/          integration icon
docs/protocol.md       notes on the customer area's web services
scripts/prototipo.py   command-line prototype (macOS, Italian)
tests/                 automatic tests; tests/live: manual check against the real service
```

## Development environment
Python 3.14 (the version Home Assistant 2026.9 and later run on).

```sh
python3.14 -m venv ~/venvs/ha-plenitude-test
~/venvs/ha-plenitude-test/bin/pip install -r requirements-test.txt ruff
```

`pytest-homeassistant-custom-component` pins the Home Assistant version the tests run against. The CI runs them
on the minimum supported version and on the latest one:

| Home Assistant | Test kit |
|---|---|
| 2026.9.4 (minimum) | `pytest-homeassistant-custom-component==0.13.367` |
| latest | `pytest-homeassistant-custom-component` |

## Checks
```sh
~/venvs/ha-plenitude-test/bin/ruff check . && ~/venvs/ha-plenitude-test/bin/ruff format --check .
~/venvs/ha-plenitude-test/bin/python -m pytest -q -p no:logging
TZ=Europe/Rome node --test tests/frontend/
```

The Python tests use the real recorder of Home Assistant and a fake portal (`tests/conftest.py`); the network is
blocked. The Node tests check the date logic of the cards (billing periods, daylight saving time, periodic costs).

### Cards
`tests/frontend/harness.html` shows every card in light and dark theme and in English, with a fake `hass` and
synthetic data. Open it in a browser, or take a screenshot:

```sh
google-chrome --headless=new --screenshot=/tmp/cards.png --window-size=1180,3500 \
  --virtual-time-budget=4000 "file://$PWD/tests/frontend/harness.html"
```

### Live check (maintainers)
`tests/live` runs the integration against the real customer area in a test Home Assistant with the real recorder.
It prints only counts and differences, never values or codes. It is skipped unless `PLENITUDE_LIVE=1`, and reads
the credentials from the macOS Keychain (service `ha-plenitude`):

```sh
security add-generic-password -s ha-plenitude -a 'EMAIL' -w   # asks for the password without echoing it
PLENITUDE_LIVE=1 ~/venvs/ha-plenitude-test/bin/python -m pytest -s -p no:logging --tb=line tests/live
```

`scripts/prototipo.py` is the command-line prototype used to reconstruct the protocol (`login`, `stato`,
`consumi`). It keeps its session in `~/.cache/ha-plenitude/sessione.json` with permissions `600`; without
`--valori` it prints no identifiers and no consumption.

## Releasing
1. Update the version in `manifest.json`, `const.py` (`VERSION`) and `frontend/plenitude-cards.js`
   (`CARD_VERSION`), and add the section to `CHANGELOG.md`. `tests/test_repository.py` fails if they differ.
2. Commit, then tag and push: `git tag v0.3.0 && git push origin main v0.3.0`.
3. The *Release* workflow checks the version and publishes the GitHub release with the notes from the changelog.
   HACS offers the new release to the users.

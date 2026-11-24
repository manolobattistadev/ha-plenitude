# Notes on the customer area's web services

These services are not documented. Everything below was reconstructed on 2026-11-22 from the traffic of the
web app (`https://eniplenitude.com/my-eni`) and measured with `scripts/prototipo.py`; it can change at any
time. The code that implements it is `custom_components/plenitude/api.py`, which does not depend on Home
Assistant.

## Sign-in
1. **Gigya** (SAP Customer Data Cloud), host `login.eniplenitude.com`: `accounts.login` with email, password and
   `sessionExpiration` returns a `login_token`, the Gigya session. The API key in the code is the site's public
   key, visible in the page source.
2. `accounts.getJWT` with the `login_token` returns a short-lived `id_token` (JWT).
3. `serviceDAp/api/c360/getJwe` on `eniplenitude.com`, with the JWT in the `JWT` header, sets the portal cookies
   `GYSESSION` and `G-GENUI`.

Steps 2 and 3 can be repeated without the password while the Gigya session is alive.

Gigya error codes `401xxx` and `403xxx` (wrong credentials, CAPTCHA required, locked account) need the user;
`5xxxxx` are temporary. In Home Assistant the first start a re-authentication, the second a retry.

### Session cookies and the `Expires` format
`getJwe` sets the portal cookies with `Path=/`, but writes `Expires` without the comma after the day:

```
Set-Cookie: GYSESSION=…; Max-Age=86400; Expires=Mon   23 Nov 2026 20:20:54 GMT; Path=/; Secure; HttpOnly
```

The cookie parser of aiohttp before 3.14.5 (Home Assistant 2026.9 ships 3.14.3) does not recognise that date and
loses the attributes after it: `GYSESSION` and `G-GENUI` get the default path `/serviceDAp/api/c360`, so they are
sent to `c360/init` but not to `contiServices` or `profilo-energetico-services`, which answer `HTTP 401`
(`{"timestamp":…,"status":401,"error":"Unauthorized","path":…}`). aiohttp 3.14.5 parses the date. The client
brings the portal cookies back to `/` after each answer (`api._fix_cookie_paths`).

Found on 2026-11-22 by comparing, request by request, the cookies sent by the two versions; checked in the official
image of Home Assistant 2026.9.4 (version 0.3.4: 401; with the fix: 200, a few seconds apart). Two earlier
explanations of the same 401 (the User-Agent in 0.3.2, the number of open logins in 0.3.4) were wrong: they
coincided with switching between test environments with aiohttp 3.14.3 and 3.14.5.

### Sign-out
As the web app does it:
1. Gigya `accounts.logout` with the `login_token`;
2. `POST serviceDAp/api/action/logout?logHash={hash}` with body `{"logHash": "{hash}", "codiceCliente": "{cliente}"}`
   and the headers `Cache-Control: Clear-Site-Data` and `Isbeta: true`;
3. the web app then deletes the cookies `JBFFSESSIONID`, `PORTAL_VERSION`, `X-CSRF-TOKEN`, `JSESSIONID`.

The integration closes the login of the configuration at once, keeps one login (30 days) per entry, closes it
when the portal refuses it or when the entry is removed, and does not sign in with the password more than once
every 15 minutes.

The client presents itself as a current Firefox (`api.user_agent`, `Sec-Fetch-*`, `Origin` only on POST).

## Sessions (measured on 2026-11-22)
| Element | Lifetime | Renewal |
|---|---|---|
| `id_token` (JWT) | 60 s from `accounts.login`, 300 s from `accounts.getJWT` | asked when needed |
| Gigya session (`login_token`) | what `sessionExpiration` asks for: 3000 s in the web app, **30 days granted** when asked | with the password; whether 30 days really hold is still being measured |
| Portal session (`GYSESSION`, `G-GENUI`) | cookies valid 24 h (`Max-Age=86400`), but the server closes the session earlier: after **less than 55 minutes of inactivity** it answers `HTTP 406` | **without the password**, with `getJWT` + `getJwe`, while the Gigya session is valid |

## Data
All under `https://eniplenitude.com/serviceDAp`, with the portal cookies.

| Call | Content |
|---|---|
| `GET /api/c360/init` | customer and account codes |
| `GET /api/contiServices/conti/{account}/lista-forniture` | supplies (POD, address, contract) |
| `POST /api/profilo-energetico-services/{account}/users/{customer}/supplies` | supplies with the consumption analysis (house and contract ids, `contractPower` in kW). Body `{"pod": …, "pdr": …}`: as the web app, the POD of the electricity supply and the PDR of the first gas supply (`""` if none), asked only when a supply of the list has `flagMidori: true` |
| `POST /api/profilo-energetico-services/{account}/analysis/consumptions` | consumption: `type` 0 = one day (24 hourly values in `data`, 96 quarter-hours in `additionalData`), 2 = one month (one value per day, per category) |
| `GET /api/consumptionData` | monthly values by band (not used: they do not match calendar months) |

- **Day view.** `startTime` and `endTime` are the local midnights of the day in UTC. On the days the clock changes
  the server labels the hours wrongly; the client rebuilds them from the position of the values and skips a day
  whose number of values does not match its length (23, 24 or 25 hours).
- **Month view.** `startTime` is the local midnight of day **2** of the month in UTC and `endTime` the last day
  at 23:00Z; the days are named `dd/mm`. `activityId` 0 is the measured total; 1 to 8 are the estimated
  categories: 1 refrigerare, 2 standby, 3 lavare, 4 cucinare, 5 comfort_ambientale, 6 elettronica_luci, 7 altro,
  8 ricarica_elettrica.
- Data arrive about two days late; some days are missing in the customer area itself.
- **Requests at the same time.** Measured on 2026-11-23, same session, rounds interleaved (one at a time, three at
  a time, one, three): 15 day views in 15 s one at a time with a 0.4 s pause, in 5-6 s three at a time with a
  0.4 s pause after each round; average latency 0.6-0.7 s in both, same answers, no errors. The integration asks
  three at a time; a session over in a round is renewed once and the round repeated.
- Error responses are reported with the path only, with long numbers masked: paths contain customer codes.

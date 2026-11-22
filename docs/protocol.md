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

### Open logins and sign-out
The account services (`contiServices`, `profilo-energetico-services`) answer `HTTP 401` with a generic
`{"timestamp":…,"status":401,"error":"Unauthorized","path":…}` to the logins opened while too many are open on
the account; `c360/init` keeps answering, and so do the logins opened before. Renewing the portal session
(`getJWT` + `getJwe`) does not help: the refusal belongs to the Gigya login. Measured on 2026-11-22: after a day
of tests without sign-out new logins were refused; they worked again about 50 minutes later (the Gigya sessions
of the tests lasted 3000 s), and at once after closing an open login.

Sign-out, as the web app does it:
1. Gigya `accounts.logout` with the `login_token`;
2. `POST serviceDAp/api/action/logout?logHash={hash}` with body `{"logHash": "{hash}", "codiceCliente": "{cliente}"}`
   and the headers `Cache-Control: Clear-Site-Data` and `Isbeta: true`;
3. the web app then deletes the cookies `JBFFSESSIONID`, `PORTAL_VERSION`, `X-CSRF-TOKEN`, `JSESSIONID`.

The integration closes the login of the configuration at once, keeps one login (30 days) per entry, closes it
when it is refused or when the entry is removed, and does not sign in with the password more than once every 15
minutes.

The client presents itself as a current Firefox (`api.user_agent`, `Sec-Fetch-*`, `Origin` only on POST). On
2026-11-22 this looked like the fix, but it was a coincidence with the expiry of the logins of the tests.

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
| `GET /api/profilo-energetico-services/{account}/users/{customer}/supplies` | supplies with the consumption analysis (house and contract ids) |
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
- Error responses are reported with the path only, with long numbers masked: paths contain customer codes.

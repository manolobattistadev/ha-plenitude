# Security policy

## Supported versions
Only the latest release receives fixes.

## Reporting a vulnerability
Please **do not open a public issue**. Use GitHub's private reporting instead: **Security → Report a
vulnerability** in this repository. You will get an answer within a few days.

Never send credentials, session files (`.storage/plenitude.*`), POD, customer or contract codes, not even in a
private report: describe the problem and how to reproduce it with your own account.

## What the integration handles
- The email and password of the customer area, kept in the Home Assistant configuration entry and sent only to
  `login.eniplenitude.com`.
- Session tokens and cookies, kept in `.storage/plenitude.<entry id>` with owner-only permissions.
- Consumption data, stored as long-term statistics in the Home Assistant database.

The integration contacts only `eniplenitude.com` and `login.eniplenitude.com`.

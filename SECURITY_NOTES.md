# Security notes — deploy hardening

Living record of security decisions made during AWS deployment prep. Items marked
**ACCEPTED** are deliberate trade-offs for the soft launch, not oversights.

## CORS / env config (item 4)

`main.py` computes `ALLOWED_ORIGINS` (comma-separated). Because `allow_credentials=True`,
an unset value that falls back to the localhost default would make the real frontend's
requests fail CORS silently. Two guards now exist:

- **Fail-loud in prod:** when `APP_ENV=production` (or `prod`), the app *refuses to
  start* unless `ALLOWED_ORIGINS` is set to real, non-localhost origin(s).
- **Startup log:** the active origin list is logged at boot (`CORS allowed origins: [...]`),
  and a WARNING is logged whenever it's defaulting.

### Verify in AWS (can't be checked from the repo — do this in the console)

1. Confirm these are injected into the task/instance env (ECS task def, App Runner
   config, or SSM/Secrets Manager — wherever this runs):
   - `ALLOWED_ORIGINS` = the deployed frontend origin, e.g. `https://hikebuilder.app`
     (no trailing slash; include `https://www.` too if used).
   - `APP_ENV=production` — this is what arms the fail-loud guard above.
   - `JWT_SECRET_KEY` — already fail-loud (`os.environ[...]` raises at import if unset).
   - `HikeKey`, `REDIS_URL`, DB vars (`HOST`/`PORT`/`DBNAME`/`DB_USER`/`PASSWORD`),
     `GOOGLE_CLIENT_ID`.
   - `ENABLE_HSTS=true` once served over HTTPS end-to-end.
   - `TRUSTED_PROXY_HOPS` — leave `1` for a single ALB; set `2` if CloudFront fronts it.
2. After deploy, grep the boot logs for `CORS allowed origins:` and confirm the list is
   the real frontend, not localhost.
3. Smoke-test a browser request from the deployed frontend and confirm no CORS error.

## Security response headers (item 5)

`main.py` sets on every API response: `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and (behind `ENABLE_HSTS`)
`Strict-Transport-Security`. These are safe for a JSON API and can't break it.

## Content-Security-Policy — belongs on the static host, NOT the API

**ACCEPTED / TODO before public launch.** JWTs are stored in `localStorage` (`api/client.js`),
so any XSS can exfiltrate a token. A CSP is the main mitigation, but it only protects the
document that carries it — and the **API never serves the SPA's HTML**. The SPA is
static-hosted (CloudFront/S3), so the CSP must be set there: either a CloudFront
response-headers-policy or a `<meta http-equiv>` in `hiking-frontend/index.html`.

The policy must allow-list everything the SPA actually loads, or it will break the map and
Google Sign-In. Based on current usage (Mapbox GL, Google Identity Services, Google Fonts,
Nominatim geocoding, the API):

```
default-src 'self';
script-src 'self' https://accounts.google.com https://apis.google.com;
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
font-src 'self' https://fonts.gstatic.com data:;
img-src 'self' data: blob: https://*.mapbox.com https://*.googleusercontent.com https://*.google.com;
connect-src 'self' https://api.mapbox.com https://events.mapbox.com https://*.tiles.mapbox.com https://nominatim.openstreetmap.org https://accounts.google.com <API_ORIGIN>;
worker-src 'self' blob:;
child-src blob:;
frame-src https://accounts.google.com;
base-uri 'self';
object-src 'none';
frame-ancestors 'none';
```

- Replace `<API_ORIGIN>` with the deployed API origin (the `VITE_API_BASE_URL` value).
- `'unsafe-inline'` in `style-src` is required — Tailwind and Mapbox GL both inject inline
  styles. `worker-src blob:` is required for Mapbox GL's web workers.
- **Must be tested after enabling:** load the map, plan a trip, and sign in with Google;
  watch the console for CSP violations and widen the policy only as needed. Do not ship it
  blind — a wrong directive white-screens the map.
- Longer term, moving the JWT to an httpOnly cookie would remove the localStorage exfil
  vector entirely (larger change: needs CSRF protection + backend cookie auth).

## Rate limiter fails open on Redis errors (item 5)

**ACCEPTED.** `rate_limit.py` `_hit()` returns *allowed* on any Redis exception, so a cache
blip never hard-blocks legitimate traffic. Consequence: a full Redis outage removes the
per-IP brute-force cap on auth and the per-account AI quota. This is an intentional
availability-over-strictness choice for the soft launch. If abuse becomes a concern,
switch the auth path specifically to fail *closed*, and/or add a CloudWatch alarm on Redis
connection errors so an outage is noticed rather than silently un-protected.

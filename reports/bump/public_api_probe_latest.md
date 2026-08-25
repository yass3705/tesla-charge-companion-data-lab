# Bump production API — public GET probe

One official Bump station/EVSE sample was used. Requests were unauthenticated GET only; no response body is retained.

- Requests: **15**
- HTTP 200: **1**
- HTTP 401/403: **0**

## Results

- `GET /` → **200**
- `GET /openapi.json` → **404** — JSON keys: status, title, traceId, type
- `GET /swagger.json` → **404** — JSON keys: status, title, traceId, type
- `GET /docs` → **404** — JSON keys: status, title, traceId, type
- `GET /health` → **404** — JSON keys: status, title, traceId, type
- `GET /evse/FRBMPE1699` → **404** — JSON keys: status, title, traceId, type
- `GET /evses/FRBMPE1699` → **404** — JSON keys: status, title, traceId, type
- `GET /location/FRBMPS4745` → **404** — JSON keys: status, title, traceId, type
- `GET /locations/FRBMPS4745` → **404** — JSON keys: status, title, traceId, type
- `GET /charge-location/FRBMPS4745` → **404** — JSON keys: status, title, traceId, type
- `GET /charge-locations/FRBMPS4745` → **404** — JSON keys: status, title, traceId, type
- `GET /evse/FRBMPE1699/tariff` → **404** — JSON keys: status, title, traceId, type
- `GET /evses/FRBMPE1699/tariff` → **404** — JSON keys: status, title, traceId, type
- `GET /tariff/FRBMPE1699` → **404** — JSON keys: status, title, traceId, type
- `GET /tariffs/FRBMPE1699` → **404** — JSON keys: status, title, traceId, type

## Decision

A station/tariff route is usable for TCC only if it returns an explicit driver-facing tariff through an unauthenticated/read-only lookup and can be matched to Bump's official station/PDC inventory. Authentication barriers are not bypassed.

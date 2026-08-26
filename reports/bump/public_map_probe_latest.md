# Bump public map endpoint probe

Unauthenticated, read-only map/search POST requests only, using one station from Bump's official IRVE inventory.

- Sample: **Bump - Amarante - Montigny** / `FRBMPS11980` / `FRBMPE1151`
- Attempts: **22**
- HTTP 200: **0**
- Useful responses (official ID or tariff marker): **0**

## Decision rule

TCC may use this route only if the public response can be deterministically matched to an official Bump-operated station/EVSE and exposes the internal identifiers needed to query an explicit driver-facing tariff. No authentication boundary is bypassed.

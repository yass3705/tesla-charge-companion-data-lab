# ACEA Italy CPO readiness

## Decision

The exact PUN `ACE` scope is preserved as physical infrastructure, but no ACEA direct tariff is published.

- Physical CPO: **Acea Innovation**.
- Former direct eMSP: **Acea Energia / Acea e-mobility**.
- The publisher-authored app notice states that the charging service ended on **2025-12-19**.
- Physical ACEA stations remain usable through other eMSPs.
- Historical app prices and PUN tariff blocks are not current direct-tariff evidence and remain fail-closed.

## Audited snapshot

- 652 stations / 1,649 EVSE under party ID `ACE`.
- PUN labels: 1,471 `ACEA ENERGIA`, 170 `ACE`, 8 `ACEA INNOVATION`.
- 832 EVSE carry legacy PUN tariff blocks; 0 are promoted as rankable direct tariffs.
- 0 ACEA direct, selected-subscription, or former Acea eMSP offers are rankable.

## Queue

- **Atlante:** paused by user until the Mac is repaired and a native MyAtlante HTTPS capture can be obtained.
- **Next CPO:** HERA (`HER`) — 523 stations / 1,137 EVSE in this snapshot.

## Evidence

- [Acea–Plugsurfing interoperability release](https://www.acea.it/comunicati-stampa/2024/07/acea-e-plugsurfing-un-accordo-per-offrire-servizi-piu-capillari-ai-clienti-europei-della-e-mobility): identifies Acea Innovation as the infrastructure CPO.
- [Acea e-mobility App Store listing](https://apps.apple.com/app/acea-e-mobility/id1496190588): publisher-authored notice of service discontinuation from 2025-12-19.
- [InsideEVs report reproducing the customer notice](https://insideevs.it/news/782358/acea-emobility-chiusura-ricarica/): confirms that the app/eMSP stops while stations remain available through other providers.

# EnergyVision BE — simple kWh proof pilot (2026-10-13)

## Validated evidence

Production-free diagnostic PR [#267](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/267), merged at `658b0852`. PR CI [38436490141](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38436490141) and main CI [38436662460](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38436662460) both succeeded.

The pinned authenticated DATEX source is [38435009280](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38435009280), with static SHA256 `a412de196e0f92b71d2a5a0892b75fc9fbdb40cd9a06af917b86af5ac2a8423d`. No additional collection was required. Temporary proof: `energyvision-kwh-proof-38436662460` (seven-day artifact).

Of 1,228 ad-hoc station grids, **248 homogeneous stations / 817 PDC** have a single EUR/kWh, 21%-TTC component, with no additional fixed, per-minute, time-window or minute-threshold component in that grid. **778 PDC** have positive status (600 available, 178 charging); 37 unknown, one inoperative and one faulted.

Source price distribution across all 817 PDC: **€0.28/kWh: 56**, **€0.38: 366**, **€0.39: 64**, **€0.48: 323**, **€0.61: 8**. Source `lastUpdated` is March 2025 for 415 PDC, February 2026 for 330, March 2026 for eight, April 2026 for 64.

The trial validates arithmetic for a 20-kWh energy-only example. It does **not** certify retail pricing applicability on every EVSE or guarantee live checkout parity. All candidate rows explicitly keep `v9Priceable=false`; 0 numeric prices or stations are promoted into TCC V9. The complex 980 station grids remain separate.

## Evidence and next gates

The official [EnergyVision public charging dataset](https://transportdata.be/en/dataset/energyvision-public-charging-network-afir-datex) supports its network-level public scope. [DATEX II Energy documentation](https://docs.datex2.eu/v3.3/energy/) permits rate definitions at station and other hierarchy levels. Confirmation of the operator's actual station-to-PDC tariff applicability, actual consumer checkout amount and site-specific access is still needed before numeric price ranking.

Next: stratified source-versus-checkout comparison (Type2/CCS, each source price family), verify aging and applicability, then a separately approved pinned Production candidate with regression oracles. Do not deploy Pages/Cloudflare.

# Powerdot France — direct CPO national extraction

Generated: 2026-08-25T23:29:59.327846+00:00

## Coverage
- irveRows: **14175**
- uniqueIrvePdc: **7616**
- uniqueIrveStations: **1177**
- derivedChargerNames: **2507**
- unmappedPdc: **2**
- apiSuccessChargers: **2328**
- apiFailedChargers: **179**
- coveredIrvePdc: **7069**
- coveredIrveStations: **1098**
- decodedConnectors: **7063**
- pricedConnectors: **7063**
- locations: **1090**
- connectorsWithNonEnergyComponent: **5**

## Tariff components
- ENERGY: 7063
- TIME: 5

## Energy prices observed
- 0.29 €/kWh: 5 connectors
- 0.31 €/kWh: 68 connectors
- 0.35 €/kWh: 141 connectors
- 0.36 €/kWh: 109 connectors
- 0.38 €/kWh: 12 connectors
- 0.4 €/kWh: 181 connectors
- 0.42 €/kWh: 21 connectors
- 0.46 €/kWh: 12 connectors
- 0.47 €/kWh: 1282 connectors
- 0.48 €/kWh: 14 connectors
- 0.49 €/kWh: 663 connectors
- 0.52 €/kWh: 36 connectors
- 0.53 €/kWh: 31 connectors
- 0.54 €/kWh: 205 connectors
- 0.56 €/kWh: 1123 connectors
- 0.58 €/kWh: 4 connectors
- 0.59 €/kWh: 1691 connectors
- 0.6 €/kWh: 557 connectors
- 0.61 €/kWh: 667 connectors
- 0.62 €/kWh: 241 connectors

## Method
- Source: Powerdot public ad-hoc gRPC-Web API (`api.pwrdt.com`).
- `emspCode` is empty: direct CPO price, no roaming/eMSP discount.
- Charger names are derived from Powerdot IRVE EVSE identifiers and deduplicated before querying.
- No payment/session is created; only charger information is read.

## Failed charger-name sample
- `ACT_MGN_ESNVA001` — no_message
- `ACT_MGN_ESNVA002` — no_message
- `ALQ_TGN_YUFC001` — no_message
- `ALQ_TGN_YUFC002` — no_message
- `ASC_BRI_ALF03` — no_message
- `ASC_NIM_BBC20001` — no_message
- `BBM_ONI_ES2401` — no_message
- `BBM_ONI_ES2402` — no_message
- `BDM_NHV_RALF2202` — no_message
- `BDM_NHV_RALF2203` — no_message
- `BDM_NHV_RALF2204` — no_message
- `BDM_NHV_RALF2205` — no_message
- `BDM_NHV_RKMP20001` — no_message
- `BLG_FLS_ALFS2201` — no_message
- `BOU_LJE_ACHMALF002` — no_message
- `BOU_LJE_ACHMBBC001` — no_message
- `BRT_PSE_YUFC20001` — no_message
- `BRT_PSE_YUFC20002` — no_message
- `BUF_FAM_LEALF003` — no_message
- `BUF_FAM_LETIT001` — no_message
- `BUF_FAM_LETIT002` — no_message
- `CCC_NAY_ALF002` — no_message
- `CCC_NAY_BBC001` — no_message
- `CCS_AIA_LF002` — no_message
- `CCS_AIK_P200001` — no_message
- `CHA_ESS_EYALF002` — no_message
- `CHA_ESS_EYBBC001` — no_message
- `CHA_SAU_MALF002` — no_message
- `CHA_TRG_CALF002` — no_message
- `CHA_TRG_CBBC001` — no_message
- `CHA_VDB_HUB1ALF002` — no_message
- `CHA_VDB_HUB1KP001` — no_message
- `CHA_VDB_HUB2EKO002` — no_message
- `CHA_VDB_HUB2KP001` — no_message
- `CHA_VDB_HUB3BBC001` — no_message
- `CHA_VDB_HUB3EKO002` — no_message
- `COR_MSY_EFA4501` — no_message
- `COR_MSY_EFA4502` — no_message
- `COR_RNS_EFA0007` — no_message
- `COR_RNS_SCH0001` — no_message
- `COR_RNS_SCH0002` — no_message
- `COR_VYR_EFAQ4501` — no_message
- `COR_VYR_EFAQ4502` — no_message
- `CRF_LBN_EKO6001` — no_message
- `CRF_NNC_EFAQ4501` — no_message
- `ESC_UFC_20001` — no_message
- `ESC_UFC_20002` — no_message
- `ETX_ORL_KPC20001` — no_message
- `FLC_HAR_BBC001` — no_message
- `FLT_TES_HMUFC20001` — no_message

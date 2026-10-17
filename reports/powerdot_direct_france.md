# Powerdot France — direct CPO national extraction

Generated: 2026-10-17T05:37:05.481361+00:00

## Coverage
- irveRows: **7748**
- uniqueIrvePdc: **7744**
- uniqueIrveStations: **1183**
- derivedChargerNames: **2545**
- unmappedPdc: **1**
- apiSuccessChargers: **2356**
- apiFailedChargers: **189**
- coveredIrvePdc: **7171**
- coveredIrveStations: **1109**
- decodedConnectors: **7165**
- pricedConnectors: **7165**
- locations: **1101**
- connectorsWithNonEnergyComponent: **5**

## Tariff components
- ENERGY: 7165
- TIME: 5

## Energy prices observed
- 0.36 €/kWh: 1 connectors
- 0.38 €/kWh: 12 connectors
- 0.42 €/kWh: 15 connectors
- 0.46 €/kWh: 9 connectors
- 0.47 €/kWh: 3 connectors
- 0.49 €/kWh: 1487 connectors
- 0.53 €/kWh: 31 connectors
- 0.54 €/kWh: 2 connectors
- 0.55 €/kWh: 6 connectors
- 0.58 €/kWh: 4 connectors
- 0.59 €/kWh: 63 connectors
- 0.62 €/kWh: 5528 connectors
- 0.79 €/kWh: 4 connectors

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

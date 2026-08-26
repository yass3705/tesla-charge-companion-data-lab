# Tesla Charge Companion Data Lab

This repository contains data collection, validation, and normalization workflows used to build operator and tariff datasets for Tesla Charge Companion.

## AVIA / Picoty

A dedicated national AVIA/Picoty collector is being added under `scripts/` and `config/`.

Source identification rules:
- CPO/operator identifier: `FR*PY2` (Picoty)
- Commercial network label: `AVIA VOLT`
- Direct CPO pricing must remain distinct from AVIA Carte / Deft Power eMSP pricing and third-party roaming tariffs.
- Do not infer a national direct price unless it is present in a verified official source.

The generated AVIA dataset is intended to preserve station/EVSE granularity and attach tariff provenance/confidence metadata so downstream TCC logic can safely prefer verified direct-CPO tariffs when available.

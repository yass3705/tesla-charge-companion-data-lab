# Bump tariff readiness for TCC

Source generated: `2026-08-26T00:29:01.355353Z`

## Point classification

- static_rankable: **1409 points** / **748 stations**
- variable_time_requires_rule_parse: **681 points** / **654 stations**
- unpriced_point: **83 points** / **43 stations**
- priced_object_without_numeric_component: **23 points** / **21 stations**

- Unique static tariff descriptions: **49**
- Unique time-varying tariff descriptions: **14**

## Largest time-varying patterns

### 606 points

- quick: `0,55 €/kWh`
- short: `0,55 €/kWh + 1,20 € fixe. Minimum 0,50 €`
- long: `Fixed price: 1,20 € above 0.5kWh consumed

Energy consumption: 0,55 €/kWh

Minimum 0,50 € Inc. VAT`
- parking: `None`

### 16 points

- quick: `0,69 €/kWh`
- short: `0,69 €/kWh. Minimum 0,50 €`
- long: `Energy consumption: 0,69 €/kWh

Duration: 0,29 €/minute after 1h15 of usage

Minimum 0,50 € Inc. VAT`
- parking: `None`

### 14 points

- quick: `0,40 €/kWh`
- short: `0,40 €/kWh + 1,00 € fixe. Minimum 0,50 €`
- long: `Fixed price: 1,00 € above 0.5kWh consumed

Energy consumption: 0,40 €/kWh

Minimum 0,50 € Inc. VAT`
- parking: `None`

### 9 points

- quick: `0,54 €/kWh`
- short: `0,54 €/kWh. Minimum 0,50 €`
- long: `While charging:
Energy consumption: 0,54 €/kWh

While parking (no energy delivered):
Duration: 0,20 €/minute after 15 minutes of usage

Minimum 0,50 € Inc. VAT`
- parking: `Duration: 0,20 €/minute after 15 minutes of usage`

### 8 points

- quick: `0,55 €/kWh`
- short: `0,55 €/kWh + 1,20 € fixe. Minimum 0,50 €`
- long: `Fixed price: 1,20 € above 1kWh consumed and after 1 minutes of usage

Energy consumption: 0,55 €/kWh

Minimum 0,50 € Inc. VAT`
- parking: `None`

### 6 points

- quick: `0,45 €/kWh`
- short: `0,45 €/kWh + 1,00 € fixe. Minimum 0,50 €`
- long: `Fixed price: 1,00 € above 1kWh consumed and after 1 minutes of usage

Energy consumption: 0,45 €/kWh

Minimum 0,50 € Inc. VAT`
- parking: `None`

### 4 points

- quick: `0,45 €/kWh`
- short: `0,45 €/kWh. Minimum 0,50 €`
- long: `While charging:
Energy consumption: 0,45 €/kWh

While parking (no energy delivered):
Duration: 0,00 €/minute between 11:00 PM and 9:00 AM
Then 0,20 €/minute after 15 minutes of usage and between 9:00 AM and 11:00 PM

Minimum 0,50 € Inc. VAT`
- parking: `Duration: 0,00 €/minute between 11:00 PM and 9:00 AM
Then 0,20 €/minute after 15 minutes of usage and between 9:00 AM and 11:00 PM`

### 4 points

- quick: `0,25 €/kWh`
- short: `0,25 €/kWh. Minimum 0,50 €`
- long: `Energy consumption: 0,25 €/kWh between 10:00 AM and 5:00 PM
Then 0,395 €/kWh between 5:00 PM and 10:00 AM

Minimum 0,50 € Inc. VAT`
- parking: `None`

### 4 points

- quick: `0,69 €/kWh`
- short: `0,69 €/kWh. Minimum 0,50 €`
- long: `Energy consumption: 0,69 €/kWh

Duration: 0,29 €/minute after 2h of usage

Minimum 0,50 € Inc. VAT`
- parking: `None`

### 2 points

- quick: `0,40 €/kWh`
- short: `0,40 €/kWh. Minimum 0,50 €`
- long: `While charging:
Energy consumption: 0,40 €/kWh

While parking (no energy delivered):
Duration: 0,12 €/minute after 3h of usage

Minimum 0,50 € Inc. VAT`
- parking: `Duration: 0,12 €/minute after 3h of usage`

### 2 points

- quick: `0,45 €/kWh`
- short: `0,45 €/kWh + 1,00 € fixe. Minimum 0,50 €`
- long: `Fixed price: 1,00 € above 2kWh consumed

Energy consumption: 0,45 €/kWh

Minimum 0,50 € Inc. VAT`
- parking: `None`

### 2 points

- quick: `0,336 €/kWh`
- short: `0,336 €/kWh. Minimum 0,50 €`
- long: `Energy consumption: 0,336 €/kWh

Duration: 0,048 €/minute after 4h of usage

Minimum 0,50 € Inc. VAT`
- parking: `None`

### 2 points

- quick: `0,59 €/kWh`
- short: `0,59 €/kWh. Minimum 0,50 €`
- long: `While charging:
Energy consumption: 0,59 €/kWh

While parking (no energy delivered):
Duration: 0,133 €/minute after 30 minutes of usage

Minimum 0,50 € Inc. VAT`
- parking: `Duration: 0,133 €/minute after 30 minutes of usage`

### 2 points

- quick: `0,50 €/kWh`
- short: `0,50 €/kWh + 1,00 € fixe. Minimum 0,50 €`
- long: `Fixed price: 1,00 € above 0.5kWh consumed and after 2 minutes of usage

Energy consumption: 0,50 €/kWh

Minimum 0,50 € Inc. VAT`
- parking: `None`

## Integration rule

Static explicit tariffs can be promoted to a TCC candidate layer. Time-varying tariffs remain quarantined until each distinct generated rule is parsed and tested against concrete timestamps.

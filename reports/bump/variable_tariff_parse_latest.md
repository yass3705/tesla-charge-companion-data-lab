# Bump variable tariff parser

- Expected variable points: **681**
- Parsed points: **681**
- Failed points: **0**
- Parsed distinct patterns: **14**

## 606 points

```json
[
  {
    "kind": "minimum_total",
    "amountEur": 0.5
  },
  {
    "kind": "flat_fee",
    "amountEur": 1.2,
    "conditions": [
      {
        "kind": "energy_above_kwh",
        "value": 0.5
      }
    ]
  },
  {
    "kind": "energy",
    "eurPerKwh": 0.55
  }
]
```

## 16 points

```json
[
  {
    "kind": "minimum_total",
    "amountEur": 0.5
  },
  {
    "kind": "energy",
    "eurPerKwh": 0.69
  },
  {
    "kind": "session_duration_surcharge",
    "eurPerMinute": 0.29,
    "afterMinutes": 60
  }
]
```

## 14 points

```json
[
  {
    "kind": "minimum_total",
    "amountEur": 0.5
  },
  {
    "kind": "flat_fee",
    "amountEur": 1.0,
    "conditions": [
      {
        "kind": "energy_above_kwh",
        "value": 0.5
      }
    ]
  },
  {
    "kind": "energy",
    "eurPerKwh": 0.4
  }
]
```

## 9 points

```json
[
  {
    "kind": "minimum_total",
    "amountEur": 0.5
  },
  {
    "kind": "energy",
    "eurPerKwh": 0.54
  },
  {
    "kind": "post_charge_occupancy",
    "eurPerMinute": 0.2,
    "graceMinutes": 15
  }
]
```

## 8 points

```json
[
  {
    "kind": "minimum_total",
    "amountEur": 0.5
  },
  {
    "kind": "flat_fee",
    "amountEur": 1.2,
    "conditions": [
      {
        "kind": "energy_above_kwh",
        "value": 1.0
      },
      {
        "kind": "session_duration_after_minutes",
        "value": 1
      }
    ]
  },
  {
    "kind": "energy",
    "eurPerKwh": 0.55
  }
]
```

## 6 points

```json
[
  {
    "kind": "minimum_total",
    "amountEur": 0.5
  },
  {
    "kind": "flat_fee",
    "amountEur": 1.0,
    "conditions": [
      {
        "kind": "energy_above_kwh",
        "value": 1.0
      },
      {
        "kind": "session_duration_after_minutes",
        "value": 1
      }
    ]
  },
  {
    "kind": "energy",
    "eurPerKwh": 0.45
  }
]
```

## 4 points

```json
[
  {
    "kind": "minimum_total",
    "amountEur": 0.5
  },
  {
    "kind": "energy",
    "eurPerKwh": 0.45
  },
  {
    "kind": "post_charge_occupancy_time_bands",
    "bands": [
      {
        "start": "23:00",
        "end": "09:00",
        "eurPerMinute": 0.0,
        "graceMinutes": 0
      },
      {
        "start": "09:00",
        "end": "23:00",
        "eurPerMinute": 0.2,
        "graceMinutes": 15
      }
    ]
  }
]
```

## 4 points

```json
[
  {
    "kind": "minimum_total",
    "amountEur": 0.5
  },
  {
    "kind": "energy_time_bands",
    "bands": [
      {
        "start": "10:00",
        "end": "17:00",
        "eurPerKwh": 0.25
      },
      {
        "start": "17:00",
        "end": "10:00",
        "eurPerKwh": 0.395
      }
    ]
  }
]
```

## 4 points

```json
[
  {
    "kind": "minimum_total",
    "amountEur": 0.5
  },
  {
    "kind": "energy",
    "eurPerKwh": 0.69
  },
  {
    "kind": "session_duration_surcharge",
    "eurPerMinute": 0.29,
    "afterMinutes": 120
  }
]
```

## 2 points

```json
[
  {
    "kind": "minimum_total",
    "amountEur": 0.5
  },
  {
    "kind": "energy",
    "eurPerKwh": 0.4
  },
  {
    "kind": "post_charge_occupancy",
    "eurPerMinute": 0.12,
    "graceMinutes": 180
  }
]
```

## 2 points

```json
[
  {
    "kind": "minimum_total",
    "amountEur": 0.5
  },
  {
    "kind": "flat_fee",
    "amountEur": 1.0,
    "conditions": [
      {
        "kind": "energy_above_kwh",
        "value": 2.0
      }
    ]
  },
  {
    "kind": "energy",
    "eurPerKwh": 0.45
  }
]
```

## 2 points

```json
[
  {
    "kind": "minimum_total",
    "amountEur": 0.5
  },
  {
    "kind": "energy",
    "eurPerKwh": 0.336
  },
  {
    "kind": "session_duration_surcharge",
    "eurPerMinute": 0.048,
    "afterMinutes": 240
  }
]
```

## 2 points

```json
[
  {
    "kind": "minimum_total",
    "amountEur": 0.5
  },
  {
    "kind": "energy",
    "eurPerKwh": 0.59
  },
  {
    "kind": "post_charge_occupancy",
    "eurPerMinute": 0.133,
    "graceMinutes": 30
  }
]
```

## 2 points

```json
[
  {
    "kind": "minimum_total",
    "amountEur": 0.5
  },
  {
    "kind": "flat_fee",
    "amountEur": 1.0,
    "conditions": [
      {
        "kind": "energy_above_kwh",
        "value": 0.5
      },
      {
        "kind": "session_duration_after_minutes",
        "value": 2
      }
    ]
  },
  {
    "kind": "energy",
    "eurPerKwh": 0.5
  }
]
```

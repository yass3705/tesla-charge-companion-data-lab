#!/usr/bin/env python3
"""Live entry point for the current BNetzA CSV layout.

The July 2026 export contains a descriptive preamble before the actual column
header. Keep the core normalizer stable, but replace header discovery with a
layout-tolerant scan before running it against the live national export.
"""
from __future__ import annotations

try:
    from . import germany_bnetza_catalog as base
except ImportError:  # direct execution: python scripts/germany_bnetza_live.py
    import germany_bnetza_catalog as base


def find_live_header_row(rows: list[list[str]]) -> int:
    for idx, row in enumerate(rows[:250]):
        normalized = [base.norm_header(value) for value in row if base.clean(value)]
        if not normalized:
            continue
        has_operator = any("betreiber" in value for value in normalized)
        has_latitude = any(
            "breitengrad" in value or value == "latitude" or value.startswith("latitude ")
            for value in normalized
        )
        has_longitude = any(
            "langengrad" in value or value == "longitude" or value.startswith("longitude ")
            for value in normalized
        )
        if has_operator and has_latitude and has_longitude:
            return idx
    preview = [row[:8] for row in rows[:25]]
    raise RuntimeError(f"unable to locate BNetzA CSV column header; preview={preview!r}")


base.find_header_row = find_live_header_row


if __name__ == "__main__":
    base.main()

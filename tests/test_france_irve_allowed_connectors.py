#!/usr/bin/env python3
"""Regression: only normal domestic E/F, Type 2 and CCS may enter TCC IRVE."""
import importlib.util
from pathlib import Path

file = Path("scripts/france/build_france_irve_static_v9.py")
spec = importlib.util.spec_from_file_location("fr_irve", file)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
get = mod.supported_connectors

assert get({"prisetypechademo": "true"}) == [], "CHAdeMO-only EVSE excluded"
assert get({"prisetypeautre": "Type 3C"}) == [], "Type3C-only EVSE excluded"
assert get({"prisetypeautre": "CCS"}) == [], "Unknown/unverified other field excluded"
assert get({}) == [], "unknown connector excluded"
assert get({"prisetypecomboccs": "true", "prisetypechademo": "true"}) == ["CCS"], "dual CHAdeMO+CCS retains CCS only"
assert get({"prisetypeef": "1", "prisetype2": "Oui"}) == ["EF", "Type 2"], "domestic and Type2 retained"
assert get({"prisetypeef": "true", "prisetype2": "true", "prisetypecomboccs": "true", "prisetypechademo": "true"}) == ["EF", "Type 2", "CCS"], "only supported plugs retained"
assert get({"prisetype2": "non", "prisetypechademo": "true"}) == [], "unsupported-only row must disappear"
print("PASS TCC national IRVE connector scope: EF, Type2, CCS only")

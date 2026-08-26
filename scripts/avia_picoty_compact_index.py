#!/usr/bin/env python3
import json
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
d = json.loads(src.read_text(encoding='utf-8'))

stations = []
for s in d.get('stations', []):
    stations.append({
        'stationId': s.get('stationId'),
        'stationName': s.get('stationName'),
        'address': s.get('address'),
        'cityCode': s.get('cityCode'),
        'coordinatesRaw': s.get('coordinatesRaw'),
        'powerKw': s.get('powerKw') or [],
        'pdcCount': len(s.get('pdcIds') or []),
        'pdcIds': s.get('pdcIds') or [],
        'rawTarifications': s.get('rawTarifications') or [],
    })

out = {
    'schemaVersion': '1.0.0',
    'dataset': 'avia-volt-picoty-station-index',
    'generatedAt': d.get('generatedAt'),
    'sourceDataset': d.get('dataset'),
    'counts': d.get('counts'),
    'stations': stations,
}
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f"Wrote {len(stations)} Picoty stations to {dst}")

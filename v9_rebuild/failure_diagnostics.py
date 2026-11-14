"""Public-safe process diagnostics: keep structure, never arbitrary log text."""
from __future__ import annotations
import json
import re
from pathlib import PurePath

PROGRESS_FIELDS = {'page', 'offset', 'locations', 'nextOffset', 'runningLocations', 'runningEvses'}

def process_failure(completed) -> dict:
    stderr = str(getattr(completed, 'stderr', None) or '')
    stdout = str(getattr(completed, 'stdout', None) or '')
    exceptions = re.findall(r'^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception)):', stderr, re.M)
    statuses = [int(x) for x in re.findall(r'HTTP Error ([1-5][0-9]{2})(?=[:\s])', stderr)]
    frames = [{'file': PurePath(path).name, 'line': int(line), 'function': function}
              for path, line, function in re.findall(
                  r'File "([^"\n]+\.py)", line ([0-9]+), in ([A-Za-z_][A-Za-z0-9_]*|<module>)', stderr)]
    progress = []
    for line in stdout.splitlines():
        try:
            row = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(row, dict) or not isinstance(row.get('offset'), int):
            continue
        safe = {k: v for k, v in row.items() if k in PROGRESS_FIELDS
                and (v is None or isinstance(v, int) and not isinstance(v, bool))}
        progress.append(safe)
    return {'schemaVersion': 1, 'processExitCode': completed.returncode,
            'exceptionType': exceptions[-1] if exceptions else None,
            'httpStatuses': statuses, 'frames': frames[-12:], 'progress': progress,
            'rawLogsStored': False}

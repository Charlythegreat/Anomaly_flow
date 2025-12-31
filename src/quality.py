from typing import Dict, List, Tuple
import time
from .config import settings

Issue = Tuple[str, str]  # (check_name, message)

def dq_checks(evt: Dict) -> List[Issue]:
    issues: List[Issue] = []

    # Required fields
    for f in ["sensor_id", "ts", "value"]:
        if evt.get(f) is None:
            issues.append(("required", f"missing {f}"))

    # Range checks
    v = evt.get("value")
    if v is not None:
        mn, mx = settings.value_range
        if not (mn <= float(v) <= mx):
            issues.append(("range_value", f"value {v} out of [{mn},{mx}]"))

    t = evt.get("temperature")
    if t is not None:
        mn, mx = settings.temperature_range
        if not (mn <= float(t) <= mx):
            issues.append(("range_temperature", f"temperature {t} out of [{mn},{mx}]"))

    # Freshness: event not too old
    ts = evt.get("ts")
    if ts is not None:
        lag = time.time() - float(ts)
        if lag > settings.freshness_max_lag_sec:
            issues.append(("freshness", f"lag {lag:.1f}s exceeds {settings.freshness_max_lag_sec}s"))

    return issues

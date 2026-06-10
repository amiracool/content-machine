import json
from datetime import date
from pathlib import Path

QUOTA_FILE = Path(".tmp/quotas.json")

DAILY_LIMITS = {
    "youtube": 10_000,   # YouTube Data API v3 free quota units/day
    "openai": 500,       # images generated per day (soft limit)
    "anthropic": 1_000,  # API calls per day (soft limit)
}


def _load() -> dict:
    QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if QUOTA_FILE.exists():
        return json.loads(QUOTA_FILE.read_text())
    return {}


def _save(data: dict):
    QUOTA_FILE.write_text(json.dumps(data, indent=2))


def increment(service: str, units: int = 1):
    data = _load()
    today = str(date.today())
    data.setdefault(service, {}).setdefault(today, 0)
    data[service][today] += units
    _save(data)


def get_usage(service: str) -> int:
    data = _load()
    return data.get(service, {}).get(str(date.today()), 0)


def check_limit(service: str) -> bool:
    limit = DAILY_LIMITS.get(service)
    if limit is None:
        return True
    return get_usage(service) < limit


def report():
    data = _load()
    today = str(date.today())
    print(f"\n=== API Quota Report ({today}) ===")
    for service, days in data.items():
        usage = days.get(today, 0)
        limit = DAILY_LIMITS.get(service, "?")
        print(f"  {service}: {usage:,} / {limit:,} units")
    print()

"""Compare workflow_schema_version values numerically (1.10 > 1.9)."""

from __future__ import annotations

CURRENT = "1.11"


def parse(value: object) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in str(value or "").split("."))
    except ValueError:
        return ()


def at_least(value: object, minimum: str) -> bool:
    parsed = parse(value)
    return bool(parsed) and parsed >= parse(minimum)

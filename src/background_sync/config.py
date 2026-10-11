"""Reading and writing the add-on configuration, with validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from aqt import mw

ADDON_MODULE = __name__.split(".")[0]

MIN_INTERVAL_MIN = 2
MAX_INTERVAL_MIN = 240
MIN_IDLE_S = 15
MAX_IDLE_S = 900


@dataclass
class Config:
    enabled: bool = True
    interval_minutes: int = 5
    idle_seconds: int = 60
    show_indicator: bool = True
    notify_on_error: bool = True
    notify_on_success: bool = False


def _as_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(low, min(high, number))


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def load() -> Config:
    raw: dict[str, Any] = {}
    try:
        raw = mw.addonManager.getConfig(ADDON_MODULE) or {}
    except Exception:
        raw = {}
    base = Config()
    return Config(
        enabled=_as_bool(raw.get("enabled"), base.enabled),
        interval_minutes=_as_int(
            raw.get("interval_minutes"),
            base.interval_minutes,
            MIN_INTERVAL_MIN,
            MAX_INTERVAL_MIN,
        ),
        idle_seconds=_as_int(
            raw.get("idle_seconds"), base.idle_seconds, MIN_IDLE_S, MAX_IDLE_S
        ),
        show_indicator=_as_bool(raw.get("show_indicator"), base.show_indicator),
        notify_on_error=_as_bool(raw.get("notify_on_error"), base.notify_on_error),
        notify_on_success=_as_bool(
            raw.get("notify_on_success"), base.notify_on_success
        ),
    )


def save(conf: Config) -> None:
    mw.addonManager.writeConfig(ADDON_MODULE, asdict(conf))

"""Luxor wire protocol: data types and response parsing.

Pure Python with no Home Assistant or aiohttp imports, so it can be unit
tested on its own.

The controller speaks JSON over HTTP POST to ``/<Method>.json``. Field names
differ by controller generation:

* Luxor ZD (zoning + dimming): ``GroupNumber`` / ``Intensity``
  (see github.com/scottlamb/luxor, verified against a live ZD controller).
* Luxor ZDC (adds color): ``Grp`` / ``Inten`` / ``Colr``
  (see github.com/dcramer/luxor-openapi).

Both spellings are accepted everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MAX_INTENSITY = 100

STATUS_OK = 0
STATUS_NAMES: dict[int, str] = {
    0: "ok",
    1: "unknown method",
    101: "unparseable request",
    102: "invalid request",
    201: "precondition failed",
    202: "group name in use",
    205: "group number in use",
    243: "theme index out of range",
}


class LuxorError(Exception):
    """Base error for Luxor communication."""


class LuxorConnectionError(LuxorError):
    """The controller could not be reached or returned garbage."""


class LuxorStatusError(LuxorError):
    """The controller answered with a non-zero Status code."""

    def __init__(self, method: str, status: int) -> None:
        self.method = method
        self.status = status
        name = STATUS_NAMES.get(status, "unknown status")
        super().__init__(f"{method} failed: {name} ({status})")


@dataclass(slots=True)
class LuxorGroup:
    """A lighting group as reported by GroupListGet."""

    number: int
    name: str
    intensity: int
    color: int | None = None


@dataclass(slots=True)
class LuxorTheme:
    """A theme as reported by ThemeListGet.

    ``on`` mirrors the last IlluminateTheme/ExtinguishAll command, not
    necessarily what the lights look like right now.
    """

    index: int
    name: str
    on: bool


@dataclass(slots=True)
class LuxorState:
    """Snapshot of everything the integration polls."""

    groups: dict[int, LuxorGroup] = field(default_factory=dict)
    themes: dict[int, LuxorTheme] = field(default_factory=dict)
    themes_restricted: bool = False


def _first(item: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return default


def check_status(method: str, payload: Any) -> dict[str, Any]:
    """Validate a decoded response and raise on a non-zero Status."""
    if not isinstance(payload, dict):
        raise LuxorConnectionError(f"{method}: unexpected response {payload!r}")
    status = payload.get("Status", STATUS_OK)
    try:
        status = int(status)
    except (TypeError, ValueError) as err:
        raise LuxorConnectionError(f"{method}: bad Status {status!r}") from err
    if status != STATUS_OK:
        raise LuxorStatusError(method, status)
    return payload


def parse_groups(payload: dict[str, Any]) -> dict[int, LuxorGroup]:
    """Parse a GroupListGet response into groups keyed by group number."""
    groups: dict[int, LuxorGroup] = {}
    for item in payload.get("GroupList") or []:
        if not isinstance(item, dict):
            continue
        number = _first(item, "GroupNumber", "Grp")
        if number is None:
            continue
        number = int(number)
        intensity = int(_first(item, "Intensity", "Inten", default=0))
        color = _first(item, "Color", "Colr")
        groups[number] = LuxorGroup(
            number=number,
            name=str(item.get("Name") or f"Group {number}"),
            intensity=clamp_intensity(intensity),
            color=None if color is None else int(color),
        )
    return groups


def parse_themes(payload: dict[str, Any]) -> tuple[dict[int, LuxorTheme], bool]:
    """Parse a ThemeListGet response into (themes by index, restricted flag)."""
    themes: dict[int, LuxorTheme] = {}
    for item in payload.get("ThemeList") or []:
        if not isinstance(item, dict) or "ThemeIndex" not in item:
            continue
        index = int(item["ThemeIndex"])
        themes[index] = LuxorTheme(
            index=index,
            name=str(item.get("Name") or f"Theme {chr(ord('A') + index)}"),
            on=bool(int(item.get("OnOff") or 0)),
        )
    return themes, bool(int(payload.get("Restricted") or 0))


def clamp_intensity(value: int) -> int:
    """Clamp to the 0-100 range the controller treats as meaningful."""
    return max(0, min(MAX_INTENSITY, int(value)))


def brightness_to_intensity(brightness: int) -> int:
    """HA brightness (0-255) to Luxor intensity (0-100); never rounds a lit
    light down to 0."""
    if brightness <= 0:
        return 0
    return max(1, clamp_intensity(round(brightness * MAX_INTENSITY / 255)))


def intensity_to_brightness(intensity: int) -> int:
    """Luxor intensity (0-100) to HA brightness (0-255)."""
    return round(clamp_intensity(intensity) * 255 / MAX_INTENSITY)

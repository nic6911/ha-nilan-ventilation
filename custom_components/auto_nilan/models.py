"""Parsed models for the JSON payloads published by the auto_nilan component."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

TOPOLOGY_VERSION = 1


@dataclass(slots=True, frozen=True)
class NilanPoint:
    """One point (register) from the controller topology."""

    key: str
    name: str
    kind: str
    reg: str
    addr: int
    scale: int
    signed: bool
    min_value: int | None
    max_value: int | None
    unit: str | None
    options: tuple[str, ...] | None
    writable: bool
    diagnostic: bool
    disabled: bool
    cap: str | None

    @property
    def step(self) -> float:
        return float(10**self.scale)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NilanPoint:
        options = data.get("options")
        if not isinstance(options, list) or not options:
            options = None
        else:
            options = tuple(str(option) for option in options)
        return cls(
            key=str(data["key"]),
            name=str(data.get("name") or data["key"]),
            kind=str(data.get("kind") or "sensor"),
            reg=str(data.get("reg") or "holding"),
            addr=int(data.get("addr") or 0),
            scale=int(data.get("scale") or 0),
            signed=bool(data.get("signed")),
            min_value=_optional_int(data.get("min")),
            max_value=_optional_int(data.get("max")),
            unit=(str(data["unit"]) if data.get("unit") else None),
            options=options,
            writable=bool(data.get("writable")),
            diagnostic=bool(data.get("diagnostic")),
            disabled=bool(data.get("disabled")),
            cap=(str(data["cap"]) if data.get("cap") else None),
        )


@dataclass(slots=True)
class NilanTopology:
    """Controller topology payload."""

    version: int
    profile: str
    model: int
    model_name: str
    caps: tuple[str, ...]
    points: dict[str, NilanPoint]


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_topology(payload: str) -> NilanTopology:
    """Parse the topology JSON payload."""
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError("topology payload is not an object")

    raw_points = parsed.get("points")
    if not isinstance(raw_points, list):
        raise ValueError("topology payload has no points list")

    points: dict[str, NilanPoint] = {}
    for raw_point in raw_points:
        if not isinstance(raw_point, dict) or "key" not in raw_point:
            continue
        point = NilanPoint.from_dict(raw_point)
        points[point.key] = point

    caps = parsed.get("caps")
    caps_tuple = tuple(str(cap) for cap in caps) if isinstance(caps, list) else ()

    return NilanTopology(
        version=int(parsed.get("version") or 0),
        profile=str(parsed.get("profile") or "unknown"),
        model=int(parsed.get("model") or 0),
        model_name=str(parsed.get("model_name") or "Nilan"),
        caps=caps_tuple,
        points=points,
    )


def parse_values(payload: str) -> tuple[dict[str, float], bool]:
    """Parse the values JSON payload into a point key to value mapping."""
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError("values payload is not an object")

    raw_values = parsed.get("values")
    if not isinstance(raw_values, dict):
        raise ValueError("values payload has no values object")

    values: dict[str, float] = {}
    for key, value in raw_values.items():
        if isinstance(value, bool):
            values[str(key)] = 1.0 if value else 0.0
        elif isinstance(value, (int, float)):
            values[str(key)] = float(value)

    return values, bool(parsed.get("online", True))


def parse_status(payload: str) -> dict[str, Any]:
    """Parse the status JSON payload."""
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError("status payload is not an object")
    return parsed

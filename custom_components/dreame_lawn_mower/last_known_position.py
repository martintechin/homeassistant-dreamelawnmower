"""Last-known-position tracking for Dreame lawn mower.

The mower reports its position in internal map-grid coordinates while it is
online. When the device errors out and drops off the cloud, that telemetry
disappears, so the coordinator captures the freshest position fix here and
retains it (persisted to disk) for the user to find the mower afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

LAST_POSITION_STORAGE_VERSION = 1

SOURCE_RUNTIME_POSE = "runtime_pose"
SOURCE_MAP_ROBOT_POSITION = "map_robot_position"
SOURCE_CHARGER_POSITION = "charger_position"


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _number_or_none(value: Any) -> float | int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int | float) else None


@dataclass(frozen=True, slots=True)
class LastKnownPosition:
    """A retained mower position fix in map-grid coordinates."""

    x: float | int
    y: float | int
    heading_deg: float | int | None
    source: str
    captured_at: datetime
    activity: str | None = None
    error_code: int | str | None = None
    error_display: str | None = None
    docked: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        """Serialize for storage and entity attributes."""
        return {
            "x": self.x,
            "y": self.y,
            "heading_deg": self.heading_deg,
            "source": self.source,
            "captured_at": self.captured_at.isoformat(),
            "activity": self.activity,
            "error_code": self.error_code,
            "error_display": self.error_display,
            "docked": self.docked,
        }

    @classmethod
    def from_dict(cls, data: Any) -> LastKnownPosition | None:
        """Deserialize tolerantly, returning None for corrupt payloads."""
        if not isinstance(data, dict):
            return None
        x = _number_or_none(data.get("x"))
        y = _number_or_none(data.get("y"))
        raw_captured_at = data.get("captured_at")
        if x is None or y is None or not isinstance(raw_captured_at, str):
            return None
        try:
            captured_at = datetime.fromisoformat(raw_captured_at)
        except ValueError:
            return None
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=UTC)
        source = data.get("source")
        activity = data.get("activity")
        error_code = data.get("error_code")
        if isinstance(error_code, bool) or not isinstance(error_code, int | str):
            error_code = None
        error_display = data.get("error_display")
        docked = data.get("docked")
        return cls(
            x=x,
            y=y,
            heading_deg=_number_or_none(data.get("heading_deg")),
            source=source if isinstance(source, str) else "unknown",
            captured_at=captured_at,
            activity=activity if isinstance(activity, str) else None,
            error_code=error_code,
            error_display=error_display if isinstance(error_display, str) else None,
            docked=docked if isinstance(docked, bool) else None,
        )

    def same_fix(self, other: LastKnownPosition | None) -> bool:
        """Return whether another capture describes the same physical fix."""
        if other is None:
            return False
        return (
            self.x == other.x
            and self.y == other.y
            and self.heading_deg == other.heading_deg
            and self.source == other.source
            and self.docked == other.docked
        )


def _point_coordinates(point: Any) -> tuple[float | int, float | int] | None:
    x = _number_or_none(getattr(point, "x", None))
    y = _number_or_none(getattr(point, "y", None))
    if x is None or y is None:
        return None
    return x, y


def _legacy_map_position(client: Any, attribute: str) -> Any:
    """Best-effort lookup of a legacy map position on the upstream device."""
    try:
        current_map = client.device.status.current_map
    except Exception:  # noqa: BLE001 - legacy layer optional
        return None
    return getattr(current_map, attribute, None)


def capture_last_known_position(
    snapshot: Any,
    runtime_blob: Any,
    client: Any,
    now: datetime,
) -> LastKnownPosition | None:
    """Build a position fix from the freshest source, or None when unknown.

    Callers should keep their previous fix when this returns None — a lost
    signal must never erase the last usable position.
    """
    activity = getattr(snapshot, "activity", None)
    error_code = getattr(snapshot, "error_code", None)
    if isinstance(error_code, bool) or not isinstance(error_code, int | str):
        error_code = None
    error_display = getattr(snapshot, "error_display", None)
    docked = getattr(snapshot, "docked", None)
    context = {
        "captured_at": now,
        "activity": activity if isinstance(activity, str) else None,
        "error_code": error_code,
        "error_display": error_display if isinstance(error_display, str) else None,
        "docked": docked if isinstance(docked, bool) else None,
    }

    pose_x = _int_or_none(getattr(runtime_blob, "candidate_runtime_pose_x", None))
    pose_y = _int_or_none(getattr(runtime_blob, "candidate_runtime_pose_y", None))
    if pose_x is not None and pose_y is not None:
        heading = _number_or_none(
            getattr(runtime_blob, "candidate_runtime_heading_deg", None)
        )
        return LastKnownPosition(
            x=pose_x,
            y=pose_y,
            heading_deg=heading,
            source=SOURCE_RUNTIME_POSE,
            **context,
        )

    robot_position = _legacy_map_position(client, "robot_position")
    coordinates = _point_coordinates(robot_position)
    if coordinates is not None:
        return LastKnownPosition(
            x=coordinates[0],
            y=coordinates[1],
            heading_deg=_number_or_none(getattr(robot_position, "a", None)),
            source=SOURCE_MAP_ROBOT_POSITION,
            **context,
        )

    if context["docked"]:
        charger_position = _legacy_map_position(client, "charger_position")
        coordinates = _point_coordinates(charger_position)
        if coordinates is not None:
            return LastKnownPosition(
                x=coordinates[0],
                y=coordinates[1],
                heading_deg=_number_or_none(getattr(charger_position, "a", None)),
                source=SOURCE_CHARGER_POSITION,
                **context,
            )

    return None

"""Tests for last-known-position capture, persistence, and entities."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

from custom_components.dreame_lawn_mower.coordinator import DreameLawnMowerCoordinator
from custom_components.dreame_lawn_mower.last_known_position import (
    SOURCE_CHARGER_POSITION,
    SOURCE_MAP_ROBOT_POSITION,
    SOURCE_RUNTIME_POSE,
    LastKnownPosition,
    capture_last_known_position,
)
from custom_components.dreame_lawn_mower.sensor import (
    DreameLawnMowerLastKnownPositionSensor,
    DreameLawnMowerLastSeenSensor,
)

_NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


def _snapshot(**overrides) -> SimpleNamespace:
    values = {
        "available": True,
        "activity": "mowing",
        "error_code": None,
        "error_display": None,
        "docked": False,
        "raw_attributes": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _blob(x=None, y=None, heading=None) -> SimpleNamespace:
    return SimpleNamespace(
        candidate_runtime_pose_x=x,
        candidate_runtime_pose_y=y,
        candidate_runtime_heading_deg=heading,
    )


def _client(robot_position=None, charger_position=None) -> SimpleNamespace:
    client = SimpleNamespace(
        device=SimpleNamespace(
            status=SimpleNamespace(
                current_map=SimpleNamespace(
                    robot_position=robot_position,
                    charger_position=charger_position,
                )
            )
        ),
        position_updates=[],
    )
    client.update_last_known_position = client.position_updates.append
    return client


def _fix(**overrides) -> LastKnownPosition:
    values = {
        "x": 5910,
        "y": 12400,
        "heading_deg": 63.5,
        "source": SOURCE_RUNTIME_POSE,
        "captured_at": _NOW,
        "activity": "mowing",
        "error_code": None,
        "error_display": None,
        "docked": False,
    }
    values.update(overrides)
    return LastKnownPosition(**values)


def test_capture_prefers_runtime_pose() -> None:
    position = capture_last_known_position(
        _snapshot(),
        _blob(x=5910, y=12400, heading=63.5),
        _client(robot_position=SimpleNamespace(x=1.0, y=2.0, a=None)),
        _NOW,
    )

    assert position is not None
    assert position.source == SOURCE_RUNTIME_POSE
    assert position.x == 5910
    assert position.y == 12400
    assert position.heading_deg == 63.5
    assert position.captured_at is _NOW
    assert position.activity == "mowing"
    assert position.docked is False


def test_capture_records_error_context() -> None:
    position = capture_last_known_position(
        _snapshot(activity="error", error_code=54, error_display="Edge"),
        _blob(x=100, y=200),
        _client(),
        _NOW,
    )

    assert position is not None
    assert position.activity == "error"
    assert position.error_code == 54
    assert position.error_display == "Edge"


def test_capture_rejects_boolean_pose_values() -> None:
    position = capture_last_known_position(
        _snapshot(),
        _blob(x=True, y=True),
        _client(),
        _NOW,
    )

    assert position is None


def test_capture_falls_back_to_map_robot_position() -> None:
    position = capture_last_known_position(
        _snapshot(),
        _blob(),
        _client(robot_position=SimpleNamespace(x=480.5, y=260.0, a=91.5)),
        _NOW,
    )

    assert position is not None
    assert position.source == SOURCE_MAP_ROBOT_POSITION
    assert position.x == 480.5
    assert position.y == 260.0
    assert position.heading_deg == 91.5


def test_capture_uses_charger_position_only_when_docked() -> None:
    charger = SimpleNamespace(x=10, y=20, a=None)

    undocked = capture_last_known_position(
        _snapshot(docked=False),
        _blob(),
        _client(charger_position=charger),
        _NOW,
    )
    docked = capture_last_known_position(
        _snapshot(docked=True, activity="docked"),
        _blob(),
        _client(charger_position=charger),
        _NOW,
    )

    assert undocked is None
    assert docked is not None
    assert docked.source == SOURCE_CHARGER_POSITION
    assert docked.docked is True


def test_capture_survives_missing_legacy_device_layer() -> None:
    position = capture_last_known_position(
        _snapshot(),
        None,
        SimpleNamespace(device=None),
        _NOW,
    )

    assert position is None


def test_round_trip_serialization() -> None:
    original = _fix(activity="error", error_code=54, error_display="Edge")

    restored = LastKnownPosition.from_dict(original.as_dict())

    assert restored == original


def test_from_dict_rejects_corrupt_payloads() -> None:
    assert LastKnownPosition.from_dict(None) is None
    assert LastKnownPosition.from_dict("garbage") is None
    assert LastKnownPosition.from_dict({}) is None
    assert LastKnownPosition.from_dict({"x": "garbage", "y": 2}) is None
    assert (
        LastKnownPosition.from_dict({"x": 1, "y": 2, "captured_at": "not-a-date"})
        is None
    )


def test_from_dict_assumes_utc_for_naive_timestamps() -> None:
    restored = LastKnownPosition.from_dict(
        {"x": 1, "y": 2, "captured_at": "2026-07-11T12:00:00"}
    )

    assert restored is not None
    assert restored.captured_at.tzinfo is UTC


def test_same_fix_ignores_capture_time_and_context() -> None:
    first = _fix()
    later = _fix(
        captured_at=datetime(2026, 7, 11, 12, 5, tzinfo=UTC),
        activity="paused",
    )
    moved = _fix(x=6000)

    assert later.same_fix(first) is True
    assert moved.same_fix(first) is False
    assert first.same_fix(None) is False


class _StoreRecorder:
    def __init__(self) -> None:
        self.delay_saves: list[tuple[object, float]] = []

    def async_delay_save(self, data_fn, delay) -> None:
        self.delay_saves.append((data_fn, delay))


def _bare_coordinator() -> DreameLawnMowerCoordinator:
    coordinator = object.__new__(DreameLawnMowerCoordinator)
    coordinator.last_known_position = None
    coordinator._last_position_store = _StoreRecorder()
    return coordinator


def test_offline_update_retains_last_known_position() -> None:
    coordinator = _bare_coordinator()
    coordinator.data = SimpleNamespace(state="stale")
    coordinator.runtime_status_blob = {"status": "stale"}
    coordinator.last_known_position = _fix()
    offline_snapshot = SimpleNamespace(available=False)
    tracking_updates: list[tuple[object, bool]] = []

    async def _refresh() -> SimpleNamespace:
        return offline_snapshot

    coordinator.client = SimpleNamespace(
        async_refresh=_refresh,
        update_runtime_live_tracking=lambda value, *, active: tracking_updates.append(
            (value, active)
        ),
    )

    result = asyncio.run(coordinator._async_update_data())

    assert result is offline_snapshot
    assert coordinator.runtime_status_blob is None
    assert tracking_updates == [(None, False)]
    assert coordinator.last_known_position == _fix()


def test_capture_updates_position_and_schedules_save() -> None:
    coordinator = _bare_coordinator()
    coordinator.runtime_status_blob = _blob(x=5910, y=12400, heading=63.5)
    coordinator.client = _client()

    coordinator._capture_last_known_position(_snapshot())

    assert coordinator.last_known_position is not None
    assert coordinator.last_known_position.x == 5910
    assert coordinator.client.position_updates == [(5910, 12400)]
    assert len(coordinator._last_position_store.delay_saves) == 1
    data_fn, delay = coordinator._last_position_store.delay_saves[0]
    assert data_fn() == coordinator.last_known_position.as_dict()
    assert delay == 30


def test_capture_does_not_reschedule_save_for_same_fix() -> None:
    coordinator = _bare_coordinator()
    coordinator.runtime_status_blob = _blob(x=5910, y=12400, heading=63.5)
    coordinator.client = _client()

    coordinator._capture_last_known_position(_snapshot())
    first_captured_at = coordinator.last_known_position.captured_at
    coordinator._capture_last_known_position(_snapshot())

    assert len(coordinator._last_position_store.delay_saves) == 1
    assert coordinator.last_known_position.captured_at >= first_captured_at


def test_capture_keeps_previous_fix_when_signal_is_lost() -> None:
    coordinator = _bare_coordinator()
    coordinator.last_known_position = _fix()
    coordinator.runtime_status_blob = None
    coordinator.client = _client()

    coordinator._capture_last_known_position(_snapshot())

    assert coordinator.last_known_position == _fix()
    assert coordinator._last_position_store.delay_saves == []


def test_load_restores_persisted_fix() -> None:
    coordinator = _bare_coordinator()
    coordinator.client = _client()
    stored = _fix().as_dict()

    async def _load():
        return stored

    coordinator._last_position_store = SimpleNamespace(async_load=_load)

    asyncio.run(coordinator.async_load_last_known_position())

    assert coordinator.last_known_position == _fix()
    assert coordinator.client.position_updates == [(5910, 12400)]


def test_load_tolerates_missing_or_corrupt_store() -> None:
    coordinator = _bare_coordinator()

    async def _load_none():
        return None

    coordinator._last_position_store = SimpleNamespace(async_load=_load_none)
    asyncio.run(coordinator.async_load_last_known_position())
    assert coordinator.last_known_position is None

    async def _load_raises():
        raise OSError("corrupt store")

    coordinator._last_position_store = SimpleNamespace(async_load=_load_raises)
    asyncio.run(coordinator.async_load_last_known_position())
    assert coordinator.last_known_position is None


def test_last_known_position_sensor_reports_while_offline() -> None:
    entity = object.__new__(DreameLawnMowerLastKnownPositionSensor)
    entity.coordinator = SimpleNamespace(
        data=SimpleNamespace(available=False),
        last_known_position=_fix(activity="error", error_code=54, error_display="Edge"),
    )

    assert entity.available is True
    assert entity.native_value == "5910, 12400"
    attributes = entity.extra_state_attributes
    assert attributes["x"] == 5910
    assert attributes["y"] == 12400
    assert attributes["heading_deg"] == 63.5
    assert attributes["source"] == SOURCE_RUNTIME_POSE
    assert attributes["captured_at"] == _NOW.isoformat()
    assert attributes["activity_at_capture"] == "error"
    assert attributes["error_at_capture"] == "Edge"
    assert attributes["error_code_at_capture"] == 54
    assert attributes["docked_at_capture"] is False
    assert attributes["device_currently_online"] is False


def test_last_known_position_sensor_unavailable_before_first_fix() -> None:
    entity = object.__new__(DreameLawnMowerLastKnownPositionSensor)
    entity.coordinator = SimpleNamespace(
        data=SimpleNamespace(available=True),
        last_known_position=None,
    )

    assert entity.available is False
    assert entity.native_value is None
    assert entity.extra_state_attributes == {}


def test_last_seen_sensor_reports_capture_time_while_offline() -> None:
    entity = object.__new__(DreameLawnMowerLastSeenSensor)
    entity.coordinator = SimpleNamespace(
        data=SimpleNamespace(available=False),
        last_known_position=_fix(),
    )

    assert entity.available is True
    assert entity.native_value == _NOW


def test_last_seen_sensor_unavailable_before_first_fix() -> None:
    entity = object.__new__(DreameLawnMowerLastSeenSensor)
    entity.coordinator = SimpleNamespace(
        data=SimpleNamespace(available=True),
        last_known_position=None,
    )

    assert entity.available is False
    assert entity.native_value is None


def test_legacy_map_fix_is_recorded_but_not_pushed_to_renderer() -> None:
    coordinator = _bare_coordinator()
    coordinator.runtime_status_blob = None
    coordinator.client = _client(
        robot_position=SimpleNamespace(x=480.5, y=260.0, a=None)
    )

    coordinator._capture_last_known_position(_snapshot())

    assert coordinator.last_known_position is not None
    assert coordinator.last_known_position.source == SOURCE_MAP_ROBOT_POSITION
    # Legacy map coordinates are not verified against the vector map frame,
    # so no marker hint is sent to the renderer.
    assert coordinator.client.position_updates == []

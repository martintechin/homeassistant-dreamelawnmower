"""Unit tests for Home Assistant map camera helpers."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from custom_components.dreame_lawn_mower.map_attributes import map_camera_attributes
from custom_components.dreame_lawn_mower.map_cache import (
    DreameLawnMowerMapCameraCache,
    map_camera_available,
)
from dreame_lawn_mower_client.models import (
    DreameLawnMowerMapSummary,
    DreameLawnMowerMapView,
)


def test_map_camera_attributes_include_app_map_summary_counts() -> None:
    """Camera attributes preserve app-map counts validated from live payloads."""
    refreshed_at = datetime(2026, 4, 18, 12, 30, tzinfo=UTC)
    view = DreameLawnMowerMapView(
        source="app_action_map",
        summary=DreameLawnMowerMapSummary(
            available=True,
            map_id=0,
            width=521,
            height=900,
            segment_count=2,
            active_area_count=2,
            spot_area_count=2,
            no_go_area_count=0,
            path_point_count=63,
            robot_present=True,
            charger_present=True,
        ),
        image_png=b"png",
    )

    attributes = map_camera_attributes(
        view,
        image_cached=True,
        refreshed_at=refreshed_at,
        last_error=None,
    )

    assert attributes["map_cached"] is True
    assert attributes["map_placeholder"] is False
    assert attributes["map_source"] == "app_action_map"
    assert attributes["map_has_image"] is True
    assert attributes["map_available"] is True
    assert attributes["map_id"] == 0
    assert attributes["width"] == 521
    assert attributes["height"] == 900
    assert attributes["segment_count"] == 2
    assert attributes["active_area_count"] == 2
    assert attributes["spot_area_count"] == 2
    assert attributes["no_go_area_count"] == 0
    assert attributes["path_point_count"] == 63
    assert attributes["robot_present"] is True
    assert attributes["charger_present"] is True
    assert attributes["last_map_refresh"] == "2026-04-18T12:30:00+00:00"
    assert attributes["app_map_count"] is None
    assert attributes["app_maps"] is None
    assert attributes["app_map_object_count"] is None
    assert attributes["app_map_objects"] is None


def test_offline_map_camera_keeps_serving_cached_image() -> None:
    snapshot = SimpleNamespace(
        available=False,
        mapping_available=True,
        capabilities=("map",),
    )

    assert map_camera_available(snapshot, image_cached=True) is True


def test_offline_map_camera_without_cached_image_is_unavailable() -> None:
    snapshot = SimpleNamespace(
        available=False,
        mapping_available=True,
        capabilities=("map",),
    )

    assert map_camera_available(snapshot, image_cached=False) is False


def test_online_diagnostic_map_camera_does_not_require_map_capability() -> None:
    snapshot = SimpleNamespace(
        available=True,
        mapping_available=False,
        capabilities=(),
    )

    assert (
        map_camera_available(
            snapshot,
            image_cached=False,
            requires_map_capability=False,
        )
        is True
    )


def test_offline_diagnostic_map_camera_remains_unavailable() -> None:
    snapshot = SimpleNamespace(
        available=False,
        mapping_available=False,
        capabilities=(),
    )

    assert (
        map_camera_available(
            snapshot,
            image_cached=False,
            requires_map_capability=False,
        )
        is False
    )


def test_map_camera_attributes_include_all_app_map_metadata() -> None:
    """Camera attributes expose all app maps, not only the rendered map."""
    view = DreameLawnMowerMapView(
        source="app_action_map",
        app_maps={
            "map_count": 2,
            "current_map_index": 0,
            "available_map_count": 2,
            "created_map_count": 2,
            "error_count": 0,
            "object_count": 2,
            "object_error": None,
            "objects": [
                {"name": "map-a.bin", "extension": "bin", "url_present": False},
                {"name": "map-b.bin", "extension": "bin", "url_present": False},
            ],
            "maps": [
                {"idx": 0, "current": True, "available": True},
                {"idx": 1, "current": False, "available": True},
            ],
        },
    )

    attributes = map_camera_attributes(
        view,
        image_cached=False,
        refreshed_at=None,
        last_error=None,
    )

    assert attributes["app_map_count"] == 2
    assert attributes["app_current_map_index"] == 0
    assert attributes["app_available_map_count"] == 2
    assert attributes["app_created_map_count"] == 2
    assert attributes["app_map_error_count"] == 0
    assert attributes["app_map_object_count"] == 2
    assert attributes["app_map_object_error"] is None
    assert attributes["app_map_objects"] == [
        {"name": "map-a.bin", "extension": "bin", "url_present": False},
        {"name": "map-b.bin", "extension": "bin", "url_present": False},
    ]
    assert attributes["app_maps"] == [
        {"idx": 0, "current": True, "available": True},
        {"idx": 1, "current": False, "available": True},
    ]
    assert attributes["map_has_live_path"] is None
    assert attributes["map_details"] is None


def test_map_camera_attributes_include_live_path_metadata() -> None:
    """Camera attributes expose vector live-path details when present."""
    view = DreameLawnMowerMapView(
        source="batch_vector_map",
        details={
            "map_name": "Primary",
            "map_id": 1,
            "map_index": 0,
            "current_map_id": 2,
            "total_area": 10.5,
            "zone_count": 2,
            "zone_names": ["Front Yard", "Back Yard"],
            "contour_count": 1,
            "contour_ids": [[1, 0]],
            "clean_point_count": 1,
            "cruise_point_count": 0,
            "mow_path_count": 1,
            "mow_path_segment_count": 3,
            "mow_path_point_count": 18,
            "mow_path_length_m": 9.87,
            "has_live_path": True,
            "available_map_count": 2,
            "available_maps": [
                {"map_id": 1, "map_index": 0, "name": "Primary", "total_area": 10.5},
                {"map_id": 2, "map_index": 1, "name": "Back", "total_area": 8.0},
            ],
        },
    )

    attributes = map_camera_attributes(
        view,
        image_cached=False,
        refreshed_at=None,
        last_error=None,
    )

    assert attributes["map_name"] == "Primary"
    assert attributes["map_index"] == 0
    assert attributes["map_current_map_id"] == 2
    assert attributes["map_total_area"] == 10.5
    assert attributes["map_zone_count"] == 2
    assert attributes["map_zone_names"] == ["Front Yard", "Back Yard"]
    assert attributes["map_contour_count"] == 1
    assert attributes["map_contour_ids"] == [[1, 0]]
    assert attributes["map_clean_point_count"] == 1
    assert attributes["map_cruise_point_count"] == 0
    assert attributes["map_trajectory_count"] is None
    assert attributes["map_trajectory_point_count"] is None
    assert attributes["map_cut_relation_count"] is None
    assert attributes["mow_path_count"] == 1
    assert attributes["mow_path_segment_count"] == 3
    assert attributes["mow_path_point_count"] == 18
    assert attributes["mow_path_length_m"] == 9.87
    assert attributes["map_has_live_path"] is True
    assert attributes["map_available_vector_map_count"] == 2
    assert attributes["map_available_vector_maps"] == [
        {"map_id": 1, "map_index": 0, "name": "Primary", "total_area": 10.5},
        {"map_id": 2, "map_index": 1, "name": "Back", "total_area": 8.0},
    ]
    assert attributes["map_details"] == {
        "map_name": "Primary",
        "map_id": 1,
        "map_index": 0,
        "current_map_id": 2,
        "total_area": 10.5,
        "zone_count": 2,
        "zone_names": ["Front Yard", "Back Yard"],
        "contour_count": 1,
        "contour_ids": [[1, 0]],
        "clean_point_count": 1,
        "cruise_point_count": 0,
        "mow_path_count": 1,
        "mow_path_segment_count": 3,
        "mow_path_point_count": 18,
        "mow_path_length_m": 9.87,
        "has_live_path": True,
        "available_map_count": 2,
        "available_maps": [
            {"map_id": 1, "map_index": 0, "name": "Primary", "total_area": 10.5},
            {"map_id": 2, "map_index": 1, "name": "Back", "total_area": 8.0},
        ],
    }


def test_map_camera_attributes_include_app_trajectory_details() -> None:
    """App-map trajectory metadata is promoted into camera attributes."""
    view = DreameLawnMowerMapView(
        source="app_action_map",
        details={
            "map_name": "Garden",
            "map_index": 1,
            "total_area": 550,
            "map_area_total": 550.0,
            "zone_count": 2,
            "spot_area_count": 0,
            "clean_point_count": 0,
            "trajectory_count": 1,
            "trajectory_point_count": 64,
            "trajectory_length_m": 12.34,
            "cut_relation_count": 0,
            "has_live_path": True,
            "current": True,
            "created": True,
        },
    )

    attributes = map_camera_attributes(
        view,
        image_cached=False,
        refreshed_at=None,
        last_error=None,
    )

    assert attributes["map_name"] == "Garden"
    assert attributes["map_total_area"] == 550
    assert attributes["map_zone_count"] == 2
    assert attributes["map_clean_point_count"] == 0
    assert attributes["map_trajectory_count"] == 1
    assert attributes["map_trajectory_point_count"] == 64
    assert attributes["map_trajectory_length_m"] == 12.34
    assert attributes["map_cut_relation_count"] == 0
    assert attributes["map_has_live_path"] is True


def test_map_camera_attributes_report_placeholder_without_view() -> None:
    """Empty cache attributes remain explicit for HA diagnostics."""
    attributes = map_camera_attributes(
        None,
        image_cached=False,
        refreshed_at=None,
        last_error="offline",
    )

    assert attributes["map_cached"] is False
    assert attributes["map_placeholder"] is True
    assert attributes["map_source"] is None
    assert attributes["map_has_image"] is False
    assert attributes["map_error"] == "offline"
    assert attributes["map_available"] is None
    assert attributes["spot_area_count"] is None
    assert attributes["no_go_area_count"] is None
    assert attributes["last_map_refresh"] is None


def test_map_camera_cache_reuses_fresh_view() -> None:
    """Shared camera cache avoids duplicate app-map refreshes."""
    calls = 0
    cache = DreameLawnMowerMapCameraCache(ttl=timedelta(seconds=60))
    first_now = datetime(2026, 4, 19, 8, 0, tzinfo=UTC)

    async def refresh() -> DreameLawnMowerMapView:
        nonlocal calls
        calls += 1
        return DreameLawnMowerMapView(source="app_action_map")

    async def run() -> None:
        first = await cache.async_get_view(refresh, now=first_now)
        second = await cache.async_get_view(
            refresh,
            now=first_now + timedelta(seconds=30),
        )
        assert first is second

    asyncio.run(run())

    assert calls == 1
    assert cache.last_view is not None
    assert cache.last_refresh_at == first_now


def test_map_camera_cache_refreshes_after_ttl() -> None:
    """Expired cache entries are refreshed on demand."""
    calls = 0
    cache = DreameLawnMowerMapCameraCache(ttl=timedelta(seconds=60))
    first_now = datetime(2026, 4, 19, 8, 0, tzinfo=UTC)

    async def refresh() -> DreameLawnMowerMapView:
        nonlocal calls
        calls += 1
        return DreameLawnMowerMapView(source=f"app_action_map_{calls}")

    async def run() -> None:
        first = await cache.async_get_view(refresh, now=first_now)
        second = await cache.async_get_view(
            refresh,
            now=first_now + timedelta(seconds=61),
        )
        assert first.source == "app_action_map_1"
        assert second.source == "app_action_map_2"

    asyncio.run(run())

    assert calls == 2


def test_map_camera_cache_invalidates_image_when_view_refreshes() -> None:
    """A refreshed map view must not reuse an older rendered JPEG."""
    cache = DreameLawnMowerMapCameraCache(ttl=timedelta(seconds=60))
    first_now = datetime(2026, 4, 19, 8, 0, tzinfo=UTC)

    cache.store_view(
        DreameLawnMowerMapView(source="app_action_map", image_png=b"first"),
        now=first_now,
    )
    cache.store_image(b"jpeg-first")

    cache.store_view(
        DreameLawnMowerMapView(source="app_action_map", image_png=b"second"),
        now=first_now + timedelta(seconds=61),
    )

    assert cache.last_image is None
    assert cache.last_view is not None
    assert cache.last_view.image_png == b"second"


def test_map_camera_cache_coalesces_concurrent_refreshes() -> None:
    """Concurrent map camera refreshes share the same in-flight result."""
    calls = 0
    cache = DreameLawnMowerMapCameraCache(ttl=timedelta(seconds=60))
    now = datetime(2026, 4, 19, 8, 0, tzinfo=UTC)

    async def refresh() -> DreameLawnMowerMapView:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return DreameLawnMowerMapView(source="app_action_map")

    async def run() -> None:
        first, second = await asyncio.gather(
            cache.async_get_view(refresh, now=now),
            cache.async_get_view(refresh, now=now),
        )
        assert first is second

    asyncio.run(run())

    assert calls == 1


def test_map_camera_cache_stores_error_view() -> None:
    """Refresh failures are cached as explicit diagnostic map views."""
    cache = DreameLawnMowerMapCameraCache(ttl=timedelta(seconds=60))
    now = datetime(2026, 4, 19, 8, 0, tzinfo=UTC)

    cache.store_view(
        DreameLawnMowerMapView(source="app_action_map", image_png=b"first"),
        now=now - timedelta(seconds=61),
    )
    cache.store_image(b"jpeg-first")

    view = cache.store_error("offline", source="app_action_map", now=now)

    assert view.source == "app_action_map"
    assert view.error == "offline"
    assert cache.last_view is view
    assert cache.last_image is None
    assert cache.last_error == "offline"
    assert cache.last_refresh_at == now


def test_offline_camera_returns_cached_image_without_refreshing() -> None:
    """While the mower is offline, the cached frame is served untouched."""
    import sys
    import types

    if "turbojpeg" not in sys.modules:
        # homeassistant.components.camera imports turbojpeg unconditionally,
        # but the accelerated JPEG library is absent from the test install.
        stub = types.ModuleType("turbojpeg")
        stub.TurboJPEG = object
        sys.modules["turbojpeg"] = stub
    from custom_components.dreame_lawn_mower.camera import DreameLawnMowerMapCamera

    cache = DreameLawnMowerMapCameraCache(ttl=timedelta(seconds=60))
    cache.store_view(
        DreameLawnMowerMapView(source="app_action_map", image_png=b"png"),
        now=datetime(2026, 7, 11, 8, 0, tzinfo=UTC) - timedelta(hours=2),
    )
    cache.store_image(b"jpeg-last-fix")
    refresh_calls: list[bool] = []

    entity = object.__new__(DreameLawnMowerMapCamera)
    entity.coordinator = SimpleNamespace(
        data=SimpleNamespace(available=False),
        client=SimpleNamespace(
            async_refresh_map_view=lambda **kwargs: refresh_calls.append(True),
        ),
    )
    entity._map_cache = cache

    image = asyncio.run(entity._async_get_map_image())

    assert image == b"jpeg-last-fix"
    assert refresh_calls == []
    assert cache.last_image == b"jpeg-last-fix"


def test_cached_frame_helpers_round_trip(tmp_path) -> None:
    from custom_components.dreame_lawn_mower.map_cache import (
        load_cached_frame,
        save_cached_frame,
    )

    path = str(tmp_path / "frame.jpg")

    assert load_cached_frame(path) is None

    save_cached_frame(path, b"jpeg-one")
    restored = load_cached_frame(path)
    assert restored is not None
    assert restored[0] == b"jpeg-one"
    assert restored[1].tzinfo is not None

    save_cached_frame(path, b"jpeg-two")
    restored = load_cached_frame(path)
    assert restored is not None
    assert restored[0] == b"jpeg-two"

    save_cached_frame(path, b"")
    # An empty file is treated as no frame.
    assert load_cached_frame(path) is None


def test_stale_cached_frame_served_with_single_background_refresh() -> None:
    import sys
    import types

    if "turbojpeg" not in sys.modules:
        stub = types.ModuleType("turbojpeg")
        stub.TurboJPEG = object
        sys.modules["turbojpeg"] = stub
    from custom_components.dreame_lawn_mower.camera import DreameLawnMowerMapCamera

    cache = DreameLawnMowerMapCameraCache(ttl=timedelta(seconds=60))
    cache.store_image(b"jpeg-stale")
    cache.last_refresh_at = datetime.now(UTC) - timedelta(hours=1)

    scheduled: list[object] = []

    class _FakeTask:
        def done(self) -> bool:
            return False

    def create_task(coro) -> _FakeTask:
        scheduled.append(coro)
        coro.close()
        return _FakeTask()

    entity = object.__new__(DreameLawnMowerMapCamera)
    entity.coordinator = SimpleNamespace(data=SimpleNamespace(available=True))
    entity._map_cache = cache
    entity._frame_path = None
    entity._last_persisted_frame = None
    entity._map_refresh_task = None
    entity.hass = SimpleNamespace(async_create_task=create_task)

    first = asyncio.run(entity._async_get_map_image())
    second = asyncio.run(entity._async_get_map_image())

    assert first == b"jpeg-stale"
    assert second == b"jpeg-stale"
    # Only one background refresh gets scheduled while the first is in flight.
    assert len(scheduled) == 1


def test_fresh_cached_frame_served_without_any_refresh() -> None:
    import sys
    import types

    if "turbojpeg" not in sys.modules:
        stub = types.ModuleType("turbojpeg")
        stub.TurboJPEG = object
        sys.modules["turbojpeg"] = stub
    from custom_components.dreame_lawn_mower.camera import DreameLawnMowerMapCamera

    cache = DreameLawnMowerMapCameraCache(ttl=timedelta(seconds=60))
    cache.store_image(b"jpeg-fresh")
    cache.last_refresh_at = datetime.now(UTC)

    entity = object.__new__(DreameLawnMowerMapCamera)
    entity.coordinator = SimpleNamespace(data=SimpleNamespace(available=True))
    entity._map_cache = cache
    entity._frame_path = None
    entity._last_persisted_frame = None
    entity._map_refresh_task = None
    entity.hass = SimpleNamespace(
        async_create_task=lambda coro: (_ for _ in ()).throw(
            AssertionError("no refresh expected for a fresh frame")
        )
    )

    assert asyncio.run(entity._async_get_map_image()) == b"jpeg-fresh"


def test_restored_frame_keeps_camera_available_offline() -> None:
    cache = DreameLawnMowerMapCameraCache(ttl=timedelta(seconds=60))
    cache.store_image(b"jpeg-restored")
    snapshot = SimpleNamespace(
        available=False,
        mapping_available=True,
        capabilities=("map",),
    )

    assert (
        map_camera_available(snapshot, image_cached=cache.last_image is not None)
        is True
    )


def _map_camera_stub(cache, *, online=True, create_task=None):
    import sys
    import types

    if "turbojpeg" not in sys.modules:
        stub = types.ModuleType("turbojpeg")
        stub.TurboJPEG = object
        sys.modules["turbojpeg"] = stub
    from custom_components.dreame_lawn_mower.camera import DreameLawnMowerMapCamera

    entity = object.__new__(DreameLawnMowerMapCamera)
    entity.coordinator = SimpleNamespace(data=SimpleNamespace(available=online))
    entity._map_cache = cache
    entity._frame_path = None
    entity._last_persisted_frame = None
    entity._map_refresh_task = None
    entity._held_frame = cache.last_image
    entity.hass = SimpleNamespace(
        async_create_task=create_task
        or (lambda coro: (_ for _ in ()).throw(AssertionError("unexpected task")))
    )
    return entity


def test_held_frame_served_while_cache_is_rebuilding() -> None:
    cache = DreameLawnMowerMapCameraCache(ttl=timedelta(seconds=60))
    cache.store_image(b"jpeg-good")

    scheduled: list[object] = []

    def create_task(coro):
        scheduled.append(coro)
        coro.close()
        return SimpleNamespace(done=lambda: False)

    entity = _map_camera_stub(cache, create_task=create_task)
    # First request records the held frame.
    assert asyncio.run(entity._async_get_map_image()) == b"jpeg-good"
    # A refresh clears the cached image mid-flight (store_view behavior).
    cache.last_image = None

    served = asyncio.run(entity._async_get_map_image())

    # The held frame is served instantly instead of blocking on the cloud.
    assert served == b"jpeg-good"
    assert len(scheduled) >= 1


def test_failed_refresh_restores_held_frame_into_cache() -> None:
    cache = DreameLawnMowerMapCameraCache(ttl=timedelta(seconds=60))
    cache.store_image(b"jpeg-good")
    entity = _map_camera_stub(cache)

    async def failing_refresh():
        # Mirrors _async_refresh_map_view's error path, which wipes the image.
        return cache.store_error("cloud unavailable")

    entity._async_refresh_map_view = failing_refresh
    entity.async_write_ha_state = lambda: None

    served = asyncio.run(entity._async_fetch_map_image())

    assert served == b"jpeg-good"
    assert cache.last_image == b"jpeg-good"
    assert entity.available is True


def test_offline_with_wiped_cache_still_serves_held_frame() -> None:
    cache = DreameLawnMowerMapCameraCache(ttl=timedelta(seconds=60))
    cache.store_image(b"jpeg-good")
    cache.last_refresh_at = datetime.now(UTC)
    entity = _map_camera_stub(cache, online=True)
    assert asyncio.run(entity._async_get_map_image()) == b"jpeg-good"

    # Robot dies right after a refresh wiped the cache.
    cache.store_error("robot went offline")
    entity.coordinator.data = SimpleNamespace(
        available=False,
        mapping_available=True,
        capabilities=("map",),
    )

    assert asyncio.run(entity._async_get_map_image()) == b"jpeg-good"
    assert entity.available is True

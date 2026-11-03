"""Optional diagnostics are listener-driven and cannot break base status."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stirling_pdf.api import StirlingPdfApiError
from custom_components.stirling_pdf.binary_sensor import StirlingPdfOptionalBinarySensor
from custom_components.stirling_pdf.metrics import (
    BOOLEAN_METRICS,
    METRICS,
    Metric,
    languages,
    metric_value,
)
from custom_components.stirling_pdf.sensor import StirlingPdfMetricSensor


@pytest.mark.parametrize(
    ("value", "description", "expected"),
    [
        (4, Metric("x", "x"), 4),
        (0.5, Metric("x", "x"), 0.5),
        (True, Metric("x", "x"), None),
        (-1, Metric("x", "x"), None),
        (float("nan"), Metric("x", "x"), None),
        ("4", Metric("x", "x"), None),
        ({"n": 9}, Metric("x", "x", "n"), 9),
        ({}, Metric("x", "x", "n"), None),
        ("0d 1h 2m 3s", Metric("x", "x", kind="duration"), 3723),
        ("2d 0h 0m 0s", Metric("x", "x", kind="duration"), 172800),
        ("bad", Metric("x", "x", kind="duration"), None),
        (None, Metric("x", "x", kind="duration"), None),
        ("OK", Metric("x", "x", kind="text"), "OK"),
        ("", Metric("x", "x", kind="text"), None),
        ("x" * 256, Metric("x", "x", kind="text"), None),
        (True, Metric("x", "x", kind="boolean"), True),
        (False, Metric("x", "x", kind="boolean"), False),
        (1, Metric("x", "x", kind="boolean"), None),
        (["eng", "deu", "eng", {}, "<html>"], Metric("x", "x", kind="languages"), 2),
        (None, Metric("x", "x", kind="languages"), None),
    ],
)
def test_metric_value_rejects_guesses(value, description, expected) -> None:
    assert metric_value(value, description) == expected


def test_language_attributes_are_bounded_and_sanitized() -> None:
    assert languages(None) == []
    assert languages(["eng", "deu", "eng", "a/b", "x" * 33, {}]) == ["deu", "eng"]
    assert len(languages([f"lang{i}" for i in range(300)])) == 256


async def test_optional_entities_start_disabled_and_do_not_poll(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    metrics = loaded_entry.runtime_data.metrics
    metrics.client.async_get_optional_data = AsyncMock()
    registry = er.async_get(hass)
    for description in (*METRICS, *BOOLEAN_METRICS):
        platform = "binary_sensor" if description.kind == "boolean" else "sensor"
        entity_id = registry.async_get_entity_id(
            platform, "stirling_pdf", f"{loaded_entry.entry_id}_{description.key}"
        )
        assert entity_id is not None
        assert (
            registry.async_get(entity_id).disabled_by
            is er.RegistryEntryDisabler.INTEGRATION
        )
        assert hass.states.get(entity_id) is None
    assert await metrics._async_update_data() == {}
    metrics.client.async_get_optional_data.assert_not_awaited()


async def test_shared_endpoint_is_polled_once_and_errors_are_isolated(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    coordinator = loaded_entry.runtime_data.metrics
    read = AsyncMock(side_effect=[StirlingPdfApiError("unsupported"), {"totalJobs": 4}])
    coordinator.client.async_get_optional_data = read
    remove = [
        coordinator.async_add_listener(lambda: None, context=group)
        for group in ("jobs", "jobs", "ai_status")
    ]
    try:
        data = await coordinator._async_update_data()
        assert data == {"ai_status": None, "jobs": {"totalJobs": 4}}
        assert read.await_count == 2
        assert loaded_entry.runtime_data.last_update_success is True
    finally:
        for listener in remove:
            listener()


async def test_all_optional_entity_properties_and_lifecycle(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    coordinator = loaded_entry.runtime_data.metrics
    coordinator.async_request_refresh = AsyncMock()
    with patch.object(CoordinatorEntity, "async_added_to_hass", new=AsyncMock()):
        for description in METRICS:
            entity = StirlingPdfMetricSensor(coordinator, loaded_entry, description)
            coordinator.async_set_updated_data({})
            assert entity.available is False
            assert entity.native_value is None
            raw = (
                ["eng"]
                if description.kind == "languages"
                else "0d 0h 0m 1s"
                if description.kind == "duration"
                else "value"
                if description.kind == "text"
                else 1
            )
            coordinator.async_set_updated_data(
                {
                    description.group: {description.field: raw}
                    if description.field
                    else raw
                }
            )
            assert entity.available is True
            if description.kind == "languages":
                assert entity.extra_state_attributes == {"languages": ["eng"]}
                coordinator.async_set_updated_data({})
                assert entity.extra_state_attributes is None
            else:
                assert entity.extra_state_attributes is None
            await entity.async_added_to_hass()
        for description in BOOLEAN_METRICS:
            entity = StirlingPdfOptionalBinarySensor(
                coordinator, loaded_entry, description
            )
            coordinator.async_set_updated_data({})
            assert entity.available is False
            coordinator.async_set_updated_data(
                {description.group: {description.field: False}}
            )
            assert entity.available is True
            assert entity.is_on is False
            await entity.async_added_to_hass()
    assert coordinator.async_request_refresh.await_count == len(METRICS) + len(
        BOOLEAN_METRICS
    )

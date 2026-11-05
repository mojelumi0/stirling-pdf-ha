"""Optional diagnostics are listener-driven and cannot break base status."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import MAX_LENGTH_STATE_STATE, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stirling_pdf.api import StirlingPdfApiError
from custom_components.stirling_pdf.binary_sensor import StirlingPdfOptionalBinarySensor
from custom_components.stirling_pdf.const import DOMAIN
from custom_components.stirling_pdf.metrics import (
    BOOLEAN_METRICS,
    METRICS,
    Metric,
    languages,
    metric_value,
)
from custom_components.stirling_pdf.sensor import StirlingPdfMetricSensor


@pytest.fixture
async def enabled_metric_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    enable_custom_integrations: None,
) -> AsyncIterator[MockConfigEntry]:
    """Enable one real platform entity before setup; keep backend HTTP mocked."""
    er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        f"{mock_config_entry.entry_id}_total_jobs",
        config_entry=mock_config_entry,
        suggested_object_id="stirling_metric_regression",
        disabled_by=None,
    )
    with (
        patch(
            "custom_components.stirling_pdf.api.StirlingPdfApiClient.async_validate_connection",
            new=AsyncMock(return_value={"status": "UP", "version": "3.2.0"}),
        ),
        patch(
            "custom_components.stirling_pdf.api.StirlingPdfApiClient.async_get_optional_data",
            new=AsyncMock(return_value={"totalJobs": 7}),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield mock_config_entry


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


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0),
        (2**63 - 1, 2**63 - 1),
        (2**80, 2**80),
        (10**MAX_LENGTH_STATE_STATE - 1, 10**MAX_LENGTH_STATE_STATE - 1),
        (10**MAX_LENGTH_STATE_STATE, None),
        (10**400, None),
        (-(10**400), None),
        pytest.param(10**5000, None, id="above-python-int-text-limit"),
        (True, None),
        (False, None),
    ],
)
@pytest.mark.parametrize("as_mapping", [False, True])
def test_integer_metrics_are_exact_bounded_and_never_converted_to_float(
    value, expected, as_mapping: bool
) -> None:
    description = Metric("x", "jobs", "totalJobs" if as_mapping else "")
    data = {"totalJobs": value} if as_mapping else value
    with patch("custom_components.stirling_pdf.metrics.math.isfinite") as isfinite:
        result = metric_value(data, description)
        isfinite.assert_not_called()
    assert result == expected
    if result is not None:
        assert type(result) is int


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, 0.0),
        (0.5, 0.5),
        (1e308, 1e308),
        (-0.5, None),
        (float("inf"), None),
        (-float("inf"), None),
        (float("nan"), None),
    ],
)
def test_float_metric_validation_remains_finite_and_non_negative(
    value, expected
) -> None:
    assert metric_value(value, Metric("x", "x")) == expected


def test_uptime_input_is_bounded_before_integer_parsing() -> None:
    description = Metric("uptime", "uptime", kind="duration")
    assert metric_value("9" * 5000 + "d 0h 0m 0s", description) is None
    assert metric_value("1d 2h 3m 4s", description) == 93784


@pytest.mark.parametrize(
    "invalid_value",
    [
        10**MAX_LENGTH_STATE_STATE,
        10**400,
        pytest.param(10**5000, id="huge-integer"),
        -(10**400),
        True,
        False,
        float("inf"),
        float("nan"),
    ],
)
async def test_optional_metric_entity_publishes_unavailable_and_recovers(
    hass: HomeAssistant, enabled_metric_entry: MockConfigEntry, invalid_value
) -> None:
    """Use HA's real sensor state validation and state-machine write path."""
    coordinator = enabled_metric_entry.runtime_data.metrics
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{enabled_metric_entry.entry_id}_total_jobs"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id) is not None
    for value, expected in [(7, "7"), (invalid_value, STATE_UNAVAILABLE), (9, "9")]:
        coordinator.async_set_updated_data({"jobs": {"totalJobs": value}})
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected
        assert enabled_metric_entry.runtime_data.last_update_success is True
        assert enabled_metric_entry.runtime_data.jobs_processed == 0
        assert enabled_metric_entry.runtime_data.last_operation is None


async def test_largest_supported_integer_survives_actual_ha_state_validation(
    hass: HomeAssistant, enabled_metric_entry: MockConfigEntry
) -> None:
    coordinator = enabled_metric_entry.runtime_data.metrics
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{enabled_metric_entry.entry_id}_total_jobs"
    )
    assert entity_id is not None
    value = 10**MAX_LENGTH_STATE_STATE - 1
    coordinator.async_set_updated_data({"jobs": {"totalJobs": value}})
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == str(value)
    assert len(state.state) == MAX_LENGTH_STATE_STATE


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


@pytest.mark.parametrize(
    ("platform", "suffix", "group", "expected"),
    [
        ("sensor", "total_jobs", "jobs", "7"),
        ("binary_sensor", "ai_enabled", "ai_status", "on"),
    ],
)
async def test_optional_metric_device_identity_and_listener_survive_registry_rename(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    enable_custom_integrations: None,
    platform: str,
    suffix: str,
    group: str,
    expected: str,
) -> None:
    """Exercise actual enabled optional entities, not just their Python properties."""
    registry = er.async_get(hass)
    registered = registry.async_get_or_create(
        platform,
        DOMAIN,
        f"{mock_config_entry.entry_id}_{suffix}",
        config_entry=mock_config_entry,
        suggested_object_id=f"optional_{suffix}",
        disabled_by=None,
    )
    with (
        patch(
            "custom_components.stirling_pdf.api.StirlingPdfApiClient.async_validate_connection",
            new=AsyncMock(return_value={"status": "UP", "version": "3.2.2"}),
        ),
        patch(
            "custom_components.stirling_pdf.api.StirlingPdfApiClient.async_get_optional_data",
            new=AsyncMock(return_value={"totalJobs": 7, "enabled": True}),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        device = dr.async_get(hass).async_get_device_by_identifier(
            (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
        )
        assert device is not None
        assert registry.async_get(registered.entity_id).device_id == device.id
        assert hass.states.get(registered.entity_id).state == expected
        metrics = mock_config_entry.runtime_data.metrics
        assert list(metrics.async_contexts()) == [group]

        renamed = f"{platform}.renamed_optional_{suffix}"
        registry.async_update_entity(registered.entity_id, new_entity_id=renamed)
        await hass.async_block_till_done()
        assert hass.states.get(registered.entity_id) is None
        assert registry.async_get(renamed).id == registered.id
        assert registry.async_get(renamed).device_id == device.id
        assert list(metrics.async_contexts()) == [group]

        metrics.async_set_updated_data({group: None})
        await hass.async_block_till_done()
        assert hass.states.get(renamed).state == STATE_UNAVAILABLE
        metrics.async_set_updated_data({group: {"totalJobs": 7, "enabled": True}})
        await hass.async_block_till_done()
        assert hass.states.get(renamed).state == expected

        assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert registry.async_get(renamed).id == registered.id
        assert registry.async_get(renamed).device_id == device.id
        assert hass.states.get(renamed).state == expected
        assert list(mock_config_entry.runtime_data.metrics.async_contexts()) == [group]
        assert mock_config_entry.runtime_data.jobs_processed == 0

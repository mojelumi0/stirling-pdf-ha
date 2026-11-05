"""Sensors for Stirling PDF."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SERVICES
from .coordinator import StirlingPdfCoordinator
from .entity import StirlingPdfEntity
from .metrics import (
    METRICS,
    Metric,
    StirlingPdfMetricsCoordinator,
    languages,
    metric_value,
)

# Entity updates are supplied by the shared coordinator, not individual polls.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Stirling PDF sensors."""
    coordinator: StirlingPdfCoordinator = entry.runtime_data
    async_add_entities(
        [
            StirlingPdfVersionSensor(coordinator, entry),
            StirlingPdfJobsProcessedSensor(coordinator, entry),
            StirlingPdfLastOperationSensor(coordinator, entry),
            *[
                StirlingPdfMetricSensor(coordinator.metrics, entry, description)
                for description in METRICS
            ],
        ]
    )


class StirlingPdfVersionSensor(StirlingPdfEntity, SensorEntity):
    """Report the server version."""

    _attr_translation_key = "version"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: StirlingPdfCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_version"

    @property
    def native_value(self) -> str | None:
        """Return the version from known response keys."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("version") or self.coordinator.data.get(
            "appVersion"
        )


class StirlingPdfJobsProcessedSensor(StirlingPdfEntity, SensorEntity):
    """Count successful actions run through this integration."""

    _attr_translation_key = "jobs_processed"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: StirlingPdfCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_jobs_processed"

    @property
    def available(self) -> bool:
        """Keep locally recorded statistics available during API outages."""
        return True

    @property
    def native_value(self) -> int:
        """Return the local successful-operation count."""
        return self.coordinator.jobs_processed


class StirlingPdfLastOperationSensor(StirlingPdfEntity, SensorEntity):
    """Report the last successful action run through this integration."""

    _attr_translation_key = "last_operation"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(SERVICES)

    def __init__(self, coordinator: StirlingPdfCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_operation"

    @property
    def available(self) -> bool:
        """Keep locally recorded statistics available during API outages."""
        return True

    @property
    def native_value(self) -> str | None:
        """Return the most recent successful action name."""
        return self.coordinator.last_operation

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the UTC timestamp of the latest successful action."""
        if self.coordinator.last_operation_time is None:
            return None
        return {"last_run": self.coordinator.last_operation_time.isoformat()}


class StirlingPdfMetricSensor(
    CoordinatorEntity[StirlingPdfMetricsCoordinator], SensorEntity
):
    """An optional diagnostic sensor, with no polling while it is disabled."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: StirlingPdfMetricsCoordinator,
        entry: ConfigEntry,
        description: Metric,
    ) -> None:
        super().__init__(coordinator, context=description.group)
        self.description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_native_unit_of_measurement = description.unit
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})
        # Job counts are a retained snapshot, not monotonic historical totals.
        if description.kind in ("number", "duration"):
            self._attr_state_class = SensorStateClass.MEASUREMENT

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self.coordinator.async_request_refresh()

    @property
    def native_value(self) -> int | float | str | None:
        return metric_value(
            (self.coordinator.data or {}).get(self.description.group), self.description
        )

    @property
    def available(self) -> bool:
        return self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.description.kind != "languages":
            return None
        data = (self.coordinator.data or {}).get(self.description.group)
        return (
            {"languages": languages(data.get("languages"))}
            if isinstance(data, dict)
            else None
        )

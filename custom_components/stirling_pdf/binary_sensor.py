"""Binary sensor for Stirling PDF."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StirlingPdfCoordinator
from .entity import StirlingPdfEntity
from .metrics import (
    BOOLEAN_METRICS,
    Metric,
    StirlingPdfMetricsCoordinator,
    metric_value,
)

# Entity updates are supplied by the shared coordinator, not individual polls.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Stirling PDF connectivity sensor."""
    coordinator: StirlingPdfCoordinator = entry.runtime_data
    async_add_entities(
        [
            StirlingPdfReachableSensor(coordinator, entry),
            *[
                StirlingPdfOptionalBinarySensor(coordinator.metrics, entry, metric)
                for metric in BOOLEAN_METRICS
            ],
        ]
    )


class StirlingPdfReachableSensor(StirlingPdfEntity, BinarySensorEntity):
    """Report whether the most recent status request succeeded."""

    _attr_translation_key = "reachable"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: StirlingPdfCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_reachable"

    @property
    def available(self) -> bool:
        """Keep the entity available so a failed poll is represented as off."""
        return True

    @property
    def is_on(self) -> bool:
        """Return whether the last coordinator update succeeded."""
        return self.coordinator.last_update_success


class StirlingPdfOptionalBinarySensor(
    CoordinatorEntity[StirlingPdfMetricsCoordinator], BinarySensorEntity
):
    """An opt-in capability indication, never a control for the server."""

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
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self.coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        return self.is_on is not None

    @property
    def is_on(self) -> bool | None:
        value = metric_value(
            (self.coordinator.data or {}).get(self.description.group), self.description
        )
        return value if isinstance(value, bool) else None

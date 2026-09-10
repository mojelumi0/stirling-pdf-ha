"""Binary sensor for Stirling PDF."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import StirlingPdfCoordinator
from .entity import StirlingPdfEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Stirling PDF connectivity sensor."""
    coordinator: StirlingPdfCoordinator = entry.runtime_data
    async_add_entities([StirlingPdfReachableSensor(coordinator, entry)])


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

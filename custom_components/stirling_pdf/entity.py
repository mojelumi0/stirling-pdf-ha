"""Shared entity base class for Stirling PDF."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StirlingPdfCoordinator


class StirlingPdfEntity(CoordinatorEntity[StirlingPdfCoordinator]):
    """Represent an entity belonging to the configured Stirling PDF server."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: StirlingPdfCoordinator, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        data = coordinator.data or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Stirling PDF",
            model="Server",
            sw_version=data.get("version") or data.get("appVersion"),
            configuration_url=coordinator.client.base_url,
        )

"""Config flow for Stirling PDF."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from yarl import URL

from .api import (
    StirlingPdfApiClient,
    StirlingPdfApiError,
    StirlingPdfAuthError,
    StirlingPdfConnectionError,
    StirlingPdfInvalidUrlError,
    normalize_base_url,
)
from .const import DEFAULT_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _data_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the configuration schema with suggested defaults."""
    values = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_URL, default=values.get(CONF_URL, DEFAULT_URL)
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
            vol.Optional(
                CONF_API_KEY, default=values.get(CONF_API_KEY, "")
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        }
    )


async def _async_validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Verify credentials and connectivity using the status endpoint."""
    client = StirlingPdfApiClient(
        async_get_clientsession(hass),
        data[CONF_URL],
        data.get(CONF_API_KEY),
    )
    await client.async_get_status()


class StirlingPdfConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Stirling PDF."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial setup."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        data = user_input
        if user_input is not None:
            data, errors = await self._async_validate_and_normalize(user_input)
            if not errors:
                assert data is not None
                host = URL(data[CONF_URL]).host or data[CONF_URL]
                return self.async_create_entry(
                    title=f"Stirling PDF ({host})",
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_data_schema(data),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow the URL and API key to be changed."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        data = user_input
        if user_input is not None:
            data, errors = await self._async_validate_and_normalize(user_input)
            if not errors:
                assert data is not None
                host = URL(data[CONF_URL]).host or data[CONF_URL]
                return self.async_update_reload_and_abort(
                    entry,
                    title=f"Stirling PDF ({host})",
                    data_updates=data,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_data_schema(data or dict(entry.data)),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Start reauthentication after the server rejects the API key."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and save a replacement API key."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(entry.data) | {CONF_API_KEY: user_input.get(CONF_API_KEY, "")}
            try:
                await _async_validate_input(self.hass, data)
            except StirlingPdfAuthError:
                errors["base"] = "invalid_auth"
            except StirlingPdfConnectionError:
                errors["base"] = "cannot_connect"
            except StirlingPdfApiError:
                _LOGGER.exception("Unexpected API response during reauthentication")
                errors["base"] = "unknown"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during reauthentication")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_API_KEY: data[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_API_KEY, default=entry.data.get(CONF_API_KEY, "")
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
                }
            ),
            errors=errors,
        )

    async def _async_validate_and_normalize(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, dict[str, str]]:
        """Normalize a form submission and return any form errors."""
        try:
            normalized_url = normalize_base_url(user_input[CONF_URL])
        except StirlingPdfInvalidUrlError:
            return user_input, {"base": "invalid_url"}

        data = dict(user_input)
        data[CONF_URL] = normalized_url
        try:
            await _async_validate_input(self.hass, data)
        except StirlingPdfAuthError:
            return data, {"base": "invalid_auth"}
        except StirlingPdfConnectionError:
            return data, {"base": "cannot_connect"}
        except StirlingPdfApiError:
            _LOGGER.exception("Unexpected API response during connection validation")
            return data, {"base": "unknown"}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected exception during connection validation")
            return data, {"base": "unknown"}
        return data, {}

"""Config flow for Stirling PDF."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_URL, CONF_USERNAME
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
    StirlingPdfInvalidBasicAuthError,
    StirlingPdfInvalidUrlError,
    StirlingPdfStatusEndpointDisabledError,
    normalize_base_url,
)
from .const import API_KEY_PLACEHOLDER, DEFAULT_URL, DOMAIN, PASSWORD_PLACEHOLDER

_LOGGER = logging.getLogger(__name__)


def _credential_schema(defaults: dict[str, Any]) -> dict[vol.Marker, Any]:
    """Never send stored or previously submitted secrets back to the frontend."""
    return {
        # Suggestions, unlike defaults, let the frontend omit cleared fields.
        vol.Optional(
            CONF_API_KEY,
            description={
                "suggested_value": (
                    API_KEY_PLACEHOLDER if defaults.get(CONF_API_KEY) else ""
                )
            },
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        vol.Optional(
            CONF_USERNAME,
            description={"suggested_value": defaults.get(CONF_USERNAME, "")},
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Optional(
            CONF_PASSWORD,
            description={
                "suggested_value": (
                    PASSWORD_PLACEHOLDER if defaults.get(CONF_PASSWORD) else ""
                )
            },
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    }


def _data_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the server URL and optional authentication fields."""
    values = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_URL, default=values.get(CONF_URL, DEFAULT_URL)
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
            **_credential_schema(values),
        }
    )


def _submitted_credentials(
    user_input: dict[str, Any], previous: dict[str, Any]
) -> dict[str, Any]:
    """Resolve unchanged secrets and explicitly save cleared optional fields."""
    data = dict(user_input)
    data[CONF_API_KEY] = data.get(CONF_API_KEY, "")
    basic_fields = (CONF_USERNAME, CONF_PASSWORD)
    if any(field in data or field in previous for field in basic_fields):
        for field in basic_fields:
            data.setdefault(field, "")
    for field, placeholder in (
        (CONF_API_KEY, API_KEY_PLACEHOLDER),
        (CONF_PASSWORD, PASSWORD_PLACEHOLDER),
    ):
        if data.get(field) == placeholder:
            data[field] = previous.get(field, "")
    return data


async def _async_validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Verify connectivity and, when supported, API access."""
    client = StirlingPdfApiClient(
        async_get_clientsession(hass),
        data[CONF_URL],
        data.get(CONF_API_KEY),
        username=data.get(CONF_USERNAME),
        password=data.get(CONF_PASSWORD),
    )
    await client.async_validate_connection()


class StirlingPdfConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Stirling PDF."""

    VERSION = 1

    def __init__(self) -> None:
        """Keep submitted secrets inside the flow during recoverable errors."""
        super().__init__()
        self._user_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial setup."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        data = user_input
        if user_input is not None:
            submitted = _submitted_credentials(user_input, self._user_data)
            data, errors = await self._async_validate_and_normalize(submitted)
            self._user_data = data or {}
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
        """Allow the URL and authentication credentials to be changed."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        data = user_input
        if user_input is not None:
            submitted_data = _submitted_credentials(
                user_input, self._user_data or dict(entry.data)
            )
            data, errors = await self._async_validate_and_normalize(submitted_data)
            self._user_data = data or {}
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
        """Start reauthentication after the server rejects API access."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate replacement credentials without prefilling rejected secrets."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            credentials = _submitted_credentials(user_input, dict(entry.data))
            data, errors = await self._async_validate_and_normalize(
                dict(entry.data) | credentials
            )
            if not errors:
                assert data is not None
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=data,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                _credential_schema({CONF_USERNAME: entry.data.get(CONF_USERNAME, "")})
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
        # The frontend omits a cleared optional field. Save an explicit empty key
        # so a successful reconfiguration removes, rather than retains, the old key.
        data[CONF_API_KEY] = user_input.get(CONF_API_KEY, "")
        try:
            await _async_validate_input(self.hass, data)
        except StirlingPdfInvalidBasicAuthError:
            return data, {"base": "invalid_basic_auth"}
        except StirlingPdfAuthError:
            return data, {"base": "invalid_auth"}
        except StirlingPdfConnectionError:
            return data, {"base": "cannot_connect"}
        except StirlingPdfStatusEndpointDisabledError:
            return data, {"base": "status_endpoint_disabled"}
        except StirlingPdfApiError:
            _LOGGER.exception("Unexpected API response during connection validation")
            return data, {"base": "unknown"}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected exception during connection validation")
            return data, {"base": "unknown"}
        return data, {}

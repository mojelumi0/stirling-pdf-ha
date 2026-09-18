"""Tests for the Stirling PDF config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stirling_pdf.api import (
    StirlingPdfApiError,
    StirlingPdfAuthError,
    StirlingPdfConnectionError,
    StirlingPdfStatusEndpointDisabledError,
)
from custom_components.stirling_pdf.const import API_KEY_PLACEHOLDER, DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """Test a successful setup from the UI."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.stirling_pdf.config_flow._async_validate_input",
        new=AsyncMock(),
    ) as validate:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: " HTTP://PDF.LOCAL:8080/ ",
                CONF_API_KEY: "new-secret",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Stirling PDF (pdf.local)"
    assert result["data"] == {
        CONF_URL: "http://pdf.local:8080",
        CONF_API_KEY: "new-secret",
    }
    validate.assert_awaited_once_with(
        hass,
        {
            CONF_URL: "http://pdf.local:8080",
            CONF_API_KEY: "new-secret",
        },
    )


@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        (StirlingPdfAuthError("bad key"), "invalid_auth"),
        (StirlingPdfConnectionError("offline"), "cannot_connect"),
        (
            StirlingPdfStatusEndpointDisabledError("disabled"),
            "status_endpoint_disabled",
        ),
        (StirlingPdfApiError("bad response"), "unknown"),
    ],
)
async def test_user_flow_reports_connection_errors(
    hass: HomeAssistant,
    error: Exception,
    expected_error: str,
) -> None:
    """Test that typed client failures become useful form errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        "custom_components.stirling_pdf.config_flow._async_validate_input",
        new=AsyncMock(side_effect=error),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://pdf.local:8080", CONF_API_KEY: "secret"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_user_flow_rejects_invalid_url(hass: HomeAssistant) -> None:
    """Test URL validation before a network request is attempted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        "custom_components.stirling_pdf.config_flow._async_validate_input",
        new=AsyncMock(),
    ) as validate:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "pdf.local:8080", CONF_API_KEY: ""},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url"}
    validate.assert_not_awaited()


async def test_user_flow_allows_only_one_instance(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a second Stirling PDF instance is rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_reconfigure_never_exposes_stored_api_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that reconfigure uses a placeholder instead of the stored secret."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    defaults = result["data_schema"]({})
    assert defaults == {
        CONF_URL: "http://pdf.local:8080",
        CONF_API_KEY: API_KEY_PLACEHOLDER,
    }
    assert "stored-secret" not in repr(result["data_schema"])


async def test_reconfigure_keeps_api_key_when_placeholder_is_unchanged(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test retaining the stored key without sending it to the frontend."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    with patch(
        "custom_components.stirling_pdf.config_flow._async_validate_input",
        new=AsyncMock(),
    ) as validate:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "http://new-pdf.local:8080",
                CONF_API_KEY: API_KEY_PLACEHOLDER,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_URL: "http://new-pdf.local:8080",
        CONF_API_KEY: "stored-secret",
    }
    validate.assert_awaited_once_with(
        hass,
        {
            CONF_URL: "http://new-pdf.local:8080",
            CONF_API_KEY: "stored-secret",
        },
    )


@pytest.mark.parametrize(
    ("submitted_key", "saved_key"),
    [("replacement-secret", "replacement-secret"), ("", "")],
)
async def test_reconfigure_replaces_or_removes_api_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    submitted_key: str,
    saved_key: str,
) -> None:
    """Test replacing and explicitly clearing the stored key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    with patch(
        "custom_components.stirling_pdf.config_flow._async_validate_input",
        new=AsyncMock(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "http://pdf.local:8080",
                CONF_API_KEY: submitted_key,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert mock_config_entry.data[CONF_API_KEY] == saved_key


async def test_reauth_form_is_blank_and_saves_replacement(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that reauthentication never pre-fills the rejected key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=dict(mock_config_entry.data),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["data_schema"]({})[CONF_API_KEY] == ""
    assert "stored-secret" not in repr(result["data_schema"])

    with patch(
        "custom_components.stirling_pdf.config_flow._async_validate_input",
        new=AsyncMock(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "replacement-secret"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "replacement-secret"

"""Tests for the Stirling PDF config flow."""

from __future__ import annotations

from collections.abc import Iterator
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


@pytest.fixture(autouse=True)
def mock_entry_setup() -> Iterator[None]:
    """Keep background entry setup/reloads out of these isolated flow tests."""
    with (
        patch(
            "custom_components.stirling_pdf.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "custom_components.stirling_pdf.async_unload_entry",
            new=AsyncMock(return_value=True),
        ),
    ):
        yield


async def _async_recover_user(hass: HomeAssistant, flow_id: str) -> None:
    """Finish the same flow after correcting the input or server problem."""
    expected = {CONF_URL: "http://pdf.local:8080", CONF_API_KEY: "correct-key"}
    with patch(
        "custom_components.stirling_pdf.config_flow._async_validate_input",
        new=AsyncMock(),
    ) as validate:
        result = await hass.config_entries.flow.async_configure(flow_id, expected)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == expected
    # Uniqueness deliberately uses the single-instance guard, not a mutable IP.
    assert result["result"].unique_id is None
    validate.assert_awaited_once_with(hass, expected)
    await hass.async_block_till_done()


async def _async_recover_existing(
    hass: HomeAssistant,
    flow_id: str,
    entry: MockConfigEntry,
    source: str,
) -> None:
    """Recover a reconfigure/reauth flow without replacing its config entry."""
    original_entry_id = entry.entry_id
    original_unique_id = entry.unique_id
    submitted = {CONF_API_KEY: "correct-key"}
    expected = {**entry.data, CONF_API_KEY: "correct-key"}
    if source == config_entries.SOURCE_RECONFIGURE:
        submitted[CONF_URL] = "http://new-pdf.local:8080"
        expected[CONF_URL] = submitted[CONF_URL]
    with patch(
        "custom_components.stirling_pdf.config_flow._async_validate_input",
        new=AsyncMock(),
    ) as validate:
        result = await hass.config_entries.flow.async_configure(flow_id, submitted)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == f"{source}_successful"
    assert entry.entry_id == original_entry_id
    assert entry.unique_id == original_unique_id
    assert entry.data == expected
    validate.assert_awaited_once_with(hass, expected)
    await hass.async_block_till_done()


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
    assert result["result"].unique_id is None
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


async def test_user_flow_accepts_omitted_key_when_server_allows_it(
    hass: HomeAssistant,
) -> None:
    """Keep setup without authentication possible when no key is required."""
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
            {CONF_URL: "http://pdf.local:8080"},
        )

    expected_data = {CONF_URL: "http://pdf.local:8080", CONF_API_KEY: ""}
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == expected_data
    assert result["result"].unique_id is None
    validate.assert_awaited_once_with(hass, expected_data)


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
        (RuntimeError("unexpected failure"), "unknown"),
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
    await _async_recover_user(hass, result["flow_id"])


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
    await _async_recover_user(hass, result["flow_id"])


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


async def test_user_flow_rejects_entry_created_while_form_is_open(
    hass: HomeAssistant,
) -> None:
    """Exercise the integration guard, not just HA's pre-flow instance check."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    # HA checks single_config_entry before starting a flow. An entry added
    # afterwards must also be rejected when this already-open form is submitted.
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Stirling PDF (existing.local)",
        data={CONF_URL: "http://existing.local:8080", CONF_API_KEY: "existing-key"},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.stirling_pdf.config_flow._async_validate_input",
        new=AsyncMock(),
    ) as validate:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://another.local:8080", CONF_API_KEY: "another-key"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    validate.assert_not_awaited()
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert entry.data == {
        CONF_URL: "http://existing.local:8080",
        CONF_API_KEY: "existing-key",
    }


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
    schema = result["data_schema"]
    api_key_field = next(
        field for field in schema.schema if field.schema == CONF_API_KEY
    )
    assert api_key_field.description == {"suggested_value": API_KEY_PLACEHOLDER}
    # A cleared optional field is omitted by the frontend. The schema must not
    # reinsert the keep-key placeholder as a default in that case.
    assert schema({}) == {CONF_URL: "http://pdf.local:8080"}
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
    [("replacement-secret", "replacement-secret"), ("", ""), (None, "")],
    ids=["replacement", "explicit-empty", "frontend-omits-empty"],
)
async def test_reconfigure_replaces_or_removes_api_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    submitted_key: str | None,
    saved_key: str,
) -> None:
    """Remove a key only after the server accepts unauthenticated access."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    submitted_data = {CONF_URL: "http://pdf.local:8080"}
    if submitted_key is not None:
        submitted_data[CONF_API_KEY] = submitted_key

    with patch(
        "custom_components.stirling_pdf.config_flow._async_validate_input",
        new=AsyncMock(),
    ) as validate:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            submitted_data,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_API_KEY] == saved_key
    validate.assert_awaited_once_with(
        hass,
        {CONF_URL: "http://pdf.local:8080", CONF_API_KEY: saved_key},
    )


@pytest.mark.parametrize("omit_key", [False, True], ids=["explicit-empty", "omitted"])
async def test_reconfigure_rejects_removing_required_api_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    omit_key: bool,
) -> None:
    """A rejected empty key must not silently keep or replace the stored key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )
    submitted_data = {CONF_URL: "http://pdf.local:8080"}
    if not omit_key:
        submitted_data[CONF_API_KEY] = ""

    with patch(
        "custom_components.stirling_pdf.config_flow._async_validate_input",
        new=AsyncMock(side_effect=StirlingPdfAuthError("Missing key")),
    ) as validate:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], submitted_data
        )

    validate.assert_awaited_once_with(
        hass,
        {CONF_URL: "http://pdf.local:8080", CONF_API_KEY: ""},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert mock_config_entry.data[CONF_API_KEY] == "stored-secret"
    await _async_recover_existing(
        hass, result["flow_id"], mock_config_entry, config_entries.SOURCE_RECONFIGURE
    )


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


async def test_user_validation_checks_access_after_public_status(
    hass: HomeAssistant,
) -> None:
    """Reject a missing key even when status is publicly reachable."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    with (
        patch(
            "custom_components.stirling_pdf.api.StirlingPdfApiClient.async_get_status",
            new=AsyncMock(return_value={"status": "UP", "version": "3.2.0"}),
        ),
        patch(
            "custom_components.stirling_pdf.api.StirlingPdfApiClient.async_check_authentication",
            new=AsyncMock(side_effect=StirlingPdfAuthError("Missing key")),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://pdf.local", CONF_API_KEY: ""},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    await _async_recover_user(hass, result["flow_id"])


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
        (RuntimeError("unexpected failure"), "unknown"),
    ],
)
async def test_reauth_reports_errors_and_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    error: Exception,
    expected_error: str,
) -> None:
    """Do not save another rejected key or clear the reauth request."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=dict(mock_config_entry.data),
    )
    with patch(
        "custom_components.stirling_pdf.config_flow._async_validate_input",
        new=AsyncMock(side_effect=error),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "wrong-again"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    assert mock_config_entry.data[CONF_API_KEY] == "stored-secret"
    await _async_recover_existing(
        hass, result["flow_id"], mock_config_entry, config_entries.SOURCE_REAUTH
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
        (RuntimeError("unexpected failure"), "unknown"),
    ],
)
async def test_reconfigure_reports_errors_and_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    error: Exception,
    expected_error: str,
) -> None:
    """Leave saved settings intact on failure and accept a corrected submission."""
    original_data = dict(mock_config_entry.data)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )
    with patch(
        "custom_components.stirling_pdf.config_flow._async_validate_input",
        new=AsyncMock(side_effect=error),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "http://new-pdf.local:8080", CONF_API_KEY: "wrong-key"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    assert mock_config_entry.data == original_data
    assert "stored-secret" not in repr(result["data_schema"])
    assert "wrong-key" not in repr(result["data_schema"])
    await _async_recover_existing(
        hass, result["flow_id"], mock_config_entry, config_entries.SOURCE_RECONFIGURE
    )


async def test_reconfigure_invalid_url_can_be_corrected(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Reject a malformed changed URL locally, then recover in the same flow."""
    original_data = dict(mock_config_entry.data)
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
            {CONF_URL: "not-a-url", CONF_API_KEY: API_KEY_PLACEHOLDER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url"}
    validate.assert_not_awaited()
    assert mock_config_entry.data == original_data
    await _async_recover_existing(
        hass, result["flow_id"], mock_config_entry, config_entries.SOURCE_RECONFIGURE
    )


@pytest.mark.parametrize("source", ["reconfigure", "reauth"])
async def test_existing_entry_without_key_can_use_an_unauthenticated_server(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, source: str
) -> None:
    """Accept an omitted optional key for legacy entries without authentication."""
    hass.config_entries.async_update_entry(
        mock_config_entry, data={CONF_URL: "http://pdf.local:8080"}
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": mock_config_entry.entry_id},
        data=dict(mock_config_entry.data) if source == "reauth" else None,
    )
    assert result["type"] is FlowResultType.FORM
    submitted = {CONF_URL: "http://pdf.local:8080"} if source == "reconfigure" else {}
    with patch(
        "custom_components.stirling_pdf.config_flow._async_validate_input",
        new=AsyncMock(),
    ) as validate:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], submitted
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == f"{source}_successful"
    assert mock_config_entry.data[CONF_API_KEY] == ""
    validate.assert_awaited_once_with(
        hass, {CONF_URL: "http://pdf.local:8080", CONF_API_KEY: ""}
    )

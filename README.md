# Stirling PDF for Home Assistant

Use your self-hosted [Stirling PDF](https://www.stirlingpdf.com/) server from Home
Assistant. Merge scans, extract pages, run OCR or compress a file as part of an
automation.

[![Install with Marketplace or HACS](https://img.shields.io/badge/Marketplace%20%2F%20HACS-Custom-41BDF5.svg?logo=home-assistant)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mojelumi0&repository=stirling-pdf-ha&category=integration)

This is a custom integration for Home Assistant **2026.9.0 or newer**. You need
a Stirling PDF server that Home Assistant can reach.

> **Trying the 0.4.0 alpha?** Back up Home Assistant and use copies of your PDFs.
> Stay on a regular release for everyday use. Do not downgrade a setup with
> multiple server entries to 0.3.x, which only supports one.

## Installation

### Marketplace (Home Assistant 2026.11 or newer)

1. Open **Settings > Marketplace**. If you already installed Stirling PDF
   through HACS, keep your existing integration entry. See
   [Coming from HACS](https://www.home-assistant.io/integrations/marketplace/#coming-from-hacs).
2. Use the install button above or choose **Add from link** and enter
   `https://github.com/mojelumi0/stirling-pdf-ha`. Connect GitHub if prompted.
3. Open **Stirling PDF** in the Marketplace and select **Install**. Follow
   any restart prompt before setting up the integration.

This repository can be added as a custom repository. That is not the same as
being listed in the public catalog.

### HACS (Home Assistant before 2026.11)

Use the install button above, or add `mojelumi0/stirling-pdf-ha` as a custom
**Integration** repository in HACS. Download **Stirling PDF**, then restart
Home Assistant.

### Manual installation

Download the intended release from
[GitHub Releases](https://github.com/mojelumi0/stirling-pdf-ha/releases), copy
`custom_components/stirling_pdf` to `/config/custom_components/stirling_pdf`,
and restart Home Assistant.

Use the store's pre-release option only if you want to test an alpha.
[Marketplace update and pre-release instructions](https://www.home-assistant.io/integrations/marketplace/#keeping-installations-up-to-date)
are available in the Home Assistant docs. Restart Home Assistant when applying
an update to an already loaded integration.

## Connect to your server

Go to **Settings > Devices & services > Add integration > Stirling PDF**.
Enter the server's base URL, such as `https://pdf.example.com`, without an API
endpoint. Use the final URL rather than one that redirects. Add an API key or
HTTP Basic credentials only if your server or proxy requires them.

For the **Stirling PDF Community App**, use its
[direct Web interface & API address](https://github.com/hassio-addons/app-stirling-pdf/blob/main/stirling-pdf/DOCS.md#direct-access),
not the Ingress link. Enter your Home Assistant username and password in the
**HTTP Basic** fields, not an access token. Keep the app's authentication
enabled. Publishing the direct port changes who can reach it; prefer trusted
HTTPS and do not expose it to untrusted networks. HTTP Basic is not encryption.

Add a separate integration entry for each server. If you have more than one,
select **Server** in each action (YAML: `config_entry_id`). There is no fallback
to another server, even if only one is online. Set the server on existing
automations before adding a second entry.

Use **Reconfigure** to change a URL or credentials. Leave masked values alone
to keep them. Clear both HTTP Basic fields to remove that login. Protect Home
Assistant storage and backups: masking a secret in the UI does not encrypt it.

## File access

Input and output paths are **paths on Home Assistant**, not on the Stirling PDF
server. Create a dedicated directory, for example `/config/pdf`. Add it to
`allowlist_external_dirs` under your existing `homeassistant:` section in
`configuration.yaml`, then restart Home Assistant.

```yaml
homeassistant:
  allowlist_external_dirs:
    - /config/pdf
```

Use absolute paths and an existing output directory. Existing output files
are only replaced if you turn on **Overwrite**. Start with copies of your
documents and avoid allowing more directories than you need.

## Available actions

Find **Stirling PDF** in the Home Assistant action picker. Try an action in
the [Actions tab](https://www.home-assistant.io/docs/tools/dev-tools/#actions-tab)
or add it to a script or automation.

| Action | What it does | Output |
|---|---|---|
| `stirling_pdf.merge` | Combine PDFs in the order supplied | PDF |
| `stirling_pdf.split` | Split a PDF at the specified pages | ZIP |
| `stirling_pdf.extract_pages` | Save selected pages, for example `1,3-5` | PDF |
| `stirling_pdf.ocr` | Make a scan searchable using installed languages | PDF |
| `stirling_pdf.compress` | Reduce file size with an optimization level of 1 to 9 | PDF |

In a script, merge two scans without replacing an existing output:

```yaml
action: stirling_pdf.merge
data:
  file_paths:
    - /config/pdf/scan-1.pdf
    - /config/pdf/scan-2.pdf
  output_path: /config/pdf/merged.pdf
  overwrite: false
response_variable: merged
```

The example uses a single configured server. If you have several, choose one
in the action editor. The optional `response_variable` lets later steps use
details such as the output path or size. Page numbers start at 1. Extraction
takes explicit pages and ascending ranges; it does not accept `all` or formulas.

The [additional action catalog](https://github.com/mojelumi0/stirling-pdf-ha/blob/main/docs/ACTIONS.md)
lists tools such as rotation, watermarks, metadata, conversions and analysis.
Availability depends on the Stirling PDF version, installed tools and
permissions. Some actions return data without creating a file.

Sensitive, external network and AI tools are off by default. Enable only what
you need under the selected server's **Configure** options. User-initiated
calls to those tools require a Home Assistant administrator. Review the
server's settings first: external tools, conversions or AI backends may send
data outside your network. Passwords supplied to actions may be kept in YAML,
traces or backups. Check redaction and signature results independently.

## Available entities

Each server has its own **Reachable**, **Version**, **Jobs processed** and
**Last operation** entities. The job counter only tracks successful actions
from Home Assistant, not jobs run in the Stirling PDF web interface. The
counter and last operation survive reloads and restarts. Optional server and
OCR diagnostics can be enabled individually in the entity settings.

## Troubleshooting

- **Cannot connect?** Check that Home Assistant can reach the final URL, that
  the server has finished starting and that HA trusts its HTTPS certificate.
  For the Community App, check the direct API port and HTTP Basic login.
- **Reachable, but an action fails?** Check the credentials and whether that
  tool is available on your server. A status check does not prove access to
  every tool. On Stirling PDF 3.3.0 and newer, the old `replace_text` action is
  no longer supported. See the action catalog for converter requirements.
- **File path rejected?** Check the allowlist, file extension and output
  directory. Split results use `.zip`; selected-page extraction uses `.pdf`.
- **OCR fails?** Check that the requested language, such as `eng` or `deu`,
  is installed on the selected server.

To uninstall, first disable or update any automations using the integration.
Removing a server entry deletes its local job history, not your PDFs. Remove
the integration files through your installer (or remove only its own folder
if installed manually), then restart Home Assistant.

## Help

[Open an issue](https://github.com/mojelumi0/stirling-pdf-ha/issues/new/choose)
with the integration, Home Assistant and Stirling PDF versions, the action
used and a sanitized error. **Do not share private PDFs, credentials or logs
containing them.** You can download diagnostics from the integration entry;
review the file before sharing it.

[Contributing](https://github.com/mojelumi0/stirling-pdf-ha/blob/main/CONTRIBUTING.md)
explains how to run the project's checks. The maintainer reviews changes before
release, including AI-assisted contributions. This is an independent community
project, not an official Stirling PDF or Home Assistant integration.

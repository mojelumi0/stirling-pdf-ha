# Native Home Assistant acceptance test

`ha_test.yaml` is a single script for Home Assistant's UI YAML editor. Its
filename and title do not contain an integration version. Optional version and
deployment labels are user-provided information, not automatically verified
facts. Script progress and report messages are in German.

## Before running

1. Make a Home Assistant backup before installing a development integration.
2. Keep the existing integration entry. Deleting it removes its local history.
3. Create `/config/pdf-test`, add copies of two non-sensitive PDFs named `a.pdf`
   and `b.pdf`, and add that folder to `homeassistant.allowlist_external_dirs`
   if not already allowed. Restart HA manually after changing its configuration.
4. Enable the integration's reachability, processed-jobs and last-operation
   entities. The script discovers their entity IDs; it stops if ambiguous.
5. Ensure Stirling PDF is reachable and authenticated. Only use OCR languages
   installed on that server; this script requests English (`eng`).
6. Do not run other PDF actions during this test, as it compares job counters.

## Install and run the script

1. Open **Settings > Automations & scenes > Scripts** and create a new script.
2. Select **Edit in YAML** and replace the editor content with `ha_test.yaml`.
   Do not add an outer `script:` or script-ID wrapper.
3. Save and run it with the existing test folder.
4. Leave **Seitenextraktion mitpruefen** enabled when testing the new extraction
   action. Disable it only for a legacy integration without that action.
   This option does not automatically detect or certify an installed version.
5. Optionally supply the installed version copied from diagnostics and a label
   such as `Community App` or `standalone API key`. Never put credentials there.

With extraction enabled, a complete run expects **6 successful operations and
8 deliberate rejections**, with a job-counter increase of **6**. With extraction
disabled, it expects 5 successes and 6 rejections, and explicitly skips the
3 extraction cases. Disabling a new feature is not acceptance evidence for it.

The script validates responses and local sensor changes. It does not parse PDFs
or automatically verify the installed integration version, OCR quality,
diagnostic redaction, exact failure reasons, or persistence across restarts.

## Safety and manual follow-up

- Input PDFs are never used as output targets.
- Output names have a unique `stirling_test_...` prefix.
- Only one test enables overwrite, for its own previously generated compressed
  output. The script performs no deletions, reloads or restarts.
- Unreachable or ambiguous integrations stop before PDF processing.
- A failed prerequisite skips dependent cases instead of counting them as passed.
- `ABGEWIESEN` means no success response and unchanged statistics, not proof of
  the expected rejection reason. Check every such case in the HA trace. A
  connection failure could otherwise look like a successful negative test.

Open every generated PDF and ZIP. The extracted PDF must contain exactly the
first page of the merged PDF. Check OCR searchability visually as well as file
readability; successful output creation alone does not prove OCR quality.

Then note the final count, operation, timestamp and entity IDs. Manually reload
the integration and restart HA; compare the same values without rerunning this
script. Verify secret placeholders and diagnostic redaction locally. Do not
delete/re-add the integration to test persistence.

Use a separately labelled run for the Community App and standalone API-key
deployment. Protect the Community App's direct API port, keep authentication
enabled, and prefer trusted HTTPS or an isolated trusted local connection.

The CI tests validate the example's HA script schema, render its cases and
summary with HA templates, and check safe output targets and expected counts.
They do not execute this whole script against a real HA installation.

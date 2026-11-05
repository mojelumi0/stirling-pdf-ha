# Native Home Assistant acceptance test

## Additional standard tools

After the regular `ha_test.yaml` run, `ha_tools_test.yaml` is a separate UI script
for six representative new tools: rotation, repair, metadata, watermark,
page-count analysis and a no-match text filter. It requires an explicit server
selection, uses only `a.pdf`, creates four uniquely named PDFs and never enables
sensitive/external/AI options. Full success adds six to that server's counter.
Inspect the four outputs and verify the other server's count did not change.
This does not test the complete additional action catalog.

Install it with **Settings > Automations & scenes > Scripts > Create script >
Edit in YAML**, as for the main script below. Do not wrap either file in
`script:` or put two scripts into one UI editor.

`ha_test.yaml` is a single script for Home Assistant's UI YAML editor. Its
filename and title do not contain an integration version. Optional version and
deployment labels are user-provided information, not automatically verified
facts. All three scripts use English field labels, progress messages, reports and
script-authored errors. Home Assistant's own error messages may still follow
its configured UI language. The scripts do not change that language setting.

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
7. With multiple servers, select **Stirling PDF server** when running the script.
   It discovers only that entry's entities and sends every action to that entry.
   An omitted selection with multiple matching sensor sets stops before uploads.
   Run separately for each server and verify that the other's count is unchanged.

The examples discover the selected server through HA's supported
`integration_entities`, `config_entry_attr` and `config_entry_id` filter APIs.
Candidates are filtered by the exact entry ID, so identical friendly names do
not mix servers. Both scripts render their initial discovery variables in CI,
including the `config_entry_id` script input, invalid selections and missing input.

If a copied script reports `config_entry_entities is undefined`, replace its UI
YAML with the current example. No integration update or HA restart is needed for
this script-only correction. Updating the GitHub examples does not automatically
replace scripts already saved in Home Assistant.

## Install and run the script

1. Open **Settings > Automations & scenes > Scripts** and create a new script.
2. Select **Edit in YAML** and replace the editor content with `ha_test.yaml`.
   Do not add an outer `script:` or script-ID wrapper.
3. Save and run it with the existing test folder.
4. Leave **Include page extraction** enabled when testing the new extraction
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
- `REJECTED` means no success response and unchanged statistics, not proof of
  the expected rejection reason. Check every such case in the HA trace. A
  connection failure could otherwise look like a successful negative test.

The report uses `OK`, `REJECTED`, `FAILED` and `SKIPPED`. When investigating the
first normal action, open the trace step **Call PDF action and capture response**,
iteration 1. The additional script uses **Call additional tool and capture response**.

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

The main/additional-tools CI tests validate HA schemas, render cases and reports,
and check safe output targets and expected counts. They do not execute those
whole scripts against a real HA installation.

## Image-only OCR test

`ha_ocr_test.yaml` is a separate UI script for a genuine scan-to-searchable-text
case. It requires the alpha catalog's `check_contains_text` and
`analyze_page_count` actions in addition to `ocr`. It does not enable any
sensitive, external or AI option and never overwrites, retries, reloads or restarts.

1. Copy the committed `tests_live/fixtures/ocr_scan.pdf` to
   `/config/pdf-test/stirling_ocr_fixture_4df4d3d1.pdf` using your existing file
   access. Keep the original fixture unchanged. Its SHA-256 is
   `4df4d3d180b7b42720a9bd3af40ef75b20169cf507354799f8c18a6adde88622`.
   Verify this outside the script; the script cannot independently hash a file.
2. Ensure that folder is already allowlisted and the selected server has English
   OCR (`eng`). Use the exact fixture, not an already-searchable invoice.
3. Open **Settings > Automations & scenes > Scripts > Create script > Edit in
   YAML**. Paste `ha_ocr_test.yaml` as a new script, without an outer `script:`
   wrapper. Do not replace your existing main/tools acceptance scripts.
4. Save, select the intended **Stirling PDF server**, leave the fixture/output
   directory defaults unless you deliberately copied it elsewhere, and run once.
   Do not run other PDF actions while comparing counters.
5. Open the persistent notification and the trace. A complete PASS means all six
   checks succeeded: input does not contain `STIRLING`, OCR produces a new PDF,
   output contains `STIRLING`, `INVOICE` and `12345`, and output has one page.
   Each successful check records an action, including the expected input no-match.
   The selected counter rises by six; other server counters/last-operation
   values must remain unchanged.
6. Open the reported `stirling_ocr_test_<run>_searchable.pdf`. Check the page is
   legible and search/copy its text. Keep the report, trace and actual installed
   integration/backend versions. Run separately for another server only when
   ready; this creates another unique output and another six recorded actions.

At the first unexpected response/counter or connection failure, the script stops
and reports FAILED. Later cases are not run. Inspect the trace before deciding
whether to retry manually; no unchanged counter can prove the server did nothing.

The fixture's source and image-only property are documented in
[`tests_live/fixtures/README.md`](../tests_live/fixtures/README.md). The input
word check alone does not prove every possible string is absent. This test proves
only this synthetic English case, not arbitrary scan quality, all languages,
the complete tool catalog, security, or automatic merge/release approval.
Installed integration version and fixture hash are not checked automatically.

The OCR CI tests validate the HA schema and execute the full native sequence with
synthetic registered services, including early failures and isolation checks.
That is distinct from actual OCR execution on a real Home Assistant/server pair.

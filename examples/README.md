# Testing in Home Assistant

Run these scripts on a test instance with non-sensitive documents. They are
optional test tools, not part of installation.

## Set up

1. Back up Home Assistant before testing a development build. Keep existing
   server entries; deleting them removes their local statistics.
2. Create `/config/pdf-test`, allowlist it as described in the
   [README](../README.md#file-access), and put copies of two PDFs named `a.pdf`
   and `b.pdf` there.
3. Make sure the intended server is reachable, its job and last-operation
   sensors are enabled, and it has English OCR (`eng`).
4. In **Settings > Automations & scenes > Scripts**, create a new script for
   each example you want. Use **Edit in YAML** and paste the example without
   adding an outer `script:` wrapper. Save and choose the intended server
   when running it.

## Scripts

| Script | What to expect |
|---|---|
| [Basic actions](ha_test.yaml) | 6 successes and 8 deliberate rejections with extraction enabled; 5 successes and 6 rejections without it. |
| [Additional tools](ha_tools_test.yaml) | 6 successes: rotate, repair, metadata, watermark, page count and a text-filter non-match. |
| [Image-only OCR](ha_ocr_test.yaml) | 6 checks: absence of a word before OCR, OCR itself, three recognized markers and a one-page result. |

For the OCR test, copy the [synthetic scan](../tests_live/fixtures/ocr_scan.pdf)
to `/config/pdf-test/stirling_ocr_fixture_4df4d3d1.pdf`. Use the
[fixture notes](../tests_live/fixtures/README.md) to verify its checksum; the
script does not check the input hash.

## Read the results

- Run one script at a time so job counts can be checked. Only the selected
  server's statistics should change.
- Check the trace for each deliberate rejection: a connection failure with an
  unchanged counter is not the expected validation error. Record unexpected
  failures before deciding whether to retry.
- Open the generated PDFs and ZIPs. Check page order, rotation, watermark and
  OCR text as applicable. A successful response alone does not verify content.
- Check the installed versions separately. When testing persistence, compare
  counts, last operation, timestamp and entity IDs after a reload or restart
  without running the scripts again. Do not delete and re-add the entry.

The scripts create their own outputs. Only the basic script's explicit
overwrite test replaces a file, and only one created by that run. They do not
delete files, restart Home Assistant or enable sensitive, external or AI tools.

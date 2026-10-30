# Synthetic OCR fixture

`ocr_scan.pdf` is a one-page image-only PDF made from `ocr_scan.svg` in this
repository. All visible text is synthetic. It contains no personal documents,
external images or embedded font programs. It is covered by the repository's
license.

The source artwork is rasterized at 300 DPI and embedded as a PNG image on a
612 x 792 point page. The PDF intentionally has no searchable text layer.
The test checks that prerequisite before asking the real server to add OCR.
Successful OCR must produce one readable page containing `STIRLING`, `INVOICE`
and `12345`; it cannot pass merely by returning a PDF signature or skipping an
already searchable input.

The generator is an optional Node.js maintainer tool requiring `sharp` and
`pdf-lib`. Run it from a development environment where those packages are
available:

```bash
node scripts/generate_ocr_fixture.mjs
```

If packages are installed in a separate node_modules directory, set
`STIRLING_FIXTURE_NODE_MODULES` to its absolute path first. Regeneration replaces
only this fixture PDF. Review the diff and render the result after regenerating.
System font/rendering versions can affect the binary output, so byte-for-byte
regeneration is not an acceptance criterion.

This generator is not a Home Assistant dependency and does not run in CI. CI
reads the committed PDF with the existing pypdf test dependency. No real user
document is uploaded to the disposable test server.

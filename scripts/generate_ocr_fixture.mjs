// Optional maintainer tool. CI consumes the committed PDF, not this generator.
import { readFile, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const moduleRoot = process.env.STIRLING_FIXTURE_NODE_MODULES;
const require = createRequire(moduleRoot ? join(moduleRoot, "package.json") : import.meta.url);
const sharp = require("sharp");
const { PDFDocument } = require("pdf-lib");
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const directory = join(root, "tests_live", "fixtures");
const source = await readFile(join(directory, "ocr_scan.svg"));
const png = await sharp(source, { density: 300 }).png().toBuffer();
const pdf = await PDFDocument.create();
pdf.setTitle("Synthetic image-only OCR fixture");
pdf.setAuthor("stirling-pdf-ha contributors");
pdf.setCreationDate(new Date("2026-01-01T00:00:00Z"));
pdf.setModificationDate(new Date("2026-01-01T00:00:00Z"));
const page = pdf.addPage([612, 792]);
const image = await pdf.embedPng(png);
page.drawImage(image, { x: 0, y: 0, width: 612, height: 792 });
const output = join(directory, "ocr_scan.pdf");
await writeFile(output, await pdf.save({ useObjectStreams: false }));
console.log(`Created image-only OCR fixture: ${output}`);

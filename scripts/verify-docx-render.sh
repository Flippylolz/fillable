#!/bin/sh
# Synthetic browser artifacts only. This tool is not a retained-document writer.
set -eu
proof_reports=${1:?Pass the browser-results directory}
proof_reports=$(cd "$proof_reports" && pwd)
cp fixtures/docx/v1/client-intake-uk-v1.docx "$proof_reports/original.docx"
cmp "$proof_reports/original.docx" "$proof_reports/unchanged.docx"
docker build -f infra/docx-proof.Dockerfile -t fillable-docx-proof .
docker run --rm --user "$(id -u):$(id -g)" -v "$proof_reports:/output" fillable-docx-proof sh -c '
  soffice -env:UserInstallation=file:///tmp/lo-proof --headless --convert-to pdf --outdir /output /output/original.docx /output/unchanged.docx /output/edited.docx /output/multiline.docx
  for name in original unchanged edited; do
    test "$(pdfinfo /output/$name.pdf | awk '\''/^Pages:/ { print $2 }'\'')" = 3
    pdftoppm -scale-to 1200 -png /output/$name.pdf /output/$name
  done
  for page in 1 2 3; do cmp /output/original-$page.png /output/unchanged-$page.png; done
  cmp /output/original-2.png /output/edited-2.png
  pdftotext /output/edited.pdf /output/edited.txt
  python -c '\''from pathlib import Path; text=Path("/output/edited.txt").read_text(); assert "Ґанна" in text and "Єва Їжак" in text'\''
  test "$(pdfinfo /output/multiline.pdf | awk '\''/^Pages:/ { print $2 }'\'')" = 5
  pdftoppm -scale-to 1200 -png /output/multiline.pdf /output/multiline
  pdftotext /output/multiline.pdf /output/multiline.txt
  python -c '\''from pathlib import Path; text=" ".join(Path("/output/multiline.txt").read_text().split()); assert text.count("Ілля Ґудзик") == 2 and text.count("контактний зв’язок.") == 100 and text.count("🙂") == 102'\''
  pdftotext -bbox /output/multiline.pdf /output/multiline.bbox.html
  python -c '\''from xml.etree import ElementTree as ET
pages=ET.parse("/output/multiline.bbox.html").findall(".//{http://www.w3.org/1999/xhtml}page")
checked=0
for page in pages:
    words=page.findall(".//{http://www.w3.org/1999/xhtml}word")
    first=[float(word.get("yMax")) for word in words if word.text == "Ілля"]
    if first:
        second=[float(word.get("yMin")) for word in words if word.text == "Їжак"]
        assert second and 0 < min(second) - min(first) < 30
        checked += 1
assert checked == 2'\''
'
printf '%s\n' 'PASS: identical no-edit package/pages; three edited pages; unchanged page two; five multiline pages with exact repeated Ukrainian/astral text.'

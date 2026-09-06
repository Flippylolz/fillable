#!/bin/sh
# Synthetic browser artifacts only. This tool is not a retained-document writer.
set -eu
proof_reports=${1:?Pass the browser-results directory}
proof_reports=$(cd "$proof_reports" && pwd)
cp fixtures/docx/v1/client-intake-uk-v1.docx "$proof_reports/original.docx"
cmp "$proof_reports/original.docx" "$proof_reports/unchanged.docx"
docker build -f infra/docx-proof.Dockerfile -t fillable-docx-proof .
docker run --rm --user "$(id -u):$(id -g)" -v "$proof_reports:/output" fillable-docx-proof sh -c '
  soffice -env:UserInstallation=file:///tmp/lo-proof --headless --convert-to pdf --outdir /output /output/original.docx /output/unchanged.docx /output/edited.docx
  for name in original unchanged edited; do
    test "$(pdfinfo /output/$name.pdf | awk '\''/^Pages:/ { print $2 }'\'')" = 3
    pdftoppm -scale-to 1200 -png /output/$name.pdf /output/$name
  done
  for page in 1 2 3; do cmp /output/original-$page.png /output/unchanged-$page.png; done
  cmp /output/original-2.png /output/edited-2.png
  pdftotext /output/edited.pdf /output/edited.txt
  python -c '\''from pathlib import Path; text=Path("/output/edited.txt").read_text(); assert "Ґанна" in text and "Єва Їжак" in text'\''
'
printf '%s\n' 'PASS: identical no-edit package/pages; three edited pages; unchanged page two; Ukrainian text.'

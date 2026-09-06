"""Generate a test model from the source DOCX, never from its answer key."""
import json
import sys
from pathlib import Path

from app.documents.package import DocxPackage

package = DocxPackage(Path('/fixtures/docx/v1/client-intake-uk-v1.docx').read_bytes())
Path(sys.argv[1]).write_text(json.dumps(package.model, ensure_ascii=False, indent=2) + '\n')

"""Generate a test model from the source DOCX, never from its answer key."""
import json
import sys
from pathlib import Path
from uuid import UUID

from app.documents.package import DocxPackage
from app.fields.blanks import discover

package = DocxPackage(Path('/fixtures/docx/v1/client-intake-uk-v1.docx').read_bytes())
Path(sys.argv[1]).write_text(json.dumps(package.model, ensure_ascii=False, indent=2) + '\n')
if len(sys.argv) > 2:
    Path(sys.argv[2]).write_text(json.dumps(discover(package.model, UUID(int=0)).model_dump(mode='json'), ensure_ascii=False, indent=2) + '\n')

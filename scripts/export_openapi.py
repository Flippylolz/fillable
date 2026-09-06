"""Export without runtime service connections; stable ordering allows drift checks."""
import json
import sys
from pathlib import Path

from app.main import app

Path(sys.argv[1]).write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2,
                                      sort_keys=True) + "\n")

"""Pytest bootstrap: make scripts/ importable so tests import the same
`course_pairing` package the runnable entry points use."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

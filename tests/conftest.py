from __future__ import annotations

import os
import tempfile
from pathlib import Path


_LOCAL_TMP = Path(__file__).resolve().parents[1] / "tmp"
_LOCAL_TMP.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(_LOCAL_TMP)
os.environ["TMP"] = str(_LOCAL_TMP)
os.environ["TEMP"] = str(_LOCAL_TMP)
os.environ["TMPDIR"] = str(_LOCAL_TMP)


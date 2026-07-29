#!/usr/bin/env python3
"""
Stop hook — project-scope copy.

Delegates to the workspace-root stop.py by searching upward from this
file's location for the docs/FEATURE_TRACEABILITY.csv marker. Fails
closed on any missing scaffold or validator error.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


def _find_workspace() -> Path:
    start = Path(__file__).resolve().parent
    for candidate in [start, *start.parents]:
        if (candidate / "docs" / "FEATURE_TRACEABILITY.csv").exists():
            return candidate
        if (candidate / "scripts" / "validate_traceability.py").exists():
            return candidate
    return Path("/Users/bharatvishwakarma/Desktop/D-Eye")


ROOT = _find_workspace()
CSV = ROOT / "docs" / "FEATURE_TRACEABILITY.csv"
VALIDATE = ROOT / "scripts" / "validate_traceability.py"


def _emit(reason: str, allow: bool, code: int) -> None:
    decision = "approve" if allow else "block"
    sys.stdout.write(json.dumps({"decision": decision, "reason": reason}) + "\n")
    sys.exit(code)


def main() -> None:
    if not CSV.exists():
        _emit(
            f"Stop hook BLOCK: traceability CSV missing at {CSV}. "
            "Regenerate with `python3 scripts/build_traceability.py`.",
            allow=False, code=2,
        )
        return
    if not VALIDATE.exists():
        _emit(
            f"Stop hook BLOCK: validator missing at {VALIDATE}.",
            allow=False, code=2,
        )
        return
    r = subprocess.run(
        [sys.executable, str(VALIDATE)],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        _emit(
            "Stop hook BLOCK: traceability validator failed.\n"
            f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}",
            allow=False, code=2,
        )
        return
    rows = list(csv.DictReader(CSV.open()))
    total = len(rows)
    prod = sum(1 for x in rows if (x.get("d_eye_status") or "").strip() == "PRODUCTION READY")
    blocked_or_na = sum(
        1 for x in rows
        if (x.get("d_eye_status") or "").strip() in {"BLOCKED BY EXTERNAL PLATFORM", "NOT APPLICABLE"}
    )
    remaining = total - prod - blocked_or_na
    _emit(
        f"Stop hook OK — traceability validates. "
        f"PRODUCTION_READY={prod}/{total}, remaining_work={remaining}, "
        f"blocked_or_na={blocked_or_na}.",
        allow=True, code=0,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.stdout.write(json.dumps({
            "decision": "block",
            "reason": f"Stop hook exception (FAIL CLOSED): {type(e).__name__}: {e}",
        }) + "\n")
        sys.exit(2)

"""Print the section of CHANGELOG.md for a version (used by the release workflow)."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def notes(version: str, changelog: str) -> str:
    match = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]: |\Z)", changelog, re.M | re.S)
    if not match:
        raise SystemExit(f"Version {version} not found in CHANGELOG.md")
    return match.group(1).strip() + "\n"


if __name__ == "__main__":
    sys.stdout.write(notes(sys.argv[1], (Path(__file__).parent.parent / "CHANGELOG.md").read_text(encoding="utf-8")))

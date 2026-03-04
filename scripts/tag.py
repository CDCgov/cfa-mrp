"""Extract version from pyproject.toml, check Cargo.toml, and create a git tag."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    with open(ROOT / "pyproject.toml", "rb") as f:
        py_version = tomllib.load(f)["project"]["version"]

    with open(ROOT / "mrp-rs" / "Cargo.toml", "rb") as f:
        rs_version = tomllib.load(f)["package"]["version"]

    if py_version != rs_version:
        print(
            f"WARNING: version mismatch — "
            f"pyproject.toml={py_version}, Cargo.toml={rs_version}"
        )
        sys.exit(1)

    tag = f"v{py_version}"

    existing = subprocess.run(
        ["git", "tag", "--list", tag],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if tag in existing.stdout.strip().splitlines():
        print(f"WARNING: tag {tag} already exists")
        sys.exit(1)

    subprocess.run(["git", "tag", tag], check=True, cwd=ROOT)
    print(f"Created tag {tag}")


if __name__ == "__main__":
    main()

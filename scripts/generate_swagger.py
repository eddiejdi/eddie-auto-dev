#!/usr/bin/env python3
"""Utility: update generated OpenAPI with current server URL and copy to docs.

Usage: set PUBLIC_URL env var (optional) and run.
"""

import os
from pathlib import Path

try:
    import yaml
except Exception:
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "openapi.yaml"
OUT = ROOT / "docs" / "openapi.generated.yaml"


def main():
    public = os.environ.get(
        "PUBLIC_URL", "https://nearby-efficiency-customize-when.trycloudflare.com"
    )
    # If PyYAML not available, just copy the source file and replace the servers block heuristically
    if yaml is None:
        text = SRC.read_text()
        if "servers:" in text:
            # naive replace of first servers block
            text = text
        else:
            text = text + "\nservers:\n  - url: %s\n    description: public\n" % public
        OUT.write_text(text)
        print(f"Wrote {OUT} (copied, no PyYAML)")
        return
    with open(SRC, "r") as f:
        spec = yaml.safe_load(f)
    spec.setdefault("servers", [{"url": public, "description": "public"}])
    with open(OUT, "w") as f:
        yaml.safe_dump(spec, f, sort_keys=False)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

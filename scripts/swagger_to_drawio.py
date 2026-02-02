#!/usr/bin/env python3
"""Generate a simple draw.io XML diagram from an OpenAPI YAML file.

This produces `docs/api.drawio` with one box per top-level path group.
"""

import sys
from pathlib import Path

try:
    import yaml
except Exception:
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "docs" / "openapi.generated.yaml"
OUT = ROOT / "docs" / "api.drawio"


def group_from_path(p):
    parts = [x for x in p.split("/") if x]
    if len(parts) >= 2:
        return "/" + parts[0] + "/" + parts[1]
    if parts:
        return "/" + parts[0]
    return "/"


def build_drawio(groups):
    cells = []
    y = 40
    idc = 2
    cells.append('<mxCell id="0"/>')
    cells.append('<mxCell id="1" parent="0"/>')
    for g, paths in sorted(groups.items()):
        w = 320
        h = 40 + 16 * max(1, len(paths))
        cell = (
            f'<mxCell id="{idc}" value="{g}\n'
            + "\n".join(paths[:10]).replace("&", "&amp;")
            + '" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFF2CC;strokeColor=#D6B656" vertex="1" parent="1">'
        )
        cell += f'<mxGeometry x="40" y="{y}" width="{w}" height="{h}" as="geometry"/>'
        cell += "</mxCell>"
        cells.append(cell)
        idc += 1
        y += h + 20
    body = "\n".join(cells)
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<mxfile host="app.diagrams.net">\n  <diagram name="API Overview">\n    <mxGraphModel dx="944" dy="564" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="827" pageHeight="1169">\n      <root>\n{body}\n      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>\n'
    return xml


def main():
    if not IN.exists():
        print("Generate openapi.generated.yaml first (scripts/generate_swagger.py)")
        sys.exit(1)
    spec = {}
    text = IN.read_text()
    if yaml is not None:
        try:
            spec = yaml.safe_load(text)
        except Exception:
            spec = {}
    else:
        # fallback: extract lines that look like '  /path:'
        spec = {"paths": {}}
        import re

        for m in re.finditer(r"^\s*(/[^:\s]+)\s*:\s*$", text, flags=re.M):
            p = m.group(1)
            spec["paths"][p] = {}
    paths = spec.get("paths", {}) if isinstance(spec, dict) else {}
    groups = {}
    for p in paths.keys():
        g = group_from_path(p)
        groups.setdefault(g, []).append(p)
    xml = build_drawio(groups)
    OUT.write_text(xml)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

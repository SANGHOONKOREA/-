"""Validate a sld_spec.json before running the builder.

Checks:
- All required top-level keys exist.
- No '???' or null values remain (these indicate the engineer hasn't
  filled in fields the LLM couldn't read).
- Generator and feeder X-coordinates lie inside the busbar range.
- Feeder thruster types are one of {AZIMUTH, TUNNEL}.
- Remark numbers referenced from feeders exist in
  annotations.remark_table.

Exit status 0 = valid; 1 = problems found.  Run as:

    python .claude/skills/sketch-to-sld/validate.py image-to-dwg/sld_spec.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL = {
    "drawing", "main_busbar", "generators", "feeders",
    "level_y", "annotations",
}
REQUIRED_DRAWING = {
    "title", "drawing_no", "revision", "date", "sheet_size_mm",
}
REQUIRED_BUSBAR = {
    "voltage_v", "frequency_hz", "y", "x_start", "x_end",
}
REQUIRED_FEEDER = {
    "id", "x", "transformer", "vfd", "motor", "thruster",
}
ALLOWED_THRUSTER_TYPES = {"AZIMUTH", "TUNNEL"}


def _walk_unfilled(node: Any, path: str, problems: list[str]) -> None:
    """Find any '???' or null values still in the spec."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k.startswith("_"):  # _doc / _comment fields are notes
                continue
            _walk_unfilled(v, f"{path}.{k}" if path else k, problems)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _walk_unfilled(item, f"{path}[{i}]", problems)
    else:
        if node is None or node == "???":
            problems.append(f"unfilled value at {path}: {node!r}")


def validate(path: Path) -> list[str]:
    problems: list[str] = []
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"invalid JSON: {e}"]
    except FileNotFoundError:
        return [f"file not found: {path}"]

    # Top-level
    missing = REQUIRED_TOP_LEVEL - set(spec.keys())
    if missing:
        problems.append(f"missing top-level keys: {sorted(missing)}")

    # Drawing
    if "drawing" in spec:
        miss = REQUIRED_DRAWING - set(spec["drawing"].keys())
        if miss:
            problems.append(f"drawing missing keys: {sorted(miss)}")

    # Busbar
    bus = spec.get("main_busbar", {})
    miss = REQUIRED_BUSBAR - set(bus.keys())
    if miss:
        problems.append(f"main_busbar missing keys: {sorted(miss)}")
    x_start = bus.get("x_start", 50)
    x_end = bus.get("x_end", 400)

    # Generators
    for i, g in enumerate(spec.get("generators", [])):
        if "tag" not in g or "x" not in g:
            problems.append(f"generator[{i}] missing tag or x")
        x = g.get("x")
        if isinstance(x, (int, float)) and not (x_start <= x <= x_end):
            problems.append(
                f"generator[{i}] x={x} outside busbar range "
                f"[{x_start}, {x_end}]"
            )

    # Feeders
    valid_remarks = {
        item["no"] for item in spec.get("annotations", {})
                                 .get("remark_table", [])
        if isinstance(item, dict) and "no" in item
    }
    for i, f in enumerate(spec.get("feeders", [])):
        miss = REQUIRED_FEEDER - set(f.keys())
        if miss:
            problems.append(f"feeders[{i}] missing keys: {sorted(miss)}")
            continue
        x = f["x"]
        if isinstance(x, (int, float)) and not (x_start <= x <= x_end):
            problems.append(
                f"feeders[{i}].x={x} outside busbar range "
                f"[{x_start}, {x_end}]"
            )
        thr_type = f.get("thruster", {}).get("type")
        if thr_type not in ALLOWED_THRUSTER_TYPES:
            problems.append(
                f"feeders[{i}].thruster.type={thr_type!r} not in "
                f"{sorted(ALLOWED_THRUSTER_TYPES)}"
            )
        for ref in ("remark_no_tx", "remark_no_vfd", "remark_no_motor"):
            n = f.get(ref)
            if isinstance(n, int) and n not in valid_remarks:
                problems.append(
                    f"feeders[{i}].{ref}={n} has no entry in "
                    f"annotations.remark_table"
                )

    # Walk for unfilled values
    _walk_unfilled(spec, "", problems)
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python validate.py <path/to/sld_spec.json>",
              file=sys.stderr)
        return 2
    problems = validate(Path(argv[1]))
    if not problems:
        print("OK: spec is valid and fully filled in.")
        return 0
    print(f"FAIL: {len(problems)} problem(s):")
    for p in problems:
        print(f"  - {p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

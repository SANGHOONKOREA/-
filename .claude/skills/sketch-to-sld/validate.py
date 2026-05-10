"""Validate a sld_spec.json before running the builder.

Three categories of checks (all run in one pass):

1. STRUCTURAL: required keys exist, types are correct, references
   resolve.

2. UNFILLED: any value still equal to '???' or null indicates the
   engineer hasn't reviewed a field that the LLM couldn't read.

3. PLAUSIBILITY (domain rules): catches digit-confusion errors that
   pass a pure schema check.  Examples:
   - Voltages must lie in a known set (110/220/380/440/690/...)
   - Frequencies must be 50 or 60.
   - Motor V must equal one of the transformer secondary voltages.
   - Motor kW must not exceed the sum of secondary kVA capacities.
   - Motor RPM must be in 100-5000.
   - Generator V must equal busbar V.

Use this as a gate between Claude's extraction and the builder.

    python .claude/skills/sketch-to-sld/validate.py \
        image-to-dwg/sld_spec.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


# ----- Required keys --------------------------------------------------------
REQUIRED_TOP = {"drawing", "main_busbar", "generators", "feeders",
                "level_y", "annotations"}
REQUIRED_DRAWING = {"title", "drawing_no", "revision", "date",
                    "sheet_size_mm"}
REQUIRED_BUSBAR  = {"voltage_v", "frequency_hz", "y", "x_start", "x_end"}
REQUIRED_FEEDER  = {"id", "x", "transformer", "vfd", "motor", "thruster"}
REQUIRED_TX      = {"kva_primary", "kva_sec1", "kva_sec2",
                    "v_primary", "v_sec1", "v_sec2"}
REQUIRED_MOTOR   = {"kw", "v", "hz", "rpm"}

# ----- Plausibility sets ----------------------------------------------------
PLAUSIBLE_LV_AC = {110, 115, 120, 200, 208, 220, 230, 240, 380, 400,
                   415, 440, 460, 480, 525, 575, 600, 660, 690}
PLAUSIBLE_MV_AC = {2400, 3300, 4160, 6000, 6600, 11000, 13800, 15000}
PLAUSIBLE_VOLTS = PLAUSIBLE_LV_AC | PLAUSIBLE_MV_AC
PLAUSIBLE_FREQS = {50, 60}
PLAUSIBLE_PHASES = {1, 3}
ALLOWED_THRUSTER_TYPES = {"AZIMUTH", "TUNNEL"}


# ============================================================================
# Helpers
# ============================================================================
def _walk_unfilled(node: Any, path: str, problems: list[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if k.startswith("_"):
                continue
            _walk_unfilled(v, f"{path}.{k}" if path else k, problems)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _walk_unfilled(item, f"{path}[{i}]", problems)
    else:
        if node is None or node == "???":
            problems.append(f"unfilled value at {path}: {node!r}")


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ============================================================================
# Per-category checks
# ============================================================================
def _check_structure(spec: dict, problems: list[str]) -> None:
    miss = REQUIRED_TOP - set(spec.keys())
    if miss:
        problems.append(f"[STRUCT] missing top-level keys: {sorted(miss)}")

    if "drawing" in spec:
        m = REQUIRED_DRAWING - set(spec["drawing"].keys())
        if m:
            problems.append(f"[STRUCT] drawing missing: {sorted(m)}")

    bus = spec.get("main_busbar", {})
    m = REQUIRED_BUSBAR - set(bus.keys())
    if m:
        problems.append(f"[STRUCT] main_busbar missing: {sorted(m)}")

    for i, g in enumerate(spec.get("generators", [])):
        for k in ("tag", "x", "kva", "v", "hz"):
            if k not in g:
                problems.append(f"[STRUCT] generators[{i}] missing {k!r}")

    for i, f in enumerate(spec.get("feeders", [])):
        m = REQUIRED_FEEDER - set(f.keys())
        if m:
            problems.append(f"[STRUCT] feeders[{i}] missing: {sorted(m)}")
            continue
        m = REQUIRED_TX - set(f.get("transformer", {}).keys())
        if m:
            problems.append(
                f"[STRUCT] feeders[{i}].transformer missing: {sorted(m)}")
        m = REQUIRED_MOTOR - set(f.get("motor", {}).keys())
        if m:
            problems.append(
                f"[STRUCT] feeders[{i}].motor missing: {sorted(m)}")
        thr = f.get("thruster", {}).get("type")
        if thr not in ALLOWED_THRUSTER_TYPES:
            problems.append(
                f"[STRUCT] feeders[{i}].thruster.type={thr!r} "
                f"not in {sorted(ALLOWED_THRUSTER_TYPES)}")


def _check_geometry(spec: dict, problems: list[str]) -> None:
    bus = spec.get("main_busbar", {})
    x_start = bus.get("x_start", 50)
    x_end = bus.get("x_end", 400)
    for i, g in enumerate(spec.get("generators", [])):
        x = g.get("x")
        if _is_num(x) and not (x_start <= x <= x_end):
            problems.append(
                f"[GEO] generators[{i}].x={x} outside busbar "
                f"[{x_start}, {x_end}]")
    for i, f in enumerate(spec.get("feeders", [])):
        x = f.get("x")
        if _is_num(x) and not (x_start <= x <= x_end):
            problems.append(
                f"[GEO] feeders[{i}].x={x} outside busbar "
                f"[{x_start}, {x_end}]")


def _check_remarks(spec: dict, problems: list[str]) -> None:
    valid = {item["no"] for item in spec.get("annotations", {})
             .get("remark_table", [])
             if isinstance(item, dict) and "no" in item}
    for i, f in enumerate(spec.get("feeders", [])):
        for ref in ("remark_no_tx", "remark_no_vfd", "remark_no_motor"):
            n = f.get(ref)
            if isinstance(n, int) and n not in valid:
                problems.append(
                    f"[REF] feeders[{i}].{ref}={n} has no entry in "
                    f"annotations.remark_table")


def _check_plausibility(spec: dict, problems: list[str]) -> None:
    bus = spec.get("main_busbar", {})
    bus_v  = bus.get("voltage_v")
    bus_hz = bus.get("frequency_hz")
    bus_ph = bus.get("phases")

    if _is_num(bus_v) and bus_v not in PLAUSIBLE_VOLTS:
        problems.append(
            f"[DOMAIN] main_busbar.voltage_v={bus_v} not in standard "
            f"voltage classes (likely digit-confusion)")
    if _is_num(bus_hz) and bus_hz not in PLAUSIBLE_FREQS:
        problems.append(
            f"[DOMAIN] main_busbar.frequency_hz={bus_hz} "
            f"not in {PLAUSIBLE_FREQS}")
    if _is_num(bus_ph) and bus_ph not in PLAUSIBLE_PHASES:
        problems.append(
            f"[DOMAIN] main_busbar.phases={bus_ph} "
            f"not in {PLAUSIBLE_PHASES}")

    for i, g in enumerate(spec.get("generators", [])):
        v = g.get("v")
        if _is_num(v):
            if v not in PLAUSIBLE_VOLTS:
                problems.append(
                    f"[DOMAIN] generators[{i}].v={v} not standard")
            elif _is_num(bus_v) and v != bus_v:
                problems.append(
                    f"[DOMAIN] generators[{i}].v={v} does not match "
                    f"main_busbar.voltage_v={bus_v}")
        hz = g.get("hz")
        if _is_num(hz) and hz not in PLAUSIBLE_FREQS:
            problems.append(
                f"[DOMAIN] generators[{i}].hz={hz} not in "
                f"{PLAUSIBLE_FREQS}")

    for i, f in enumerate(spec.get("feeders", [])):
        tx = f.get("transformer", {})
        m = f.get("motor", {})

        v_pri  = tx.get("v_primary")
        v_sec1 = tx.get("v_sec1")
        v_sec2 = tx.get("v_sec2")
        for name, v in [("v_primary", v_pri), ("v_sec1", v_sec1),
                        ("v_sec2", v_sec2)]:
            if _is_num(v) and v not in PLAUSIBLE_VOLTS:
                problems.append(
                    f"[DOMAIN] feeders[{i}].transformer.{name}={v} "
                    f"not standard")

        if _is_num(v_pri) and _is_num(bus_v) and v_pri != bus_v:
            problems.append(
                f"[DOMAIN] feeders[{i}].transformer.v_primary={v_pri} "
                f"!= main_busbar.voltage_v={bus_v}")

        m_v  = m.get("v")
        m_hz = m.get("hz")
        m_kw = m.get("kw")
        m_rpm = m.get("rpm")

        if _is_num(m_v) and m_v not in PLAUSIBLE_VOLTS:
            problems.append(
                f"[DOMAIN] feeders[{i}].motor.v={m_v} not standard")
        if (_is_num(m_v) and (_is_num(v_sec1) or _is_num(v_sec2))
                and m_v not in (v_sec1, v_sec2)):
            problems.append(
                f"[DOMAIN] feeders[{i}].motor.v={m_v} does not match "
                f"any transformer secondary "
                f"({v_sec1}, {v_sec2})")
        if _is_num(m_hz) and m_hz not in PLAUSIBLE_FREQS:
            problems.append(
                f"[DOMAIN] feeders[{i}].motor.hz={m_hz} not in "
                f"{PLAUSIBLE_FREQS}")
        if _is_num(m_rpm) and not (100 <= m_rpm <= 5000):
            problems.append(
                f"[DOMAIN] feeders[{i}].motor.rpm={m_rpm} outside "
                f"100-5000 plausible range")

        # Motor kW vs total secondary kVA
        kva_sec_total = sum(
            tx.get(k, 0) or 0 for k in ("kva_sec1", "kva_sec2")
        )
        if _is_num(m_kw) and kva_sec_total > 0:
            if m_kw > kva_sec_total * 0.95:
                problems.append(
                    f"[DOMAIN] feeders[{i}].motor.kw={m_kw} exceeds "
                    f"95% of transformer secondary capacity "
                    f"({kva_sec_total} kVA)")
            elif m_kw < kva_sec_total * 0.4:
                problems.append(
                    f"[DOMAIN] feeders[{i}].motor.kw={m_kw} is "
                    f"<40% of TX secondary {kva_sec_total} kVA "
                    f"(usually means kW or kVA was misread)")

        # Primary kVA should be >= sum of secondaries (or close)
        kva_pri = tx.get("kva_primary")
        if _is_num(kva_pri) and kva_sec_total > 0:
            if kva_pri < kva_sec_total * 0.8:
                problems.append(
                    f"[DOMAIN] feeders[{i}].transformer.kva_primary="
                    f"{kva_pri} much less than sum of secondaries "
                    f"({kva_sec_total} kVA)")


# ============================================================================
# Public API
# ============================================================================
def validate(path: Path) -> list[str]:
    problems: list[str] = []
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"[STRUCT] invalid JSON: {e}"]
    except FileNotFoundError:
        return [f"[STRUCT] file not found: {path}"]

    _check_structure(spec, problems)
    _check_geometry(spec, problems)
    _check_remarks(spec, problems)
    _check_plausibility(spec, problems)
    _walk_unfilled(spec, "", problems)
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python validate.py <path/to/sld_spec.json>",
              file=sys.stderr)
        return 2
    problems = validate(Path(argv[1]))
    if not problems:
        print("OK: spec is valid, fully filled, and passes plausibility "
              "checks.")
        return 0
    print(f"FAIL: {len(problems)} problem(s):")
    by_tag: dict[str, list[str]] = {}
    for p in problems:
        tag = p.split("]", 1)[0][1:] if p.startswith("[") else "OTHER"
        by_tag.setdefault(tag, []).append(p)
    for tag in ("STRUCT", "REF", "GEO", "DOMAIN", "OTHER"):
        if tag in by_tag:
            print(f"\n  {tag}:")
            for p in by_tag[tag]:
                print(f"    - {p[len(tag) + 3:] if p.startswith('[') else p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

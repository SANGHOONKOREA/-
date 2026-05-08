"""CLI entry point: generate the SLD DXF from sld_spec.json."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import builder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build SHI 18K BV electric SLD DXF from a JSON spec.",
    )
    parser.add_argument(
        "--spec", type=Path,
        default=Path(__file__).resolve().parents[1] / "sld_spec.json",
        help="Path to sld_spec.json (default: ../sld_spec.json)",
    )
    parser.add_argument(
        "--out", type=Path,
        default=Path(__file__).resolve().parents[1] / "output" /
                "SHI_18K_BV_SLD.dxf",
        help="Output DXF path (default: ../output/SHI_18K_BV_SLD.dxf)",
    )
    args = parser.parse_args(argv)

    if not args.spec.exists():
        print(f"ERROR: spec file not found: {args.spec}", file=sys.stderr)
        return 2

    builder.build(args.spec, args.out)
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

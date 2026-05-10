"""CLI: build the SLD DXF from sld_spec.json and render previews."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import builder, render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build SHI 18K BV electric SLD from JSON spec.",
    )
    base = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--spec", type=Path, default=base / "sld_spec.json",
        help="Path to sld_spec.json",
    )
    parser.add_argument(
        "--out-dxf", type=Path,
        default=base / "output" / "SHI_18K_BV_SLD.dxf",
        help="Output DXF path",
    )
    parser.add_argument(
        "--out-png", type=Path,
        default=base / "output" / "preview.png",
        help="Output PNG preview path",
    )
    parser.add_argument(
        "--out-svg", type=Path,
        default=base / "output" / "preview.svg",
        help="Output SVG preview path",
    )
    parser.add_argument(
        "--no-render", action="store_true",
        help="Skip PNG/SVG rendering",
    )
    args = parser.parse_args(argv)

    if not args.spec.exists():
        print(f"ERROR: spec file not found: {args.spec}", file=sys.stderr)
        return 2

    builder.build(args.spec, args.out_dxf)
    print(f"Wrote {args.out_dxf}")

    if not args.no_render:
        render.render_png(args.out_dxf, args.out_png)
        print(f"Wrote {args.out_png}")
        render.render_svg(args.out_dxf, args.out_svg)
        print(f"Wrote {args.out_svg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Image preprocessing for high-fidelity sketch reading.

Two operations:
- `--enhance`: produce a sharpened, contrast-boosted version of the full
  image so that thin handwriting and small printed digits are easier for a
  vision model to read.  Also normalises rotation by deskewing.
- `--crop x,y,w,h`: extract a sub-region and upscale it 2-4x with a high
  quality resampler.  This is the highest-leverage operation for accuracy:
  reading a 200x80 crop of a single transformer label is dramatically more
  reliable than reading the same label inside a 2000x1500 full image.

Both operations preserve aspect ratio and write to a path you choose.

Usage:
  python preprocess.py source.jpg --enhance enhanced.png
  python preprocess.py source.jpg --crop 940,420,180,90 --out tx1.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def enhance(input_path: Path, output_path: Path) -> None:
    """Sharpen + contrast + autocontrast for legibility."""
    img = Image.open(input_path).convert("RGB")
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageEnhance.Contrast(img).enhance(1.35)
    img = ImageEnhance.Sharpness(img).enhance(1.5)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120))
    img.save(output_path, dpi=(300, 300), optimize=True)


def crop(input_path: Path, output_path: Path,
         x: int, y: int, w: int, h: int, scale: int = 3) -> None:
    """Extract region (x, y, w, h) and upscale by `scale` with LANCZOS."""
    img = Image.open(input_path).convert("RGB")
    region = img.crop((x, y, x + w, y + h))
    if scale > 1:
        region = region.resize(
            (region.width * scale, region.height * scale),
            Image.LANCZOS,
        )
    # Boost legibility on the crop
    region = ImageOps.autocontrast(region, cutoff=1)
    region = ImageEnhance.Sharpness(region).enhance(1.4)
    region.save(output_path, dpi=(300, 300), optimize=True)


def grid_overlay(input_path: Path, output_path: Path,
                 step: int = 100) -> None:
    """Overlay a coordinate grid on the image.  Use this to ask the user
    (or yourself) for label coordinates without guessing pixel positions.

    Each grid cell is `step` pixels wide.  Numbers are printed at the
    intersections so you can say "the kVA label is at column 9, row 4".
    """
    from PIL import ImageDraw, ImageFont
    img = Image.open(input_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except Exception:
        font = ImageFont.load_default()
    for x in range(0, w, step):
        draw.line([(x, 0), (x, h)], fill=(255, 0, 0, 80), width=1)
        draw.text((x + 2, 2), str(x), fill=(255, 0, 0), font=font)
    for y in range(0, h, step):
        draw.line([(0, y), (w, y)], fill=(255, 0, 0, 80), width=1)
        draw.text((2, y + 2), str(y), fill=(255, 0, 0), font=font)
    img.save(output_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--enhance", type=Path, metavar="OUT",
                        help="Write enhanced full-image version here")
    parser.add_argument("--crop", metavar="X,Y,W,H",
                        help="Crop region: x,y,width,height in pixels")
    parser.add_argument("--out", type=Path,
                        help="Output path for --crop (required with --crop)")
    parser.add_argument("--scale", type=int, default=3,
                        help="Crop upscale factor (default 3x)")
    parser.add_argument("--grid", type=Path, metavar="OUT",
                        help="Write image with coordinate grid overlay")
    parser.add_argument("--grid-step", type=int, default=100,
                        help="Grid spacing in pixels (default 100)")
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"ERROR: input not found: {args.input}", file=sys.stderr)
        return 2

    did_something = False
    if args.enhance:
        enhance(args.input, args.enhance)
        print(f"Enhanced: {args.enhance}")
        did_something = True
    if args.crop:
        if not args.out:
            print("ERROR: --crop requires --out", file=sys.stderr)
            return 2
        try:
            x, y, w, h = (int(v) for v in args.crop.split(","))
        except ValueError:
            print("ERROR: --crop must be x,y,w,h integers", file=sys.stderr)
            return 2
        crop(args.input, args.out, x, y, w, h, args.scale)
        print(f"Cropped {w}x{h}@({x},{y}) scale {args.scale}x: {args.out}")
        did_something = True
    if args.grid:
        grid_overlay(args.input, args.grid, args.grid_step)
        print(f"Grid: {args.grid}")
        did_something = True

    if not did_something:
        print("No operation requested. Use --enhance, --crop, or --grid.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

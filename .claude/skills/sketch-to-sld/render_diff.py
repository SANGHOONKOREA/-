"""Side-by-side comparison of source image and built preview.

After running the builder, call this with the original sketch and the
generated `preview.png`.  It produces a single image with both placed
side-by-side at matched height plus a third panel that draws the source
on top of the preview at 50% opacity for direct overlay inspection.

Read the result back with the vision model and ask:
    "Compare LEFT (source) and MIDDLE (built). What is missing or wrong
    in the built version? Use the RIGHT panel (overlay) to check
    alignment."

This iteration loop is the single largest accuracy lever after the
first-pass extraction.

Usage:
  python render_diff.py --original src.jpg --preview preview.png \
                        --out diff.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


GAP = 18
LABEL_H = 30


def _label_panel(img: Image.Image, label: str) -> Image.Image:
    """Stack a labeled header on top of an image."""
    canvas = Image.new(
        "RGB", (img.width, img.height + LABEL_H), "white",
    )
    canvas.paste(img, (0, LABEL_H))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    except Exception:
        font = ImageFont.load_default()
    draw.rectangle([(0, 0), (img.width, LABEL_H)], fill="#1f4ed8")
    draw.text((8, 5), label, fill="white", font=font)
    return canvas


def make_diff(original_path: Path, preview_path: Path,
              out_path: Path, target_h: int = 900) -> None:
    a = Image.open(original_path).convert("RGB")
    b = Image.open(preview_path).convert("RGB")

    # Normalise both to target height
    def _resize(img: Image.Image, h: int) -> Image.Image:
        new_w = max(1, int(img.width * h / img.height))
        return img.resize((new_w, h), Image.LANCZOS)

    a_n = _resize(a, target_h)
    b_n = _resize(b, target_h)

    # Build overlay panel: stretch built preview to source aspect, then
    # blend.  Useful even though aspect ratios differ, because relative
    # left-to-right ordering of components is preserved.
    overlay_b = b_n.resize(a_n.size, Image.LANCZOS)
    overlay = Image.blend(a_n, overlay_b, alpha=0.5)

    # Compose: [SOURCE] [GAP] [BUILT] [GAP] [OVERLAY]
    a_panel = _label_panel(a_n, "SOURCE (original)")
    b_panel = _label_panel(b_n, "BUILT (from sld_spec.json)")
    o_panel = _label_panel(overlay, "OVERLAY 50% (alignment check)")

    total_w = a_panel.width + b_panel.width + o_panel.width + 2 * GAP
    total_h = max(a_panel.height, b_panel.height, o_panel.height)
    canvas = Image.new("RGB", (total_w, total_h), "white")
    canvas.paste(a_panel, (0, 0))
    canvas.paste(b_panel, (a_panel.width + GAP, 0))
    canvas.paste(o_panel, (a_panel.width + b_panel.width + 2 * GAP, 0))
    canvas.save(out_path, optimize=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--preview",  type=Path, required=True)
    parser.add_argument("--out",      type=Path, required=True)
    parser.add_argument("--height",   type=int, default=900,
                        help="Target panel height in px (default 900)")
    args = parser.parse_args(argv)

    for p in (args.original, args.preview):
        if not p.exists():
            print(f"ERROR: not found: {p}", file=sys.stderr)
            return 2

    make_diff(args.original, args.preview, args.out, args.height)
    print(f"Diff: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

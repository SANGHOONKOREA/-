"""Tesseract OCR cross-check for printed labels.

This is a *cross-check*, not a primary extractor.  Vision models read
hand-drawn text well but printed digits unevenly; Tesseract reads
printed digits well but fails on hand-drawn text.  When both methods
agree on a digit you can trust the value; when they disagree, flag it
for the engineer.

Use on whole image (cluttered, less reliable):

    python ocr_check.py source.png

Or on a tightly cropped label region (highly reliable for printed):

    python ocr_check.py crop_tx1.png --whitelist 0123456789kVAV/.,

The whitelist restricts Tesseract to known characters and dramatically
reduces digit-vs-letter confusion on label fragments.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import pytesseract
    from PIL import Image
    HAS = True
except ImportError:
    HAS = False


def ocr(img_path: Path, lang: str = "eng",
        whitelist: str | None = None,
        psm: int = 6) -> dict:
    if not HAS:
        return {"error": "pytesseract / PIL not installed"}
    if not img_path.exists():
        return {"error": f"file not found: {img_path}"}
    img = Image.open(img_path)
    config_parts = [f"--psm {psm}"]
    if whitelist:
        config_parts.append(f"-c tessedit_char_whitelist={whitelist}")
    config = " ".join(config_parts)
    try:
        text = pytesseract.image_to_string(img, lang=lang, config=config)
        data = pytesseract.image_to_data(
            img, lang=lang, config=config,
            output_type=pytesseract.Output.DICT,
        )
        words = []
        for i, w in enumerate(data["text"]):
            if w.strip() and int(data["conf"][i]) > 0:
                words.append({
                    "text": w,
                    "conf": int(data["conf"][i]),
                    "box":  [data["left"][i], data["top"][i],
                             data["width"][i], data["height"][i]],
                })
        return {"text": text.strip(), "words": words}
    except pytesseract.TesseractNotFoundError:
        return {"error": "tesseract binary not found on system PATH"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--lang", default="eng",
                        help="Tesseract language pack(s), e.g. 'eng' "
                        "or 'eng+kor' (default eng)")
    parser.add_argument("--whitelist",
                        help="Restrict to these characters")
    parser.add_argument("--psm", type=int, default=6,
                        help="Tesseract page segmentation mode "
                        "(6=block, 7=single-line, 8=single-word, 11=sparse)")
    args = parser.parse_args(argv)
    result = ocr(args.input, args.lang, args.whitelist, args.psm)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())

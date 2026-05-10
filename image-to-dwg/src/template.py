"""DWG template setup: layers, text styles, drawing units, title block.

Conforms to a generic shipbuilding electrical drawing template that an
AutoCAD 2018 (R32) user is expected to receive.
"""
from __future__ import annotations

import ezdxf
from ezdxf.document import Drawing
from ezdxf.enums import TextEntityAlignment


# AutoCAD release -> DXF version code
DXF_VERSION_R2018 = "AC1032"


# Layer definitions: (name, ACI color, linetype, lineweight in 1/100 mm)
LAYERS = [
    ("0-FRAME",          7, "Continuous", 35),   # title block / sheet frame, white/black
    ("1-BUSBAR_440V",    1, "Continuous", 70),   # red, thick
    ("2-CABLE_690V",     3, "Continuous", 35),   # green
    ("2-CABLE_440V",     2, "Continuous", 35),   # yellow
    ("3-SYMBOL",         7, "Continuous", 25),   # white/black
    ("4-TEXT",           7, "Continuous", 18),   # white/black
    ("5-DIM",            8, "Continuous", 18),   # gray
    ("6-ANNO",           5, "Continuous", 25),   # blue (remark numbers)
    ("7-HIDDEN",         8, "DASHED",     18),   # gray, dashed (drawout breaker frame)
]


# Text styles. ISOCPEUR is the standard ISO style; we map to TrueType for
# portability when shx is not available.
TEXT_STYLES = [
    ("ISO",      "isocp.shx",   "isocp.shx"),
    ("ISO_BOLD", "isocpb.shx",  "isocpb.shx"),
    ("ROMANS",   "romans.shx",  "romans.shx"),
]


def create_document() -> Drawing:
    """Create a new DXF document targeting AutoCAD 2018 (R32)."""
    doc = ezdxf.new(dxfversion=DXF_VERSION_R2018, setup=True)
    doc.units = ezdxf.units.MM
    doc.header["$INSUNITS"] = 4  # millimetres
    doc.header["$LUNITS"] = 2    # decimal
    doc.header["$LUPREC"] = 1    # 1 decimal precision for length
    doc.header["$AUNITS"] = 0    # decimal degrees
    doc.header["$AUPREC"] = 1
    return doc


def setup_layers(doc: Drawing) -> None:
    # Ensure required linetypes exist (setup=True loads many; DASHED is included).
    for name, color, linetype, lineweight in LAYERS:
        if name in doc.layers:
            layer = doc.layers.get(name)
        else:
            layer = doc.layers.add(name)
        layer.color = color
        try:
            layer.dxf.linetype = linetype
        except Exception:
            layer.dxf.linetype = "Continuous"
        layer.dxf.lineweight = lineweight


def setup_text_styles(doc: Drawing) -> None:
    for name, font, big_font in TEXT_STYLES:
        if name not in doc.styles:
            doc.styles.add(name=name, font=font)


def setup_title_block(doc: Drawing) -> None:
    """Define the TITLE_BLOCK block. Attributes are filled at INSERT time."""
    if "TITLE_BLOCK" in doc.blocks:
        return
    blk = doc.blocks.new(name="TITLE_BLOCK")

    # Outer rectangle (180 x 40 mm)
    w, h = 180.0, 40.0
    pts = [(0, 0), (w, 0), (w, h), (0, h), (0, 0)]
    blk.add_lwpolyline(pts, dxfattribs={"layer": "0-FRAME"})

    # Internal divider lines
    blk.add_line((0, 30), (w, 30), dxfattribs={"layer": "0-FRAME"})
    blk.add_line((0, 20), (w, 20), dxfattribs={"layer": "0-FRAME"})
    blk.add_line((0, 10), (w, 10), dxfattribs={"layer": "0-FRAME"})
    blk.add_line((60, 0), (60, 30), dxfattribs={"layer": "0-FRAME"})
    blk.add_line((120, 0), (120, 30), dxfattribs={"layer": "0-FRAME"})
    blk.add_line((90, 30), (90, 40), dxfattribs={"layer": "0-FRAME"})

    # Static labels
    def _lbl(text: str, x: float, y: float, height: float = 2.0):
        t = blk.add_text(text, dxfattribs={"layer": "4-TEXT", "height": height, "style": "ISO"})
        t.set_placement((x, y), align=TextEntityAlignment.LEFT)

    _lbl("PROJECT",   2,  37, 2.0)
    _lbl("TITLE",     92, 37, 2.0)
    _lbl("DRAWN",     2,  27, 1.8)
    _lbl("CHECKED",   62, 27, 1.8)
    _lbl("APPROVED",  122, 27, 1.8)
    _lbl("DATE",      2,  17, 1.8)
    _lbl("SCALE",     62, 17, 1.8)
    _lbl("DWG NO.",   122, 17, 1.8)
    _lbl("REV",       2,  7,  1.8)

    # Attribute definitions (fillable)
    def _att(tag: str, prompt: str, default: str, x: float, y: float,
             height: float = 3.0):
        att = blk.add_attdef(
            tag=tag, text=default, insert=(x, y),
            dxfattribs={"layer": "4-TEXT", "height": height, "style": "ISO"},
        )
        att.dxf.prompt = prompt

    _att("PROJECT",  "Project name",  "SHI 18K BUNKERING VESSEL", 5, 32, 3.0)
    _att("TITLE",    "Drawing title", "ELECTRIC SINGLE LINE DIAGRAM", 95, 32, 3.0)
    _att("DRAWN",    "Drawn by",      "S&SYS",                     5, 22, 2.5)
    _att("CHECKED",  "Checked by",    "",                          65, 22, 2.5)
    _att("APPROVED", "Approved by",   "",                          125, 22, 2.5)
    _att("DATE",     "Date",          "2026-05-08",                5, 12, 2.5)
    _att("SCALE",    "Scale",         "NTS",                       65, 12, 2.5)
    _att("DWGNO",    "Drawing no.",   "SHI-18K-BV-ELE-SLD-001",    125, 12, 2.5)
    _att("REV",      "Revision",      "0",                         5, 2, 2.5)


def draw_sheet_frame(msp, sheet_w: float, sheet_h: float) -> None:
    """Draw outer sheet frame and inner drawing frame on the model space."""
    margin_outer = 5.0
    margin_inner = 15.0
    # Outer cut frame
    msp.add_lwpolyline(
        [(margin_outer, margin_outer),
         (sheet_w - margin_outer, margin_outer),
         (sheet_w - margin_outer, sheet_h - margin_outer),
         (margin_outer, sheet_h - margin_outer),
         (margin_outer, margin_outer)],
        dxfattribs={"layer": "0-FRAME"},
    )
    # Inner drawing frame (where all content lives)
    msp.add_lwpolyline(
        [(margin_inner, margin_inner),
         (sheet_w - margin_inner, margin_inner),
         (sheet_w - margin_inner, sheet_h - margin_inner),
         (margin_inner, sheet_h - margin_inner),
         (margin_inner, margin_inner)],
        dxfattribs={"layer": "0-FRAME"},
    )


def setup_template(doc: Drawing) -> None:
    setup_layers(doc)
    setup_text_styles(doc)
    setup_title_block(doc)

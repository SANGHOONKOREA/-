"""Assembles the SHI 18K Bunkering Vessel SLD into a DXF document.

Reads `sld_spec.json` (the structured spec captured from the source PowerPoint
screenshot) and emits an AutoCAD 2018 (R32) compatible DXF.

Key design rule: every cable is drawn from one block's named port to the
adjacent block's named port via `blocks.port(...)`.  This guarantees that no
line ever overshoots a symbol, falls short, or sits askew - the connection
geometry is implied by the block library, not duplicated in the builder.
"""
from __future__ import annotations

import json
from pathlib import Path

from ezdxf.document import Drawing
from ezdxf.enums import TextEntityAlignment

from . import blocks, template


BUS_LAYER = "1-BUSBAR_440V"
CABLE_690 = "2-CABLE_690V"
CABLE_440 = "2-CABLE_440V"
SYMBOL = "3-SYMBOL"
TEXT = "4-TEXT"
ANNO = "6-ANNO"


# ---------------------------------------------------------------------------
# Drawing primitives
# ---------------------------------------------------------------------------
def _text(msp, text: str, x: float, y: float, height: float = 2.5,
          layer: str = TEXT, align=TextEntityAlignment.LEFT,
          style: str = "ISO"):
    t = msp.add_text(
        text, dxfattribs={"layer": layer, "height": height, "style": style}
    )
    t.set_placement((x, y), align=align)
    return t


def _circle_marker(msp, x: float, y: float, no: int):
    msp.add_circle(center=(x, y), radius=2.0, dxfattribs={"layer": ANNO})
    _text(msp, str(no), x, y, height=2.5, layer=ANNO,
          align=TextEntityAlignment.MIDDLE_CENTER, style="ISO_BOLD")


def _insert(msp, name: str, xy: tuple[float, float],
            layer: str = SYMBOL):
    msp.add_blockref(name=name, insert=xy, dxfattribs={"layer": layer})
    return xy


def _connect(msp, top_block: str, top_xy: tuple[float, float],
             bottom_block: str, bottom_xy: tuple[float, float],
             layer: str) -> None:
    """Draw a straight cable from top_block's bottom port to
    bottom_block's top port.  Both ports must exist in BLOCK_PORTS."""
    p_top = blocks.port(top_block, "bottom", top_xy)
    p_bot = blocks.port(bottom_block, "top", bottom_xy)
    msp.add_line(p_top, p_bot, dxfattribs={"layer": layer})


def _connect_to_busbar(msp, top_block: str, top_xy: tuple[float, float],
                       busbar_y: float, layer: str) -> None:
    p_top = blocks.port(top_block, "bottom", top_xy)
    msp.add_line(p_top, (top_xy[0], busbar_y), dxfattribs={"layer": layer})


def _connect_from_busbar(msp, busbar_y: float,
                         bottom_block: str, bottom_xy: tuple[float, float],
                         layer: str) -> None:
    p_bot = blocks.port(bottom_block, "top", bottom_xy)
    msp.add_line((bottom_xy[0], busbar_y), p_bot,
                 dxfattribs={"layer": layer})


# ---------------------------------------------------------------------------
# Top-level build
# ---------------------------------------------------------------------------
def build(spec_path: Path, out_dxf_path: Path) -> Drawing:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    doc = template.create_document()
    template.setup_template(doc)
    blocks.define_all_blocks(doc)

    msp = doc.modelspace()

    sheet_w, sheet_h = spec["drawing"]["sheet_size_mm"]
    template.draw_sheet_frame(msp, sheet_w, sheet_h)

    # --- Title bar ------------------------------------------------------
    _text(
        msp, spec["drawing"]["title"],
        sheet_w / 2, spec["level_y"]["title"],
        height=6.0, layer=TEXT,
        align=TextEntityAlignment.MIDDLE_CENTER, style="ISO_BOLD",
    )

    # --- Title block (bottom-right) -------------------------------------
    tb_w = 180.0
    tb_x = sheet_w - 15.0 - tb_w
    tb_y = 15.0
    title_attribs = {
        "PROJECT":  "SHI 18K BUNKERING VESSEL",
        "TITLE":    "ELECTRIC SINGLE LINE DIAGRAM",
        "DRAWN":    spec["drawing"].get("drawn_by", ""),
        "CHECKED":  spec["drawing"].get("checked_by", ""),
        "APPROVED": spec["drawing"].get("approved_by", ""),
        "DATE":     spec["drawing"].get("date", ""),
        "SCALE":    spec["drawing"].get("scale", "NTS"),
        "DWGNO":    spec["drawing"].get("drawing_no", ""),
        "REV":      spec["drawing"].get("revision", "0"),
    }
    msp.add_blockref(
        name="TITLE_BLOCK", insert=(tb_x, tb_y),
        dxfattribs={"layer": "0-FRAME"},
    ).add_auto_attribs(title_attribs)

    # --- Main 440 V busbar ---------------------------------------------
    bus = spec["main_busbar"]
    L = spec["level_y"]
    y_bus = L["busbar"]

    # The busbar is drawn as two segments around the bus tie so that the
    # bus tie's own horizontal stubs (which extend from x +/- 2.5 to x +/- 6)
    # plug exactly into the busbar gap.
    tie_x = bus["tie"]["x"]
    bustie_left = blocks.port("IEC_BUSTIE", "left", (tie_x, y_bus))
    bustie_right = blocks.port("IEC_BUSTIE", "right", (tie_x, y_bus))
    msp.add_line((bus["x_start"], y_bus), bustie_left,
                 dxfattribs={"layer": BUS_LAYER, "lineweight": 70})
    msp.add_line(bustie_right, (bus["x_end"], y_bus),
                 dxfattribs={"layer": BUS_LAYER, "lineweight": 70})
    _insert(msp, "IEC_BUSTIE", (tie_x, y_bus))

    _text(msp, bus["label"], bus["label_xy"][0], bus["label_xy"][1],
          height=3.0, layer=TEXT, style="ISO_BOLD")

    # --- Generators and gen-side ACBs ----------------------------------
    for g in spec["generators"]:
        x = g["x"]
        gen_xy     = _insert(msp, "IEC_GEN",         (x, L["gen"]))
        gen_acb_xy = _insert(msp, "IEC_ACB_DRAWOUT", (x, L["gen_acb"]))
        # gen -> gen_acb (440V)
        _connect(msp, "IEC_GEN", gen_xy,
                 "IEC_ACB_DRAWOUT", gen_acb_xy, layer=CABLE_440)
        # gen_acb -> busbar
        _connect_to_busbar(msp, "IEC_ACB_DRAWOUT", gen_acb_xy,
                           y_bus, layer=CABLE_440)
        # Tag and ratings to the right of the generator
        _text(msp, g["tag"],            x + 7, L["gen"] + 3, 2.5,
              style="ISO_BOLD")
        _text(msp, f"{g['kva']} kVA",   x + 7, L["gen"] - 0.5, 2.0)
        _text(msp, f"{g['v']}V {g['hz']}Hz", x + 7, L["gen"] - 3.5, 2.0)

    # --- Feeders --------------------------------------------------------
    for f in spec["feeders"]:
        x = f["x"]

        fdr_acb_xy  = _insert(msp, "IEC_ACB_DRAWOUT", (x, L["feeder_acb"]))
        fdr_disc_xy = _insert(msp, "IEC_DISC",        (x, L["feeder_disc"]))
        tx_xy       = _insert(msp, "IEC_TX_3WND",     (x, L["tx"]))
        vfd_xy      = _insert(msp, "IEC_VFD",         (x, L["vfd"]))
        motor_xy    = _insert(msp, "IEC_MOTOR",       (x, L["motor"]))

        if f["thruster"]["type"] == "AZIMUTH":
            thruster_block = "IEC_AZIMUTH_THR"
            label = "AZIMUTH\\PTHRUSTER"
        else:
            thruster_block = "IEC_TUNNEL_THR"
            label = "TUNNEL\\PTHRUSTER"
        thr_xy = _insert(msp, thruster_block, (x, L["thruster"]))

        # Wiring (top to bottom)
        _connect_from_busbar(msp, y_bus,
                             "IEC_ACB_DRAWOUT", fdr_acb_xy, CABLE_440)
        _connect(msp, "IEC_ACB_DRAWOUT", fdr_acb_xy,
                 "IEC_DISC", fdr_disc_xy, CABLE_440)
        _connect(msp, "IEC_DISC", fdr_disc_xy,
                 "IEC_TX_3WND", tx_xy, CABLE_440)
        _connect(msp, "IEC_TX_3WND", tx_xy,
                 "IEC_VFD", vfd_xy, CABLE_690)
        _connect(msp, "IEC_VFD", vfd_xy,
                 "IEC_MOTOR", motor_xy, CABLE_690)
        _connect(msp, "IEC_MOTOR", motor_xy,
                 thruster_block, thr_xy, SYMBOL)

        # Transformer label and rating (left of TX)
        tx = f["transformer"]
        _circle_marker(msp, x - 32, L["tx_label"], f["remark_no_tx"])
        _text(msp, f"{tx['kva_primary']}kVA/{tx['kva_sec1']}kVA/{tx['kva_sec2']}kVA",
              x - 28, L["tx_label"] + 1.5, 2.2)
        _text(msp, f"{tx['v_primary']}V / {tx['v_sec1']}V / {tx['v_sec2']}V",
              x - 28, L["tx_label"] - 1.5, 2.2)
        _text(msp, tx["tag"], x + 7, L["tx"] + 0.5, 2.2, style="ISO_BOLD")

        # VFD label
        _circle_marker(msp, x - 18, L["vfd"], f["remark_no_vfd"])
        _text(msp, f["vfd"]["tag"], x + 9, L["vfd"] + 0.5, 2.2,
              style="ISO_BOLD")

        # Motor label (left)
        m = f["motor"]
        _circle_marker(msp, x - 32, L["motor_label"], f["remark_no_motor"])
        _text(msp, f"AC{m['v']}V",   x - 28, L["motor_label"] + 3.0, 2.0)
        _text(msp, f"{m['kw']}KW",   x - 28, L["motor_label"] + 0.5, 2.0)
        _text(msp, f"{m['hz']}HZ",   x - 28, L["motor_label"] - 2.0, 2.0)
        _text(msp, f"{m['rpm']}RPM", x - 28, L["motor_label"] - 4.5, 2.0)
        _text(msp, m["tag"], x + 7, L["motor"] + 0.5, 2.2, style="ISO_BOLD")

        # Thruster label (below symbol)
        msp.add_mtext(
            label,
            dxfattribs={
                "layer": TEXT, "char_height": 2.5, "style": "ISO_BOLD",
                "attachment_point": 2,
                "insert": (x, L["thruster_label"]),
            },
        )
        _text(msp, f["thruster"]["tag"], x + 11, L["thruster"], 2.2,
              style="ISO_BOLD")

    # --- Remarks panel (lower-left, mirrors title block) ---------------
    rem = spec["annotations"]["remark_table"]
    rx, ry = 22, 50
    _text(msp, "REMARKS", rx, ry, 3.5, style="ISO_BOLD", layer=ANNO)
    for i, item in enumerate(rem):
        y = ry - 8 - i * 6
        _circle_marker(msp, rx + 3, y + 1, item["no"])
        _text(msp, item["text"], rx + 8, y, 2.2,
              align=TextEntityAlignment.LEFT)

    # --- Save ----------------------------------------------------------
    out_dxf_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out_dxf_path)
    return doc

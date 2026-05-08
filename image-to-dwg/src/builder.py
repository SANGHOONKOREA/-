"""Assembles the SHI 18K Bunkering Vessel SLD into a DXF document.

Reads `sld_spec.json` (the structured spec that captures everything visible in
the source PowerPoint screenshot) and emits an AutoCAD 2018 (R32) compatible
DXF on disk.  Convert the DXF to DWG with the ODA File Converter (free) or by
opening it in AutoCAD and using SAVEAS DWG 2018.
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


def _text(msp, text: str, x: float, y: float, height: float = 2.5,
          layer: str = TEXT, align=TextEntityAlignment.LEFT,
          style: str = "ISO"):
    t = msp.add_text(
        text, dxfattribs={"layer": layer, "height": height, "style": style}
    )
    t.set_placement((x, y), align=align)
    return t


def _circle_marker(msp, x: float, y: float, no: int):
    """Draw the encircled remark number used in the original drawing."""
    msp.add_circle(center=(x, y), radius=2.0, dxfattribs={"layer": ANNO})
    _text(msp, str(no), x, y, height=2.5, layer=ANNO,
          align=TextEntityAlignment.MIDDLE_CENTER, style="ISO_BOLD")


def build(spec_path: Path, out_dxf_path: Path) -> Drawing:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    doc = template.create_document()
    template.setup_template(doc)
    blocks.define_all_blocks(doc)

    msp = doc.modelspace()

    sheet_w, sheet_h = spec["drawing"]["sheet_size_mm"]
    template.draw_sheet_frame(msp, sheet_w, sheet_h)

    # ---- Title bar (top of sheet) ---------------------------------------
    _text(
        msp, spec["drawing"]["title"],
        sheet_w / 2, spec["level_y"]["title"],
        height=6.0, layer=TEXT,
        align=TextEntityAlignment.MIDDLE_CENTER, style="ISO_BOLD",
    )

    # ---- Title block (bottom-right) -------------------------------------
    tb_w, tb_h = 180.0, 40.0
    tb_x = sheet_w - 15.0 - tb_w   # 15 mm inner margin
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

    # ---- Main 440 V busbar ----------------------------------------------
    bus = spec["main_busbar"]
    y_bus = bus["y"]
    msp.add_line((bus["x_start"], y_bus), (bus["x_end"], y_bus),
                 dxfattribs={"layer": BUS_LAYER, "lineweight": 70})
    _text(msp, bus["label"], bus["label_xy"][0], bus["label_xy"][1],
          height=3.0, layer=TEXT, style="ISO_BOLD")

    # Bus tie
    tie = bus["tie"]
    msp.add_blockref(
        name="IEC_BUSTIE", insert=(tie["x"], y_bus),
        dxfattribs={"layer": SYMBOL},
    )

    # ---- Generators and their drop-down feeders to the busbar ----------
    y_gen = spec["level_y"]["gen_symbol"]
    y_acb_top = spec["level_y"]["gen_acb"]
    for g in spec["generators"]:
        x = g["x"]
        # Generator symbol
        msp.add_blockref(
            name="IEC_GEN", insert=(x, y_gen),
            dxfattribs={"layer": SYMBOL},
        )
        # Cable from generator down to its ACB
        msp.add_line((x, y_gen - 5), (x, y_acb_top + 5),
                     dxfattribs={"layer": CABLE_440})
        # ACB between gen and busbar
        msp.add_blockref(
            name="IEC_ACB_DRAWOUT", insert=(x, y_acb_top),
            dxfattribs={"layer": SYMBOL},
        )
        # Cable from ACB down to busbar
        msp.add_line((x, y_acb_top - 5), (x, y_bus),
                     dxfattribs={"layer": CABLE_440})
        # Generator tag and rating
        _text(msp, g["tag"], x + 7, y_gen + 2,
              height=2.5, style="ISO_BOLD")
        _text(msp, f"{g['kva']} kVA", x + 7, y_gen - 1,
              height=2.0)
        _text(msp, f"{g['v']}V {g['hz']}Hz", x + 7, y_gen - 4,
              height=2.0)

    # ---- Feeders --------------------------------------------------------
    L = spec["level_y"]
    for f in spec["feeders"]:
        x = f["x"]

        # Feeder takeoff from busbar -> ACB -> Disconnector
        # Busbar to feeder ACB
        msp.add_line((x, y_bus), (x, L["feeder_acb"] + 5),
                     dxfattribs={"layer": CABLE_440})
        msp.add_blockref(
            name="IEC_ACB_DRAWOUT", insert=(x, L["feeder_acb"]),
            dxfattribs={"layer": SYMBOL},
        )
        msp.add_line((x, L["feeder_acb"] - 5), (x, L["feeder_disc"] + 5),
                     dxfattribs={"layer": CABLE_440})
        msp.add_blockref(
            name="IEC_DISC", insert=(x, L["feeder_disc"]),
            dxfattribs={"layer": SYMBOL},
        )

        # Disconnector down to transformer top stub
        msp.add_line(
            (x, L["feeder_disc"] - 5), (x, L["tx_symbol"] + 12),
            dxfattribs={"layer": CABLE_440},
        )

        # 3-winding transformer
        msp.add_blockref(
            name="IEC_TX_3WND", insert=(x, L["tx_symbol"]),
            dxfattribs={"layer": SYMBOL},
        )
        # TX rating label (left of transformer)
        tx = f["transformer"]
        _circle_marker(msp, x - 30, L["tx_label"], f["remark_no_tx"])
        _text(msp, f"{tx['kva_primary']}kVA/{tx['kva_sec1']}kVA/{tx['kva_sec2']}kVA",
              x - 26, L["tx_label"] + 1, height=2.2)
        _text(msp, f"{tx['v_primary']}V / {tx['v_sec1']}V / {tx['v_sec2']}V",
              x - 26, L["tx_label"] - 2.5, height=2.2)
        _text(msp, tx["tag"], x + 6, L["tx_symbol"], height=2.2,
              style="ISO_BOLD")

        # Transformer secondary stub down to VFD top
        msp.add_line(
            (x, L["tx_symbol"] - 12), (x, L["vfd_top"] + 14),
            dxfattribs={"layer": CABLE_690},
        )

        # VFD (rectifier on top, inverter on bottom)
        vfd_center_y = (L["vfd_top"] + L["vfd_bottom"]) / 2
        msp.add_blockref(
            name="IEC_VFD", insert=(x, vfd_center_y),
            dxfattribs={"layer": SYMBOL},
        )
        _circle_marker(msp, x - 18, vfd_center_y, f["remark_no_vfd"])
        _text(msp, f["vfd"]["tag"], x + 9, vfd_center_y, height=2.2,
              style="ISO_BOLD")

        # VFD bottom to motor symbol
        msp.add_line(
            (x, vfd_center_y - 14), (x, L["motor_symbol"] + 5),
            dxfattribs={"layer": CABLE_690},
        )

        # Motor
        msp.add_blockref(
            name="IEC_MOTOR", insert=(x, L["motor_symbol"]),
            dxfattribs={"layer": SYMBOL},
        )
        # Motor rating label (left)
        m = f["motor"]
        _circle_marker(msp, x - 30, L["motor_label"], f["remark_no_motor"])
        _text(msp, f"AC{m['v']}V", x - 26, L["motor_label"] + 1.5, height=2.2)
        _text(msp, f"{m['kw']}KW", x - 26, L["motor_label"] - 1.5, height=2.2)
        _text(msp, f"{m['hz']}HZ", x - 26, L["motor_label"] - 4.5, height=2.2)
        _text(msp, f"{m['rpm']}RPM", x - 26, L["motor_label"] - 7.5, height=2.2)
        _text(msp, m["tag"], x + 7, L["motor_symbol"], height=2.2,
              style="ISO_BOLD")

        # Motor shaft to thruster
        msp.add_line(
            (x, L["motor_symbol"] - 5), (x, L["thruster"] + 8),
            dxfattribs={"layer": SYMBOL, "lineweight": 50},
        )

        # Thruster
        if f["thruster"]["type"] == "AZIMUTH":
            msp.add_blockref(
                name="IEC_AZIMUTH_THR", insert=(x, L["thruster"]),
                dxfattribs={"layer": SYMBOL},
            )
            label = "AZIMUTH\\PTHRUSTER"
        else:
            msp.add_blockref(
                name="IEC_TUNNEL_THR", insert=(x, L["thruster"]),
                dxfattribs={"layer": SYMBOL},
            )
            label = "TUNNEL\\PTHRUSTER"

        # Two-line thruster label (uses MText to support line break)
        msp.add_mtext(
            label,
            dxfattribs={
                "layer": TEXT, "char_height": 2.5, "style": "ISO_BOLD",
                "attachment_point": 2,  # 2 = top center
                "insert": (x, L["thruster_label"]),
            },
        )
        _text(msp, f["thruster"]["tag"], x + 11, L["thruster"],
              height=2.2, style="ISO_BOLD")

    # ---- Remark table (lower-left, above the title block area) ---------
    rem = spec["annotations"]["remark_table"]
    rx, ry = 25, 70
    _text(msp, "REMARKS", rx, ry, height=3.5, style="ISO_BOLD", layer=ANNO)
    for i, item in enumerate(rem):
        y = ry - 6 - i * 5
        _circle_marker(msp, rx + 3, y, item["no"])
        _text(msp, item["text"], rx + 8, y - 1.2, height=2.0,
              align=TextEntityAlignment.LEFT)

    # ---- Save -----------------------------------------------------------
    out_dxf_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out_dxf_path)
    return doc

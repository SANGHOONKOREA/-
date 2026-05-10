"""IEC 60617 symbol block library for the SHI 18K BV SLD.

Each block has insertion point (0, 0) at the geometric "join" point that the
caller will place at a known coordinate on the drawing.  Every block also
exposes its connection ports through the BLOCK_PORTS table so that the
caller can draw cables that meet the symbol exactly - no gaps, no overlaps.

A port is defined relative to the block's insertion point, e.g. a port at
(0, +6) means "6 mm above the insertion point".  When a block is inserted at
world coordinate (x, y), the port lives at (x + dx, y + dy).
"""
from __future__ import annotations

import math
from typing import Dict

from ezdxf.document import Drawing
from ezdxf.enums import TextEntityAlignment


SYM = "3-SYMBOL"
TXT = "4-TEXT"
HID = "7-HIDDEN"


# ---------------------------------------------------------------------------
# Port table - the ONLY source of truth for where cables meet symbols.
# ---------------------------------------------------------------------------
BLOCK_PORTS: Dict[str, Dict[str, tuple[float, float]]] = {
    "IEC_GEN":          {"bottom": (0.0, -5.0)},
    "IEC_MOTOR":        {"top": (0.0,  5.0), "bottom": (0.0, -5.0)},
    "IEC_ACB_DRAWOUT":  {"top": (0.0,  6.0), "bottom": (0.0, -6.0)},
    "IEC_DISC":         {"top": (0.0,  5.0), "bottom": (0.0, -5.0)},
    "IEC_BUSTIE":       {"left": (-6.0, 0.0), "right": (6.0, 0.0)},
    "IEC_TX_3WND":      {"top": (0.0, 12.0), "bottom": (0.0, -12.0)},
    "IEC_VFD":          {"top": (0.0, 14.0), "bottom": (0.0, -14.0)},
    "IEC_AZIMUTH_THR":  {"top": (0.0,  8.0)},
    "IEC_TUNNEL_THR":   {"top": (0.0,  5.0)},
}


def port(block_name: str, port_name: str,
        insert_xy: tuple[float, float]) -> tuple[float, float]:
    """Return the world coordinate of a named port on a block instance."""
    dx, dy = BLOCK_PORTS[block_name][port_name]
    return (insert_xy[0] + dx, insert_xy[1] + dy)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _add_centered_text(blk, text: str, x: float, y: float, height: float,
                       layer: str = TXT, style: str = "ISO_BOLD"):
    t = blk.add_text(
        text,
        dxfattribs={"layer": layer, "height": height, "style": style},
    )
    t.set_placement((x, y), align=TextEntityAlignment.MIDDLE_CENTER)
    return t


def _add_attdef(blk, tag: str, default: str, x: float, y: float,
                height: float = 2.0, layer: str = TXT):
    blk.add_attdef(
        tag=tag, text=default, insert=(x, y),
        dxfattribs={"layer": layer, "height": height, "style": "ISO"},
    )


# ---------------------------------------------------------------------------
# Generator and Motor (rotating machine, IEC 60617 S00210)
# ---------------------------------------------------------------------------
def _rotating_machine(doc: Drawing, name: str, letter: str) -> None:
    if name in doc.blocks:
        return
    blk = doc.blocks.new(name=name)
    blk.add_circle(center=(0, 0), radius=5, dxfattribs={"layer": SYM})
    _add_centered_text(blk, letter, 0, 0, height=4.5)
    _add_attdef(blk, "TAG", "", 7, 0, height=2.5)


def define_gen(doc: Drawing) -> None:
    _rotating_machine(doc, "IEC_GEN", "G")


def define_motor(doc: Drawing) -> None:
    _rotating_machine(doc, "IEC_MOTOR", "M")


# ---------------------------------------------------------------------------
# Air Circuit Breaker - drawout type (IEC 60617 S00286 + drawout indication)
# ---------------------------------------------------------------------------
def define_acb_drawout(doc: Drawing) -> None:
    name = "IEC_ACB_DRAWOUT"
    if name in doc.blocks:
        return
    blk = doc.blocks.new(name=name)
    # Lead lines from the ports inward to the contact box
    blk.add_line((0, -6), (0, -2), dxfattribs={"layer": SYM})
    blk.add_line((0,  2), (0,  6), dxfattribs={"layer": SYM})
    # Contact (diagonal stroke through the box)
    blk.add_line((-1.5, -2), (1.5, 2), dxfattribs={"layer": SYM})
    # Square box at the contact (ACB indicator)
    blk.add_lwpolyline(
        [(-1.5, -2), (1.5, -2), (1.5, 2), (-1.5, 2), (-1.5, -2)],
        dxfattribs={"layer": SYM},
    )
    # Drawout (truck-mounted) indication: dashed rectangle around the symbol
    blk.add_lwpolyline(
        [(-3.5, -5), (3.5, -5), (3.5, 5), (-3.5, 5), (-3.5, -5)],
        dxfattribs={"layer": HID},
    )


# ---------------------------------------------------------------------------
# Disconnector / Isolator (IEC 60617 S00284)
# ---------------------------------------------------------------------------
def define_disconnector(doc: Drawing) -> None:
    name = "IEC_DISC"
    if name in doc.blocks:
        return
    blk = doc.blocks.new(name=name)
    # Lead lines from ports to contact dots
    blk.add_line((0, -5), (0, -1.5), dxfattribs={"layer": SYM})
    blk.add_line((0,  5), (0,  1.5), dxfattribs={"layer": SYM})
    # Open-contact diagonal
    blk.add_line((0, -1.5), (2.5, 2), dxfattribs={"layer": SYM})
    # Contact dots (filled circles)
    blk.add_circle(center=(0, -1.5), radius=0.4, dxfattribs={"layer": SYM})
    blk.add_circle(center=(0,  1.5), radius=0.4, dxfattribs={"layer": SYM})


# ---------------------------------------------------------------------------
# Bus tie breaker - drawn inline on the busbar.  The block draws the busbar
# segment THROUGH itself so the busbar line drawn by the caller stops at the
# block's left/right ports and the block fills the gap visually.
# ---------------------------------------------------------------------------
def define_bustie(doc: Drawing) -> None:
    name = "IEC_BUSTIE"
    if name in doc.blocks:
        return
    blk = doc.blocks.new(name=name)
    # Left and right horizontal stubs that meet the busbar exactly
    blk.add_line((-6, 0), (-2.5, 0), dxfattribs={"layer": SYM})
    blk.add_line(( 2.5, 0), ( 6, 0), dxfattribs={"layer": SYM})
    # Diagonal "open" indicator
    blk.add_line((-2.5, 0), (2.5, 2.5), dxfattribs={"layer": SYM})
    # Contact dots
    blk.add_circle(center=(-2.5, 0), radius=0.4, dxfattribs={"layer": SYM})
    blk.add_circle(center=( 2.5, 0), radius=0.4, dxfattribs={"layer": SYM})


# ---------------------------------------------------------------------------
# 3-winding transformer (IEC 60617 S00604)
# ---------------------------------------------------------------------------
def define_tx_3winding(doc: Drawing) -> None:
    name = "IEC_TX_3WND"
    if name in doc.blocks:
        return
    blk = doc.blocks.new(name=name)
    r = 3.5
    # Three overlapping circles on a vertical axis
    blk.add_circle(center=(0,  6),  radius=r, dxfattribs={"layer": SYM})
    blk.add_circle(center=(0,  0),  radius=r, dxfattribs={"layer": SYM})
    blk.add_circle(center=(0, -6),  radius=r, dxfattribs={"layer": SYM})
    # Lead stubs from top of top circle to top port, and from bottom of
    # bottom circle to bottom port (port at y = +/- 12).
    blk.add_line((0,  9.5), (0, 12), dxfattribs={"layer": SYM})
    blk.add_line((0, -9.5), (0, -12), dxfattribs={"layer": SYM})


# ---------------------------------------------------------------------------
# Rectifier (AC -> DC) and Inverter (DC -> AC) (IEC 60617 S00866 / S00867)
# ---------------------------------------------------------------------------
def _sine_wave(blk, x: float, y: float, length: float = 4.0, amp: float = 1.0):
    n = 16
    pts = []
    for i in range(n + 1):
        t = i / n
        px = x - length / 2 + length * t
        py = y + amp * math.sin(2 * math.pi * t)
        pts.append((px, py))
    blk.add_lwpolyline(pts, dxfattribs={"layer": SYM})


def _dc_symbol(blk, x: float, y: float, length: float = 4.0):
    blk.add_line((x - length / 2, y + 0.6), (x + length / 2, y + 0.6),
                 dxfattribs={"layer": SYM})
    seg = length / 5
    for i in range(0, 5, 2):
        blk.add_line(
            (x - length / 2 + i * seg, y - 0.6),
            (x - length / 2 + (i + 1) * seg, y - 0.6),
            dxfattribs={"layer": SYM},
        )


def define_rectifier(doc: Drawing) -> None:
    name = "IEC_RECTIFIER"
    if name in doc.blocks:
        return
    blk = doc.blocks.new(name=name)
    blk.add_lwpolyline(
        [(-6, -6), (6, -6), (6, 6), (-6, 6), (-6, -6)],
        dxfattribs={"layer": SYM},
    )
    blk.add_line((-6, -6), (6, 6), dxfattribs={"layer": SYM})
    _sine_wave(blk, x=-2, y=2.5, length=3.5, amp=0.8)
    _dc_symbol(blk, x=2, y=-2.5, length=3.5)


def define_inverter(doc: Drawing) -> None:
    name = "IEC_INVERTER"
    if name in doc.blocks:
        return
    blk = doc.blocks.new(name=name)
    blk.add_lwpolyline(
        [(-6, -6), (6, -6), (6, 6), (-6, 6), (-6, -6)],
        dxfattribs={"layer": SYM},
    )
    blk.add_line((-6, 6), (6, -6), dxfattribs={"layer": SYM})
    _dc_symbol(blk, x=-2, y=2.5, length=3.5)
    _sine_wave(blk, x=2, y=-2.5, length=3.5, amp=0.8)


# ---------------------------------------------------------------------------
# VFD = stacked rectifier (top half) + inverter (bottom half).
# Outer enclosure spans from y = -14 to y = +14, so ports are at +/- 14.
# ---------------------------------------------------------------------------
def define_vfd(doc: Drawing) -> None:
    name = "IEC_VFD"
    if name in doc.blocks:
        return
    blk = doc.blocks.new(name=name)
    # Outer enclosure 14 wide x 28 tall
    blk.add_lwpolyline(
        [(-7, -14), (7, -14), (7, 14), (-7, 14), (-7, -14)],
        dxfattribs={"layer": SYM},
    )
    # Internal divider between rectifier and inverter
    blk.add_line((-7, 0), (7, 0), dxfattribs={"layer": SYM})
    # Top half: rectifier (diagonal /, sine top-left, dc bottom-right)
    blk.add_line((-6, 1), (6, 13), dxfattribs={"layer": SYM})
    _sine_wave(blk, x=-2.5, y=10, length=3.5, amp=0.8)
    _dc_symbol(blk, x=2.5, y=4, length=3.5)
    # Bottom half: inverter (diagonal \, dc top-left, sine bottom-right)
    blk.add_line((-6, -1), (6, -13), dxfattribs={"layer": SYM})
    _dc_symbol(blk, x=-2.5, y=-4, length=3.5)
    _sine_wave(blk, x=2.5, y=-10, length=3.5, amp=0.8)


# ---------------------------------------------------------------------------
# Azimuth Thruster - propeller with 360 degree rotation indication
# ---------------------------------------------------------------------------
def define_azimuth_thruster(doc: Drawing) -> None:
    name = "IEC_AZIMUTH_THR"
    if name in doc.blocks:
        return
    blk = doc.blocks.new(name=name)
    # Propeller blades (front-view)
    blk.add_ellipse(center=(-2.5, 0), major_axis=(2.5, 0), ratio=0.45,
                    dxfattribs={"layer": SYM})
    blk.add_ellipse(center=( 2.5, 0), major_axis=(2.5, 0), ratio=0.45,
                    dxfattribs={"layer": SYM})
    # 360 degree rotation arc with arrowhead
    blk.add_arc(center=(0, 0), radius=7.5, start_angle=20, end_angle=340,
                dxfattribs={"layer": SYM})
    # Arrowhead
    arr_x = 7.5 * math.cos(math.radians(340))
    arr_y = 7.5 * math.sin(math.radians(340))
    blk.add_line((arr_x, arr_y), (arr_x - 1.0, arr_y + 1.4),
                 dxfattribs={"layer": SYM})
    blk.add_line((arr_x, arr_y), (arr_x + 1.0, arr_y + 1.4),
                 dxfattribs={"layer": SYM})
    # Drive shaft from top port (0, 8) down to top of propeller (~y=1.5)
    blk.add_line((0, 8), (0, 1.5), dxfattribs={"layer": SYM})


# ---------------------------------------------------------------------------
# Tunnel Thruster - propeller inside a horizontal tunnel
# ---------------------------------------------------------------------------
def define_tunnel_thruster(doc: Drawing) -> None:
    name = "IEC_TUNNEL_THR"
    if name in doc.blocks:
        return
    blk = doc.blocks.new(name=name)
    # Propeller blades
    blk.add_ellipse(center=(-2.5, 0), major_axis=(2.5, 0), ratio=0.45,
                    dxfattribs={"layer": SYM})
    blk.add_ellipse(center=( 2.5, 0), major_axis=(2.5, 0), ratio=0.45,
                    dxfattribs={"layer": SYM})
    # Tunnel walls
    blk.add_line((-9, 2.5), (9, 2.5), dxfattribs={"layer": SYM})
    blk.add_line((-9, -2.5), (9, -2.5), dxfattribs={"layer": SYM})
    # Bidirectional arrows
    blk.add_line((-9, 2.5), (-7.5, 3.3), dxfattribs={"layer": SYM})
    blk.add_line((-9, 2.5), (-7.5, 1.7), dxfattribs={"layer": SYM})
    blk.add_line(( 9, -2.5), (7.5, -3.3), dxfattribs={"layer": SYM})
    blk.add_line(( 9, -2.5), (7.5, -1.7), dxfattribs={"layer": SYM})
    # Drive shaft from top port (0, 5) down to top wall (y=2.5)
    blk.add_line((0, 5), (0, 2.5), dxfattribs={"layer": SYM})


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def define_all_blocks(doc: Drawing) -> None:
    define_gen(doc)
    define_motor(doc)
    define_acb_drawout(doc)
    define_disconnector(doc)
    define_bustie(doc)
    define_tx_3winding(doc)
    define_rectifier(doc)
    define_inverter(doc)
    define_vfd(doc)
    define_azimuth_thruster(doc)
    define_tunnel_thruster(doc)

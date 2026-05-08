"""IEC 60617 symbol block library for the SHI 18K BV SLD.

Each block has insertion point (0, 0) at the geometric "join" point that the
caller will place at a known coordinate on the drawing.  Connection stubs are
NOT included in the blocks - the caller draws explicit cables/busbars between
insertions.  This keeps blocks reusable across drawings with different stack
heights.

Block contents are placed on layer "3-SYMBOL" (geometry) and "4-TEXT" (lettering)
unless otherwise noted.
"""
from __future__ import annotations

import math

from ezdxf.document import Drawing
from ezdxf.enums import TextEntityAlignment


SYM = "3-SYMBOL"
TXT = "4-TEXT"
HID = "7-HIDDEN"


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
                height: float = 2.0, layer: str = TXT,
                align=TextEntityAlignment.LEFT):
    att = blk.add_attdef(
        tag=tag, text=default, insert=(x, y),
        dxfattribs={"layer": layer, "height": height, "style": "ISO"},
    )
    if align != TextEntityAlignment.LEFT:
        att.set_placement((x, y), align=align)
    return att


# ---------------------------------------------------------------------------
# Generator and Motor (rotating machine, IEC 60617 S00210)
# ---------------------------------------------------------------------------
def _rotating_machine(doc: Drawing, name: str, letter: str,
                      attribute_tag: str = "TAG") -> None:
    """Circle with a single capital letter in the middle (G or M)."""
    if name in doc.blocks:
        return
    blk = doc.blocks.new(name=name)
    blk.add_circle(center=(0, 0), radius=5, dxfattribs={"layer": SYM})
    _add_centered_text(blk, letter, 0, 0, height=4.5)
    _add_attdef(blk, attribute_tag, "", 7, 0, height=2.5)


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
    # Vertical lead line passing through the symbol
    blk.add_line((0, -6), (0, -2), dxfattribs={"layer": SYM})
    blk.add_line((0,  2), (0,  6), dxfattribs={"layer": SYM})
    # Breaker contact: short diagonal showing the moving contact
    blk.add_line((0, -2), (2.2, 2), dxfattribs={"layer": SYM})
    # ACB indicator: small filled square / box at the break point
    blk.add_lwpolyline(
        [(-1.5, -2.2), (1.5, -2.2), (1.5, 2.2), (-1.5, 2.2), (-1.5, -2.2)],
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
    # Lead in / lead out
    blk.add_line((0, -5), (0, -1.5), dxfattribs={"layer": SYM})
    blk.add_line((0,  1.5), (0,  5), dxfattribs={"layer": SYM})
    # Open-contact diagonal
    blk.add_line((0, -1.5), (2.5, 2), dxfattribs={"layer": SYM})
    # Contact dots
    blk.add_circle(center=(0, -1.5), radius=0.4, dxfattribs={"layer": SYM})
    blk.add_circle(center=(0,  1.5), radius=0.4, dxfattribs={"layer": SYM})


# ---------------------------------------------------------------------------
# Bus tie breaker (drawn inline on a horizontal busbar)
# ---------------------------------------------------------------------------
def define_bustie(doc: Drawing) -> None:
    name = "IEC_BUSTIE"
    if name in doc.blocks:
        return
    blk = doc.blocks.new(name=name)
    # Horizontal lead in/out
    blk.add_line((-6, 0), (-2.5, 0), dxfattribs={"layer": SYM})
    blk.add_line(( 2.5, 0), ( 6, 0), dxfattribs={"layer": SYM})
    # Open / break diagonal indicating a switching device
    blk.add_line((-2.5, 0), (2.5, 2.5), dxfattribs={"layer": SYM})
    # Contact dots
    blk.add_circle(center=(-2.5, 0), radius=0.4, dxfattribs={"layer": SYM})
    blk.add_circle(center=( 2.5, 0), radius=0.4, dxfattribs={"layer": SYM})


# ---------------------------------------------------------------------------
# 3-winding transformer (IEC 60617 S00604) - vertical stack
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
    # Lead stubs above the top circle and below the bottom circle
    blk.add_line((0,  9.5), (0, 12), dxfattribs={"layer": SYM})
    blk.add_line((0, -9.5), (0, -12), dxfattribs={"layer": SYM})


# ---------------------------------------------------------------------------
# Rectifier (AC -> DC) and Inverter (DC -> AC) (IEC 60617 S00866 / S00867)
# ---------------------------------------------------------------------------
def _sine_wave(blk, x: float, y: float, length: float = 4.0, amp: float = 1.0):
    """Approximate a single sine cycle as 16 line segments centred at (x,y)."""
    n = 16
    pts = []
    for i in range(n + 1):
        t = i / n
        px = x - length / 2 + length * t
        py = y + amp * math.sin(2 * math.pi * t)
        pts.append((px, py))
    blk.add_lwpolyline(pts, dxfattribs={"layer": SYM})


def _dc_symbol(blk, x: float, y: float, length: float = 4.0):
    """Draw '=' style DC indicator (one solid + one dashed line)."""
    blk.add_line((x - length / 2, y + 0.6), (x + length / 2, y + 0.6),
                 dxfattribs={"layer": SYM})
    # dashed-style equivalent using short segments
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
    # Square box 12 x 12
    blk.add_lwpolyline(
        [(-6, -6), (6, -6), (6, 6), (-6, 6), (-6, -6)],
        dxfattribs={"layer": SYM},
    )
    # Diagonal (top-right to bottom-left) separating AC and DC sides
    blk.add_line((-6, -6), (6, 6), dxfattribs={"layer": SYM})
    # AC sine wave in upper-left triangle (input side)
    _sine_wave(blk, x=-2, y=2.5, length=3.5, amp=0.8)
    # DC equals sign in lower-right triangle (output side)
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
    # Diagonal (top-left to bottom-right)
    blk.add_line((-6, 6), (6, -6), dxfattribs={"layer": SYM})
    # DC equals sign in upper-left triangle (input side)
    _dc_symbol(blk, x=-2, y=2.5, length=3.5)
    # AC sine wave in lower-right triangle (output side)
    _sine_wave(blk, x=2, y=-2.5, length=3.5, amp=0.8)


# ---------------------------------------------------------------------------
# VFD (Variable Frequency Drive) - rectifier + inverter combined
# ---------------------------------------------------------------------------
def define_vfd(doc: Drawing) -> None:
    name = "IEC_VFD"
    if name in doc.blocks:
        return
    blk = doc.blocks.new(name=name)
    # Outer enclosure 14 x 28 around two stacked 12x12 boxes
    blk.add_lwpolyline(
        [(-7, -14), (7, -14), (7, 14), (-7, 14), (-7, -14)],
        dxfattribs={"layer": SYM},
    )
    # Internal divider between rectifier (top) and inverter (bottom)
    blk.add_line((-7, 0), (7, 0), dxfattribs={"layer": SYM})
    # Top half: rectifier
    blk.add_line((-6, 1), (6, 13), dxfattribs={"layer": SYM})
    _sine_wave(blk, x=-2, y=9.5, length=3.5, amp=0.8)
    _dc_symbol(blk, x=2, y=4.5, length=3.5)
    # Bottom half: inverter
    blk.add_line((-6, -1), (6, -13), dxfattribs={"layer": SYM})
    _dc_symbol(blk, x=-2, y=-4.5, length=3.5)
    _sine_wave(blk, x=2, y=-9.5, length=3.5, amp=0.8)


# ---------------------------------------------------------------------------
# Azimuth Thruster - propeller with 360 degree rotation indication
# ---------------------------------------------------------------------------
def define_azimuth_thruster(doc: Drawing) -> None:
    name = "IEC_AZIMUTH_THR"
    if name in doc.blocks:
        return
    blk = doc.blocks.new(name=name)
    # Two side-by-side ellipses representing propeller blades (front view)
    blk.add_ellipse(center=(-2.5, 0), major_axis=(2.5, 0), ratio=0.45,
                    dxfattribs={"layer": SYM})
    blk.add_ellipse(center=( 2.5, 0), major_axis=(2.5, 0), ratio=0.45,
                    dxfattribs={"layer": SYM})
    # Rotation arrow: full circle around the assembly indicating 360 deg
    blk.add_arc(center=(0, 0), radius=8, start_angle=20, end_angle=340,
                dxfattribs={"layer": SYM})
    # Arrow head at the open end of the arc
    blk.add_line((7.5, -2.7), (8.5, -1.5), dxfattribs={"layer": SYM})
    blk.add_line((7.5, -2.7), (6.4, -1.7), dxfattribs={"layer": SYM})
    # Drive shaft stub
    blk.add_line((0, 5), (0, 8), dxfattribs={"layer": SYM})


# ---------------------------------------------------------------------------
# Tunnel Thruster - propeller inside a tunnel (bidirectional, horizontal)
# ---------------------------------------------------------------------------
def define_tunnel_thruster(doc: Drawing) -> None:
    name = "IEC_TUNNEL_THR"
    if name in doc.blocks:
        return
    blk = doc.blocks.new(name=name)
    # Two propeller ellipses
    blk.add_ellipse(center=(-2.5, 0), major_axis=(2.5, 0), ratio=0.45,
                    dxfattribs={"layer": SYM})
    blk.add_ellipse(center=( 2.5, 0), major_axis=(2.5, 0), ratio=0.45,
                    dxfattribs={"layer": SYM})
    # Tunnel walls (top and bottom horizontal lines extending through the unit)
    blk.add_line((-9, 2.5), (9, 2.5), dxfattribs={"layer": SYM})
    blk.add_line((-9, -2.5), (9, -2.5), dxfattribs={"layer": SYM})
    # Bidirectional arrows on tunnel walls
    blk.add_line((-9, 2.5), (-7.5, 3.3), dxfattribs={"layer": SYM})
    blk.add_line((-9, 2.5), (-7.5, 1.7), dxfattribs={"layer": SYM})
    blk.add_line((9, -2.5), (7.5, -3.3), dxfattribs={"layer": SYM})
    blk.add_line((9, -2.5), (7.5, -1.7), dxfattribs={"layer": SYM})
    # Drive shaft stub
    blk.add_line((0, 2.5), (0, 5), dxfattribs={"layer": SYM})


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

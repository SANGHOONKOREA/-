"""Render a DXF document to PNG and SVG using ezdxf's matplotlib backend.

Both outputs use a white background and the BackgroundPolicy.WHITE config so
that BYLAYER colour 7 (which AutoCAD inverts based on viewport background)
renders as solid black instead of being invisible on a white page.
"""
from __future__ import annotations

from pathlib import Path

import ezdxf
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend


def _render(dxf_path: Path, out_path: Path, dpi: int = 150) -> None:
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    fig, ax = plt.subplots(figsize=(20, 14.14), dpi=dpi)
    ctx = RenderContext(doc)
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE)
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend, config=cfg).draw_layout(msp, finalize=True)
    ax.axis("off")
    fig.savefig(
        out_path, dpi=dpi, bbox_inches="tight", pad_inches=0.1,
        facecolor="white",
    )
    plt.close(fig)


def render_png(dxf_path: Path, png_path: Path, dpi: int = 150) -> None:
    _render(dxf_path, png_path, dpi=dpi)


def render_svg(dxf_path: Path, svg_path: Path) -> None:
    _render(dxf_path, svg_path, dpi=150)

#!/usr/bin/env python3
"""Build the three A4 print sheets for the Noriël birth cards.

All sheets are A4 landscape, two pages each (front, back) for duplex
printing with FLIP ON LONG EDGE. `alt-short-edge-flip/` holds the same
sheets prepared for flip-on-short-edge printers.

    1-passport.pdf   2 passports per sheet. Card 125 x 176 mm, folds at 88 mm
                     to a 125 x 88 mm (88 x 125 upright) passport.
                     Page 1 outside (2_2.png), page 2 inside (1_2.png).
    2-ticket.pdf     2 boarding passes per sheet, 216.3 x 70 mm.
                     Page 1 artwork (1_1.png), page 2 designed back.
    3-tag.pdf        55 name tags per sheet, 50 x 16.2 mm, cut on shared lines.
                     Page 1 artwork (1.png), page 2 designed back.

Artwork is embedded losslessly at native resolution (no resampling) and
drawn exactly at trim size; 3 mm bleed around every piece is filled by
extending the artwork's edge pixels (or solid red for the tag).

Usage:
    python3 print/make_pdfs.py
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "source"
FONTS = HERE / "fonts"
ASSETS = HERE / "assets"
OUT = HERE / "out"

A4L = (297.0 * mm, 210.0 * mm)
BLEED = 3.0 * mm
MARK_GAP = 1.0 * mm
MARK_LEN = 5.0 * mm

# Colours sampled from the artwork.
RED = (85 / 255, 13 / 255, 26 / 255)
RED_SOFT = (99 / 255, 19 / 255, 33 / 255)    # faint watermark on red
GOLD = (218 / 255, 170 / 255, 68 / 255)
GOLD_SOFT = (232 / 255, 196 / 255, 120 / 255)

# Trim sizes in mm.
PASSPORT_W, PASSPORT_H = 125.0, 176.0        # unfolded, fold at 88 mm
TICKET_W, TICKET_H = 216.3, 70.0
TAG_W = 50.0
TAG_H = 50.0 * 647 / 2000                    # 16.175, follows the artwork ratio


# --------------------------------------------------------------------------- assets

@dataclass
class Asset:
    reader: ImageReader
    width: int      # un-padded pixel size
    height: int
    pad: int        # bleed padding in pixels (same on all sides)


def load_asset(name: str, trim_w_mm: float, bleed_fill: tuple[int, int, int] | None = None) -> Asset:
    """Load a PNG and pad it with bleed. The pad repeats the edge pixels unless
    `bleed_fill` gives a solid colour. Pixels are never resampled."""
    im = Image.open(SOURCE / name)
    im.load()
    if im.mode != "RGB":
        im = im.convert("RGB")
    arr = np.asarray(im)
    pad = int(round(BLEED / mm * im.width / trim_w_mm))
    if bleed_fill is None:
        padded = np.pad(arr, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
    else:
        padded = np.empty((arr.shape[0] + 2 * pad, arr.shape[1] + 2 * pad, 3), dtype=arr.dtype)
        padded[:, :] = np.array(bleed_fill, dtype=arr.dtype)
        padded[pad:pad + arr.shape[0], pad:pad + arr.shape[1]] = arr
    buf = io.BytesIO()
    Image.fromarray(padded).save(buf, format="PNG", compress_level=6)
    buf.seek(0)
    return Asset(ImageReader(buf), im.width, im.height, pad)


def place(c: canvas.Canvas, a: Asset, x: float, y: float, w: float, h: float, rot: int = 0) -> None:
    """Draw the asset so its un-padded artwork fills the trim rect (x, y, w, h)
    in points, rotated `rot` degrees counter-clockwise about the rect centre."""
    c.saveState()
    c.translate(x + w / 2, y + h / 2)
    c.rotate(rot)
    aw, ah = (h, w) if rot % 180 == 90 else (w, h)
    sx, sy = aw / a.width, ah / a.height
    px, py = a.pad * sx, a.pad * sy
    c.drawImage(a.reader, -aw / 2 - px, -ah / 2 - py, width=aw + 2 * px, height=ah + 2 * py)
    c.restoreState()


# --------------------------------------------------------------------------- marks

def _mark_style(c: canvas.Canvas) -> None:
    c.setLineWidth(0.25)
    c.setStrokeColorRGB(0, 0, 0)
    c.setDash()


def crop_marks(c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
    """Crop marks for a single piece with bleed around it."""
    g = BLEED + MARK_GAP
    c.saveState()
    _mark_style(c)
    for xx in (x, x + w):
        c.line(xx, y - g, xx, y - g - MARK_LEN)
        c.line(xx, y + h + g, xx, y + h + g + MARK_LEN)
    for yy in (y, y + h):
        c.line(x - g, yy, x - g - MARK_LEN, yy)
        c.line(x + w + g, yy, x + w + g + MARK_LEN, yy)
    c.restoreState()


def fold_marks(c: canvas.Canvas, x: float, y_fold: float, w: float) -> None:
    """Dashed fold marks left and right of a piece, at height y_fold."""
    g = BLEED + MARK_GAP
    c.saveState()
    _mark_style(c)
    c.setDash(1.5, 1.5)
    c.line(x - g, y_fold, x - g - MARK_LEN, y_fold)
    c.line(x + w + g, y_fold, x + w + g + MARK_LEN, y_fold)
    c.restoreState()


def grid_marks(c: canvas.Canvas, x: float, y: float, w: float, h: float, cols: int, rows: int) -> None:
    """Crop marks for a block of butt-joined pieces: one mark per cut line on
    each side of the block."""
    g = BLEED + MARK_GAP
    c.saveState()
    _mark_style(c)
    for i in range(cols + 1):
        xx = x + i * w / cols
        c.line(xx, y - g, xx, y - g - MARK_LEN)
        c.line(xx, y + h + g, xx, y + h + g + MARK_LEN)
    for j in range(rows + 1):
        yy = y + j * h / rows
        c.line(x - g, yy, x - g - MARK_LEN, yy)
        c.line(x + w + g, yy, x + w + g + MARK_LEN, yy)
    c.restoreState()


def sheet_label(c: canvas.Canvas, text: str) -> None:
    c.saveState()
    c.setFont("Helvetica", 6)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(8 * mm, 4 * mm, text)
    c.restoreState()


# --------------------------------------------------------------------------- vector art

def register_fonts() -> None:
    for name, file in [
        ("Poppins", "Poppins-Regular.ttf"),
        ("Poppins-Medium", "Poppins-Medium.ttf"),
        ("Poppins-SemiBold", "Poppins-SemiBold.ttf"),
        ("Bebas", "BebasNeue-Regular.ttf"),
        ("SpaceMono", "SpaceMono-Regular.ttf"),
        ("GreatVibes", "GreatVibes-Regular.ttf"),
    ]:
        pdfmetrics.registerFont(TTFont(name, str(FONTS / file)))


def tracked_width(text: str, font: str, size: float, track: float) -> float:
    return pdfmetrics.stringWidth(text, font, size) + track * max(len(text) - 1, 0)


def text(c: canvas.Canvas, x: float, y: float, s: str, font: str, size: float,
         track: float = 0.0, align: str = "left", color=GOLD) -> None:
    w = tracked_width(s, font, size, track)
    if align == "center":
        x -= w / 2
    elif align == "right":
        x -= w
    c.saveState()
    c.setFillColorRGB(*color)
    t = c.beginText(x, y)
    t.setFont(font, size)
    t.setCharSpace(track)
    t.textOut(s)
    c.drawText(t)
    c.restoreState()


_PLANE_PARTS = [
    # fuselage (full outline, nose at +x)
    [(1.0, 0.0), (0.93, 0.055), (0.6, 0.085), (0.0, 0.095), (-0.7, 0.075), (-0.96, 0.035), (-1.0, 0.0),
     (-0.96, -0.035), (-0.7, -0.075), (0.0, -0.095), (0.6, -0.085), (0.93, -0.055)],
    # wings
    [(0.34, 0.06), (-0.36, 0.98), (-0.58, 0.98), (-0.12, 0.06)],
    [(0.34, -0.06), (-0.36, -0.98), (-0.58, -0.98), (-0.12, -0.06)],
    # tail planes
    [(-0.72, 0.04), (-0.98, 0.42), (-1.1, 0.42), (-0.96, 0.04)],
    [(-0.72, -0.04), (-0.98, -0.42), (-1.1, -0.42), (-0.96, -0.04)],
]


def plane(c: canvas.Canvas, x: float, y: float, half_len: float, angle: float = 0.0, color=GOLD) -> None:
    """Top-down plane silhouette centred at (x, y), nose pointing +x rotated by `angle`."""
    c.saveState()
    c.translate(x, y)
    c.rotate(angle)
    c.scale(half_len, half_len)
    c.setFillColorRGB(*color)
    c.setStrokeColorRGB(*color)
    c.setLineWidth(0.08)
    c.setLineJoin(1)
    for part in _PLANE_PARTS:
        p = c.beginPath()
        p.moveTo(*part[0])
        for pt in part[1:]:
            p.lineTo(*pt)
        p.close()
        c.drawPath(p, stroke=1, fill=1)
    c.restoreState()


def heart(c: canvas.Canvas, x: float, y: float, size: float, color=GOLD, fill: bool = True) -> None:
    """Heart centred roughly at (x, y); `size` is its width."""
    s = size / 2
    c.saveState()
    c.translate(x, y + 0.15 * size)
    c.setFillColorRGB(*color)
    c.setStrokeColorRGB(*color)
    c.setLineWidth(max(size * 0.06, 0.3))
    p = c.beginPath()
    p.moveTo(0, -s * 0.95)
    p.curveTo(-s * 1.15, -s * 0.2, -s * 1.05, s * 0.75, -s * 0.5, s * 0.75)
    p.curveTo(-s * 0.2, s * 0.75, 0, s * 0.45, 0, s * 0.25)
    p.curveTo(0, s * 0.45, s * 0.2, s * 0.75, s * 0.5, s * 0.75)
    p.curveTo(s * 1.05, s * 0.75, s * 1.15, -s * 0.2, 0, -s * 0.95)
    p.close()
    c.drawPath(p, stroke=1, fill=1 if fill else 0)
    c.restoreState()


def dotted_curve(c: canvas.Canvas, pts, color=GOLD, width: float = 0.5, dash=(0.1, 1.6)) -> None:
    """Round-dotted cubic bezier through control points ((x0,y0),(c1),(c2),(x1,y1))."""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = pts
    c.saveState()
    c.setStrokeColorRGB(*color)
    c.setLineWidth(width)
    c.setLineCap(1)
    c.setDash(list(dash))
    p = c.beginPath()
    p.moveTo(x0, y0)
    p.curveTo(x1, y1, x2, y2, x3, y3)
    c.drawPath(p, stroke=1, fill=0)
    c.restoreState()


def barcode(c: canvas.Canvas, x: float, y: float, w: float, h: float, seed: str, color=GOLD) -> None:
    """Decorative Code-128-looking bars, deterministic from `seed`."""
    digest = hashlib.sha256(seed.encode()).digest() * 4
    widths = []
    for b in digest:
        widths.append(1 + (b & 3))
        widths.append(1 + ((b >> 2) & 3))
    # start/stop guards
    widths = [2, 1, 1, 2] + widths + [2, 3, 1, 1, 2]
    unit = w / sum(widths)
    c.saveState()
    c.setFillColorRGB(*color)
    cx = x
    for i, wd in enumerate(widths):
        if i % 2 == 0:
            c.rect(cx, y, wd * unit, h, stroke=0, fill=1)
        cx += wd * unit
    c.restoreState()


# --------------------------------------------------------------------------- world map

_ROBINSON_PLEN = [1.0000, 0.9986, 0.9954, 0.9900, 0.9822, 0.9730, 0.9600, 0.9427, 0.9216, 0.8962,
                  0.8679, 0.8350, 0.7986, 0.7597, 0.7186, 0.6732, 0.6213, 0.5722, 0.5322]
_ROBINSON_PDFE = [0.0000, 0.0620, 0.1240, 0.1860, 0.2480, 0.3100, 0.3720, 0.4340, 0.4958, 0.5571,
                  0.6176, 0.6769, 0.7346, 0.7903, 0.8435, 0.8936, 0.9394, 0.9761, 1.0000]


def _robinson(lon: float, lat: float) -> tuple[float, float]:
    """Robinson projection, unit radius. Returns x in [-2.67, 2.67], y in [-1.35, 1.35]."""
    a = abs(lat) / 5.0
    i = min(int(a), 17)
    f = a - i
    plen = _ROBINSON_PLEN[i] + (_ROBINSON_PLEN[i + 1] - _ROBINSON_PLEN[i]) * f
    pdfe = _ROBINSON_PDFE[i] + (_ROBINSON_PDFE[i + 1] - _ROBINSON_PDFE[i]) * f
    x = 0.8487 * plen * lon * 3.141592653589793 / 180.0
    y = 1.3523 * pdfe * (1 if lat >= 0 else -1)
    return x, y


def world_map(c: canvas.Canvas, cx: float, cy: float, width: float, color=RED_SOFT) -> None:
    """Fill the continents (no Antarctica) centred at (cx, cy), `width` points wide."""
    data = json.loads((ASSETS / "world.geo.json").read_text())
    scale = width / (2 * 0.8487 * 3.141592653589793)
    c.saveState()
    c.setFillColorRGB(*color)
    c.setStrokeColorRGB(*color)
    c.setLineWidth(0.15)
    c.setLineJoin(1)
    for feat in data["features"]:
        if feat["properties"].get("name") == "Antarctica":
            continue
        geom = feat["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        for poly in polys:
            ring = poly[0]              # outer ring only
            if len(ring) < 4:
                continue
            p = c.beginPath()
            for k, (lon, lat) in enumerate(ring):
                x, y = _robinson(lon, lat)
                X, Y = cx + x * scale, cy + y * scale
                if k == 0:
                    p.moveTo(X, Y)
                else:
                    p.lineTo(X, Y)
            p.close()
            c.drawPath(p, stroke=1, fill=1)
    c.restoreState()


# --------------------------------------------------------------------------- back designs

def ticket_back(c: canvas.Canvas, x: float, y: float) -> None:
    """Back of the boarding pass: a quiet background, no repeated details.
    (x, y) is the trim origin in points."""
    W, H = TICKET_W * mm, TICKET_H * mm
    stub_x = W * 1479.5 / 2000   # the perforation column on the front artwork
    main_cx = (stub_x - 12 * mm) / 2 + 2 * mm   # centre of the main section, left of the circle
    c.saveState()
    c.translate(x, y)
    p = c.beginPath()
    p.rect(-BLEED, -BLEED, W + 2 * BLEED, H + 2 * BLEED)
    c.clipPath(p, stroke=0, fill=0)
    c.setFillColorRGB(*RED)
    c.rect(-BLEED, -BLEED, W + 2 * BLEED, H + 2 * BLEED, stroke=0, fill=1)

    # faint world map across the whole ticket
    world_map(c, W / 2 + 4 * mm, H / 2, 148 * mm)   # 148 mm wide = 75 mm tall, within the bleed

    # sweeping flight path: heart at the left, dotted arc up to the plane circle
    circle_c = (stub_x - 22 * mm, 35 * mm)
    circle_r = 15 * mm
    heart(c, 16 * mm, 16 * mm, 3.4 * mm)
    dotted_curve(c, [(18.5 * mm, 17.5 * mm), (40 * mm, 60 * mm), (95 * mm, 62 * mm),
                     (circle_c[0] - circle_r * 0.72, circle_c[1] + circle_r * 0.72)],
                 width=0.7, dash=(0.1, 2.0))
    # thin solid sweep under the title, like a contrail
    c.setStrokeColorRGB(*GOLD)
    c.setLineWidth(0.35)
    sp = c.beginPath()
    sp.moveTo(-BLEED, 7 * mm)
    sp.curveTo(60 * mm, 4 * mm, 100 * mm, 14 * mm, circle_c[0] - circle_r * 0.7, circle_c[1] - circle_r * 0.7)
    c.drawPath(sp, stroke=1, fill=0)

    # title
    tx = 12 * mm + (circle_c[0] - circle_r - 12 * mm) / 2
    text(c, tx, 37 * mm, "DE WAELE AIRLINES", "Poppins-Medium", 21, track=6.5, align="center")
    text(c, tx, 29.5 * mm, "SMALL PASSENGER, BIG ADVENTURES", "Poppins", 7.6, track=3.2, align="center")

    # plane in a circle
    c.setFillColorRGB(*RED)
    c.setStrokeColorRGB(*GOLD)
    c.setLineWidth(0.9)
    c.circle(circle_c[0], circle_c[1], circle_r, stroke=1, fill=1)
    c.setLineWidth(0.3)
    c.circle(circle_c[0], circle_c[1], circle_r - 1.8 * mm, stroke=1, fill=0)
    plane(c, circle_c[0] + 0.3 * mm, circle_c[1], 8.6 * mm, angle=22)

    # perforation line (same place as on the front)
    c.setStrokeColorRGB(*GOLD)
    c.setLineWidth(0.6)
    c.setLineCap(1)
    c.setDash([0.1, 2.2])
    c.line(stub_x, -BLEED, stub_x, H + BLEED)
    c.setDash()

    # stub: just a heart on the map
    sx = (stub_x + W) / 2
    heart(c, sx, 35 * mm, 9 * mm, fill=False)
    c.restoreState()


def tag_back(c: canvas.Canvas, x: float, y: float) -> None:
    """Back of the name tag. Keeps 12.5 mm at both ends free for the hole."""
    W, H = TAG_W * mm, TAG_H * mm
    c.saveState()
    c.translate(x, y)
    c.setFillColorRGB(*RED)
    c.rect(0, 0, W, H, stroke=0, fill=1)   # bleed is handled by the neighbours / block edge
    cy = H / 2
    heart(c, 15 * mm, cy - 0.3 * mm, 2.6 * mm)
    dotted_curve(c, [(17.2 * mm, cy + 0.2 * mm), (21 * mm, cy + 4.2 * mm), (27 * mm, cy + 4.2 * mm),
                     (30.6 * mm, cy + 1.2 * mm)], width=0.55, dash=(0.1, 1.5))
    plane(c, 33.9 * mm, cy, 3.6 * mm, angle=-28)
    c.restoreState()


# --------------------------------------------------------------------------- sheets

def new_canvas(path: Path, title: str, subject: str) -> canvas.Canvas:
    c = canvas.Canvas(str(path), pagesize=A4L)
    c.setTitle(title)
    c.setAuthor("De Waele")
    c.setSubject(subject)
    c.setCreator("make_pdfs.py")
    return c


def start_back_page(c: canvas.Canvas, short_edge: bool) -> None:
    """For short-edge duplex the whole back page is rotated 180 degrees."""
    if short_edge:
        c.translate(A4L[0], A4L[1])
        c.rotate(180)


def build_passport(outside: Asset, inside: Asset, out_dir: Path, short_edge: bool) -> Path:
    W, H = PASSPORT_W * mm, PASSPORT_H * mm
    gap = 14 * mm
    x0 = (A4L[0] - (2 * W + gap)) / 2
    y0 = (A4L[1] - H) / 2
    xs = [x0, x0 + W + gap]
    path = out_dir / "1-passport.pdf"
    c = new_canvas(path, "Noriël - passport", f"2-up, card {PASSPORT_W:g} x {PASSPORT_H:g} mm, fold at 88 mm, 3 mm bleed")
    flip = "short" if short_edge else "long"
    for page, (asset, side) in enumerate([(outside, "outside"), (inside, "inside")]):
        c.saveState()
        if page == 1:
            start_back_page(c, short_edge)
        for x in xs:
            place(c, asset, x, y0, W, H, rot=90)
            crop_marks(c, x, y0, W, H)
            fold_marks(c, x, y0 + H / 2, W)
        sheet_label(c, f"Noriël passport · {side} (page {page + 1}/2) · card {PASSPORT_W:g} x {PASSPORT_H:g} mm, "
                       f"fold at 88 mm · 3 mm bleed · duplex, flip on {flip} edge")
        c.restoreState()
        c.showPage()
    c.save()
    return path


def build_ticket(front: Asset, out_dir: Path, short_edge: bool) -> Path:
    W, H = TICKET_W * mm, TICKET_H * mm
    gap = 14 * mm
    x0 = (A4L[0] - W) / 2
    y0 = (A4L[1] - (2 * H + gap)) / 2
    ys = [y0, y0 + H + gap]
    path = out_dir / "2-ticket.pdf"
    c = new_canvas(path, "Noriël - boarding pass", f"2-up, ticket {TICKET_W:g} x {TICKET_H:g} mm, 3 mm bleed")
    flip = "short" if short_edge else "long"
    for page in (0, 1):
        c.saveState()
        if page == 1:
            start_back_page(c, short_edge)
        for y in ys:
            if page == 0:
                place(c, front, x0, y, W, H)
            else:
                ticket_back(c, x0, y)
            crop_marks(c, x0, y, W, H)
        sheet_label(c, f"Noriël boarding pass · {'front' if page == 0 else 'back'} (page {page + 1}/2) · "
                       f"ticket {TICKET_W:g} x {TICKET_H:g} mm · 3 mm bleed · duplex, flip on {flip} edge")
        c.restoreState()
        c.showPage()
    c.save()
    return path


def build_tag(front: Asset, out_dir: Path, short_edge: bool) -> Path:
    W, H = TAG_W * mm, TAG_H * mm
    cols, rows = 5, 11
    BW, BH = cols * W, rows * H
    x0 = (A4L[0] - BW) / 2
    y0 = (A4L[1] - BH) / 2
    path = out_dir / "3-tag.pdf"
    c = new_canvas(path, "Noriël - name tag", f"{cols * rows}-up, tag {TAG_W:g} x {TAG_H:.1f} mm, shared cut lines, 3 mm bleed")
    flip = "short" if short_edge else "long"
    for page in (0, 1):
        c.saveState()
        if page == 1:
            start_back_page(c, short_edge)
        # solid red under the whole block including bleed (the tag edges are plain red)
        c.setFillColorRGB(*RED)
        c.rect(x0 - BLEED, y0 - BLEED, BW + 2 * BLEED, BH + 2 * BLEED, stroke=0, fill=1)
        for j in range(rows):
            for i in range(cols):
                x, y = x0 + i * W, y0 + j * H
                if page == 0:
                    # clip each tag to its own cell so neighbours never cover it
                    c.saveState()
                    p = c.beginPath()
                    p.rect(x, y, W, H)
                    c.clipPath(p, stroke=0, fill=0)
                    place(c, front, x, y, W, H)
                    c.restoreState()
                else:
                    tag_back(c, x, y)
        grid_marks(c, x0, y0, BW, BH, cols, rows)
        sheet_label(c, f"Noriël name tag · {'front' if page == 0 else 'back'} (page {page + 1}/2) · "
                       f"tag {TAG_W:g} x {TAG_H:.1f} mm, {cols} x {rows} = {cols * rows} per sheet, cut on the shared lines · "
                       f"duplex, flip on {flip} edge")
        c.restoreState()
        c.showPage()
    c.save()
    return path


def main() -> int:
    needed = ["2_2.png", "1_2.png", "1_1.png", "1.png"]
    missing = [f for f in needed if not (SOURCE / f).exists()]
    if missing:
        print(f"missing source images in {SOURCE}: {missing}", file=sys.stderr)
        return 1
    register_fonts()
    outside = load_asset("2_2.png", PASSPORT_H)        # artwork width runs along the card height (rotated)
    inside = load_asset("1_2.png", PASSPORT_H)
    ticket = load_asset("1_1.png", TICKET_W)
    tag = load_asset("1.png", TAG_W, bleed_fill=(85, 13, 26))

    for short_edge, out_dir in [(False, OUT), (True, OUT / "alt-short-edge-flip")]:
        out_dir.mkdir(parents=True, exist_ok=True)
        for p in (build_passport(outside, inside, out_dir, short_edge),
                  build_ticket(ticket, out_dir, short_edge),
                  build_tag(tag, out_dir, short_edge)):
            print(p.relative_to(HERE.parent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

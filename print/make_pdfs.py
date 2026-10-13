#!/usr/bin/env python3
"""Build print-ready PDFs for the Noriël birth cards.

Every card is a two-page PDF (one page per side). Each page is the trim size
plus 3 mm bleed on every edge. The bleed is filled by extending the outer
pixels of the design outward, so the artwork itself stays exactly at trim
size and nothing in the design is lost when the printer cuts the card.

PDF boxes are set so a print shop can read the trim size from the file:
MediaBox = BleedBox = trim + bleed, TrimBox = ArtBox = trim.

Usage:
    python3 print/make_pdfs.py            # writes print/out/*.pdf
    python3 print/make_pdfs.py --marks    # also writes print/out/cropmarks/*.pdf

Edit TRIM_MM below if the print shop wants another size. The artwork is
scaled to fill the trim box, so only the aspect ratio matters.
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "source"
OUT = HERE / "out"

BLEED_MM = 3.0
MARK_LEN_MM = 5.0   # crop mark length
MARK_GAP_MM = 1.0   # gap between the bleed edge and the start of the mark

# Trim sizes in mm (width, height).
TRIM_MM = {
    # A5 landscape, folded once to A6 (105 x 148 mm). Outside: left half is
    # the back cover (map), right half is the front cover (Belgian passport).
    # Inside: left page is the invitation, right page is the passport data.
    "passport": (210.0, 148.0),
    # Same width as the open passport. Height follows the artwork ratio.
    "boarding-pass": (210.0, 68.0),
}

# card name -> (trim key, [(side label, source file), ...])
CARDS = {
    "passport": ("passport", [("outside", "2_2.png"), ("inside", "1_2.png")]),
    "boarding-pass": ("boarding-pass", [("front", "1_1.png"), ("back", "1.png")]),
    # Alternatives, in case the plain red sides are the intended backs.
    "boarding-pass-plain-back": ("boarding-pass", [("front", "1_1.png"), ("back", "2_1.png")]),
    "name-strip": ("boarding-pass", [("front", "1.png"), ("back", "2.png")]),
}


def load_rgb(path: Path) -> Image.Image:
    im = Image.open(path)
    im.load()
    if im.mode != "RGB":
        im = im.convert("RGB")
    return im


def add_bleed(im: Image.Image, trim_w_mm: float, bleed_mm: float) -> tuple[Image.Image, int]:
    """Pad the image on all sides by `bleed_mm` worth of pixels, repeating edge pixels."""
    px_per_mm = im.width / trim_w_mm
    pad = int(round(bleed_mm * px_per_mm))
    arr = np.asarray(im)
    padded = np.pad(arr, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
    return Image.fromarray(padded), pad


def draw_crop_marks(c: canvas.Canvas, ox: float, oy: float, tw: float, th: float, bleed: float) -> None:
    """Draw crop marks around the trim rectangle (ox, oy, tw, th) in points."""
    gap = bleed + MARK_GAP_MM * mm
    length = MARK_LEN_MM * mm
    c.saveState()
    c.setLineWidth(0.25)
    c.setStrokeColorRGB(0, 0, 0)
    for x in (ox, ox + tw):
        c.line(x, oy - gap, x, oy - gap - length)              # bottom
        c.line(x, oy + th + gap, x, oy + th + gap + length)    # top
    for y in (oy, oy + th):
        c.line(ox - gap, y, ox - gap - length, y)              # left
        c.line(ox + tw + gap, y, ox + tw + gap + length, y)    # right
    c.restoreState()


def build(card: str, marks: bool, out_dir: Path) -> Path:
    trim_key, sides = CARDS[card]
    trim_w_mm, trim_h_mm = TRIM_MM[trim_key]
    tw, th = trim_w_mm * mm, trim_h_mm * mm
    bleed = BLEED_MM * mm
    slug = (MARK_GAP_MM + MARK_LEN_MM + 1.0) * mm if marks else 0.0

    page_w = tw + 2 * bleed + 2 * slug
    page_h = th + 2 * bleed + 2 * slug
    ox, oy = bleed + slug, bleed + slug  # trim origin on the page

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{card}.pdf"
    c = canvas.Canvas(str(out_path), pagesize=(page_w, page_h))
    c.setTitle(f"Noriël De Waele - {card}")
    c.setAuthor("De Waele")
    c.setSubject(f"{trim_w_mm:g} x {trim_h_mm:g} mm + {BLEED_MM:g} mm bleed")

    for label, filename in sides:
        im = load_rgb(SOURCE / filename)
        padded, pad = add_bleed(im, trim_w_mm, BLEED_MM)
        # Round-trip through PNG so reportlab embeds it losslessly.
        buf = io.BytesIO()
        padded.save(buf, format="PNG")
        buf.seek(0)
        reader = ImageReader(buf)

        # Scale so the un-padded artwork lands exactly on the trim box. The
        # horizontal and vertical scales differ by well under 1% for these
        # sources, which is invisible and avoids cropping the design.
        sx, sy = tw / im.width, th / im.height
        c.drawImage(reader, ox - pad * sx, oy - pad * sy,
                    width=padded.width * sx, height=padded.height * sy)

        if marks:
            draw_crop_marks(c, ox, oy, tw, th, bleed)
            c.saveState()
            c.setFont("Helvetica", 6)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(ox, page_h - (slug / 2),
                         f"{card} / {label} / trim {trim_w_mm:g} x {trim_h_mm:g} mm / bleed {BLEED_MM:g} mm")
            c.restoreState()

        bx, by = ox - bleed, oy - bleed
        c.setTrimBox((ox, oy, ox + tw, oy + th))
        c.setArtBox((ox, oy, ox + tw, oy + th))
        c.setBleedBox((bx, by, bx + tw + 2 * bleed, by + th + 2 * bleed))
        c.showPage()

    c.save()
    return out_path


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--marks", action="store_true", help="also write versions with crop marks")
    ap.add_argument("--only", nargs="*", choices=sorted(CARDS), help="build only these cards")
    args = ap.parse_args(argv)

    missing = [f for _, sides in CARDS.values() for _, f in sides if not (SOURCE / f).exists()]
    if missing:
        print(f"missing source images in {SOURCE}: {sorted(set(missing))}", file=sys.stderr)
        return 1

    for card in (args.only or list(CARDS)):
        p = build(card, marks=False, out_dir=OUT)
        print(p.relative_to(HERE.parent))
        if args.marks:
            p = build(card, marks=True, out_dir=OUT / "cropmarks")
            print(p.relative_to(HERE.parent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

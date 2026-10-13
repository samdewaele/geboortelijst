# Print sheets for the birth cards

`make_pdfs.py` turns the exported card artwork in `source/` into three A4
print sheets in `out/`. `source/` and `out/` are git-ignored because the
artwork carries the baby photo and the home address; keep them local and
hand the PDFs to the printer directly.

## Build

```
python3 print/make_pdfs.py
```

Needs Pillow, numpy and reportlab. Fonts in `fonts/` are Google Fonts under
the SIL Open Font License (Poppins, Bebas Neue, Space Mono, Great Vibes).

## Source files

| File      | Content                                       | Used in |
|-----------|-----------------------------------------------|---------|
| `2_2.png` | Passport cover (map = back, Belgium = front)  | `1-passport.pdf` page 1 |
| `1_2.png` | Passport inside (invitation + ID page)        | `1-passport.pdf` page 2 |
| `1_1.png` | Boarding pass                                 | `2-ticket.pdf` page 1 |
| `1.png`   | Name tag                                      | `3-tag.pdf` page 1 |
| `2.png`, `2_1.png` | Plain red export pages               | not used |

## Output

All sheets are A4 landscape, two pages: page 1 is the front, page 2 the
back. Print double-sided with **flip on long edge**. If the printer only
offers flip on short edge, use the files in `out/alt-short-edge-flip/`
instead (same sheets, back page rotated 180 degrees).

| PDF              | Pieces per sheet | Piece size | Notes |
|------------------|------------------|------------|-------|
| `1-passport.pdf` | 2                | 125 x 176 mm, fold at 88 mm | Folded: 125 x 88 mm lying on the sheet, i.e. an upright 88 x 125 mm passport. Artwork is rotated 90 degrees so the fold runs across the card. Dashed marks show the fold. |
| `2-ticket.pdf`   | 2                | 216.3 x 70 mm | Back is a designed boarding-pass reverse; its perforation line sits exactly behind the one on the front. |
| `3-tag.pdf`      | 55 (5 x 11)      | 50 x 16.2 mm | Tags butt against each other and are cut on the shared lines. Back has a heart, trail and plane in the middle; 12.5 mm at both ends stays plain for the hole. |

Each piece has 3 mm bleed. For the artwork the bleed repeats the outer
pixels (solid red for the tag) so the design itself is not cropped. Crop
marks sit outside the bleed. A small label in the bottom-left margin names
the sheet, side and flip setting; it is outside every piece.

Images are embedded losslessly at native resolution and drawn exactly at
trim size, which gives about 289 dpi for the passport, 235 dpi for the
ticket and 1016 dpi for the tag. Colours are RGB; a print shop converts to
CMYK, so ask for a proof if the exact red matters.

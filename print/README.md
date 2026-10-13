# Print files for the birth cards

`make_pdfs.py` turns the exported card artwork in `source/` into print-ready
PDFs in `out/`. Both folders are git-ignored because the artwork contains the
baby photo and the home address; keep them local and hand the PDFs to the
print shop directly.

## Build

```
python3 print/make_pdfs.py          # out/*.pdf
python3 print/make_pdfs.py --marks  # also out/cropmarks/*.pdf with crop marks
```

Needs Pillow, numpy and reportlab.

## Source files

| File      | Content                                   | Used as                      |
|-----------|-------------------------------------------|------------------------------|
| `2_2.png` | Passport cover (map left, Belgium right)  | `passport.pdf` page 1 (outside) |
| `1_2.png` | Passport inside spread (invite + ID page) | `passport.pdf` page 2 (inside)  |
| `1_1.png` | Boarding pass                             | `boarding-pass.pdf` page 1   |
| `1.png`   | Name strip with map                       | `boarding-pass.pdf` page 2   |
| `2.png`   | Plain red                                 | `name-strip.pdf` page 2      |
| `2_1.png` | Plain red                                 | `boarding-pass-plain-back.pdf` page 2 |

## Output

Every PDF has one page per side, at trim size plus 3 mm bleed on each edge.
The bleed repeats the outer pixels of the artwork, so the design itself is
not cropped. TrimBox and BleedBox are set so the print shop can read the
sizes from the file.

| PDF                            | Trim size        | Notes |
|--------------------------------|------------------|-------|
| `passport.pdf`                 | 210 x 148 mm     | A5 landscape, fold once to A6. Fold line at 105 mm. |
| `boarding-pass.pdf`            | 210 x 68 mm      | Front: boarding pass. Back: name strip. |
| `boarding-pass-plain-back.pdf` | 210 x 68 mm      | Same front with the plain red back. |
| `name-strip.pdf`               | 210 x 68 mm      | Name strip front, plain red back. |

`out/cropmarks/` holds the same files with crop marks and a small label in
the margin, for proofing or for a printer that asks for marks.

The artwork is 2000 px wide, which is about 240 dpi at these sizes. Colours
are RGB; most print shops convert to CMYK themselves. To change a size, edit
`TRIM_MM` in `make_pdfs.py`. The artwork is stretched to the trim box, so
keep the width-to-height ratio close to the source (about 1.41:1 for the
passport, 3.09:1 for the boarding pass).

#!/usr/bin/env python3
"""
Cut the aprs.fi symbol sprite sheets (hessu/aprs-symbols) into one PNG per symbol.

    python3 aprs_symbols.py SHEET_DIR OUT_DIR

SHEET_DIR holds aprs-symbols-24-{0,1,2}@2x.png (48 x 48 pixels per symbol,
16 columns, symbols in ASCII order from "!"): 0 = primary table, 1 = alternate
table, 2 = overlay characters. Written are

    p-XX.png      primary table, XX = hex code of the symbol character
    s-XX.png      alternate table
    o-YY-XX.png   alternate symbol XX with overlay character YY (0-9, A-Z)

radiomoni/aprs_parse.py names the same files (`symbol_id`). The sheets are not
part of the repository (mixed licences, see docs/usage.md); the web image
downloads a pinned version at build time.
"""

import sys
from pathlib import Path

from PIL import Image

CELL = 48
COLUMNS = 16
OVERLAYS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'


def cell(sheet: Image.Image, char: str) -> Image.Image:
    index = ord(char) - 33
    x, y = (index % COLUMNS) * CELL, (index // COLUMNS) * CELL
    return sheet.crop((x, y, x + CELL, y + CELL))


def main(sheet_dir: str, out_dir: str) -> None:
    src, out = Path(sheet_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    primary, alternate, overlay = (Image.open(src / f'aprs-symbols-24-{n}@2x.png').convert('RGBA')
                                   for n in range(3))
    count = 0
    for code in map(chr, range(33, 127)):
        name = f'{ord(code):02x}'
        cell(primary, code).save(out / f'p-{name}.png', optimize=True)
        base = cell(alternate, code)
        base.save(out / f's-{name}.png', optimize=True)
        count += 2
        for ov in OVERLAYS:
            Image.alpha_composite(base, cell(overlay, ov)).save(out / f'o-{ord(ov):02x}-{name}.png', optimize=True)
            count += 1
    print(f'{count} APRS symbols written to {out}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])

#!/usr/bin/env python3
"""
Copy hindstrike's explosion and smoke animations into assets/src/fx.bmp.

    python3 tools/fx_art.py [~/hindstrike/gfx/sprites1.bmp]

One-off authoring helper, not part of the build: it writes the sheet the
Makefile's bmp2chr rule converts (4bpp, through tools/bmp4.py, since
bmp2chr -b4 insists on a 4-bit BMP and PIL writes only 8-bit).

hindstrike's sprites1.bmp is a 128-wide sheet of 16x16 cells; an animation
is a row of cells its particle code steps through two tiles at a time
(game_particles.asm). The three taken, each to a row of fx.bmp, which is
what src/fx.r65's FX_* tile numbers count from:

    fx row 0  SPR_EXPLODE_1  ($A0: cells 0-7 of row 5)  big explosion, 8 frames
    fx row 1  SPR_EXPLODE_2  ($88: cells 4-7 of row 4)  small explosion, 4 frames
    fx row 2  SPR_SMOKE      ($C0: cells 0-7 of row 6)  spark to smoke ring, 8 frames

The palette is sprites1's own 16 colours: entry 0, its olive background, is
the transparent one, so it is copied as it is (video.r65 uploads it as OBJ
palette 5).
"""
import os
import sys

from PIL import Image

from bmp4 import save_bmp4

OUT = 'assets/src/fx.bmp'
CELL = 16
ROWS = [
    (5, 0, 8),          # (source cell row, first cell, cells) per fx row
    (4, 4, 4),
    (6, 0, 8),
]


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/hindstrike/gfx/sprites1.bmp')
    sheet = Image.open(src)
    assert sheet.mode == 'P' and sheet.size[0] == 128, (sheet.mode, sheet.size)
    out = Image.new('P', (128, CELL * len(ROWS)), 0)
    out.putpalette(sheet.getpalette()[:48])
    for r, (row, first, cells) in enumerate(ROWS):
        box = (first * CELL, row * CELL, (first + cells) * CELL, (row + 1) * CELL)
        out.paste(sheet.crop(box), (0, r * CELL))
    save_bmp4(out, OUT)
    print(f"{OUT}: {len(ROWS)} animations from {src}")


if __name__ == '__main__':
    main()

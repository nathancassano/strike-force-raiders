#!/usr/bin/env python3
"""
Stamp the gunfire sprites into assets/src/obj.bmp: the round and its
impact on the ground.

One-off authoring helper, not part of the build, like struct_art.py (which
draws the rest of the sheet's rows and leaves these cells alone). It
touches only its own cells, so it can be run after base_art.py without
losing the base.

    row 0      col 12: the round (8x8 tile 12, muni.r65 MUNI_TILE_BULLET) -
               a 3x3 cross, cream with orange arms, centred on the tile
    row 14     cols 0-1: the round hitting the ground (8x8 tiles 224 and
               225, fx.r65 FX_HIT) - a spark kicking up dirt, then the dust
               of it; the tile's column 4 is where it struck and its bottom
               rows sit on the dirt (cols 2-3 and row 15's 0-3 are free)

Drawn in the sheet's palette 0 (munitions are not recoloured by side):
c cream (12), o orange (6), r red (11), g light grey (5), b blue-grey (10),
d charcoal (9).

    python3 tools/muni_art.py && make
"""

import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bmp4 import save_bmp4

BMP = 'assets/src/obj.bmp'
K = {'.': 0, 'c': 12, 'o': 6, 'r': 11, 'g': 5, 'b': 10, 'd': 9}

ROUND = [
    "........",
    "........",
    "........",
    "....o...",
    "...oco..",
    "....o...",
    "........",
    "........",
]

HIT_SPARK = [
    "........",
    "........",
    "........",
    "..c.c.c.",
    "...ooo..",
    "..oocoo.",
    ".r.ccc.r",
    "..rooor.",
]

HIT_DUST = [
    "........",
    "........",
    "........",
    "..g...g.",
    "....g...",
    "...gbgg.",
    "..gbggbg",
    "..dbbbd.",
]


def stamp(px, x0, y0, rows):
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            px[x0 + x, y0 + y] = K[ch]


def main():
    im = Image.open(BMP)
    assert im.mode == 'P' and im.size == (128, 128), (im.mode, im.size)
    im = im.copy()
    px = im.load()
    stamp(px, 96, 0, ROUND)                     # tile 12
    for y in range(16):                         # the old 16x16 impact cells
        for x in range(32):
            px[x, 112 + y] = 0
    stamp(px, 0, 112, HIT_SPARK)                # tile 224
    stamp(px, 8, 112, HIT_DUST)                 # tile 225
    save_bmp4(im, BMP)
    print(f"{BMP}: round and ground impact stamped")


if __name__ == '__main__':
    sys.exit(main())

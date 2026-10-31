#!/usr/bin/env python3
"""
Draw the home base into assets/src/obj.bmp, pixel by pixel.

One-off authoring helper, not part of the build, like base_art.py, whose
ComfyUI render it replaces and whose strips it stamps into (STRIPS): a
64x64 box, its lower half the base's 4x2 grid at STRUCT_TILE_BASE, its
upper half the two 8x2 strips BASE_TILE_TOP and BASE_TILE_MID.

The look is assets/reference/basecc.png's, drawn fresh at the base's size:
a flat-roofed hangar with a window band and a slatted door, a tall
checkered control tower at the east end with a glass cab, a radar box and
a flag, a striped mast on the roof. The missile launcher is drawn over it
at BASE_LAUNCHER_DX/_DY (struct.r65, 24/19), so the roof is flat and clear
there.

Colours are the sheet's, plus two of its free entries: 14 a pale teal, the
walls, and 15 a deep one, their shade. The owner's colour is the roof's
trim, the awning and the flag's field - entries 2, 3, 7 and 8, the greens
struct_palettes recolours per side - so the enemy's base wears its red-brown
where the reference has red.

    python3 tools/base_draw.py [--preview OUT.png] && make
"""

import argparse
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base_art import BMP, STRIPS, W, H
from bmp4 import save_bmp4

# The sheet's entries this uses.
CLEAR, INK, OWN_DK, OWN_LT, SKY, GREY, RED = 0, 1, 2, 3, 4, 5, 6
OWN_DKR, OWN_MID, BLACK, SLATE, CREAM, STEEL = 7, 8, 9, 10, 12, 13
TEAL, TEAL_DK = 14, 15
EXTRAS = {TEAL: (136, 200, 176), TEAL_DK: (72, 128, 120)}


def draw():
    art = [[CLEAR] * W for _ in range(H)]

    def rect(x0, y0, x1, y1, c):            # inclusive
        for y in range(max(0, y0), min(H - 1, y1) + 1):
            for x in range(max(0, x0), min(W - 1, x1) + 1):
                art[y][x] = c

    def put(x, y, c):
        if 0 <= x < W and 0 <= y < H:
            art[y][x] = c

    def line(x0, y0, x1, y1, c):
        n = max(abs(x1 - x0), abs(y1 - y0))
        for k in range(n + 1):
            put(round(x0 + (x1 - x0) * k / n), round(y0 + (y1 - y0) * k / n), c)

    # The hangar: x 2-46, its roof on row 35 (the launcher stands on it).
    rect(2, 36, 46, 63, TEAL)
    rect(2, 36, 2, 63, TEAL_DK)                 # its west edge in shade
    rect(3, 60, 46, 63, TEAL_DK)                # the plinth
    rect(1, 34, 47, 34, OWN_LT)                 # the roof's trim, the owner's
    rect(1, 35, 47, 35, OWN_DK)
    rect(2, 36, 46, 36, TEAL_DK)                # under the eaves
    # The window band.
    rect(5, 39, 44, 42, CREAM)
    for x0 in range(6, 44, 8):
        rect(x0, 40, x0 + 6, 41, SKY)
        put(x0, 40, CREAM)
    # The hangar door: grey slats in a dark frame.
    rect(7, 45, 36, 63, INK)
    rect(8, 46, 35, 63, GREY)
    for y in range(48, 63, 3):
        rect(8, y, 35, y, STEEL)
    rect(21, 46, 22, 63, STEEL)                 # where its leaves meet

    # The tower: x 47-60, checkered, from the cab down to the ground.
    for y in range(17, 64):
        for x in range(48, 60):
            art[y][x] = TEAL if ((x - 48) >> 2) ^ ((y - 17) >> 2) & 1 else CREAM
    rect(47, 17, 47, 63, INK)
    rect(60, 17, 60, 63, INK)
    # A stair rising across it, west to east.
    for k in range(10):
        rect(48 + k, 38 - k, 49 + k, 39 - k, TEAL_DK)
        put(48 + k, 37 - k, CREAM)
    # Its door, under an awning in the owner's colour.
    rect(46, 49, 61, 49, OWN_LT)
    rect(46, 50, 61, 50, OWN_DK)
    rect(50, 52, 57, 63, BLACK)
    rect(49, 51, 58, 51, INK)

    # The cab: a wider glass box on the shaft.
    rect(44, 14, 63, 16, GREY)                  # its floor
    rect(44, 16, 63, 16, STEEL)
    rect(45, 7, 62, 13, SLATE)                  # the glass
    for x in range(46, 62, 4):
        rect(x, 8, x + 1, 9, SKY)               # glints
        rect(x + 2, 7, x + 2, 13, CREAM)        # mullions
    rect(45, 7, 45, 13, CREAM)
    rect(62, 7, 62, 13, CREAM)
    rect(43, 5, 63, 6, GREY)                    # its roof
    rect(43, 6, 63, 6, STEEL)
    # The radar box on the roof.
    rect(47, 1, 52, 4, GREY)
    rect(47, 4, 52, 4, STEEL)
    rect(48, 0, 51, 0, CREAM)
    # The flag on its pole, the owner's field with a white bar.
    rect(57, 0, 57, 4, INK)
    rect(58, 0, 63, 3, OWN_DK)
    rect(58, 1, 63, 1, CREAM)
    rect(58, 0, 60, 1, OWN_LT)                  # its canton

    # The mast on the hangar roof, west of the launcher: red and white.
    for y in range(16, 34):
        put(12, y, RED if (y >> 1) & 1 else CREAM)
    put(12, 15, RED)
    line(12, 19, 7, 33, STEEL)                  # its guys
    line(12, 19, 17, 33, STEEL)

    return art


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview', help='write a 4x PNG over the sky instead of stamping')
    args = ap.parse_args()

    sheet = Image.open(BMP)
    flat = sheet.getpalette()[:48]
    pal = [tuple(flat[i * 3:i * 3 + 3]) for i in range(16)]
    for i, rgb in EXTRAS.items():
        pal[i] = rgb
    art = draw()

    if args.preview:
        im = Image.new('RGB', (W, H), (61, 154, 236))
        for y in range(H):
            for x in range(W):
                if art[y][x]:
                    im.putpixel((x, y), pal[art[y][x]])
        im.resize((W * 4, H * 4), Image.NEAREST).save(args.preview)
        return

    out = sheet.copy()
    opx = out.load()
    for y in range(H):
        sx, sy = STRIPS[y >> 4]
        for x in range(W):
            opx[sx + x, sy + (y & 15)] = art[y][x]
    out.putpalette([c for rgb in pal for c in rgb])
    save_bmp4(out, BMP)
    print(f'{BMP}: base drawn, entries 14-15 {EXTRAS[TEAL]} {EXTRAS[TEAL_DK]}')


if __name__ == '__main__':
    main()

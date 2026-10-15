#!/usr/bin/env python3
"""
Draw the order menu's unit icons, assets/src/icons.tilemap.bmp.

One-off authoring helper, not part of the build: it writes the bitmap the
Makefile's tilemap rule converts (2bpp, de-duplicated), so the BMP stays the
source of truth and an ordinary `make` picks an edit up. Programmer art,
derived from the units' own sprites so an icon reads as the unit it buys.

The icons are BG3 tiles, not sprites: the order menu (hud.r65) is a column
of them down the left edge of the HUD layer. Six 32x32 icons, stacked in
ring order (order.r65 order_stats) - van, launcher, tank, infantry,
engineer, heli - so the sheet is 32x192 and icon k is map rows 4k..4k+3.
Each is a navy square with a 1 px transparent margin (the sky shows
between them) and the unit in two tones:

    0  transparent      1  navy, the HUD's panel
    2  dark: outline, tracks, wheels, windows
    3  light: the body

A vehicle is its 24 px sprite stretched to 28 px wide, a man is doubled,
the airframe is its level frame as it is, less the tail rotor's last
column; each is centred in its panel. Glass is dark, so a van has windows. The engineer shares the
infantryman's sprite, so his icon adds a shovel.

The palette is hud.r65's ICON_PAL (normal) and ICON_PAL_SEL (the selected
icon: a brighter panel); this file's four colours are the normal one.

    python3 tools/icon_art.py && make
"""

import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bmp4 import save_bmp4

OUT = 'assets/src/icons.tilemap.bmp'
OBJ = 'assets/src/obj.bmp'
HELI = 'assets/src/heli.bmp'
ICON = 32
INNER = 30                          # inside the transparent margin

PALETTE = [
    (0, 0, 0),          # 0 transparent
    (33, 41, 66),       # 1 navy, the HUD's panel
    (66, 90, 49),       # 2 dark
    (165, 198, 140),    # 3 light
]
NAVY, DARK, LIGHT = 1, 2, 3
DARK_BELOW = 60                     # source luminance under this is DARK
GLASS = 4                           # obj.bmp's and heli.bmp's canopy blue: DARK too


def frame(sheet, tile, w, h=16):
    x0, y0 = (tile % 16) * 8, (tile // 16) * 8
    return sheet.crop((x0, y0, x0 + w, y0 + h))


def tones(im):
    """The frame in the icon's two tones, cropped to what is drawn."""
    pal = im.getpalette()
    src = im.load()
    out = Image.new('P', im.size, 0)
    px = out.load()
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            i = src[x, y]
            if i == 0:
                continue
            r, g, b = pal[i * 3:i * 3 + 3]
            dark = i == GLASS or 0.3 * r + 0.59 * g + 0.11 * b < DARK_BELOW
            px[x, y] = DARK if dark else LIGHT
    return out.crop(out.getbbox())


def scaled(im, w=None, k=None):
    if k:
        return im.resize((im.size[0] * k, im.size[1] * k), Image.NEAREST)
    h = max(1, round(im.size[1] * w / im.size[0]))
    return im.resize((w, h), Image.NEAREST)


def icon(sheet, k, art, shovel=False):
    """Icon *k*: the panel, then *art* centred."""
    y0 = k * ICON
    for y in range(1, ICON - 1):
        for x in range(1, ICON - 1):
            sheet.putpixel((x, y0 + y), NAVY)
    w, h = art.size
    ax = (ICON - w) // 2
    ay = y0 + (ICON - h) // 2
    px = art.load()
    for y in range(h):
        for x in range(w):
            if px[x, y]:
                sheet.putpixel((ax + x, ay + y), px[x, y])
    if shovel:
        # Shouldered: a shaft from the hand up past the head, the blade up.
        bx = ax + w + 1
        for y in range(ay + 6, ay + 22):
            sheet.putpixel((bx, y), LIGHT)
        for y in range(ay + 1, ay + 6):
            for x in range(bx - 1, bx + 2):
                sheet.putpixel((x, y), LIGHT)


def main():
    obj = Image.open(OBJ)
    heli = Image.open(HELI)
    sheet = Image.new('P', (ICON, ICON * 6), 0)
    sheet.putpalette([c for rgb in PALETTE for c in rgb] + [0] * (48 - 12))
    vehicle = lambda t: scaled(tones(frame(obj, t, 24)), w=28)
    man = scaled(tones(frame(obj, 68, 16)), k=2)
    icon(sheet, 0, vehicle(42))                                    # van
    icon(sheet, 1, vehicle(64))                                    # launcher
    icon(sheet, 2, vehicle(38))                                    # tank
    icon(sheet, 3, man)                                            # infantry
    icon(sheet, 4, man, shovel=True)                               # engineer
    airframe = tones(heli.crop((32, 0, 64, 16)))
    icon(sheet, 5, airframe.crop((airframe.size[0] - INNER, 0) + airframe.size))   # heli
    save_bmp4(sheet, OUT)
    print(f"{OUT} is {sheet.size[0]}x{sheet.size[1]}")


if __name__ == '__main__':
    main()

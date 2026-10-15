#!/usr/bin/env python3
"""
Draw the alert avatar's sprite sheet, assets/src/avatar.bmp.

One-off authoring helper, not part of the build: it writes the bitmap the
Makefile's bmp2chr rule converts, so the BMP stays the source of truth and
an ordinary `make` picks an edit up. Programmer art - a placeholder until
the portrait is drawn properly; what matters is the layout, which
alert.r65's ALERT_TILE0 and alert_draw depend on.

The sheet loads into the second OBJ name block straight after the
explosions' (alert.r65 ALERT_TILE0), with its own OBJ palette (6), and
must be 16 tiles (128 px) wide like every sprite sheet: the hardware
addresses a 16x16 sprite as tiles T, T+1, T+16, T+17. Two 32x32 frames,
each drawn as four 16x16 sprites:

    cols 0-3   mouth shut   (tiles 0, 2, 32, 34)
    cols 4-7   mouth open   (tiles 4, 6, 36, 38)

The portrait is the radio operator: helmet, goggles, headset and mic, in a
navy frame matching the HUD's so it reads as part of the alert box.

    python3 tools/avatar_art.py && make
"""

import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bmp4 import save_bmp4

BMP = 'assets/src/avatar.bmp'
SHEET_W, SHEET_H = 128, 32

PALETTE = [
    (0, 0, 0),          # 0 transparent
    (16, 16, 24),       # 1 outline
    (33, 41, 66),       # 2 navy, the HUD's
    (165, 198, 231),    # 3 frame, the HUD's light blue
    (74, 90, 49),       # 4 helmet shadow
    (115, 132, 74),     # 5 helmet
    (189, 123, 90),     # 6 skin shadow
    (231, 173, 132),    # 7 skin
    (40, 48, 56),       # 8 goggle lens
    (200, 230, 255),    # 9 glint
    (140, 40, 40),      # 10 mouth
    (140, 148, 156),    # 11 headset grey
    (240, 240, 240),    # 12 teeth
]

OUTLINE, NAVY, FRAME = 1, 2, 3
HELMET_D, HELMET = 4, 5
SKIN_D, SKIN = 6, 7
LENS, GLINT, MOUTH, GREY, TEETH = 8, 9, 10, 11, 12


def portrait(d, ox, talking):
    """One 32x32 frame with its top-left at (ox, 0)."""
    d.rectangle((ox, 0, ox + 31, 31), fill=NAVY)
    # Shoulders, in the helmet's olive, running off the frame's foot.
    d.ellipse((ox + 3, 24, ox + 28, 42), fill=HELMET, outline=OUTLINE)
    d.rectangle((ox + 13, 20, ox + 18, 25), fill=SKIN_D)          # neck
    d.ellipse((ox + 9, 8, ox + 22, 24), fill=SKIN, outline=OUTLINE)
    # The helmet's dome and brim over the top of the face.
    d.chord((ox + 7, 2, ox + 24, 22), 180, 360, fill=HELMET, outline=OUTLINE)
    d.line((ox + 7, 12, ox + 24, 12), fill=HELMET_D)
    # Goggles pushed up on the helmet.
    d.rectangle((ox + 10, 7, ox + 21, 10), fill=OUTLINE)
    d.rectangle((ox + 11, 8, ox + 14, 9), fill=LENS)
    d.rectangle((ox + 17, 8, ox + 20, 9), fill=LENS)
    d.point((ox + 12, 8), fill=GLINT)
    d.point((ox + 18, 8), fill=GLINT)
    # Eyes and nose.
    d.point((ox + 13, 15), fill=OUTLINE)
    d.point((ox + 18, 15), fill=OUTLINE)
    d.rectangle((ox + 15, 16, ox + 16, 17), fill=SKIN_D)
    # Headset: the ear cup and the mic boom round to the mouth.
    d.rectangle((ox + 7, 13, ox + 9, 18), fill=GREY, outline=OUTLINE)
    d.line((ox + 9, 18, ox + 12, 21), fill=GREY)
    d.point((ox + 12, 21), fill=OUTLINE)
    if talking:
        d.rectangle((ox + 14, 19, ox + 17, 21), fill=MOUTH)
        d.line((ox + 14, 19, ox + 17, 19), fill=TEETH)
    else:
        d.line((ox + 14, 20, ox + 17, 20), fill=MOUTH)
    # The frame last, over whatever ran off the edge.
    d.rectangle((ox, 0, ox + 31, 31), outline=FRAME)


def main():
    im = Image.new('P', (SHEET_W, SHEET_H), 0)
    flat = [c for rgb in PALETTE for c in rgb]
    im.putpalette(flat + [0] * (48 - len(flat)))
    d = ImageDraw.Draw(im)
    portrait(d, 0, False)
    portrait(d, 32, True)
    save_bmp4(im, BMP)
    print(BMP)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Paint the alert avatar's sprite sheet, assets/src/avatar.bmp, from a
ComfyUI render.

One-off authoring helper, not part of the build: it writes the bitmap the
Makefile's bmp2chr rule converts, so the BMP stays the source of truth and
an ordinary `make` picks an edit up. What the code depends on is the
layout - alert.r65's ALERT_TILE0 and alert_draw.

The sheet loads into the second OBJ name block straight after the
explosions' (alert.r65 ALERT_TILE0), with its own OBJ palette (6), and
must be 16 tiles (128 px) wide like every sprite sheet: the hardware
addresses a 16x16 sprite as tiles T, T+1, T+16, T+17. Two 32x32 frames,
each drawn as four 16x16 sprites:

    cols 0-3   mouth shut   (tiles 0, 2, 32, 34)
    cols 4-7   mouth open   (tiles 4, 6, 36, 38)

The portrait is the radio operator, Rachel (assets/reference/rachel.png):
a navy beret with a red and gold badge, short dark hair, an olive headset
and a black mic, inside the HUD's light-blue frame so it reads as part of
the alert box - on a slate of its own, not the HUD's navy, which her beret
and hair vanished into. The tool keys the render's white background out
from the border, crops it (--box), box-filters it to the 30x30 inside the
frame, maps every pixel to PALETTE by nearest colour and drops pixels left
alone in a field of one other colour (not KEEP's). At 30 px the eyes
average to mud - lash, iris and white in one pixel - so it paints them
(--eyes, a lash line over iris and glint) and the two mouths (--mouth),
so the frames differ only at the mouth.

    python3 tools/avatar_art.py RENDER.png [--box L,T,R,B] [--eyes X,Y,X,Y] [--mouth X,Y] && make

The current portrait is ComfyUI render sfr_rachel_s12_00001_ - the saved
pixel_art_sdxl_ref workflow (pixelArtDiffusionXL_pixelWorld, 25 steps,
start_at_step 12, cfg 8, seed 2026) over rachel.png's head and shoulders
(its rows 40-1040, centred on white 1000 px square, scaled to 1024x1024) -
at the defaults. Prompt: "pixel art portrait, 16-bit snes game character
portrait, anime woman soldier, short dark brown hair, brown eyes, slight
smile, navy blue beret with a red and gold badge, olive green headset with
black microphone, light blue grey collared shirt, camouflage vest, plain
white background, bold outlines, crisp pixels, limited palette, retro";
negative: "text, letters, watermark, signature, blurry, photo, 3d render,
frame, border, extra people, hands".
"""

import argparse
import os
import sys
from collections import deque

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bmp4 import save_bmp4

BMP = 'assets/src/avatar.bmp'
SHEET_W, SHEET_H = 128, 32
N = 30                                  # the portrait inside the frame

PALETTE = [
    (0, 0, 0),          # 0 transparent
    (16, 14, 24),       # 1 outline, lashes, the mic
    (96, 112, 140),     # 2 the background, a slate
    (165, 198, 231),    # 3 frame, the HUD's light blue
    (26, 40, 104),      # 4 beret
    (56, 78, 160),      # 5 beret light
    (40, 22, 18),       # 6 hair dark, pupils
    (100, 60, 40),      # 7 hair light
    (226, 158, 130),    # 8 skin shadow
    (250, 214, 186),    # 9 skin
    (40, 58, 36),       # 10 headset, camo dark
    (88, 110, 66),      # 11 headset light, camo
    (240, 240, 240),    # 12 glints, collar
    (200, 72, 56),      # 13 badge red, mouth
    (228, 180, 60),     # 14 badge gold
    (168, 112, 56),     # 15 irises, amber
]
OUTLINE, BACK, FRAME, PUPIL, GLINT, MOUTH, IRIS = 1, 2, 3, 6, 12, 13, 15
KEEP = {OUTLINE, PUPIL, GLINT, MOUTH, 14, IRIS}     # never cleaned away


def keyed(im):
    """The render on the HUD's navy: its near-white background, as far as
    it reaches in from the border, replaced."""
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    q = deque([(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)])
    while q:
        x, y = q.popleft()
        if not (0 <= x < w and 0 <= y < h) or seen[y * w + x]:
            continue
        p = px[x, y]
        if min(p) <= 200 or max(p) - min(p) >= 40:
            continue
        seen[y * w + x] = 1
        q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    mask = Image.frombytes('L', (w, h), bytes(255 if s else 0 for s in seen))
    out = im.copy()
    out.paste(Image.new('RGB', (w, h), PALETTE[BACK]), (0, 0), mask)
    return out


def nearest(rgb):
    r, g, b = rgb
    return min((i for i in range(1, 16) if i != FRAME),
               key=lambda i: (PALETTE[i][0] - r) ** 2 * 3 + (PALETTE[i][1] - g) ** 2 * 4 + (PALETTE[i][2] - b) ** 2 * 2)


def face(render, box):
    """The 30x30 portrait as palette indexes, rows of columns."""
    small = keyed(render).crop(box).resize((N, N), Image.BOX)
    a = [[nearest(small.getpixel((x, y))) for x in range(N)] for y in range(N)]
    b = [row[:] for row in a]
    for y in range(1, N - 1):
        for x in range(1, N - 1):
            nb = {a[y][x + 1], a[y][x - 1], a[y + 1][x], a[y - 1][x]}
            if a[y][x] not in KEEP and len(nb) == 1 and a[y][x] not in nb:
                b[y][x] = nb.pop()
    return b


def eye(f, x, y):
    """One eye, its top-left at (x, y): a lash line, then iris, pupil and a
    glint."""
    for yy in (y + 1, y + 2):               # the averaging's olive round it is skin
        for xx in range(x - 1, x + 4):
            if f[yy][xx] in (10, 11):
                f[yy][xx] = 9
    f[y][x] = f[y][x + 1] = f[y][x + 2] = OUTLINE
    f[y + 1][x], f[y + 1][x + 1], f[y + 1][x + 2] = IRIS, PUPIL, GLINT


def mouth(f, mx, my, talking):
    """The mouth, its left half's column at mx: a short line shut, a small
    oval open."""
    if talking:
        f[my][mx] = f[my][mx + 1] = OUTLINE
        f[my + 1][mx - 1] = f[my + 1][mx + 2] = OUTLINE
        f[my + 1][mx] = f[my + 1][mx + 1] = MOUTH
        f[my + 2][mx] = f[my + 2][mx + 1] = OUTLINE
    else:
        f[my][mx] = f[my][mx + 1] = MOUTH


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('render')
    ap.add_argument('--box', default='40,20,984,964', help='crop of the render, L,T,R,B')
    ap.add_argument('--eyes', default='10,13,17,13', help='each eye\'s top-left, in the 30x30: X,Y,X,Y')
    ap.add_argument('--mouth', default='14,23', help="the mouth's left column and top row, in the 30x30")
    args = ap.parse_args()
    box = tuple(int(v) for v in args.box.split(','))
    mx, my = (int(v) for v in args.mouth.split(','))

    base = face(Image.open(args.render).convert('RGB'), box)
    ex = [int(v) for v in args.eyes.split(',')]
    for i in range(0, len(ex), 2):
        eye(base, ex[i], ex[i + 1])
    im = Image.new('P', (SHEET_W, SHEET_H), 0)
    im.putpalette([c for rgb in PALETTE for c in rgb])
    for n, talking in enumerate((False, True)):
        f = [row[:] for row in base]
        mouth(f, mx, my, talking)
        ox = n * 32
        for y in range(32):
            for x in range(32):
                edge = x in (0, 31) or y in (0, 31)
                im.putpixel((ox + x, y), FRAME if edge else f[y - 1][x - 1])
    save_bmp4(im, BMP)
    print(BMP)


if __name__ == '__main__':
    main()

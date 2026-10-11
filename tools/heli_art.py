#!/usr/bin/env python3
"""
Draw the airframe's sprite sheet, assets/src/heli.bmp.

One-off authoring helper, not part of the build: it writes the bitmap that
the Makefile's bmp2chr rule converts, so the BMP stays the source of truth
and an ordinary `make` picks an edit up. Programmer art until phase 12;
what matters is the cell layout, which heli.r65's HELI_TILE_* constants
depend on.

The airframe has a sheet of its own so that its art and its colours can be
redrawn without touching obj.bmp - and so that the two airframes can be
recoloured independently of the units and the buildings, which share the
other sheet's palette. It is loaded into the *second* OBJ name block, so
its tiles are 256 + n (heli.r65 HELI_PAGE), and it carries its own OBJ
palette (HELI_PAL_SLOT), whose greens heli_palettes() turns red-brown for
the enemy's airframe exactly as struct_palettes does for the other sheet.

The sheet must be 16 tiles (128 px) wide whatever it holds: the hardware
addresses a 16x16 sprite as tiles T, T+1, T+16, T+17, so a narrower sheet
would put a cell's lower half in the wrong place. Two rows of cells:

    row 0   the flight frames (32x16 each): nose down at cols 0-3, level
            at cols 4-7, nose up at cols 8-11  (tiles 0, 4, 8)
    row 2   the turn frames: three-quarter view at cols 0-3, head-on at
            cols 4-7, slight turn at cols 8-11 (tiles 32, 36, 40)

and the wreck in each row's last four columns: crashing (falling after a
loss) at row 0 cols 12-15, crashed (down on the ground) at row 2 cols
12-15 (tiles 12, 44). The sheet is drawn art now (ec7833d), which this
tool would overwrite; the wreck frames were added to it by hand.

Palette indices: 1 black, 2 dark green, 3 green, 4 canopy blue, 5 light
grey, 6 orange. 0 is transparent. The order matches obj.bmp's first seven
entries, so the same two greens carry the owner's colour.

    python3 tools/heli_art.py && make
"""

import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bmp4 import save_bmp4

BMP = 'assets/src/heli.bmp'
SHEET_W, SHEET_H = 128, 32

# The airframe's own palette: what it uses out of the shared sheet's, and
# nothing else. Index 0 is transparent and never drawn.
PALETTE = [
    (0, 0, 0),          # 0 transparent
    (16, 24, 32),       # 1 outline
    (82, 106, 74),      # 2 dark green   - the owner's colour ...
    (131, 164, 115),    # 3 green        - ... and its highlight
    (115, 180, 230),    # 4 canopy
    (172, 180, 197),    # 5 rotor grey
    (213, 98, 65),      # 6 nose orange
]

K = {'.': 0, 'k': 1, 'D': 2, 'G': 3, 'b': 4, 'w': 5, 'o': 6}


def stamp(px, x0, y0, rows):
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            px[x0 + x, y0 + y] = K[ch]


# The flight frames: level, and the same airframe pitched nose-down and
# nose-up. Facing left is the hflip bit, so there is no mirrored art -
# which is why the frames are named for the subject and not the screen.

NOSE_DOWN = [
    "..wwwwwwwwwwwwwwwwwwwwwwwwwwww..",
    "...............kk...............",
    "ww.............kk...............",
    "ww..............................",
    "ww..........kkkkkkkkkkkk........",
    "wwooooookkkkGGGGGGGGGGGDkkkkkkkk",
    "wwooooooDDDDGGGGGGGGGGGDDbbbbbbD",
    "wwooooookkkkDDDDDDDDDDDDDbbbbbbD",
    "ww..........DDDDDDDDDDDDDbbbbbbD",
    "ww..........DDDDDDDDDDDDDbbbbbbD",
    "ww..........DDDDDDDDDDDDDDDDDDDD",
    "ww..........kkkkkkkkkkkkDDDDDDDD",
    "...............k........kkkkkkkk",
    ".............kkkkkkkkkkkkkkkk...",
    "................................",
    "................................",
]

LEVEL = [
    "..wwwwwwwwwwwwwwwwwwwwwwwwwwww..",
    "...............kk...............",
    "ww.............kk...............",
    "ww..............................",
    "ww..........kkkkkkkkkkkkkkkkkkkk",
    "wwoooooo....GGGGGGGGGGGDDDDDDDDD",
    "wwooooookkkkGGGGGGGGGGGDDbbbbbbD",
    "wwooooooDDDDDDDDDDDDDDDDDbbbbbbD",
    "ww......kkkkDDDDDDDDDDDDDbbbbbbD",
    "ww..........DDDDDDDDDDDDDbbbbbbD",
    "ww..........DDDDDDDDDDDDDDDDDDDD",
    "ww..........kkkkkkkkkkkkkkkkkkkk",
    "...............k..........k.....",
    ".............kkkkkkkkkkkkkkkk...",
    "................................",
    "................................",
]

NOSE_UP = [
    "..wwwwwwwwwwwwwwwwwwwwwwwwwwww..",
    "...............kk...............",
    "ww.............kk...............",
    "ww......................kkkkkkkk",
    "ww..........kkkkkkkkkkkkDDDDDDDD",
    "wwoooooo....GGGGGGGGGGGDDDDDDDDD",
    "wwoooooo....GGGGGGGGGGGDDbbbbbbD",
    "wwooooookkkkDDDDDDDDDDDDDbbbbbbD",
    "ww......DDDDDDDDDDDDDDDDDbbbbbbD",
    "ww......kkkkDDDDDDDDDDDDDbbbbbbD",
    "ww..........DDDDDDDDDDDDkkkkkkkk",
    "ww..........kkkkkkkkkkkk........",
    "...............k..........k.....",
    ".............kkkkkkkkkkkkkkkk...",
    "................................",
    "................................",
]


# The airframe mid-turn: the level frame foreshortened. Three-quarter
# view (nose still right, tail swinging toward the viewer), then head-on
# (tail hidden, canopy centred). Same palette as the flight frames.
TURN_34 = [
    "....wwwwwwwwwwwwwwwwwwwwwwww....",
    "...............kk...............",
    "...............kk...............",
    "................................",
    "........kkkkkkkkkkkkkkkkkkk.....",
    "....oooooGGGGGGGGGGDDDDDDDDD....",
    "....ooooooGGGGGGGGGDDbbbbbbD....",
    "....oooooDDDDDDDDDDDDbbbbbbD....",
    "....kkkkkDDDDDDDDDDDDbbbbbbD....",
    "........DDDDDDDDDDDDDDbbbbD.....",
    "........DDDDDDDDDDDDDDDDDDD.....",
    "........kkkkkkkkkkkkkkkkkkk.....",
    "..............k.......k.........",
    "............kkkkkkkkkkkkk.......",
    "................................",
    "................................",
]
# Just off the level frame: the tail foreshortened a little, the body a
# few pixels narrower, the canopy starting to face the viewer.
TURN_SLIGHT = [
    "..wwwwwwwwwwwwwwwwwwwwwwwwwwww..",
    "...............kk...............",
    "...............kk...............",
    "................................",
    "..........kkkkkkkkkkkkkkkkkkkk..",
    "..ooooooo.GGGGGGGGGGGDDDDDDDDDD.",
    "..oooooookkGGGGGGGGGGDDbbbbbbbD.",
    "..ooooooDDDDDDDDDDDDDDDbbbbbbbD.",
    "..kkkkkkkkDDDDDDDDDDDDDbbbbbbbD.",
    "..........DDDDDDDDDDDDDDbbbbbD..",
    "..........DDDDDDDDDDDDDDDDDDDD..",
    "..........kkkkkkkkkkkkkkkkkkkk..",
    "...............k.........k......",
    ".............kkkkkkkkkkkkkkk....",
    "................................",
    "................................",
]

TURN_HEAD = [
    "..............wwww..............",
    "...............kk...............",
    "...............kk...............",
    "................................",
    "............kkkkkkkk............",
    "...........kGGGGGGGGk...........",
    "...........kGbbbbbbGk...........",
    "...........kDbbbbbbDk...........",
    "...........kDbbbbbbDk...........",
    "...........kDDbbbbDDk...........",
    "...........kDDDDDDDDk...........",
    "............kkkkkkkk............",
    ".............k....k.............",
    "...........kkkkkkkkkkk..........",
    "................................",
    "................................",
]


def main():
    im = Image.new('P', (SHEET_W, SHEET_H), 0)
    pal = []
    for c in PALETTE:
        pal += list(c)
    im.putpalette(pal + [0, 0, 0] * (16 - len(PALETTE)))
    px = im.load()

    stamp(px, 0, 0, NOSE_DOWN)                  # tile 0
    stamp(px, 32, 0, LEVEL)                     # tile 4
    stamp(px, 64, 0, NOSE_UP)                   # tile 8
    stamp(px, 0, 16, TURN_34)                   # tile 32
    stamp(px, 32, 16, TURN_HEAD)                # tile 36
    stamp(px, 64, 16, TURN_SLIGHT)              # tile 40
    save_bmp4(im, BMP)
    print(f"airframe drawn; {BMP} is {im.size[0]}x{im.size[1]}")


if __name__ == '__main__':
    main()

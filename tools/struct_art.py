#!/usr/bin/env python3
"""
Stamp the structure sprites into assets/src/obj.bmp.

One-off authoring helper, not part of the build: it edits the bitmap that
the Makefile's bmp2chr rule converts, so the BMP stays the source of truth
and an ordinary `make` picks the edit up. Programmer
art until phase 12; what matters is the cell layout, which struct.r65's
STRUCT_TILE_* constants depend on.

The sheet is 16 tiles wide; a 16x16 OBJ cell at tile row r, column c is
tile r*16 + c, and a cell's right neighbour is +2, its lower neighbour +32.
Rows 0-5 hold the munitions, the decks and the units; the airframe has a
sheet of its own (tools/heli_art.py), and the cells it used to occupy -
rows 0-1 and 14-15, columns 0-11 - are cleared here so the two cannot
drift apart, all but rows 14-15's columns 0-3, which are muni_art.py's
(the round's ground impact, tiles 224-225; it draws the round, tile 12, too).
Columns 4-11 of both are the 64x64 base's upper half now, which
tools/base_art.py stamps there after this. This adds rows 6-13:

    row  6-7   turret (16x16) at col 0    balloon (16x16) at col 2
               chain (8x8) at col 4       bunker (32x24 in 32x32) at cols 6-9
               bank   (32x24 in 32x32) at cols 10-13
    row 10-13  super bunker (40x24 in 48x32) at cols 0-5
               base's lower half (64x32) at cols 6-13 - now
               tools/base_art.py's, from a ComfyUI render, with its upper
               half in rows 0-1 and 14-15: re-run it after this, or lose it
    row 14-15  cols 12-15: the base's missile launcher, loaded at tile 236
               and empty at 238 (16x16 each), drawn on the base's roof
    row 1      cols 12-14: the missile heading E, NE, N (8x8 tiles 28-30)
               col 15: the radar's camera bracket (8x8 tile 31, radar.r65
               RADAR_BRACKET_TILE) - the window's edges, drawn as a sprite
               over the radar row
    row  4-5   col 6: the infantryman firing (tile 70, unit.r65
               UNIT_TILE_INFANTRY_FIRE) - the standing man with the rifle
               levelled and a flash at the muzzle
               col 8: the parachute canopy (tile 72, para.r65 PARA_TILE):
               drawn over the standing man's cell, lines meeting at his
               shoulders in the cell below
               col 10: the man mid-stride (tile 74, unit.r65
               UNIT_TILE_MAN_WALK) - the walk's second frame, the
               standing man being the first
               col 12: the man down (tile 76, unit.r65
               UNIT_TILE_MAN_DOWN) - lying where he fell, shown a
               moment by fx.r65's FX_MAN

Palette indices: 1 black, 2 dark green, 3 green, 4 light blue, 5 light
grey, 6 orange, 7 darker green, 8 mid green, 9 charcoal, 10 blue-grey,
11 red. Structures are concrete (5/9/1) with green trim so the enemy
palette swap (greens -> red-browns) marks the owner.

    python3 tools/struct_art.py && make
"""

import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bmp4 import save_bmp4

BMP = 'assets/src/obj.bmp'
SHEET_W, SHEET_H = 128, 128

K = {'.': 0, 'k': 1, 'D': 2, 'G': 3, 'b': 4, 'w': 5, 'o': 6, 'd': 7,
     'g': 8, 'c': 9, 's': 10, 'r': 11}


def clear(px, x0, y0, w, h):
    for y in range(h):
        for x in range(w):
            px[x0 + x, y0 + y] = 0


def stamp(px, x0, y0, rows):
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            px[x0 + x, y0 + y] = K[ch]


TURRET = [
    "................",
    "................",
    "......kkkk......",
    ".....kwwwwk.....",
    "....kwwGGwwk....",
    "kkkkkwGGGGwkkkkk",
    "kwwwwwGGGGwwwwwk",
    ".kwwwwwGGwwwwwk.",
    "..kwwwwwwwwwwk..",
    "..kccccccccccck.",
    ".kcccccccccccck.",
    ".kcccccccccccck.",
    "kccccccccccccccck",
    "kkkkkkkkkkkkkkkk",
    "................",
    "................",
][:16]
TURRET = [r[:16].ljust(16, '.') for r in TURRET]

BALLOON = [
    "....kkkkkkkk....",
    "..kkwwwwwwwwkk..",
    ".kwwwwwwwwwwwwk.",
    "kwwwwwwwwwwwwwwk",
    "kwwwwGGwwwwwwwwk",
    "kwwwGGGGwwwwwwwk",
    "kwwwwGGwwwwwwwwk",
    "kwwwwwwwwwwwwwwk",
    ".kwwwwwwwwwwwwk.",
    "..kkwwwwwwwwkk..",
    "....kkkkkkkk....",
    ".......kk.......",
    ".......kk.......",
    "......kkkk......",
    "......kcck......",
    "......kkkk......",
]

CHAIN = [
    "...kk...",
    "..k..k..",
    "..k..k..",
    "...kk...",
    "...kk...",
    "..k..k..",
    "..k..k..",
    "...kk...",
]


def box(w, h, top='k', body='w', shade='c'):
    """A concrete block *w* x *h* with an outline and a shaded right/bottom."""
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            edge = x == 0 or y == 0 or x == w - 1 or y == h - 1
            row.append('k' if edge else (shade if (x >= w - 3 or y >= h - 3) else body))
        rows.append(''.join(row))
    return rows


def bunker():
    """32x24 in a 32x32 cell pair: a slab with a slit and a green door."""
    rows = box(32, 24)
    for y in range(8, 12):
        rows[y] = rows[y][:6] + 'kkkkkkkkkkkkkkkkkkkk' + rows[y][26:]
    for y in range(14, 23):
        rows[y] = rows[y][:12] + 'GGGGGGGG' + rows[y][20:]
    rows[9] = rows[9][:8] + 'cccccccccccccccc' + rows[9][24:]
    return [''] * 8 + rows                      # 8 empty rows above


def bank():
    """32x24: the bunker's slab with a barred front and a green roof line."""
    rows = box(32, 24)
    rows[1] = 'k' + 'G' * 30 + 'k'
    rows[2] = 'k' + 'G' * 30 + 'k'
    for y in range(8, 22):
        rows[y] = ''.join('k' if (x % 4 == 2 and 4 <= x <= 27) else ch
                          for x, ch in enumerate(rows[y]))
    return [''] * 8 + rows


def super_bunker():
    """40x24 in a 48x32 box: two slits and a wide green door."""
    rows = box(40, 24)
    for y in (7, 8, 9):
        rows[y] = rows[y][:4] + 'kkkkkkkkkkkk' + rows[y][16:24] + 'kkkkkkkkkkkk' + rows[y][36:]
    for y in range(13, 23):
        rows[y] = rows[y][:14] + 'GGGGGGGGGGGG' + rows[y][26:]
    rows = [r + '.' * 8 for r in rows]          # pad to 48 wide
    return [''] * 8 + rows


def base():
    """64x32: a long low hall with a green tower."""
    rows = box(64, 32)
    for y in range(1, 12):
        rows[y] = rows[y][:24] + 'kGGGGGGGGGGGGGGk' + rows[y][40:]
    for y in range(12, 31):
        rows[y] = ''.join('k' if (x % 8 == 4 and 4 <= x <= 59 and 18 <= y <= 30) else ch
                          for x, ch in enumerate(rows[y]))
    return rows


# The missile, 8x8, heading east, north-east and north; the sprite's
# flip bits turn those into the other five headings (muni.r65).
MISSILE_E = [
    "........",
    "........",
    "........",
    "c.....k.",
    "ccccccko",
    "c.....k.",
    "........",
    "........",
]
MISSILE_NE = [
    ".......k",
    "......ko",
    ".....ck.",
    "....c...",
    "...c....",
    "..c.....",
    ".c......",
    "........",
]
MISSILE_N = [
    "....k...",
    "...kok..",
    "....c...",
    "....c...",
    "....c...",
    "....c...",
    "...ccc..",
    "........",
]


# The infantryman of tile 68 with his rifle up: same body in columns 2-7,
# so the facing-left mirror lands where his standing frame does, the
# barrel out to column 11 and the flash past it.
INFANTRY_FIRE = [
    "................",
    "................",
    "...kkk..........",
    "...GGG..........",
    "...GGG..........",
    "..kkkkk.........",
    "..ddddkkkkkkoo..",
    "..ddddkk....oo..",
    "..ddddd.........",
    "..ddddd.........",
    "..ddddd.........",
    "..dd.dd.........",
    "..dd.dd.........",
    "..dd.dd.........",
    "..kk.kk.........",
    "................",
]


# The canopy, one cell, sitting directly above the man's cell (tile 68):
# a domed chute with the shroud lines converging at columns 7-8, row 14.
# The man's head is columns 3-5 from row 2, so para.r65 draws this cell
# 3 px toward him and 12 px up (PARA_CHUTE_DX/DY) rather than straight
# above - keep those in step if either drawing moves.
PARACHUTE = [
    "......wwww......",
    "....wwwwwwww....",
    "...wwwwwwwwww...",
    "..wwwwwwwwwwww..",
    "..wcwwwwcwwwwcw.",
    "..wwwwwwwwwwww..",
    "..kwwwwwwwwwwk..",
    "...kk......kk...",
    "....k......k....",
    "....k.....k.....",
    ".....k....k.....",
    ".....k...k......",
    "......k..k......",
    "......k.k.......",
    ".......kk.......",
    "................",
]


# The base's missile launcher, one cell standing on the tower: a cradle
# with two rails, loaded and empty (struct.r65 STRUCT_TILE_LAUNCHER_*).
# The missile stands between the rails nose up, the way it leaves; the
# cradle carries the owner's greens so the palette swap marks it too.
LAUNCHER_LOADED = [
    "................",
    "................",
    "................",
    ".......kk.......",
    "......krrk......",
    ".....ckrrkc.....",
    ".....ckwwkc.....",
    ".....ckwwkc.....",
    ".....ckwwkc.....",
    ".....ckwwkc.....",
    "....kcksskck....",
    "....kkkookkk....",
    "..kkkkkkkkkkkk..",
    "..kGGGGGGGGGGk..",
    "..kDDDDDDDDDDk..",
    "..kkkkkkkkkkkk..",
]
LAUNCHER_EMPTY = [
    "................",
    "................",
    "................",
    "................",
    "................",
    ".....c....c.....",
    ".....c....c.....",
    ".....c....c.....",
    ".....c....c.....",
    ".....c....c.....",
    "....kc....ck....",
    "....kk....kk....",
    "..kkkkkkkkkkkk..",
    "..kGGGGGGGGGGk..",
    "..kDDDDDDDDDDk..",
    "..kkkkkkkkkkkk..",
]


# The man of tile 68 mid-stride, legs passing: the second frame of the
# walk, the standing frame the first. Body unchanged in columns 2-7 so the
# facing-left mirror (UNIT_MIRROR_MAN) holds for both frames.
INFANTRY_WALK = [
    "................",
    "................",
    "...kkk..........",
    "...GGG..........",
    "...GGG..........",
    "..kkkkk.........",
    "..ddddkk........",
    "..ddddkk........",
    "..ddddd.........",
    "..ddddd.........",
    "..ddddd.........",
    "...ddd..........",
    "...ddd..........",
    "...ddd..........",
    "...kkkk.........",
    "................",
]


# The man of tile 68 fallen on his back, head to the west - the way he
# was walking from, for the player's; the enemy's is the mirror. Columns
# 2-13, so mirrored he lies in the same span and one x serves both sides.
INFANTRY_DOWN = [
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "...k...d........",
    "..kGGkddddddkk..",
    "..kkkkddddddkk..",
    "................",
]


# The camera window on the radar: 8 px wide, its top and bottom edges and
# a tick down each side. A sprite, so it moves every frame without a
# redraw of the radar row (light grey, index 5, in OBJ palette 0).
RADAR_BRACKET = [
    "wwwwwwww",
    "w......w",
    "........",
    "........",
    "........",
    "........",
    "w......w",
    "wwwwwwww",
]


def main():
    src = Image.open(BMP)
    assert src.mode == 'P' and src.size[0] == SHEET_W, (src.mode, src.size)
    im = Image.new('P', (SHEET_W, SHEET_H), 0)
    im.putpalette(src.getpalette())
    im.paste(src, (0, 0))
    px = im.load()

    clear(px, 0, 0, 96, 16)                     # the airframe's flight frames
    clear(px, 32, 112, 64, 16)                  # ... and its turn frames (cols 0-3: muni_art.py's)
    stamp(px, 0, 48, TURRET)
    stamp(px, 16, 48, BALLOON)
    stamp(px, 32, 48, CHAIN)
    stamp(px, 48, 48, [r.ljust(32, '.') for r in bunker()])
    stamp(px, 80, 48, [r.ljust(32, '.') for r in bank()])
    stamp(px, 0, 80, [r.ljust(48, '.') for r in super_bunker()])
    stamp(px, 48, 80, base())
    stamp(px, 48, 32, INFANTRY_FIRE)            # tile 70
    stamp(px, 64, 32, PARACHUTE)                # tile 72
    stamp(px, 80, 32, INFANTRY_WALK)            # tile 74
    stamp(px, 96, 32, INFANTRY_DOWN)            # tile 76
    stamp(px, 120, 8, RADAR_BRACKET)            # tile 31
    stamp(px, 96, 8, MISSILE_E)                 # tiles 28, 29, 30
    stamp(px, 104, 8, MISSILE_NE)
    stamp(px, 112, 8, MISSILE_N)
    stamp(px, 96, 112, LAUNCHER_LOADED)         # tile 236
    stamp(px, 112, 112, LAUNCHER_EMPTY)         # tile 238
    save_bmp4(im, BMP)
    print(f"structures stamped; {BMP} is now {im.size[0]}x{im.size[1]}")


if __name__ == '__main__':
    main()

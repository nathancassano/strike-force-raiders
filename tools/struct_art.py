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
Rows 0-5 hold the airframe, munitions, decks and units. This adds rows
6-13 (the sheet grows to 128x112):

    row  6-7   turret (16x16) at col 0    balloon (16x16) at col 2
               chain (8x8) at col 4       bunker (32x24 in 32x32) at cols 6-9
               bank   (32x24 in 32x32) at cols 10-13
    row 10-13  super bunker (40x24 in 48x32) at cols 0-5
               base (64x32) at cols 6-13
    row 1      cols 12-14: the missile heading E, NE, N (8x8 tiles 28-30)
               col 15: the radar's camera bracket (8x8 tile 31, radar.r65
               RADAR_BRACKET_TILE) - the window's edges, drawn as a sprite
               over the radar row
    row 14-15  the airframe's turn frames (32x16 each): three-quarter view
               at cols 0-3, head-on at cols 4-7, slight turn at cols 8-11
               (heli.r65 HELI_TILE_TURN_*)
    row  4-5   col 6: the infantryman firing (tile 70, unit.r65
               UNIT_TILE_INFANTRY_FIRE) - the standing man with the rifle
               levelled and a flash at the muzzle
               col 8: the parachute canopy (tile 72, para.r65 PARA_TILE):
               drawn over the standing man's cell, lines meeting at his
               shoulders in the cell below

Palette indices: 1 black, 2 dark green, 3 green, 4 light blue, 5 light
grey, 6 orange, 7 darker green, 8 mid green, 9 charcoal, 10 blue-grey,
11 red. Structures are concrete (5/9/1) with green trim so the enemy
palette swap (greens -> red-browns) marks the owner.

    python3 tools/struct_art.py && make
"""

import struct

from PIL import Image

BMP = 'assets/src/obj.bmp'
SHEET_W, SHEET_H = 128, 128

K = {'.': 0, 'k': 1, 'D': 2, 'G': 3, 'b': 4, 'w': 5, 'o': 6, 'd': 7,
     'g': 8, 'c': 9, 's': 10, 'r': 11}


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
# a domed chute with the shroud lines converging on the man's shoulders
# at columns 3-5 of the cell below.
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


def save_bmp4(im, path):
    """Write a 16-colour indexed image as a 4-bit BMP.

    bmp2chr -b4 refuses anything but a 4-bit file, and PIL only writes
    8-bit indexed BMPs, so the header and packed rows are built here.
    """
    w, h = im.size
    pal = im.getpalette()[:48]
    px = im.load()
    stride = ((w * 4 + 31) // 32) * 4
    rows = bytearray()
    for y in range(h - 1, -1, -1):              # bottom-up
        row = bytearray(stride)
        for x in range(w):
            v = px[x, y] & 0xF
            if x & 1:
                row[x >> 1] |= v
            else:
                row[x >> 1] |= v << 4
        rows += row
    palette = b''.join(struct.pack('<BBBB', pal[i + 2], pal[i + 1], pal[i], 0)
                       for i in range(0, 48, 3))
    off = 14 + 40 + len(palette)
    header = struct.pack('<2sIHHI', b'BM', off + len(rows), 0, 0, off)
    info = struct.pack('<IiiHHIIiiII', 40, w, h, 1, 4, 0, len(rows), 2835, 2835, 16, 16)
    with open(path, 'wb') as f:
        f.write(header + info + palette + rows)


def main():
    src = Image.open(BMP)
    assert src.mode == 'P' and src.size[0] == SHEET_W, (src.mode, src.size)
    im = Image.new('P', (SHEET_W, SHEET_H), 0)
    im.putpalette(src.getpalette())
    im.paste(src, (0, 0))
    px = im.load()

    stamp(px, 0, 48, TURRET)
    stamp(px, 16, 48, BALLOON)
    stamp(px, 32, 48, CHAIN)
    stamp(px, 48, 48, [r.ljust(32, '.') for r in bunker()])
    stamp(px, 80, 48, [r.ljust(32, '.') for r in bank()])
    stamp(px, 0, 80, [r.ljust(48, '.') for r in super_bunker()])
    stamp(px, 48, 80, base())
    stamp(px, 0, 112, TURN_34)
    stamp(px, 32, 112, TURN_HEAD)
    stamp(px, 64, 112, TURN_SLIGHT)
    stamp(px, 48, 32, INFANTRY_FIRE)            # tile 70
    stamp(px, 64, 32, PARACHUTE)                # tile 72
    stamp(px, 120, 8, RADAR_BRACKET)            # tile 31
    stamp(px, 96, 8, MISSILE_E)                 # tiles 28, 29, 30
    stamp(px, 104, 8, MISSILE_NE)
    stamp(px, 112, 8, MISSILE_N)
    save_bmp4(im, BMP)
    print(f"structures stamped; {BMP} is now {im.size[0]}x{im.size[1]}")


if __name__ == '__main__':
    main()

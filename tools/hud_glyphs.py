#!/usr/bin/env python3
"""
Stamp the HUD glyph strip into assets/src/bg1.bmp.

One-off authoring helper, not part of the build: it edits the bitmap that
`make assets` then converts, so the BMP stays the source of truth. The
glyphs go on tile row HUD_GLYPH_ROW - below the 224 scanlines NTSC shows -
and the game reads their tile IDs back out of bg1.tilemap at runtime, so
the strip can be redrawn freely as long as the *order* here matches
`hud.r65`'s GLYPH_* constants.

Colour indices follow the BG1 palette: 1 navy (background), 2 white,
3 light blue.

    python3 tools/hud_glyphs.py && make assets
"""

from PIL import Image

BMP = 'assets/src/bg1.bmp'
GLYPH_ROW = 28

# 8x8 glyphs; '.' is navy, '#' white, '+' light blue.
DIGITS = [
    ".####...", "#....#..", "#...##..", "#..#.#..", "#.#..#..", "##...#..", ".####...", "........",  # 0
    "..#.....", ".##.....", "..#.....", "..#.....", "..#.....", "..#.....", ".###....", "........",  # 1
    ".####...", "#....#..", ".....#..", "...##...", "..#.....", ".#......", "######..", "........",  # 2
    ".####...", "#....#..", ".....#..", "..###...", ".....#..", "#....#..", ".####...", "........",  # 3
    "....#...", "...##...", "..#.#...", ".#..#...", "######..", "....#...", "....#...", "........",  # 4
    "######..", "#.......", "#####...", ".....#..", ".....#..", "#....#..", ".####...", "........",  # 5
    ".####...", "#.......", "#####...", "#....#..", "#....#..", "#....#..", ".####...", "........",  # 6
    "######..", ".....#..", "....#...", "...#....", "..#.....", "..#.....", "..#.....", "........",  # 7
    ".####...", "#....#..", "#....#..", ".####...", "#....#..", "#....#..", ".####...", "........",  # 8
    ".####...", "#....#..", "#....#..", ".#####..", ".....#..", ".....#..", ".####...", "........",  # 9
]
SYMBOLS = [
    "..#.....", ".####...", "#.#.....", ".###....", "..#.#...", ".####...", "..#.....", "........",  # $
    "..###...", "..#.....", "..#.....", "..#.....", "..#.....", "..#.....", "..###...", "........",  # [
    "..###...", "....#...", "....#...", "....#...", "....#...", "....#...", "..###...", "........",  # ]
]
ICONS = [
    "........", "..++++..", ".++++++.", ".++++++.", ".++++++.", "########", ".#....#.", "........",  # van
    "........", ".....++.", "....++..", "...++...", ".++++...", "########", ".#....#.", "........",  # launcher
    "........", "...++...", "..+++++.", ".++++++.", "########", "########", ".######.", "........",  # tank
    "...##...", "...##...", "..++++..", ".+.++.+.", "...++...", "...++...", "..+..+..", "..+..+..",  # infantry
    "...##...", "...##...", "..++++..", ".+.++.+#", "...++.#.", "...++...", "..+..+..", "..+..+..",  # engineer
    ".#######", "....#...", "..+++++.", ".+++++++", "#++++++.", "...+.+..", "..+++++.", "........",  # heli
]

PIX = {'.': 1, '#': 2, '+': 3}


def stamp(px, col, rows):
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            px[col * 8 + x, GLYPH_ROW * 8 + y] = PIX[ch]


def main():
    im = Image.open(BMP)
    assert im.mode == 'P' and im.size == (256, 256), (im.mode, im.size)
    px = im.load()
    glyphs = [DIGITS[i:i + 8] for i in range(0, len(DIGITS), 8)]
    glyphs += [SYMBOLS[i:i + 8] for i in range(0, len(SYMBOLS), 8)]
    glyphs += [ICONS[i:i + 8] for i in range(0, len(ICONS), 8)]
    for col, rows in enumerate(glyphs):
        assert len(rows) == 8 and all(len(r) == 8 for r in rows), col
        stamp(px, col, rows)
    im.save(BMP)
    print(f"{len(glyphs)} glyphs stamped on tile row {GLYPH_ROW} of {BMP}")


if __name__ == '__main__':
    main()

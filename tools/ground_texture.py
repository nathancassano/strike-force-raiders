#!/usr/bin/env python3
"""
Paint the ground band of assets/src/bg4.bmp.

One-off authoring helper, not part of the build: it edits the bitmap that
`make assets` converts, so the BMP stays the source of truth.

The band used to carry a yellow marker bar every 32 px so tools/parallax.py
could measure each scanline's displacement - plain soil is periodic at a
few pixels and correlates equally well at any shift. The markers read as
vertical artifacts on screen. This paints soil with a pseudo-random stone
field instead: every row gets stones at positions no other 256 px stretch
repeats, which is all the correlation needs, and the same field is stamped
on both halves of the 512 px layer so the tool's wrap at the screen width
still lines up exactly.

The stones also make the parallax legible. Bands differ in *speed*, and
the eye needs something to track from one strip to the next, so stones
grow from grit on the horizon to 4-5 px rocks at the bottom and the dot
pattern opens out with nearness - the cue perspective gives anyway.

Colour indices follow the BG4 palette: 1 dark earth, 2 earth, 3 highlight.

    python3 tools/ground_texture.py && make assets
"""

from PIL import Image

BMP = 'assets/src/bg4.bmp'
SCREEN_W = 256
GROUND_Y = 168                # matches video.r65 GROUND_Y
GROUND_H = 56                 # 8 HDMA bands of 7 scanlines
HALVES = (0, 256)             # left screen at rows 0-255, right below it

HIGHLIGHT = (150, 122, 70)    # was the marker yellow; now a sandy highlight


def lcg(seed):
    """A tiny deterministic generator, so the bitmap is reproducible."""
    state = seed & 0xFFFFFFFF
    while True:
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        yield state >> 8


BANDS = 8
BAND_H = 7


def soil(x, row):
    """Base earth for *row* of the band (1..55): a dot pattern whose
    density falls with nearness, so the far strips read darker and busier
    and the near ones open out - the same cue perspective gives."""
    band = row // BAND_H
    period = 5 + band                               # 5 .. 12
    if row % 3 == 1 and (x + (row // 3) * 2) % period == 1:
        return 1
    return 2


def rock(field, x, row, size, rnd):
    """A stone: a dark blob *size* wide, two rows tall from three up, with
    a light pixel on its sunlit corner."""
    tall = 2 if size >= 3 else 1
    for dy in range(tall):
        y = row + dy
        if y >= GROUND_H:
            return
        for dx in range(size):
            field[y][(x + dx) % SCREEN_W] = 1
    field[row][x % SCREEN_W] = 3
    if size >= 4 and next(rnd) & 1:
        field[row][(x + 1) % SCREEN_W] = 3


def paint(px):
    rnd = lcg(0x5EED)
    field = [[soil(x, row) for x in range(SCREEN_W)]
             for row in range(GROUND_H)]
    # Stones grow with nearness: grit on the horizon, rocks at the bottom.
    # Every row gets its own, so each scanline has features to lock onto -
    # a row of bare dots is periodic and correlates at the dot period.
    for row in range(1, GROUND_H):
        band = row // BAND_H
        size_min = 1 + band // 2                    # 1 .. 4
        size_max = size_min + 1
        for _ in range(SCREEN_W // 40):
            x = next(rnd) % SCREEN_W
            size = size_min + next(rnd) % (size_max - size_min + 1)
            if size == 1:
                field[row][x] = 3 if next(rnd) % 3 == 0 else 1
            else:
                rock(field, x, row, size, rnd)
    # A light pixel scattered on the near bands: sand catching the light.
    for _ in range(SCREEN_W // 6):
        x = next(rnd) % SCREEN_W
        row = GROUND_H // 2 + next(rnd) % (GROUND_H // 2)
        if field[row][x] == 2:
            field[row][x] = 3
    field[0] = [3] * SCREEN_W                       # the horizon line
    for base in HALVES:
        for row in range(GROUND_H):
            for x in range(SCREEN_W):
                px[x, base + GROUND_Y + row] = field[row][x]


def main():
    im = Image.open(BMP).copy()        # a mapped BMP is read-only
    assert im.mode == 'P' and im.size == (256, 512), (im.mode, im.size)
    pal = im.getpalette()
    pal[9:12] = list(HIGHLIGHT)
    im.putpalette(pal)
    paint(im.load())
    im.save(BMP)
    print(f"ground band painted on {BMP}")


if __name__ == '__main__':
    main()

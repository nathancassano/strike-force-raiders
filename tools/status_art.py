#!/usr/bin/env python3
"""
Draw the status rows' glyphs, assets/src/status.tilemap.bmp.

One-off authoring helper, not part of the build, like hud_glyphs.py: the
bitmap is the source of truth and `make` converts it. It holds what the
HUD's top and bottom rows (hud.r65) are composed from - a bold two-tone
font with a drop shadow, the airframe and man icons, and the health and
fuel meters' cells - in the style of the reference shot
assets/reference/hud.png.

The sheet is BG3 2bpp, but drawn in three of BG3's eight sub-palettes, and
the bitmap says which: an 8-bit BMP whose pixels are CGRAM indices, so a
tile drawn in 20-23 is sub-palette 5, and bmp2chr writes that into the
tilemap entry (each tile one sub-palette; 0 is transparent in all of them).
hud.r65 reads the words back out of the map by position, palette and all.

  5  CGRAM 20-23  gold: the labels' font, and the meters' orange-yellow
  6  CGRAM 24-27  red: the meters' red end
  7  CGRAM 28-31  white: the digits and icons, and the meters' white end

Colour 1 of each is the one dark shadow, which is also the meters' rim and
their empty part; 2 and 3 are the two tones. Glyphs are bold - 2 px stems,
6x7 - light on their top four rows and deep below, with the shadow a pixel
right and down, all inside the tile, so nothing behind needs to be opaque:
the rows draw straight over the sky and the dirt.

A meter is six cells, 48 px, and every cell is its own palette and pattern,
so the fill runs red, red/orange, orange, orange/yellow, yellow, white:
the gradient is the tile palette doing it, three colours a cell. Each
cell has five fills (0, 2, 4, 6, 8 px) on its own row of the sheet, the
patterns de-duplicating across cells; the end caps are one tile, flipped.

Layout (tile columns of row 0, then the meter rows) - the contract with
hud.r65's STAT_* constants:

  row 0  0-9 digits, 10 $, 11 H, 12 F, 13 the gun, 14 a bomb, 15 airframe, 16 man,
         17 the meter's left cap, 18 its right cap; 31 is blank
  row 1+c  meter cell c (0-5), fills 0, 2, 4, 6, 8 px at columns 0-4

    python3 tools/status_art.py && make
"""

import os
import sys

from PIL import Image

BMP = 'assets/src/status.tilemap.bmp'
W, ROWS = 256, 7

SHADOW = (16, 16, 48)
PALETTES = {
    'gold':  (20, (248, 224, 56), (240, 120, 16)),
    'red':   (24, (208, 32, 16), (240, 120, 16)),
    'white': (28, (248, 248, 248), (200, 208, 232)),
}

FONT = {
    '0': [" #### ", "##  ##", "##  ##", "##  ##", "##  ##", "##  ##", " #### "],
    '1': ["  ##  ", " ###  ", "  ##  ", "  ##  ", "  ##  ", "  ##  ", " #### "],
    '2': [" #### ", "##  ##", "    ##", "  ### ", " ##   ", "##    ", "######"],
    '3': [" #### ", "##  ##", "    ##", "  ### ", "    ##", "##  ##", " #### "],
    '4': ["   ## ", "  ### ", " # ## ", "#  ## ", "######", "   ## ", "   ## "],
    '5': ["######", "##    ", "##### ", "    ##", "    ##", "##  ##", " #### "],
    '6': [" #### ", "##    ", "##### ", "##  ##", "##  ##", "##  ##", " #### "],
    '7': ["######", "##  ##", "   ## ", "  ##  ", "  ##  ", "  ##  ", "  ##  "],
    '8': [" #### ", "##  ##", "##  ##", " #### ", "##  ##", "##  ##", " #### "],
    '9': [" #### ", "##  ##", "##  ##", " #####", "    ##", "   ## ", " ###  "],
    '$': ["  ##  ", " #####", "## #  ", " #### ", "  # ##", "##### ", "  ##  "],
    'H': ["##  ##", "##  ##", "##  ##", "######", "##  ##", "##  ##", "##  ##"],
    'F': ["######", "##    ", "##    ", "##### ", "##    ", "##    ", "##    "],
}
ICONS = {
    # The airframe, facing right, and a man.
    'heli': ["###### ", "   #   ", "# #### ", "#######", "  #### ", "  #  # ", " ##### "],
    'man':  ["  ##   ", "  ##   ", " ####  ", "# ## # ", "  ##   ", " #  #  ", " #  #  "],
    # The gun's rounds - a cartridge - and a bomb, nose right.
    'gun':  ["  ##   ", " ####  ", " ####  ", " ####  ", "###### ", " ####  ", " ####  "],
    'bomb': ["       ", "##  ## ", " ######", "#######", " ######", "##  ## ", "       "],
}
LIGHT_ROWS = 4                  # the top tone's rows; the deep one below

# The meters: each cell's palette and pattern - A the light tone, B the
# deep one, D the two in a checker.
CELLS = [('red', 'A'), ('red', 'D'), ('red', 'B'), ('gold', 'D'), ('gold', 'A'), ('white', 'A')]
FILL_TOP, FILL_ROWS = 2, 4      # the fill's rows; the rim is the row above and below


def glyph(px, col, row, rows, pal):
    """A glyph at tile (col, row): two tones, the shadow under-right."""
    base = PALETTES[pal][0]
    x0, y0 = col * 8, row * 8
    ink = {(x, y) for y, line in enumerate(rows) for x, ch in enumerate(line) if ch == '#'}
    for x, y in ink:
        if (x + 1, y + 1) not in ink:
            px[x0 + x + 1, y0 + y + 1] = base + 1
    for x, y in ink:
        px[x0 + x, y0 + y] = base + (2 if y < LIGHT_ROWS else 3)


def meter_cell(px, col, row, pal, pattern, fill):
    """A meter cell: the rim top and bottom, *fill* px of the pattern from
    the left, the rest of the inside dark."""
    base = PALETTES[pal][0]
    x0, y0 = col * 8, row * 8
    for x in range(8):
        px[x0 + x, y0 + FILL_TOP - 1] = base + 1
        px[x0 + x, y0 + FILL_TOP + FILL_ROWS] = base + 1
        for y in range(FILL_TOP, FILL_TOP + FILL_ROWS):
            c = 1
            if x < fill:
                c = {'A': 2, 'B': 3, 'D': 2 + ((x + y) & 1)}[pattern]
            px[x0 + x, y0 + y] = base + c


def cap(px, col, row, right):
    """A meter's end: the rim rounded off. Drawn in the cell's palettes'
    shared dark, so either end's palette will do - gold here."""
    base = PALETTES['gold'][0]
    x0, y0 = col * 8, row * 8
    for y in range(FILL_TOP - 1, FILL_TOP + FILL_ROWS + 1):
        for x in (6, 7):
            if x == 6 and y in (FILL_TOP - 1, FILL_TOP + FILL_ROWS):
                continue                    # the corner, rounded
            px[x0 + (7 - x if right else x), y0 + y] = base + 1


def main():
    im = Image.new('P', (W, ROWS * 8), 0)
    pal = [(0, 0, 0)] * 32
    for base, light, deep in PALETTES.values():
        pal[base + 1], pal[base + 2], pal[base + 3] = SHADOW, light, deep
    im.putpalette([c for rgb in pal for c in rgb])
    px = im.load()
    for i, ch in enumerate('0123456789$'):
        glyph(px, i, 0, FONT[ch], 'white' if ch != '$' else 'gold')
    for i, ch in enumerate('HF'):
        glyph(px, 11 + i, 0, FONT[ch], 'gold')
    glyph(px, 13, 0, ICONS['gun'], 'white')
    glyph(px, 14, 0, ICONS['bomb'], 'white')
    glyph(px, 15, 0, ICONS['heli'], 'white')
    glyph(px, 16, 0, ICONS['man'], 'white')
    cap(px, 17, 0, False)
    cap(px, 18, 0, True)
    for c, (p, pattern) in enumerate(CELLS):
        for k in range(5):
            meter_cell(px, k, 1 + c, p, pattern, k * 2)
    os.makedirs(os.path.dirname(BMP), exist_ok=True)
    im.save(BMP)
    print(f'{BMP}: {W}x{ROWS * 8}, {len(FONT) + len(ICONS)} glyphs, {len(CELLS)} meter cells')


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""
Generate placeholder Mode 0 background art for Rotor Raiders.

Emits a shared 2bpp tileset, one tilemap per BG layer, and the 128-colour
BG palette block, plus src/assets.r65 declaring them with include_bytes!.

The art is deliberately instrumented rather than pretty: every scrolling
layer carries tick columns at a known period in its own colour, so a
screenshot taken at two camera positions proves each layer moved by its own
parallax rate. Replaced with real art in phase 12.

  python3 tools/gen_assets.py
"""
import os
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GFX = os.path.join(ROOT, 'assets', 'gfx')

# ---------------------------------------------------------------- tiles ----
# 2bpp: 16 bytes per tile, 8 rows of (plane0, plane1).
# Pixel values 0-3; 0 is transparent.

def tile(rows):
    """rows: 8 strings of 8 chars from '0123'."""
    out = bytearray()
    for r in rows:
        p0 = p1 = 0
        for x, ch in enumerate(r):
            v = int(ch)
            bit = 7 - x
            p0 |= (v & 1) << bit
            p1 |= ((v >> 1) & 1) << bit
        out += bytes((p0, p1))
    return bytes(out)


def solid(v):
    return tile([str(v) * 8] * 8)


TILES = []


def add(t):
    TILES.append(t)
    return len(TILES) - 1


T_EMPTY = add(solid(0))

# --- HUD (BG1) -------------------------------------------------------------
T_HUD_FILL = add(solid(1))
T_HUD_EDGE = add(tile(['22222222'] + ['11111111'] * 7))
T_HUD_MARK = add(tile(['22222222'] + ['13333331'] * 6 + ['11111111']))

# --- clouds (BG2) ----------------------------------------------------------
T_CLOUD_L = add(tile(['00000011', '00001222', '00112222', '01222222',
                      '12222222', '12222222', '01122222', '00001111']))
T_CLOUD_R = add(tile(['11000000', '2221 000'.replace(' ', '0'), '22221100',
                      '22222210', '22222221', '22222221', '22222110',
                      '11110000']))
T_CLOUD_M = add(tile(['11111111', '22222222', '22222222', '22222222',
                      '22222222', '22222222', '22222222', '11111111']))
# Tick column: a bright vertical bar, the parallax measuring stick.
T_CLOUD_TICK = add(tile(['00333300'] * 8))

# --- hills (BG3) -----------------------------------------------------------
T_HILL_UP = add(tile(['00000001', '00000012', '00000122', '00001222',
                      '00012222', '00122222', '01222222', '12222222']))
T_HILL_DN = add(tile(['10000000', '21000000', '22100000', '22210000',
                      '22221000', '22222100', '22222210', '22222221']))
T_HILL_SOLID = add(solid(2))
T_HILL_TICK = add(tile(['00033000'] * 8))

# --- ground (BG4) ----------------------------------------------------------
T_GND_TOP = add(tile(['33333333', '22222222', '22122212', '22222222',
                      '21222122', '22222222', '22221222', '12222221']))
T_GND_FILL = add(tile(['22222222', '21222122', '22222222', '12221222',
                      '22222222', '22122221', '22222222', '21222212']))
# Horizontally near-uniform dither, so band seams have nothing structured
# to break (see the band-seam note in the plan).
T_GND_DITH = add(tile(['21212121', '12121212'] * 4))
T_GND_TICK = add(tile(['00300300'] * 8))

while len(TILES) < 32:
    add(solid(0))

# ------------------------------------------------------------- palettes ----
# Mode 0 gives each BG its own 32-colour CGRAM block:
#   BG1 0-31, BG2 32-63, BG3 64-95, BG4 96-127.  Sprites use 128-255.
# Within a block, the tilemap's 3-bit palette field picks one of 8 groups
# of 4 colours. Colour 0 of every group is transparent.

def bgr555(r, g, b):
    return (b & 31) << 10 | (g & 31) << 5 | (r & 31)


PALS = {
    # layer: [group0 4 colours]
    1: [bgr555(0, 0, 0), bgr555(4, 5, 8), bgr555(28, 30, 31), bgr555(20, 24, 28)],
    2: [bgr555(0, 0, 0), bgr555(18, 22, 28), bgr555(26, 29, 31), bgr555(31, 28, 12)],
    3: [bgr555(0, 0, 0), bgr555(6, 8, 14), bgr555(10, 12, 18), bgr555(31, 12, 12)],
    4: [bgr555(0, 0, 0), bgr555(9, 7, 4), bgr555(14, 11, 6), bgr555(31, 26, 10)],
}


def build_palette():
    # 256 entries: BG layers occupy 0-127, OBJ palette 0 starts at 128.
    cg = [0] * 256
    for layer, cols in PALS.items():
        base = (layer - 1) * 32
        for grp in range(8):
            for i, c in enumerate(cols):
                cg[base + grp * 4 + i] = c
    for i, c in enumerate(OBJ_PAL):
        cg[128 + i] = c
    return b''.join(struct.pack('<H', c) for c in cg)


# ------------------------------------------------------------- tilemaps ----
COLS, ROWS = 64, 32          # 64x32 = 512px wide, wraps in hardware


def entry(tile_idx, pal=0, prio=0, hflip=0, vflip=0):
    return (tile_idx & 0x3FF) | (pal & 7) << 10 | (prio & 1) << 13 \
        | (hflip & 1) << 14 | (vflip & 1) << 15


def emit_map(cells, cols=COLS):
    """cells[row][col] -> VRAM order. A 64x32 map is two 32x32 screens,
    the right half stored immediately after the left."""
    words = []
    for screen in range(cols // 32):
        for r in range(ROWS):
            for c in range(32):
                words.append(cells[r][screen * 32 + c])
    return b''.join(struct.pack('<H', w) for w in words)


def blank(cols=COLS):
    return [[entry(T_EMPTY) for _ in range(cols)] for _ in range(ROWS)]


# BG1 - HUD strip, 32x32 (does not scroll)
def bg1_map():
    cells = blank(32)
    for c in range(32):
        cells[0][c] = entry(T_HUD_FILL)
        cells[1][c] = entry(T_HUD_MARK if c % 4 == 0 else T_HUD_FILL)
        cells[2][c] = entry(T_HUD_EDGE, vflip=1)
    return emit_map(cells, 32)


# BG2 - clouds, rows 4-11, tick column every 8 tiles (64 px)
def bg2_map():
    cells = blank()
    for c in range(COLS):
        if c % 8 == 0:
            for r in range(4, 12):
                cells[r][c] = entry(T_CLOUD_TICK)
        elif c % 8 in (2, 3, 4):
            r = 5 + (c // 8) % 4
            t = {2: T_CLOUD_L, 3: T_CLOUD_M, 4: T_CLOUD_R}[c % 8]
            cells[r][c] = entry(t)
    return emit_map(cells)


# BG3 - hill silhouette, rows 15-18, tick every 8 tiles offset by 4
def bg3_map():
    cells = blank()
    for c in range(COLS):
        peak = 15 + (c // 4 + c // 9) % 2      # a ragged skyline
        for r in range(peak, 19):
            cells[r][c] = entry(T_HILL_SOLID)
        cells[peak][c] = entry(T_HILL_UP if c % 2 == 0 else T_HILL_DN)
        if c % 8 == 4:
            cells[18][c] = entry(T_HILL_TICK)
    return emit_map(cells)


# BG4 - ground band, rows 21-27, tick every 4 tiles (32 px).
# Row 21 is y=168, so the ground is the bottom 56 of 224 scanlines - a
# quarter of the screen. Keep this in step with GND_TOP_A/GND_TOP_B and
# GND_BAND in src/video.r65, which slice the same 56 lines into HDMA bands.
GND_ROW = 21                 # first ground tile row (y = GND_ROW * 8)
GND_DITH_ROW = 25            # nearer half of the band uses the dither tile


def bg4_map():
    cells = blank()
    for c in range(COLS):
        cells[GND_ROW][c] = entry(T_GND_TOP)
        for r in range(GND_ROW + 1, 28):
            cells[r][c] = entry(T_GND_DITH if r >= GND_DITH_ROW else T_GND_FILL)
        # Tick every 4 tiles (32px) on EVERY ground row including the top
        # edge: a horizontally uniform row correlates at 100%% for any shift
        # and so cannot be measured, which hides the first HDMA band.
        if c % 4 == 0:
            for r in range(GND_ROW, 28):
                cells[r][c] = entry(T_GND_TICK)
    return emit_map(cells)



# ------------------------------------------------------------ OBJ (4bpp) ---
# Sprites are 4bpp in every BG mode: 32 bytes per 8x8 tile, bitplanes 0/1
# interleaved by row for the first 16 bytes and 2/3 for the second 16.
# Colour 0 is transparent.

OBJ_COLS = 16                # OBJ VRAM addresses tiles 16 to a row
HELI_W, HELI_H = 32, 16      # per the plan's sprite table
HELI_FRAMES = 3              # lean-left, level, lean-right (tilt is cosmetic)


def tile4(px):
    """px: 8 rows of 8 ints (0-15) -> one 4bpp tile."""
    out = bytearray()
    for plane in (0, 2):
        for row in px:
            a = b = 0
            for x, v in enumerate(row):
                bit = 7 - x
                a |= ((v >> plane) & 1) << bit
                b |= ((v >> (plane + 1)) & 1) << bit
            out += bytes((a, b))
    return bytes(out)


def grid(w, h):
    return [[0] * w for _ in range(h)]


def rect(g, x0, y0, x1, y1, c):
    for y in range(max(0, y0), min(len(g), y1 + 1)):
        for x in range(max(0, x0), min(len(g[0]), x1 + 1)):
            g[y][x] = c


# Helicopter, nose to the right. Drawn rather than hand-typed so the three
# tilt frames stay identical apart from the lean, and so the widths cannot
# drift out of the 32x16 cell.
#   1 outline  2 body  3 highlight  4 canopy  5 rotor  6 tail marking
def heli_frame(tilt):
    """tilt: -1 nose down (moving right), 0 level, +1 nose up."""
    g = grid(HELI_W, HELI_H)
    # Main rotor and mast. The disc stays level whatever the fuselage does.
    rect(g, 2, 0, 29, 0, 5)
    rect(g, 15, 1, 16, 2, 1)
    # Fuselage: nose at x=31, tail boom running left to the rotor pylon.
    for x in range(8, HELI_W):
        # Lean pivots about the cabin centre, so nose and tail move opposite.
        lean = 0
        if tilt < 0 and x >= 24: lean = 1
        if tilt < 0 and x < 12:  lean = -1
        if tilt > 0 and x >= 24: lean = -1
        if tilt > 0 and x < 12:  lean = 1
        top = (4 if x >= 12 else 6) + lean
        bot = (11 if x >= 12 else 8) + lean
        rect(g, x, top, x, bot, 2)
        g[top][x] = 1
        g[bot][x] = 1
        if 12 <= x <= 22 and top + 1 <= 6:
            rect(g, x, top + 1, x, top + 2, 3)     # highlight along the spine
    # Canopy, front of the cabin.
    rect(g, 25, 6, 30, 9, 4)
    # Tail rotor and fin at the far left.
    rect(g, 0, 2, 1, 11, 5)
    rect(g, 2, 5, 7, 7, 6)
    # Skids.
    rect(g, 13, 13, 28, 13, 1)
    rect(g, 15, 12, 15, 12, 1)
    rect(g, 26, 12, 26, 12, 1)
    return g


# Munitions are 8x8 (the plan's sprite table), so they use OBSEL's small size
# and one tile each. The helicopter's three 32x16 frames occupy tiles 0-11 and
# 16-27, leaving 12-15 and 28-31.
T_OBJ_BULLET = 12
T_OBJ_BOMB = 13


def bullet_tile():
    g = grid(8, 8)
    rect(g, 1, 3, 6, 4, 3)       # bright core, drawn long to read as a tracer
    rect(g, 0, 3, 0, 4, 1)
    rect(g, 7, 3, 7, 4, 5)
    return g


def bomb_tile():
    g = grid(8, 8)
    rect(g, 3, 0, 4, 1, 1)       # nose
    rect(g, 2, 2, 5, 5, 2)       # body
    rect(g, 3, 2, 3, 5, 3)       # highlight down one side
    rect(g, 2, 6, 5, 6, 1)       # fins
    rect(g, 1, 7, 6, 7, 6)
    return g


def obj_tiles():
    """Three 32x16 frames laid into a 16-wide OBJ tile sheet, two rows deep.

    A 16x16 OBJ sprite at tile t occupies t, t+1, t+16, t+17, so each frame's
    left half starts at t = k*4 and its right half at t = k*4 + 2."""
    sheet = [grid(8, 8) for _ in range(OBJ_COLS * 2)]
    for k in range(HELI_FRAMES):
        g = heli_frame(k - 1)
        for py in range(HELI_H):
            for px in range(HELI_W):
                t = (py // 8) * OBJ_COLS + k * 4 + (px // 8)
                sheet[t][py % 8][px % 8] = g[py][px]
    sheet[T_OBJ_BULLET] = bullet_tile()
    sheet[T_OBJ_BOMB] = bomb_tile()
    return b''.join(tile4(t) for t in sheet)


# OBJ palette 0 (CGRAM 128-143). Index 0 is transparent and never shown.
OBJ_PAL = [
    bgr555(0, 0, 0),      # 0 transparent
    bgr555(2, 3, 4),      # 1 outline
    bgr555(10, 13, 9),    # 2 body
    bgr555(16, 20, 14),   # 3 highlight
    bgr555(14, 22, 28),   # 4 canopy
    bgr555(21, 22, 24),   # 5 rotor
    bgr555(26, 12, 8),    # 6 tail marking
] + [bgr555(0, 0, 0)] * 9


# ----------------------------------------------------------------- main ----
def main():
    os.makedirs(GFX, exist_ok=True)
    files = {
        'bg_tiles.chr': b''.join(TILES),
        'bg_pal.pal': build_palette(),
        'bg1_map.bin': bg1_map(),
        'bg2_map.bin': bg2_map(),
        'bg3_map.bin': bg3_map(),
        'bg4_map.bin': bg4_map(),
        'obj_tiles.chr': obj_tiles(),
    }
    for name, data in files.items():
        with open(os.path.join(GFX, name), 'wb') as f:
            f.write(data)
        print(f"  {name:16} {len(data):6} bytes")

    decl = ['// GENERATED by tools/gen_assets.py - DO NOT EDIT',
            '// Placeholder Mode 0 background art. Regenerate with `make assets`.',
            '',
            '#[bank(1)]',
            '']
    consts = []
    for name, data in files.items():
        sym = name.split('.')[0].upper()
        decl.append(f'static {sym}: [u8; {len(data)}] = '
                    f'include_bytes!("../assets/gfx/{name}");')
        consts.append(f'const {sym}_SIZE: u16 = {len(data)};')
    decl += ['', *consts, '']
    with open(os.path.join(ROOT, 'src', 'assets.r65'), 'w') as f:
        f.write('\n'.join(decl))
    print(f"  src/assets.r65   {len(TILES)} tiles")


if __name__ == '__main__':
    main()

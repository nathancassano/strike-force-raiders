#!/usr/bin/env python3
"""Per-scanline sprite and tile load from a 544-byte SNES OAM dump.

The hardware drops sprites past 32 on a scanline and tiles past 34, so a
frame that exceeds either is losing sprites. Ground units all stand on the
same few scanlines, which is where this bites.

  oamstat.py oam.bin [--max-sprites 32] [--max-tiles 34]
"""
import sys, struct

def main():
    path = sys.argv[1]
    lim_s = int(sys.argv[sys.argv.index('--max-sprites') + 1]) if '--max-sprites' in sys.argv else 32
    lim_t = int(sys.argv[sys.argv.index('--max-tiles') + 1]) if '--max-tiles' in sys.argv else 34
    d = open(path, 'rb').read()
    if len(d) < 544:
        print(f"FAIL: {path} is {len(d)} bytes, expected 544"); return 2

    sprites = []
    for i in range(128):
        x, y, tile, attr = d[i*4], d[i*4+1], d[i*4+2], d[i*4+3]
        ext = d[512 + (i >> 2)]
        shift = (i & 3) << 1
        x |= ((ext >> shift) & 1) << 8
        large = (ext >> (shift + 1)) & 1
        size = 16 if large else 8
        if y >= 224:                      # parked
            continue
        sprites.append((x, y, size))

    rows_s = [0] * 224
    rows_t = [0] * 224
    for x, y, size in sprites:
        for sy in range(y, min(224, y + size)):
            rows_s[sy] += 1
            rows_t[sy] += size // 8       # 8x8 -> 1 tile, 16x16 -> 2 per row
    worst_s = max(rows_s); worst_t = max(rows_t)
    line_s = rows_s.index(worst_s); line_t = rows_t.index(worst_t)
    print(f"active sprites   : {len(sprites)}")
    print(f"peak sprites/line: {worst_s} (line {line_s}, limit {lim_s})")
    print(f"peak tiles/line  : {worst_t} (line {line_t}, limit {lim_t})")
    ok = worst_s <= lim_s and worst_t <= lim_t
    print("ok" if ok else "FAIL: over the per-scanline budget")
    return 0 if ok else 1

sys.exit(main())

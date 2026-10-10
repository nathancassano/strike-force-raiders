#!/usr/bin/env python3
"""
Set attribute bits on every entry of a bmp2chr tilemap, in place.

    tilemap_attr.py MAP [--pal N] [--priority] [--tile-offset N]

  --pal N          add N to each entry's palette field (bits 10-12)
  --priority       set each entry's priority bit (bit 13)
  --tile-offset N  add N to each entry's tile number (bits 0-9): for a sheet
                   whose tiles are uploaded after another sheet's on the same
                   layer (the mountains, after the clouds on BG2)

Run by the Makefile after bmp2chr, which has no flag for any of them. A sheet's
bitmap is drawn in palettes counted from 0 and its .pal is uploaded N
palettes up CGRAM, so the map has to name them N up too - in Mode 1 the 4bpp
layers share CGRAM 0-127 with each other and their first two palettes with
BG3's, so no sheet can sit at palette 0 but the HUD.
"""
import sys


def main():
    args = sys.argv[1:]
    path = args.pop(0)
    pal, prio, offset = 0, False, 0
    while args:
        a = args.pop(0)
        if a == '--pal':
            pal = int(args.pop(0))
        elif a == '--priority':
            prio = True
        elif a == '--tile-offset':
            offset = int(args.pop(0))
        else:
            raise SystemExit(f"tilemap_attr.py: unknown argument {a}")
    d = bytearray(open(path, 'rb').read())
    for i in range(0, len(d), 2):
        word = d[i] | (d[i + 1] << 8)
        tile = (word & 0x3FF) + offset
        if tile > 0x3FF:
            raise SystemExit(f"tilemap_attr.py: {path}: tile {tile} is past the 1024 a map can name")
        p = (((word >> 10) & 7) + pal) & 7
        word = (word & ~0x1FFF) | (p << 10) | tile
        if prio:
            word |= 0x2000
        d[i], d[i + 1] = word & 0xFF, word >> 8
    open(path, 'wb').write(d)


if __name__ == '__main__':
    main()

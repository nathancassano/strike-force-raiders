#!/usr/bin/env python3
"""
Set attribute bits on every entry of a bmp2chr tilemap, in place.

    tilemap_attr.py MAP [--pal N] [--priority]

  --pal N       add N to each entry's palette field (bits 10-12)
  --priority    set each entry's priority bit (bit 13)

Run by the Makefile after bmp2chr, which has no flag for either. A sheet's
bitmap is drawn in palettes counted from 0 and its .pal is uploaded N
palettes up CGRAM, so the map has to name them N up too - in Mode 1 the 4bpp
layers share CGRAM 0-127 with each other and their first two palettes with
BG3's, so no sheet can sit at palette 0 but the HUD.
"""
import sys


def main():
    args = sys.argv[1:]
    path = args.pop(0)
    pal, prio = 0, False
    while args:
        a = args.pop(0)
        if a == '--pal':
            pal = int(args.pop(0))
        elif a == '--priority':
            prio = True
        else:
            raise SystemExit(f"tilemap_attr.py: unknown argument {a}")
    d = bytearray(open(path, 'rb').read())
    for i in range(1, len(d), 2):
        hi = d[i]
        p = (((hi >> 2) & 7) + pal) & 7
        hi = (hi & ~0x1C) | (p << 2)
        if prio:
            hi |= 0x20
        d[i] = hi
    open(path, 'wb').write(d)


if __name__ == '__main__':
    main()

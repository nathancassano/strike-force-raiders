#!/usr/bin/env python3
"""Write a 16-colour indexed image as a 4-bit BMP.

`r65x bmp2chr -b4` refuses anything but a 4-bit file and PIL only writes
8-bit indexed BMPs, so the header and the packed rows are built by hand.
Shared by the authoring helpers that stamp pixels into assets/src.
"""

import struct


def save_bmp4(im, path):
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

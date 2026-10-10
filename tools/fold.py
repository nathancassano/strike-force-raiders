#!/usr/bin/env python3
"""
Fold a 512-wide BG sheet into the 256-wide layout bmp2chr needs.

    fold.py IN.bmp OUT.bmp

A 64x32 SNES tilemap is two 32x32 screens held one after the other, but
bmp2chr walks a bitmap row-major at its full width - so it has to be fed
the strip with its right-hand 256 px moved below the left: 32 tiles wide by
64 tall, after which its output is byte-identical to what the PPU expects.
The sheets in assets/src are drawn as they appear, 512x256, and the
Makefile folds each on its way into bmp2chr. A sheet that is not 512 wide
(the HUD's single 32x32 screen) is copied through unchanged.

4-bit or 8-bit BMPs - an editor may save a 16-colour sheet either way; each
256 px half is then a whole number of bytes (128 or 256), so folding is the
same byte slicing in both. The depth, palette, colour count and resolution
are carried over as they are. Plain Python, since the Makefile's python3 has
no PIL.
"""
import shutil
import struct
import sys


def main():
    src, dst = sys.argv[1], sys.argv[2]
    d = open(src, 'rb').read()
    off = struct.unpack('<I', d[10:14])[0]
    hdr = struct.unpack('<I', d[14:18])[0]
    w, h = struct.unpack('<ii', d[18:26])
    bpp = struct.unpack('<H', d[28:30])[0]
    if w != 512:
        shutil.copyfile(src, dst)
        return
    if bpp not in (4, 8):
        raise SystemExit(f"fold.py: {src}: want a 4-bit or 8-bit BMP, got {bpp}-bit")
    compression = struct.unpack('<I', d[30:34])[0]
    if compression != 0:
        raise SystemExit(f"fold.py: {src}: compressed BMP (type {compression}); save it uncompressed")
    width = w * bpp // 8                      # bytes of pixels in a row
    half = width // 2                         # one 256 px screen
    stride = (width + 3) & ~3                 # rows pad to 4 bytes
    rows = [d[off + y * stride: off + y * stride + width] for y in range(abs(h))]
    if h > 0:
        rows.reverse()                        # stored bottom-up
    folded = [r[:half] for r in rows] + [r[half:] for r in rows]
    pixels = b''.join(reversed(folded))       # write bottom-up
    palette = d[14 + hdr:off]
    info = bytearray(d[14:14 + hdr])
    struct.pack_into('<ii', info, 4, 256, len(folded))
    struct.pack_into('<I', info, 20, len(pixels))
    head = struct.pack('<2sIHHI', b'BM', 14 + len(info) + len(palette) + len(pixels), 0, 0,
                       14 + len(info) + len(palette))
    open(dst, 'wb').write(head + bytes(info) + palette + pixels)


if __name__ == '__main__':
    main()

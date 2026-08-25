#!/usr/bin/env python3
"""
Report the dominant colours of a screenshot, or assert one is present.

  pngstat.py shot.png                    list the top colours
  pngstat.py shot.png --expect 21,31,73  fail unless that colour covers
                                         >= --min-pct of the frame (default 50)

Colours are 8-bit RGB hex or 'r,g,b'. Used by tests/run.sh to check that a
frame actually rendered rather than trusting a non-zero exit code.
"""
import struct
import sys
import zlib
from collections import Counter


def read_rgb(path):
    d = open(path, 'rb').read()
    pos, w, h, idat = 8, None, None, b''
    while pos < len(d):
        ln = struct.unpack('>I', d[pos:pos + 4])[0]
        typ = d[pos + 4:pos + 8]
        data = d[pos + 8:pos + 8 + ln]
        if typ == b'IHDR':
            w, h, bd, ct = struct.unpack('>IIBB', data[:10])
            if (bd, ct) != (8, 2):
                raise SystemExit(f"{path}: expected 8-bit RGB, got depth={bd} type={ct}")
        elif typ == b'IDAT':
            idat += data
        pos += 12 + ln
    raw = zlib.decompress(idat)
    stride = w * 3 + 1
    counts = Counter()
    for y in range(h):
        if raw[y * stride] != 0:
            raise SystemExit(f"{path}: PNG filter {raw[y*stride]} unsupported")
        row = raw[y * stride + 1:(y + 1) * stride]
        for x in range(w):
            counts[tuple(row[x * 3:x * 3 + 3])] += 1
    return w, h, counts


def parse_colour(s):
    s = s.strip().lstrip('#')
    if ',' in s:
        return tuple(int(p) for p in s.split(','))
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def main():
    path = sys.argv[1]
    args = sys.argv[2:]
    w, h, counts = read_rgb(path)
    total = w * h

    if '--expect' in args:
        want = parse_colour(args[args.index('--expect') + 1])
        min_pct = 50.0
        if '--min-pct' in args:
            min_pct = float(args[args.index('--min-pct') + 1])
        pct = 100.0 * counts.get(want, 0) / total
        if pct < min_pct:
            print(f"FAIL {path}: rgb{want} covers {pct:.1f}%, wanted >= {min_pct}%")
            for px, n in counts.most_common(3):
                print(f"     saw rgb{px} {100*n/total:.1f}%")
            return 1
        print(f"ok   rgb{want} covers {pct:.1f}%")
        return 0

    print(f"{path}: {w}x{h}, {len(counts)} colours")
    for px, n in counts.most_common(8):
        print(f"  rgb{px}  {100*n/total:5.1f}%")
    return 0


if __name__ == '__main__':
    sys.exit(main())

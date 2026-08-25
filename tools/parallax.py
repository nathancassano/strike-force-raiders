#!/usr/bin/env python3
"""
Measure per-scanline horizontal displacement between two screenshots and
assert the layers scrolled at their intended parallax rates.

  parallax.py BASE.png MOVED.png                    print a row profile
  parallax.py BASE.png MOVED.png --assert-bands 8   also check the ground

Each structured scanline is cross-correlated against the same row of the
base frame; consecutive rows with equal displacement are collapsed into a
run. A correct frame yields one run per BG layer, plus one run per HDMA
ground band.
"""
import struct
import sys
import zlib


def load(path):
    d = open(path, 'rb').read()
    pos, w, h, idat = 8, None, None, b''
    while pos < len(d):
        ln = struct.unpack('>I', d[pos:pos + 4])[0]
        typ = d[pos + 4:pos + 8]
        data = d[pos + 8:pos + 8 + ln]
        if typ == b'IHDR':
            w, h, _, _ = struct.unpack('>IIBB', data[:10])
        elif typ == b'IDAT':
            idat += data
        pos += 12 + ln
    raw = zlib.decompress(idat)
    st = w * 3 + 1
    px = [[tuple(raw[y * st + 1 + x * 3: y * st + 1 + x * 3 + 3])
           for x in range(w)] for y in range(h)]
    return w, h, px


def best_shift(ra, rb, w):
    best = (-1, 0)
    for s in range(w):
        n = sum(1 for x in range(w) if rb[x] == ra[(x + s) % w])
        if n > best[0]:
            best = (n, s)
    return best[1], best[0] / w


def runs_of(a, b, w, h):
    out = []
    for y in range(h):
        if len(set(a[y])) < 2:      # uniform row: every shift matches
            continue
        s, c = best_shift(a[y], b[y], w)
        if out and out[-1][2] == s and y == out[-1][1] + 1:
            out[-1][1] = y
        else:
            out.append([y, y, s, c])
    return out


def main():
    base, moved = sys.argv[1], sys.argv[2]
    args = sys.argv[3:]
    w, h, A = load(base)
    _, _, B = load(moved)
    rs = runs_of(A, B, w, h)

    print(f"{'rows':>11} {'shift':>6} {'match':>7}")
    for a, b, s, c in rs:
        print(f"{a:4d}-{b:4d} {s:6d} {100 * c:6.1f}%")

    if '--assert-bands' in args:
        want = int(args[args.index('--assert-bands') + 1])
        # Ground bands are the trailing runs; they share a constant step
        # modulo the ground tick period.
        tail = [r for r in rs if r[0] >= h * 2 // 3]
        if len(tail) < want:
            print(f"\nFAIL: {len(tail)} ground runs, wanted {want} bands")
            return 1
        band = tail[-want:]
        steps = [(band[i + 1][2] - band[i][2]) % 32 for i in range(want - 1)]
        if len(set(steps)) != 1:
            print(f"\nFAIL: band steps not constant: {steps}")
            return 1
        if steps[0] == 0:
            print("\nFAIL: band step is 0 - HDMA is not driving BG4HOFS")
            return 1
        heights = [b[1] - b[0] + 1 for b in band]
        print(f"\nok   {want} ground bands, step {steps[0]} px, "
              f"heights {heights}")
    return 0


if __name__ == '__main__':
    sys.exit(main())

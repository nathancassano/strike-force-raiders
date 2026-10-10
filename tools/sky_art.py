#!/usr/bin/env python3
"""
Paint the sky - BG2, 4bpp, assets/src/sky.tilemap.bmp - from rendered art.

One-off authoring helper, not part of the build: it writes the bitmap that
the Makefile's bmp2chr rule converts, so the BMP stays the source of truth
and an ordinary `make` picks the edit up. The sky holds two bands at two
depths that never share a scanline, split by video.r65's SKY_SPLIT:

    clouds      rows 16-91, the bitmap's palette 0 (CGRAM 48-63), above it
    mountains   rows 135-178, palettes 1-4 (CGRAM 64-127), below it

Each band is painted on its own and leaves the other alone.

Both start as ComfyUI renders: the pixel_art_sdxl workflow at 1536x640, its
models passed through comfyui-seamless-tiling's SeamlessTile and its decode
done by CircularVAEDecode, both `x_only`, so the render's right edge
continues into its left and the layer's 512 px wrap has no seam. Prompt for
the band's subject across the whole width on a solid black sky - "black
background" weighted up, (...:1.4); any graded or hazy sky cannot be keyed.
(SeamlessTile's "Make a copy" fails to deep-copy the model on this ComfyUI;
"Modify in place" patches the cached checkpoint, so unload the models
afterwards - POST /free - or every later render of it tiles too.)

MOUNTAINS take the render's pixels. gimp crops the band out, scales the full
width to 512 and the crop to the band's height, and indexes to 128 colours
without dither (the palettes are fitted here, so gimp's job is only to tidy
the render's anti-aliasing):

    python3 tools/sky_art.py --scm > sky.scm
    gimp-console -i -b '(begin (load "sky.scm")
                        (rr-band "render.png" "band.bmp" CY CH 44))' -b '(gimp-quit 0)'
    python3 tools/sky_art.py mountains band.bmp [--key-grey] [--haze N]

CY and CH are the crop's top row and height in the render; squashing CH to
44 rows flattens the peaks, which a distant range wants.

- the sky becomes index 0, transparent, so the backdrop shows through: the
  range is keyed by silhouette (key_silhouette), the solid pixels joined
  to the bottom row and everything below their top in each column.
  --key-grey takes grey for sky as well, for a render whose clouds touch
  its peaks - not for snow caps;
- a 4bpp tile draws from one 16-colour palette, the first of which is
  transparent, so the range gets four palettes of 15 colours - every one
  of them different - fitted and split by derive_palettes, and each tile is
  given the palette that fits it with the least error.

CLOUDS take only the render's shapes. Its "pixels" are irregular blocks of
5-8 render px on no grid, and shrinking that 3x slices them into streaky
noise - fine on rock, junk on cloud. So cloud_shapes blurs the block noise
away, averages the crop down to the band and thresholds it into clean
silhouettes, and shade_clouds draws them in a ramp of 15 colours: light at
each band's top edge, darker toward its underside, a little of the render's
own brightness mixed in so long bands are not uniform:

    python3 tools/sky_art.py clouds render.png CY CH [--threshold T] [--haze N]

CY and CH are the crop in the 1536x640 render itself (no gimp step);
--threshold (0-255) moves the cloud/sky line, by default Otsu's.

Both bands:

- --haze N (0-1) blends the band's colours N of the way toward the game's
  sky - the backdrop colour main.r65 sets: the air between the viewer and
  something far off, which mutes colours and flattens contrast;
- colours are kept MIN_SEP apart, so no slot goes on a difference no one
  can see;
- bmp2chr reads a tile's palette from the index range (16N+1..16N+15). The
  bitmap is 8-bit with exactly 16 x 5 palette entries: bmp2chr sizes the
  .pal from that count, and video.r65 uploads it whole at CGRAM_SKY;
- written folded, 32 tiles wide by 64 tall, right-hand screen below the
  left.
"""

import re
import sys
from dataclasses import dataclass

import numpy as np

from PIL import Image

BMP = 'assets/src/sky.tilemap.bmp'
STRIP_W = 512
PER = 15                      # colours a palette holds; entry 0 is transparent
ENTRIES = 16 * 5              # the bitmap's palettes: clouds 0, mountains 1-4
RESTARTS = 6                  # colour splits tried; see derive_palettes
SKY_NEAR = 3 * 24 * 24        # squared RGB distance still counted as sky
MIN_SEP = 14                  # RGB distance kept between any two colours of
                              # a band: more than one 5-bit step in each channel
GREY_SPREAD = 28              # --key-grey: a colour whose channels differ by
                              # less than this is grey, a cloud's colour
SPECK = 6                     # clouds: an island or a hole this small is noise
BLUR = 4                      # clouds: render px of blur that melts its blocks
SMOOTH = 4                    # clouds: px either way the light is averaged over
CLOUD_LOW = (118, 136, 176)   # clouds: the ramp's underside ...
CLOUD_HIGH = (244, 246, 250)  # ... and its lit top edge


@dataclass
class Band:
    name: str
    top: int                  # first row
    height: int
    pal0: int                 # the bitmap's first palette for the band
    pals: int                 # how many

    @property
    def bottom(self):
        return self.top + self.height - 1


BANDS = {
    # Above SKY_SPLIT, from the row under the HUD strip (rows 0-15): a cloud
    # the crop cut flat at the top then reads as running on up behind the
    # strip, where at a row of open sky below it the cut would show.
    'clouds': Band('clouds', 16, 76, 0, 1),
    # The last row is the scanline above the dirt (GND_TOP, 179) - not under
    # it: the base of a render is where its detail is, and rows under the
    # dirt are never seen. So the band's bottom row must be solid, or sky
    # shows above the dirt; main() checks.
    'mountains': Band('mountains', 135, 44, 1, 4),
}

BAND_SCM = r'''
(define (rr-band in out cy ch h)
  (let* ((img (car (gimp-file-load RUN-NONINTERACTIVE in in))))
    (gimp-image-crop img 1536 ch 0 cy)
    (gimp-context-set-interpolation INTERPOLATION-CUBIC)
    (gimp-image-scale img 512 h)
    (gimp-image-convert-indexed img CONVERT-DITHER-NONE CONVERT-PALETTE-GENERATE 128 FALSE TRUE "")
    (file-bmp-save RUN-NONINTERACTIVE img (car (gimp-image-get-active-drawable img)) out out)
    (gimp-image-delete img)))
'''


def dist(a, b):
    return sum((x - y) * (x - y) for x, y in zip(a, b))


def flood(seeds, ok, h):
    """Every pixel reachable from *seeds* through pixels *ok* accepts; the
    strip wraps left to right."""
    hit = [[False] * STRIP_W for _ in range(h)]
    stack = list(seeds)
    while stack:
        x, y = stack.pop()
        if hit[y][x] or not ok(x, y):
            continue
        hit[y][x] = True
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= ny < h:
                stack.append((nx % STRIP_W, ny))
    return hit


def key_silhouette(rgb, grey):
    """Which pixels are drawn: the range's silhouette. A pixel is solid
    unless it is near the strip's top-left colour (the sky) - or, with
    *grey*, grey, a cloud's colour. The range is the solid pixels joined to
    the strip's bottom row, so a cloud floating between the peaks drops
    out; and in each column everything from the range's top pixel down is
    drawn whatever its colour, so a near-black crease or a grey shadow
    inside the rock is kept rather than punched through to the sky."""
    h, sky = len(rgb), rgb[0][0]

    def solid(x, y):
        c = rgb[y][x]
        if dist(c, sky) <= SKY_NEAR:
            return False
        return not (grey and max(c) - min(c) < GREY_SPREAD)

    grounded = flood([(x, h - 1) for x in range(STRIP_W)], solid, h)
    drawn = [[False] * STRIP_W for _ in range(h)]
    for x in range(STRIP_W):
        top = next((y for y in range(h) if grounded[y][x]), h)
        for y in range(top, h):
            drawn[y][x] = True
    return drawn


def otsu(values):
    """The threshold that best splits *values* into two classes."""
    hist = np.bincount(np.clip(values.astype(int), 0, 255), minlength=256).astype(float)
    total, cum, cum_mean = hist.sum(), np.cumsum(hist), np.cumsum(hist * np.arange(256))
    best, t_best = -1.0, 128
    for t in range(1, 255):
        w0, w1 = cum[t], total - cum[t]
        if w0 == 0 or w1 == 0:
            continue
        m0, m1 = cum_mean[t] / w0, (cum_mean[-1] - cum_mean[t]) / w1
        between = w0 * w1 * (m0 - m1) ** 2
        if between > best:
            best, t_best = between, t
    return t_best


def cloud_shapes(band, render, cy, ch, threshold):
    """The clouds' silhouettes and the render's brightness, both at the
    band's size. The crop is blurred - wrapping left to right, so the seam
    stays clean - and box-averaged down, which melts the render's blocks;
    then thresholded, smoothed by majority (twice, a 3x3 vote), and cleared
    of specks and pinholes under SPECK pixels."""
    im = Image.open(render).convert('L')
    w = im.size[0]
    if w != 3 * STRIP_W:
        raise SystemExit(f"sky_art.py: clouds want a {3 * STRIP_W} px wide render, got {w}")
    crop = im.crop((0, cy, w, cy + ch))
    pad = 8 * BLUR
    wide = Image.new('L', (w + 2 * pad, ch))
    wide.paste(crop.crop((w - pad, 0, w, ch)), (0, 0))
    wide.paste(crop, (pad, 0))
    wide.paste(crop.crop((0, 0, pad, ch)), (w + pad, 0))
    from PIL import ImageFilter
    wide = wide.filter(ImageFilter.GaussianBlur(BLUR))
    small = wide.crop((pad, 0, pad + w, ch)).resize((STRIP_W, band.height), Image.BOX)
    lum = np.asarray(small, float)
    t = otsu(lum.ravel()) if threshold is None else threshold
    mask = lum > t
    for _ in range(2):
        n = sum(np.roll(np.roll(mask, dy, 0), dx, 1)
                for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        n[0, :] += mask[0, :]                   # rolled rows wrap: count the edge
        n[-1, :] += mask[-1, :]                 # rows as their own neighbours
        mask = n >= 5
    h = band.height
    for want in (True, False):                  # specks, then pinholes
        seen = np.zeros_like(mask)
        for y0 in range(h):
            for x0 in range(STRIP_W):
                if mask[y0, x0] != want or seen[y0, x0]:
                    continue
                part = flood([(x0, y0)], lambda x, y: mask[y, x] == want and not seen[y, x], h)
                px = [(x, y) for y in range(h) for x in range(STRIP_W) if part[y][x]]
                for x, y in px:
                    seen[y, x] = True
                edge = any(y in (0, h - 1) for _, y in px)
                if len(px) < SPECK and (want or not edge):
                    for x, y in px:
                        mask[y, x] = not want
    return mask, lum, t


def shade_clouds(mask, lum):
    """A ramp level 1-15 for every cloud pixel, 0 for sky. In each column a
    cloud's run is lit from above: its top pixel is the highlight, and the
    rest darkens toward the run's underside; a third of the level is the
    render's own brightness, so a long band is not one flat colour. Where a
    band splits or merges the runs jump from one column to the next, so the
    light is averaged along each row within the cloud (SMOOTH px either
    way, wrapping) before it is stepped into the ramp."""
    h, w = mask.shape
    lit = lum[mask]
    lo, hi = np.percentile(lit, 5), np.percentile(lit, 95)
    light = np.zeros((h, w))
    rim = np.zeros((h, w), bool)
    for x in range(w):
        y = 0
        while y < h:
            if not mask[y, x]:
                y += 1
                continue
            top = y
            while y < h and mask[y, x]:
                y += 1
            run = y - top
            for d in range(run):
                v = 1.0 - (d / (run - 1) if run > 1 else 0.3)
                r = min(1.0, max(0.0, (lum[top + d, x] - lo) / max(1.0, hi - lo)))
                light[top + d, x] = 0.65 * v + 0.35 * r
                rim[top + d, x] = d == 0 and run >= 3
    m = mask.astype(float)
    num = sum(np.roll(light * m, k, 1) for k in range(-SMOOTH, SMOOTH + 1))
    den = sum(np.roll(m, k, 1) for k in range(-SMOOTH, SMOOTH + 1))
    light = np.where(rim, 1.0, num / np.maximum(den, 1))   # the lit edge stays lit
    out = np.zeros((h, w), int)
    out[mask] = 1 + np.minimum(PER - 1, (light[mask] * PER).astype(int))
    return out


def cloud_ramp(haze):
    """The clouds' 15 colours, underside to lit edge, hazed and snapped to
    5 bits. Not through distinct(): its nudges would step a ramp sideways in
    hue, and a ramp this wide already moves every channel at least a 5-bit
    step a colour, so its own order keeps them apart - checked."""
    ramp = []
    for i in range(PER):
        f = i / (PER - 1)
        c = tuple(lo + (hi - lo) * f for lo, hi in zip(CLOUD_LOW, CLOUD_HIGH))
        if haze:
            c = tuple(v + (k - v) * haze for v, k in zip(c, backdrop()))
        ramp.append(snes(c))
    for a, b in zip(ramp, ramp[1:]):
        if not all(q >= p for p, q in zip(a, b)) or a == b:
            raise SystemExit(f"sky_art.py: the cloud ramp is not strictly lighter at {a} -> {b}; "
                             "widen CLOUD_LOW..CLOUD_HIGH or lower --haze")
    return ramp


def tiles(band, drawn):
    """The drawn pixels of each 8x8 tile, as (x, y) in the strip. Tiles fall
    on the layer's 8 px grid, not the strip's: a band's top need not be a
    multiple of 8."""
    out = []
    for ay in range(band.top & ~7, band.bottom + 1, 8):
        rows = [y for y in range(ay - band.top, ay - band.top + 8) if 0 <= y < band.height]
        for tx in range(0, STRIP_W, 8):
            px = [(x, y) for y in rows
                  for x in range(tx, tx + 8) if drawn[y][x]]
            if px:
                out.append(px)
    return out


def snes(c):
    """*c* at the PPU's precision: 5 bits a channel, expanded back to 8 by
    bit replication, so what is fitted is what will be shown."""
    v5 = np.clip(np.rint(np.asarray(c, float) * 31 / 255), 0, 31).astype(int)
    return tuple(int(v) for v in (v5 << 3) | (v5 >> 2))


def lloyd(cols, w, init, iters=30):
    """Lloyd's k-means: centres for the colours *cols* weighted *w*, from
    *init*. A centre nobody chose moves to the worst-fitted colour."""
    cents = np.array(init, float)
    for _ in range(iters):
        d = ((cols[:, None, :] - cents[None]) ** 2).sum(-1)
        near = d.argmin(1)
        new = cents.copy()
        for j in range(len(cents)):
            m = (near == j) & (w > 0)
            if w[m].sum():
                new[j] = (cols[m] * w[m, None]).sum(0) / w[m].sum()
            elif w.sum():
                new[j] = cols[int((w * d.min(1)).argmax())]
        if np.allclose(new, cents):
            break
        cents = new
    return cents


def distinct(pal, taken=()):
    """Snap every colour to SNES precision and keep it MIN_SEP from every
    other: one too close is pushed a 5-bit step at a time away from the
    nearest. The fit puts its colours where the pixels are, and a dense
    cluster draws several a single step apart - a slot spent on a difference
    no one can see."""
    out = list(taken)
    for c in pal:
        c = snes(c)
        for tries in range(64):
            if not out:
                break
            near = min(out, key=lambda o: dist(o, c))
            if dist(near, c) >= MIN_SEP * MIN_SEP:
                break
            d = np.array(c) - np.array(near)
            if not d.any():
                d = np.ones(3) * (1 if sum(c) < 384 else -1)
            if tries >= 32:                      # pinned at a wall: go round
                d = -d
            c = snes(np.clip(np.array(c) + 8 * np.sign(d), 0, 255))
        out.append(c)
    return out[len(taken):]


def derive_palettes(rgb, tile_px, npals):
    """*npals* palettes of at most PER colours, every colour different.

    Start from the npals x PER colours that best fit the strip as a whole
    (or the strip's own colours, if it has fewer), then alternate two
    steps: split the colours into palettes - each tile is drawn in
    whichever palette fits it best, and moving a colour to another palette,
    or swapping two, is kept while it lowers the total error - and
    re-centre each palette on the pixels of the tiles that chose it (a
    palette no tile chose is re-seeded from the worst-fitted tiles, so no
    slot goes unshown). A tile cannot borrow from a second palette, so the
    split is what decides which colours meet in a tile. The whole is run
    from RESTARTS fixed-seed starts and the best kept."""
    uniq = {}
    tile_hist = []
    for px in tile_px:
        h = {}
        for x, y in px:
            u = uniq.setdefault(rgb[y][x], len(uniq))
            h[u] = h.get(u, 0) + 1
        tile_hist.append(h)
    cols = np.array(list(uniq), float)
    H = np.zeros((len(tile_px), len(cols)))
    for t, h in enumerate(tile_hist):
        for u, n in h.items():
            H[t, u] = n
    weight = H.sum(0)
    k = min(npals * PER, len(cols))
    rnd = np.random.default_rng(0x4111)

    def column(pal, group):
        if not group:
            return np.full(len(tile_px), np.inf)
        D = ((cols[:, None, :] - np.array([pal[j] for j in group], float)[None]) ** 2).sum(-1)
        return H @ D.min(1)

    def search(pal, part):
        E = np.stack([column(pal, g) for g in part], 1)
        cur = E.min(1).sum()
        improved = True
        while improved:
            improved = False
            for p in range(npals):
                for i in range(len(part[p]) - 1, -1, -1):
                    for q in range(npals):
                        if q == p or i >= len(part[p]):
                            continue
                        # Move p's colour i to q, or swap it with each of q's.
                        trials = [None] if len(part[q]) < PER else []
                        trials += list(range(len(part[q])))
                        for j in trials:
                            a, b = list(part[p]), list(part[q])
                            if j is None:
                                b.append(a.pop(i))
                            else:
                                a[i], b[j] = b[j], a[i]
                            Ep, Eq = column(pal, a), column(pal, b)
                            old_p, old_q = E[:, p].copy(), E[:, q].copy()
                            E[:, p], E[:, q] = Ep, Eq
                            e = E.min(1).sum()
                            if e < cur - 1e-9:
                                cur, improved = e, True
                                part[p], part[q] = a, b
                                break
                            E[:, p], E[:, q] = old_p, old_q
        return cur, E

    best = None
    for _ in range(RESTARTS):
        start = cols[rnd.choice(len(cols), size=k, replace=False, p=weight / weight.sum())]
        pal = distinct(lloyd(cols, weight, start))
        order = list(rnd.permutation(k))
        part = [order[n::npals] for n in range(npals)]
        for _ in range(6):
            cur, E = search(pal, part)
            if best is None or cur < best[0]:
                best = (cur, [[pal[j] for j in g] for g in part])
            owner = E.argmin(1)
            worst = list(np.argsort(-E.min(1)))
            new = list(pal)
            for n in range(npals):
                if not part[n]:
                    continue
                w = H[owner == n].sum(0)
                if not w.sum():                   # unchosen: the worst tiles
                    w = H[worst[:8]].sum(0)
                    del worst[:8]
                init = [pal[j] for j in part[n]]
                for j, c in zip(part[n], lloyd(cols, w, init)):
                    new[j] = c
            pal = distinct(new)
    pals = best[1]
    # Dark to light within a palette, palettes by their darkest colour.
    return sorted([sorted(p, key=lambda c: sum(c)) for p in pals],
                  key=lambda p: sum(p[0]) if p else 999)


def fit(band, rgb, tile_px, pals):
    """Index each pixel 0 or 16(pal0+N)+1.., one palette N a tile."""
    out = [[0] * STRIP_W for _ in range(band.height)]
    used = [0] * len(pals)
    for px in tile_px:
        best = min((n for n in range(len(pals)) if pals[n]), key=lambda n: sum(
            min(dist(rgb[y][x], c) for c in pals[n]) for x, y in px))
        used[best] += 1
        pal = pals[best]
        for x, y in px:
            k = min(range(len(pal)), key=lambda i: dist(rgb[y][x], pal[i]))
            out[y][x] = 16 * (band.pal0 + best) + 1 + k
    return out, used


def source_const(path, pattern, what):
    m = re.search(pattern, open(path).read())
    if not m:
        raise SystemExit(f"sky_art.py: no {what} in {path}")
    return m.groups()


def backdrop():
    """The game's sky: main.r65's set_backdrop!, 5-bit, at PPU precision."""
    rgb5 = source_const('src/main.r65',
                        r'set_backdrop!\(Color::rgb!\((\d+),\s*(\d+),\s*(\d+)\)\)',
                        'set_backdrop!(Color::rgb!(r, g, b))')
    return tuple((v << 3) | (v >> 2) for v in map(int, rgb5))


def check_split():
    """Each band on its side of video.r65's SKY_SPLIT, or it scrolls at the
    other band's rate."""
    split = int(source_const('src/video.r65', r'const SKY_SPLIT:\s*u8\s*=\s*(\d+)',
                             'SKY_SPLIT')[0])
    c, m = BANDS['clouds'], BANDS['mountains']
    if not (c.bottom < split <= m.top):
        raise SystemExit(f"sky_art.py: clouds end at {c.bottom} and mountains start at "
                         f"{m.top}, but SKY_SPLIT is {split}")


def opt(args, name, kind, default=None):
    return kind(args[args.index(name) + 1]) if name in args else default


def paint(band, idx, pals):
    """Write the band's indices and palettes into the bitmap, clearing its
    old art wherever it was and leaving the other band alone."""
    im = Image.open(BMP).copy()
    assert im.mode == 'P' and im.size == (256, 512), (im.mode, im.size)
    pal = (im.getpalette() + [0] * 3 * ENTRIES)[:3 * ENTRIES]
    lo, hi = 16 * band.pal0, 16 * (band.pal0 + band.pals)
    pal[3 * lo:3 * hi] = [0] * 3 * (hi - lo)
    for n, sub in enumerate(pals):
        for k, c in enumerate(sub):
            i = 16 * (band.pal0 + n) + 1 + k
            pal[3 * i:3 * i + 3] = list(c)
    im.putpalette(pal)
    px = im.load()
    for y in range(512):
        for x in range(256):
            if lo <= px[x, y] < hi:
                px[x, y] = 0
    for y in range(band.height):
        for x in range(STRIP_W):
            half, sx = divmod(x, 256)               # folded: right screen below
            if idx[y][x]:
                px[sx, half * 256 + band.top + y] = idx[y][x]
    im.save(BMP)


def main():
    if sys.argv[1:] == ['--scm']:
        print(BAND_SCM)
        return
    if len(sys.argv) < 3 or sys.argv[1] not in BANDS:
        raise SystemExit("usage: sky_art.py clouds RENDER.png CY CH [--threshold T] [--haze N]"
                         "\n       sky_art.py mountains BAND.bmp [--key-grey] [--haze N]"
                         "\n       sky_art.py --scm")
    check_split()
    band = BANDS[sys.argv[1]]

    if band.name == 'clouds':
        cy, ch = int(sys.argv[3]), int(sys.argv[4])
        args = sys.argv[5:]
        mask, lum, t = cloud_shapes(band, sys.argv[2], cy, ch, opt(args, '--threshold', int))
        level = shade_clouds(mask, lum)
        ramp = cloud_ramp(opt(args, '--haze', float, 0.0))
        idx = [[16 * band.pal0 + v if v else 0 for v in row] for row in level.tolist()]
        paint(band, idx, [ramp])
        seam = sum(mask[:, -1] != mask[:, 0])
        used = len(set(level[mask].tolist()))
        print(f"{BMP}: clouds rows {band.top}-{band.bottom}, threshold {t}, "
              f"{int(mask.sum())} px, {used} of {PER} ramp colours used, "
              f"{seam} rows differ across the wrap")
        return

    args = sys.argv[3:]
    src = Image.open(sys.argv[2]).convert('RGB')
    if src.size != (STRIP_W, band.height):
        raise SystemExit(f"sky_art.py: mountains want a {STRIP_W}x{band.height} strip, "
                         f"got {src.size[0]}x{src.size[1]} - gimp's H is the band's height")
    rgb = [[src.getpixel((x, y)) for x in range(STRIP_W)] for y in range(band.height)]
    drawn = key_silhouette(rgb, '--key-grey' in args)
    gaps = sum(not drawn[band.height - 1][x] for x in range(STRIP_W))
    if gaps:
        raise SystemExit(f"sky_art.py: {gaps} px of the strip's bottom row are sky - "
                         "crop the render shorter, or the dirt will show a gap")
    haze = opt(args, '--haze', float, 0.0)
    if haze:
        sky = backdrop()
        rgb = [[tuple(round(c + (k - c) * haze) for c, k in zip(px, sky)) for px in row]
               for row in rgb]
    tile_px = tiles(band, drawn)
    pals = derive_palettes(rgb, tile_px, band.pals)
    idx, used = fit(band, rgb, tile_px, pals)
    paint(band, idx, pals)
    # The wrap should be no harder an edge than the drawing's own: ranked
    # against every other column step (an average misleads - pixel art is
    # blocks, so most neighbouring columns are identical).
    def step(a, b):
        return sum(dist(rgb[y][a], rgb[y][b]) for y in range(band.height))
    seam = step(STRIP_W - 1, 0)
    softer = sum(step(x, x + 1) < seam for x in range(STRIP_W - 1))
    distinct_n = len({c for p in pals for c in p})
    print(f"{BMP}: mountains rows {band.top}-{band.bottom}, tiles per palette {used}, "
          f"{distinct_n} distinct colours in {band.pals * PER} slots, "
          f"wrap sharper than {softer} of {STRIP_W - 1} column edges")


if __name__ == '__main__':
    main()

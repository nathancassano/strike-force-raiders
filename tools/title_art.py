#!/usr/bin/env python3
"""
Paint the title page, assets/src/title.tilemap.bmp, from a ComfyUI render.

One-off authoring helper, not part of the build, like sky_art.py. The title
is Mode 3: BG1 is this picture at 8bpp, 256 colours, and BG2 carries the
menu in the console font at 4bpp (screen.r65). So the tool scales the
render to the 256x224 screen, letters the logo over its sky, darkens a
panel under the menu rows so the text reads over the sand, and fits the
lot to one 256-entry palette, snapped to the SNES's 5-bit channels.

Two entries are not the picture's. BG2's tiles draw from CGRAM 0-127 like
BG1's, so the font's two colours - sub-palette 2's 2 and 3, the glyphs'
edge and body (screen.r65 screen_font) - are entries 34 and 35 here,
fixed; the picture may use them as well.

    python3 tools/title_art.py RENDER.png [--sample box] [--dither] && make

The current title is ComfyUI render rotor_title_new_00004_ (the saved
pixel_art_sdxl workflow: pixelArtDiffusionXL_pixelWorld, base and refiner,
25 steps handing over at 20, cfg 8, euler/normal; 1024x896 - the screen's
8:7 - seed 2026, the fourth of a batch of four), `--sample box --dither`.
Prompt: "pixel art,
16-bit snes video game title screen illustration, a military attack
helicopter gunship in side view flying left to right in the middle of the
picture, dark olive green, rotor blades, stub wings with rocket pods, nose
gun, dramatic orange sunset sky with clouds, desert mesas and mountains
silhouetted on the horizon, dark sand dunes in the foreground at the
bottom, clear empty sky at the top, bold colours, crisp pixels, retro
arcade style"; negative: "text, letters, logo, watermark, signature,
blurry, photo, 3d render, people, multiple helicopters, cropped helicopter,
frame, border".

It reports the picture's unique tiles (flips matched, as bmp2chr -t
does): BG1's tiles are $0000-$6FFF of VRAM, 896 of them, which is every
tile of the screen, so any picture fits.
"""

import argparse
import os

from PIL import Image, ImageDraw, ImageFont

BMP = 'assets/src/title.tilemap.bmp'
W, H = 256, 224

# The logo: one line across the sky, in a heavy condensed italic, filled
# with a sunset ramp, outlined and dropped onto a shadow.
LOGO = 'STRIKE FORCE RAIDERS'
LOGO_FONT = '/usr/share/fonts/truetype/noto/NotoSans-CondensedBlackItalic.ttf'
LOGO_TOP = 6
LOGO_H = 26                      # cap height, px
LOGO_RAMP = [(255, 248, 168), (255, 214, 64), (248, 140, 24), (208, 56, 16)]
LOGO_EDGE = (40, 8, 24)
LOGO_SHADOW = (24, 8, 32)

# The menu's panel: screen.r65's title rows, from SCREEN_CODE_ROW to the
# prompt, a tile row either side, columns 6-25. Darkened, not filled, so the
# sand still shows through it.
PANEL = (6 * 8, 18 * 8 + 4, 26 * 8, 26 * 8 + 4)   # x0, y0, x1, y1
PANEL_DIM = 0.42
PANEL_FEATHER = 6

# The font's colours (screen.r65 screen_font), as the PPU shows them.
FONT_ENTRIES = {34: (18, 20, 24), 35: (31, 31, 31)}


def snes(v):
    """A 5-bit channel as the PPU expands it."""
    return (v << 3) | (v >> 2)


def snap(rgb):
    return tuple(snes(c >> 3) for c in rgb)


def logo(size):
    """The logo, RGBA, cropped to its ink."""
    font = ImageFont.truetype(LOGO_FONT, 200)
    big = Image.new('L', (2400, 300))
    ImageDraw.Draw(big).text((20, 20), LOGO, font=font, fill=255)
    big = big.crop(big.getbbox())
    w = round(big.width * LOGO_H / big.height)
    w = min(w, size[0] - 12)
    mask = big.resize((w, LOGO_H), Image.LANCZOS).point(lambda a: 255 if a >= 112 else 0)
    out = Image.new('RGBA', (w + 4, LOGO_H + 4), (0, 0, 0, 0))
    px = out.load()
    m = mask.load()
    ink = {(x, y) for y in range(LOGO_H) for x in range(w) if m[x, y]}
    # A two-pixel drop shadow, down and right, then a one-pixel edge.
    for x, y in ink:
        for dx, dy in ((2, 2), (3, 2), (2, 3), (3, 3)):
            px[x + dx, y + dy] = LOGO_SHADOW + (255,)
    for x, y in ink:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if 0 <= x + 1 + dx < out.width and 0 <= y + 1 + dy < out.height:
                    px[x + 1 + dx, y + 1 + dy] = LOGO_EDGE + (255,)
    for x, y in ink:
        t = y / (LOGO_H - 1) * (len(LOGO_RAMP) - 1)
        k = min(int(t), len(LOGO_RAMP) - 2)
        f = t - k
        c = tuple(round(a + (b - a) * f) for a, b in zip(LOGO_RAMP[k], LOGO_RAMP[k + 1]))
        px[x + 1, y + 1] = c + (255,)
    return out


def tiles(im):
    """Unique 8x8 tiles, a flip of one counting as the same."""
    px = im.load()
    seen = set()
    for ty in range(0, H, 8):
        for tx in range(0, W, 8):
            t = tuple(tuple(px[tx + x, ty + y] for x in range(8)) for y in range(8))
            flips = (t, tuple(r[::-1] for r in t), t[::-1], tuple(r[::-1] for r in t[::-1]))
            if not any(f in seen for f in flips):
                seen.add(t)
    return len(seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('render')
    ap.add_argument('--sample', choices=('box', 'lanczos', 'nearest'), default='box')
    ap.add_argument('--dither', action='store_true', help='Floyd-Steinberg into the palette')
    ap.add_argument('--out', default=BMP)
    args = ap.parse_args()

    src = Image.open(args.render).convert('RGB')
    # Centre-cropped to the screen's 8:7 if it is not already.
    if src.width * 7 != src.height * 8:
        w = min(src.width, src.height * 8 // 7)
        h = w * 7 // 8
        src = src.crop(((src.width - w) // 2, (src.height - h) // 2,
                        (src.width + w) // 2, (src.height + h) // 2))
    flt = {'box': Image.BOX, 'lanczos': Image.LANCZOS, 'nearest': Image.NEAREST}[args.sample]
    im = src.resize((W, H), flt)

    # The menu's panel, darkened, its edge feathered over PANEL_FEATHER px.
    px = im.load()
    x0, y0, x1, y1 = PANEL
    for y in range(y0 - PANEL_FEATHER, y1 + PANEL_FEATHER):
        for x in range(max(0, x0 - PANEL_FEATHER), min(W, x1 + PANEL_FEATHER)):
            d = max(x0 - x, x - (x1 - 1), y0 - y, y - (y1 - 1), 0)
            k = PANEL_DIM + (1 - PANEL_DIM) * d / PANEL_FEATHER
            px[x, y] = tuple(round(c * k) for c in px[x, y])

    mark = logo((W, H))
    im.paste(mark, ((W - mark.width) // 2, LOGO_TOP), mark)

    # 254 colours of the picture's own, then the font's two fixed in their
    # entries - everything snapped to what CGRAM can hold.
    im = Image.eval(im, lambda v: snes(v >> 3))
    q = im.quantize(colors=256 - len(FONT_ENTRIES), method=Image.Quantize.MEDIANCUT,
                    dither=Image.Dither.NONE)
    own = [snap(tuple(q.getpalette()[i * 3:i * 3 + 3])) for i in range(256 - len(FONT_ENTRIES))]
    pal, k = [], 0
    for i in range(256):
        if i in FONT_ENTRIES:
            pal.append(tuple(snes(c) for c in FONT_ENTRIES[i]))
        else:
            pal.append(own[k])
            k += 1
    ref = Image.new('P', (1, 1))
    ref.putpalette([c for rgb in pal for c in rgb])
    out = im.quantize(palette=ref,
                      dither=Image.Dither.FLOYDSTEINBERG if args.dither else Image.Dither.NONE)
    out.putpalette([c for rgb in pal for c in rgb])
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    out.save(args.out)
    print(f'{args.out}: {W}x{H}, 256 colours, {tiles(out)} unique tiles of {W * H // 64}')


if __name__ == '__main__':
    main()

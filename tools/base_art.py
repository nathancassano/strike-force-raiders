#!/usr/bin/env python3
"""
Stamp the home base into assets/src/obj.bmp from a ComfyUI render.

One-off authoring helper, not part of the build, like sky_art.py: it takes a
render's pixels (pixelArtDiffusionXL_spriteShaper, a side view of the base
on a flat light background), keys the background out, crops to the
building, box-filters it down into the base's 64x64 and maps every pixel
to the nearest colour of obj.bmp's palette. The sheet has no free 64x64
block, so the base is four strips of four 16x16 cells, each 8 tiles wide
and 2 tall (STRIPS, struct.r65's tiles): its lower half where the 64x32
base was (cols 6-13 of rows 10-13, STRUCT_TILE_BASE), its upper half in
two strips struct_art.py clears, the airframe's old cells - rows 0-1 and
14-15, cols 4-11 (BASE_TILE_TOP, BASE_TILE_MID).

The palette is the sheet's, shared with every unit and building, so the
render is fitted to it rather than the other way round - with two
exceptions: struct_palettes recolours entries 2, 3, 7 and 8 (the greens)
per owner, so green in the render lands on them and the base wears its
side's colour; and --extra adds the render's most-used colours the palette
cannot match into the free entries 12-15.

The missile launcher is drawn over the base at BASE_LAUNCHER_DX/_DY
(struct.r65) - on the hangar roof between the towers, centred over the
base's middle where the missile leaves from; the tool reports where the
art's tallest column is, should a new render want it moved.

    python3 tools/base_art.py RENDER.png [--key 40] [--extra 2] [--sample nearest] [--fill] && make

The base is drawn by tools/base_draw.py now, which imports this file's
strips; running this again replaces that drawing. The render it last
stamped was ComfyUI_00344_ (pixelArtDiffusionXL_
spriteShaper, 1024x512, 30 steps, cfg 7, seed 777, the second of a batch of
four), stamped `--extra 2 --sample nearest --fill`: the building is about twice
as wide as it is tall, so --fill stretches it to the 64x64 box (twice as
tall as the render draws it, the towers reaching the box's top) rather
than leaving the top half empty; point sampling keeps the render's own
pixels where box filtering smears them. Prompt: "pixel art game sprite, side view, a wide
low military airfield hangar building with a tall narrow control tower at
the right end, glass windows at the top of the tower, red and white striped
antenna mast, small flag, light grey concrete walls with green stripe and
green roof, simple shapes, large pixels, limited palette, retro 16-bit
arcade style, flat solid white background, isolated, whole building in
frame"; negative: "perspective, isometric, 3d render, photo, people,
vehicles, helicopter, aircraft, sky, clouds, ground, grass, text,
watermark, blurry, cropped, cluttered, tiny details". The extras it took
are entries 12 (a cream, the walls) and 13 (a slate).
"""

import argparse
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bmp4 import save_bmp4

BMP = 'assets/src/obj.bmp'
W, H = 64, 64                           # the base, in pixels
# Where each 16-row strip of the base goes on the sheet, top to bottom:
# (x, y) of its top-left pixel - tiles 4, 228, 166 and 198.
STRIPS = ((32, 0), (32, 112), (48, 80), (48, 96))
FREE = range(12, 16)                    # palette entries no art uses yet


def keyed(render, key):
    """The render with its background made clear: flood-filled from each
    corner, so a building's own light panels are kept; *key* is how far a
    pixel may differ from the corner's colour and still be background."""
    im = render.convert('RGBA')
    for xy in ((0, 0), (im.width - 1, 0), (0, im.height - 1), (im.width - 1, im.height - 1)):
        if im.getpixel(xy)[3]:
            ImageDraw.floodfill(im, xy, (0, 0, 0, 0), thresh=key)
    return im


def fitted(im, sample, fill):
    """Cropped to what is drawn and scaled into W x H, on the foot: by
    *sample*, 'box' averaging or 'nearest' point sampling - which keeps a
    render's own pixels when they come out about one to one. With *fill*
    each axis is scaled on its own to fill the box."""
    im = im.crop(im.getchannel('A').point(lambda a: 255 if a > 0 else 0).getbbox())
    if fill:
        w, h = W, H
    else:
        scale = min(W / im.width, H / im.height)
        w, h = max(1, round(im.width * scale)), max(1, round(im.height * scale))
    small = im.resize((w, h), Image.BOX if sample == 'box' else Image.NEAREST)
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    out.paste(small, ((W - w) // 2, H - h))
    return out


def nearest(rgb, pal, choices):
    r, g, b = rgb
    return min(choices, key=lambda i: (pal[i][0] - r) ** 2 * 3 + (pal[i][1] - g) ** 2 * 4 + (pal[i][2] - b) ** 2 * 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('render')
    ap.add_argument('--key', type=int, default=40, help='background: this far from the corner colour')
    ap.add_argument('--extra', type=int, default=0, help='colours to add in the free entries 12-15')
    ap.add_argument('--sample', choices=('box', 'nearest'), default='box')
    ap.add_argument('--fill', action='store_true', help='stretch to fill the box, not keep the aspect')
    args = ap.parse_args()

    sheet = Image.open(BMP)
    flat = sheet.getpalette()[:48]
    pal = [tuple(flat[i * 3:i * 3 + 3]) for i in range(16)]
    small = fitted(keyed(Image.open(args.render), args.key), args.sample, args.fill)
    px = small.load()
    used = [i for i in range(1, 12)]

    # The colours the sheet's palette matches worst become the extras.
    if args.extra:
        misses = {}
        for y in range(H):
            for x in range(W):
                r, g, b, a = px[x, y]
                if a < 128:
                    continue
                i = nearest((r, g, b), pal, used)
                d = (pal[i][0] - r) ** 2 + (pal[i][1] - g) ** 2 + (pal[i][2] - b) ** 2
                if d > 900:
                    q = (r // 16 * 16 + 8, g // 16 * 16 + 8, b // 16 * 16 + 8)
                    misses[q] = misses.get(q, 0) + 1
        # An extra the palette already holds keeps its entry: other art on
        # the sheet may use it (the base's colours are not only the base's).
        extras = sorted(misses.items(), key=lambda kv: -kv[1])[:args.extra]
        held = {pal[slot]: slot for slot in FREE}
        open_slots = [slot for slot in FREE if pal[slot] not in [rgb for rgb, _ in extras]]
        for rgb, n in extras:
            slot = held[rgb] if rgb in held else open_slots.pop(0)
            pal[slot] = rgb
            used.append(slot)
            print(f'entry {slot} = {rgb} ({n} px)')

    out = sheet.copy()
    opx = out.load()
    art = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            art[y][x] = nearest((r, g, b), pal, used) if a >= 128 else 0
            sx, sy = STRIPS[y >> 4]
            opx[sx + x, sy + (y & 15)] = art[y][x]
    out.putpalette([c for rgb in pal for c in rgb])
    save_bmp4(out, BMP)

    heights = [next((y for y in range(H) if art[y][x]), H) for x in range(W)]
    top = min(heights)
    cols = [x for x in range(W) if heights[x] == top]
    print(f'{BMP}: base stamped; tallest at x {cols[0]}..{cols[-1]} (top row {top})')
    print('drawn from row, by column: ' + ' '.join(f'{x}:{heights[x]}' for x in range(W)))


if __name__ == '__main__':
    main()

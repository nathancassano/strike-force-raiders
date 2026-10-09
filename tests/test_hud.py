"""The HUD rows, the radar and the order overlay (design.md).

The strip's rows are composed from the glyph rows, so their tile IDs are
whatever bmp2chr decided; the radar is the game's own bitmap and can be
checked byte for byte. At boot, once it has drawn (every 16th frame): tile 0
carries the airframe's 2x2 (blue) at radar x 2-3 on rows 1-2 ($30 of each
plane byte) and the bank's tick at x 3 on rows 3-5; row 0 is plain navy, and
so is row 7, the vehicles' line, with none out. The camera window is a
sprite over the row, in the slot after the airframe's two: at boot x 0, y 8
(the row's first scanline), the bracket tile.
"""

import pytest

from harness import boot, expect, screen_colour, shot

case = pytest.param


def rb(i):
    return f"s.raw('radar_buf').u8[{i}]"


def oam(i):
    return f"s.raw('oam').u8[{i}]"


@pytest.mark.parametrize("script, checks", [
    case(lambda s: boot(s, "harness").wait(16), {
        rb(0): 0xFF, rb(1): 0x00, rb(2): 0xCF, rb(3): 0x30, rb(4): 0xCF, rb(5): 0x30,
        rb(6): 0xEF, rb(7): 0x10, rb(10): 0xEF, rb(11): 0x10, rb(14): 0xFF, rb(15): 0x00,
        oam(8): 0x00, oam(9): 0x08, oam(10): 0x1F,
    }, id="radar_boot"),
    # Flown east 240 frames: the airframe's block has left tile 0, so the
    # bank's tick stands alone, and the bracket sprite is at camera_x/32.
    case(lambda s: boot(s, "harness").wait(20).right(240).wait(20), {
        rb(2): 0xFF, rb(3): 0x00, rb(6): 0xEF, rb(7): 0x10, oam(8): 0x25,
    }, id="radar_flown"),
])
def test_radar(snes, script, checks):
    script(snes)
    shot(snes)
    expect(snes, checks)


def test_strip_drawn(snes, tmp_path):
    # The strip itself: the two white gauges are what put this much white
    # across the screen.
    boot(snes, "harness").wait(16)
    shot(snes)
    assert screen_colour(snes, tmp_path, (28, 30, 31), snes_colour=True) >= 0.9


# The order overlay: shown while L is held. Right with L down moves the
# highlight from the tank to the infantry and leaves the airframe where it
# was; letting go of L hides the box and keeps the selection. The first
# snapshot is taken with L still down (Select combined with L).
@pytest.mark.parametrize("script, holding, shown", [
    case(lambda s: boot(s, "harness").wait(30).l(20).press("l", "right", frames=3), ("l",), 0x01,
         id="overlay_show"),
    case(lambda s: boot(s, "harness").wait(30).l(20).press("l", "right", frames=3).l(10).wait(5), (), 0x00,
         id="overlay_hide"),
])
def test_overlay(snes, script, holding, shown):
    script(snes)
    shot(snes, *holding)
    expect(snes, {"v.hud_ov_shown": shown, "v.order_sel": 0x03, "v.heli_x_px": 0x0040})

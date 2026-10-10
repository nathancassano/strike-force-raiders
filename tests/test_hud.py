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

from harness import boot, read_snapshot, screen_colour


def radar_row(v, row):
    """Radar tile 0's two plane bytes for one pixel row."""
    return v.radar_buf.u8[2 * row], v.radar_buf.u8[2 * row + 1]


def test_the_radar_at_boot(snes):
    boot(snes, "harness").wait(16)
    v = read_snapshot(snes)
    assert radar_row(v, 0) == (0xFF, 0x00), "row 0 is plain navy"
    assert radar_row(v, 1) == (0xCF, 0x30), "the airframe's 2x2 at x 2-3, top row"
    assert radar_row(v, 2) == (0xCF, 0x30), "the airframe's 2x2 at x 2-3, bottom row"
    assert radar_row(v, 3) == (0xEF, 0x10), "the bank's tick at x 3, top"
    assert radar_row(v, 5) == (0xEF, 0x10), "the bank's tick at x 3, bottom"
    assert radar_row(v, 7) == (0xFF, 0x00), "the vehicles' line is empty"
    assert v.oam.u8[8] == 0, "the camera bracket is at x 0"
    assert v.oam.u8[9] == 8, "the camera bracket is on the row's first scanline"
    assert v.oam.u8[10] == 0x1F, "the camera bracket's tile"


def test_the_radar_after_flying_east(snes):
    """Flown east 240 frames: the airframe's block has left tile 0, so the
    bank's tick stands alone, and the bracket sprite is at camera_x/32.
    """
    boot(snes, "harness").wait(20).right(240).wait(20)
    v = read_snapshot(snes)
    assert radar_row(v, 1) == (0xFF, 0x00), "the airframe has left tile 0"
    assert radar_row(v, 3) == (0xEF, 0x10), "the bank's tick stands alone"
    assert v.oam.u8[8] == 37, "the camera bracket is at camera_x/32"


def test_strip_drawn(snes, tmp_path):
    """The two white gauges are what put this much white across the screen."""
    boot(snes, "harness").wait(16)
    read_snapshot(snes)
    assert screen_colour(snes, tmp_path, (28, 30, 31), snes_colour=True) >= 0.9, "the white gauges are drawn"


# The order overlay: shown while L is held. Right with L down moves the
# highlight from the tank to the infantry and leaves the airframe where it
# was; letting go of L hides the box and keeps the selection.

def test_the_overlay_shows_while_l_is_held(snes):
    """The snapshot is taken with L still down (Select combined with L)."""
    boot(snes, "harness").wait(30).l(20).press("l", "right", frames=3)
    v = read_snapshot(snes, "l")
    assert v.hud_ov_shown == 1
    assert v.order_sel == 3
    assert v.heli_x_px == 64


def test_letting_go_of_l_hides_the_overlay(snes):
    boot(snes, "harness").wait(30).l(20).press("l", "right", frames=3).l(10).wait(5)
    v = read_snapshot(snes)
    assert v.hud_ov_shown == 0
    assert v.order_sel == 3
    assert v.heli_x_px == 64

"""The HUD rows, the radar and the order menu (design.md).

The strip's rows are composed from the glyph rows, so their tile IDs are
whatever bmp2chr decided; the radar is the game's own bitmap and can be
checked byte for byte. At boot, once it has drawn (every 16th frame): tile 0
carries the airframe's 2x2 (blue) at radar x 2-3 on rows 1-2 ($30 of each
plane byte) and the bank's tick at x 3 on rows 3-5; row 0 is plain navy, and
so is row 7, the vehicles' line, with none out. The camera window is a
sprite over the row, in the slot after the airframe's two: at boot x 0, y 8
(the row's first scanline), the bracket tile.
"""

from shared import boot, read_snapshot, screen_colour

FREE, VAN = 0, 2


def radar_row(v, row):
    """Radar tile 0's two plane bytes for one pixel row."""
    return v.radar_buf.u8[2 * row], v.radar_buf.u8[2 * row + 1]


def test_the_radar_at_boot(snes):
    boot(snes, "MISSION_TEST_QUIET").wait(16)
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
    boot(snes, "MISSION_TEST_QUIET").wait(20).right(240).wait(20)
    v = read_snapshot(snes)
    assert radar_row(v, 1) == (0xFF, 0x00), "the airframe has left tile 0"
    assert radar_row(v, 3) == (0xEF, 0x10), "the bank's tick stands alone"
    assert v.oam.u8[8] == 37, "the camera bracket is at camera_x/32"


# The status rows (rows 0 and 27) are drawn from status.tilemap.bmp in BG3
# sub-palettes 5-7 (tools/status_art.py): each of a meter's six cells takes
# its own, so the fill runs red (6), orange-yellow (5), white (7).
METER_PALETTES = [6, 6, 6, 5, 5, 7]


def test_the_meters_are_drawn(snes, tmp_path):
    """Two full meters' red cells - a solid one and the red of a dithered
    one, 48 px each - are the only red of that shade on screen."""
    boot(snes, "MISSION_TEST_QUIET").wait(16)
    read_snapshot(snes)
    assert screen_colour(snes, tmp_path, (26, 4, 2), snes_colour=True) >= 0.15, "the meters' red is drawn"


def test_each_meter_cell_has_its_own_palette(snes):
    """The health meter's cells, full, in the bottom row's shadow: one
    sub-palette a cell, red to white; the label is gold, the digits white."""
    boot(snes, "MISSION_TEST_QUIET").wait(16)
    row = read_snapshot(snes).hud_row.u16
    assert [palette(row[32 + 2 + c]) for c in range(6)] == METER_PALETTES
    assert palette(row[32]) == 5, "H is gold"
    assert palette(row[1]) == 7, "the purse's digits are white"


# The order menu: shown while L is held. Down with L down moves the
# highlight from the tank to the infantry and leaves the airframe where it
# was; letting go of L hides the menu and keeps the selection.

def test_the_overlay_shows_while_l_is_held(snes):
    """The snapshot is taken with L still down (Select combined with L)."""
    boot(snes, "MISSION_TEST_QUIET").wait(30).l(20).press("l", "down", frames=3)
    v = read_snapshot(snes, "l")
    assert v.hud_ov_shown == 1
    assert v.order_sel == 3
    assert v.airframes__x_px.u16[0] == 64


# What the menu puts on screen, read out of VRAM: BG3's map at word $7800.
# Icon k is map rows 2+4k..5+4k, columns 1-4, BG3 tiles from 160 (past the
# front end's font) on sub-palette 3, or 4 for the selected one, whose name
# and cost are on its top row from column 6.
MENU_ROW, ICON_TILE0, TANK, INFANTRY, HELI = 2, 160, 2, 3, 5


def bg3_map(snes):
    """BG3's 32x32 map, as words, straight out of VRAM."""
    vram = snes.dump("vram")
    base = 0x7800 * 2
    return [vram[base + 2 * i] | (vram[base + 2 * i + 1] << 8) for i in range(32 * 32)]


def icon_cells(m, k):
    """Icon k's sixteen map words."""
    return [m[(MENU_ROW + 4 * k + r) * 32 + 1 + c] for r in range(4) for c in range(4)]


def palette(word):
    return (word >> 10) & 7


def test_the_menu_shows_six_icons_the_tank_lit(snes):
    boot(snes, "MISSION_TEST_QUIET").wait(30).l(20)
    read_snapshot(snes, "l")
    m = bg3_map(snes)
    for k in range(6):
        cells = icon_cells(m, k)
        assert all((w & 0x3FF) >= ICON_TILE0 for w in cells), f"icon {k} is the icons' tiles"
        assert {palette(w) for w in cells} == ({4} if k == TANK else {3}), f"icon {k}'s palette"
    letters = snes.raw("HUD_MAP_data").u16
    assert m[(MENU_ROW + 4 * TANK) * 32 + 6:(MENU_ROW + 4 * TANK) * 32 + 10] == \
        [letters[29 * 32 + ord(c) - ord("A")] for c in "TANK"]


def test_down_lights_the_next_icon(snes):
    boot(snes, "MISSION_TEST_QUIET").wait(30).l(20).press("l", "down", frames=3).l(3)
    read_snapshot(snes, "l")
    m = bg3_map(snes)
    assert {palette(w) for w in icon_cells(m, TANK)} == {3}
    assert {palette(w) for w in icon_cells(m, INFANTRY)} == {4}
    clear = snes.raw("HUD_MAP_data").u16[10 * 32]
    assert m[(MENU_ROW + 4 * TANK) * 32 + 6] == clear, "the tank's label is gone"


def test_the_menu_goes_with_l(snes):
    """The rows go back to the art's transparent tile, which is what the map
    has under them."""
    boot(snes, "MISSION_TEST_QUIET").wait(30).l(20).wait(5)
    read_snapshot(snes)
    m = bg3_map(snes)
    clear = snes.raw("HUD_MAP_data").u16[10 * 32]
    assert all(m[(MENU_ROW + r) * 32 + c] == clear for r in range(24) for c in range(19))


def test_an_alert_beside_the_menu_leaves_the_bottom_icon(snes):
    """The opponent's first convoy alert types into rows 23-26 from column
    10 while the menu is up: the heli icon on rows 22-25 stays whole."""
    boot(snes, "MISSION_TEST_QUIET").l(100)
    v = read_snapshot(snes, "l")
    assert v.alert_state != 0
    m = bg3_map(snes)
    assert all((w & 0x3FF) >= ICON_TILE0 for w in icon_cells(m, HELI))
    box_tl = snes.raw("HUD_MAP_data").u16[30 * 32]
    assert m[23 * 32 + 10] == box_tl, "and the alert's box is up beside it"


def tank_icon_palettes(snes, frames, labels=None):
    """The tank icon's sub-palette in the menu's shadow, frame by frame, with
    L held - the purchase pressed on the first. *labels*, if a list, gets the
    first word of the tank's label each frame."""
    seen = []
    for f in range(frames):
        snes.hold("l", "a", frames=1) if f == 0 else snes.hold("l", frames=1)
        shadow = snes.raw("hud_ov").u16
        seen.append(palette(shadow[(4 * TANK) * 32 + 1]))
        if labels is not None:
            labels.append(shadow[(4 * TANK) * 32 + 6])
    return seen


def runs(seq):
    out = []
    for p in seq:
        if out and out[-1][0] == p:
            out[-1][1] += 1
        else:
            out.append([p, 1])
    return out


def test_a_purchase_flashes_its_icon(snes):
    """A tank bought: its icon goes unselected and lit by turns, two frames
    each, for 16 frames - unselected first - and stays lit. The label beside
    it does not flash. The frame of the press may still read it lit or
    already unselected, by whether that frame's tick ends before the
    emulator's frame does - which moves with the tick's cost, so either is
    taken."""
    boot(snes, "MISSION_TEST_QUIET").wait(30).l(10)
    labels = []
    seen = runs(tank_icon_palettes(snes, 28, labels))
    if seen[0] == [4, 1]:
        seen = seen[1:]                    # the press frame, still lit
    assert [p for p, n in seen] == [3, 4] * 4
    assert [n for p, n in seen[:-1]] == [2] * 7
    assert seen[-1][1] >= 2 + 8
    tee = snes.raw("HUD_MAP_data").u16[29 * 32 + ord("T") - ord("A")]
    assert set(labels) == {tee}


def test_a_refused_purchase_does_not_flash(snes):
    boot(snes, "MISSION_TEST_QUIET").wait(30).l(10)
    snes.write("funds", 0, 1)
    assert set(tank_icon_palettes(snes, 20)) == {4}


def test_letting_go_of_l_hides_the_overlay(snes):
    boot(snes, "MISSION_TEST_QUIET").wait(30).l(20).press("l", "down", frames=3).l(10).wait(5)
    v = read_snapshot(snes)
    assert v.hud_ov_shown == 0
    assert v.order_sel == 3
    assert v.airframes__x_px.u16[0] == 64


def test_a_bombed_van_stops_jamming_the_radar(snes):
    """A bomb dropped straight onto a van goes off on the ground under it and
    kills it, and the next redraw moves the jam to the van behind.

    The hunter's column has its first van (slot 8) at x 3474 by frame 9174,
    jamming from radar tile 13, and the next at 6788. The airframe is planted
    20 px ahead of the van at hover height - flying there would meet the
    column's missile truck - and drops one bomb.
    """
    boot(snes, "MISSION_TEST_HUNTER").wait(9000)
    v = read_snapshot(snes)
    assert v.units__kind__tag.u8[8] == VAN
    # radar_jam is rebuilt across a redraw's first frames; radar_blank is
    # where it is final.
    snes.until("radar_blank")
    assert snes.u16("radar_jam") == 13
    snes.write("airframes__x_px", snes.raw("units__x_px").u16[8] - 20, 2)   # where it is now
    snes.write("airframes__vx", 0, 2)
    snes.a(3).wait(60)          # stopped mid-frame: a one-frame press can miss the pad read
    v = read_snapshot(snes)
    assert v.units__kind__tag.u8[8] == FREE
    snes.until("radar_blank")
    assert snes.u16("radar_jam") == 26

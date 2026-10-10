"""Phases 1-4: boot, the scrolling battlefield, the airframe and its weapons."""

from harness import boot, screen_colour, shot, tool


# ---- Phase 1 - harness ------------------------------------------------------

def test_boot(snes, tmp_path):
    """The ROM boots, enables NMI, runs its loop and reaches snapshot_point.

    The sky backdrop must still dominate the frame - this catches a failed
    palette DMA or a layer left enabled over the whole screen.
    """
    boot(snes)
    shot(snes)
    assert screen_colour(snes, tmp_path, (33, 49, 115)) >= 40, "the sky dominates the frame"


# ---- Phase 2 - scrolling battlefield ----------------------------------------
#
# The camera is a window follow: it holds still until the focus point leaves
# a CAM_DEAD (8px) window around screen centre, then closes at up to CAM_STEP
# px/frame, settling at a lag of +8 moving right, -8 moving left. The focus is
# the helicopter's centre led by vx/8: after 240 frames right the airframe is
# at 1221 doing 312/64 px/frame, so the focus is 1221 + 16 + 39 = 1276 and
# the camera settles at 1276 - 128 - 8 = 1140.

def test_camera_holds_still_at_rest(snes):
    boot(snes, "direct")
    v = shot(snes)
    assert v.camera_x == 0


def test_camera_follows_30_frames_right(snes):
    boot(snes, "direct").wait(20).right(30)
    v = shot(snes)
    assert v.camera_x == 90


def test_camera_follows_120_frames_right(snes):
    boot(snes, "direct").wait(20).right(120)
    v = shot(snes)
    assert v.camera_x == 540


def test_camera_settles_8_px_behind_after_240_frames_right(snes):
    boot(snes, "direct").wait(20).right(240)
    v = shot(snes)
    assert v.camera_x == 1140


def test_camera_follows_back_left(snes):
    boot(snes, "direct").wait(20).right(240).left(90)
    v = shot(snes)
    assert v.camera_x == 813


def test_parallax(rom, tmp_path):
    """Four layers at four rates, and eight equal HDMA ground bands.

    The tool can measure six bands: the first is the plain ground line under
    the units' feet, and the airframe's HUD strip on the last tile row cuts
    the seventh and covers the eighth. A short move: the near band runs at
    1.875x and the tool correlates each row wrapped at the screen width.
    """
    with rom.session() as s:
        boot(s, "direct")
        shot(s)
        at_rest = s.screenshot(tmp_path / "parallax-rest.png")
    with rom.session() as s:
        boot(s, "direct").wait(20).right(40)
        shot(s)
        moved = s.screenshot(tmp_path / "parallax-moved.png")
    # Rows 216-223 are the airframe's HUD strip; below is past the screen.
    tool("parallax.py", at_rest, moved, "--assert-bands", 6, "--ignore-rows", "216-238")


# ---- Phase 3 - helicopter ---------------------------------------------------
#
# x is 16.8 (x_px + x_sub); y a u16 of 8.8 screen pixels; velocity Q10. The
# d-pad picks a target velocity and the airframe accelerates toward it, so
# the first ~20 frames of any direction are a ramp.

def test_airframe_spawns_at_rest(snes):
    """heli_init's spawn, untouched by a frame of no input."""
    boot(snes, "direct")
    v = shot(snes)
    assert v.heli_x_px == 64
    assert v.heli_y == 96 * 256


def test_airframe_flies_right(snes):
    boot(snes, "harness").wait(20).right(30)
    v = shot(snes)
    assert v.heli_x_px == 171


def test_airframe_flies_back_left(snes):
    """Leftward travel exercises the borrow path in heli_move_x.

    `>>` is a logical shift even on signed types, so a round trip that lands
    mid-world proves the explicit sign branch, where a clamp at 0 would not.
    """
    boot(snes, "direct").wait(20).right(240).left(60)
    v = shot(snes)
    assert v.heli_x_px == 1106


# All four clamps: the world edge, and the flyable box between the HUD strip
# and the ground at y=168.

def test_airframe_stops_at_the_west_edge(snes):
    boot(snes, "direct").wait(20).left(60)
    v = shot(snes)
    assert v.heli_x_px == 0


def test_airframe_stops_under_the_hud(snes):
    boot(snes, "direct").wait(20).up(60)
    v = shot(snes)
    assert v.heli_y == 16 * 256


def test_airframe_stops_on_the_ground(snes):
    boot(snes, "harness").wait(20).down(30).wait(40)
    v = shot(snes)
    assert v.heli_y == 152 * 256


# Tilt is cosmetic, from velocity ALONG THE NOSE: OAM sprite 0's tile picks
# the frame (0 nose-down, 4 level, 8 nose-up). Flying left mirrors the
# airframe, which swaps the two cells as well as setting hflip - so sprite 0
# then holds the frame's far tile (+2) and its attribute byte gains $40.
# The attribute reads $37 (or $77 mirrored): priority 3, OBJ palette 3 and
# the 9th tile bit - the airframe's own sheet (HELI_PAGE / OBJ_PAL_HELI).
#
# Reversing is a turn: five drawings held three frames each, advancing only
# while the new direction is held.

def test_airframe_sits_level_at_rest(snes):
    boot(snes, "harness")
    v = shot(snes)
    assert v.oam.u8[2] == 0x04
    assert v.oam.u8[3] == 0x37


def test_airframe_tilts_nose_down_flying_right(snes):
    boot(snes, "harness").wait(20).right(60)
    v = shot(snes)
    assert v.oam.u8[2] == 0x00
    assert v.oam.u8[3] == 0x37


def test_airframe_is_mirrored_flying_left(snes):
    boot(snes, "direct").wait(20).right(120).left(60)
    v = shot(snes)
    assert v.oam.u8[2] == 0x02
    assert v.oam.u8[3] == 0x77


def test_turn_shows_the_three_quarter_view(snes):
    """Ten frames in, the three-quarter view faces the new way.

    Its cells swap under hflip, so the first slot carries the right-hand
    cell, $22.
    """
    boot(snes, "direct").wait(20).right(120).left(10)
    v = shot(snes)
    assert v.oam.u8[2] == 0x22
    assert v.oam.u8[3] == 0x77


def test_turn_stalls_when_released(snes):
    """Six frames in and released, it stalls on the three-quarter view, still
    facing the old way ($20).
    """
    boot(snes, "harness").wait(20).right(120).left(6).wait(20)
    v = shot(snes)
    assert v.oam.u8[2] == 0x20
    assert v.oam.u8[3] == 0x37


def test_turn_wound_back_never_changes_facing(snes):
    boot(snes, "direct").wait(20).right(120).left(6).right(6).wait(2)
    v = shot(snes)
    assert v.oam.u8[3] == 0x37


# ---- Phase 4 - weapons and munitions ----------------------------------------
#
# Gunfire and bombs share one pool with a rotating free cursor; slot 0 is the
# first one a cold pool hands out, so a single shot always lands there.

FREE, BULLET, BOMB = 0, 1, 2


def test_loadout_is_64_rounds_and_10_bombs(snes):
    boot(snes, "direct")
    v = shot(snes)
    assert v.heli_gun == 64
    assert v.heli_bombs == 10


def test_30_frames_of_fire_is_5_rounds(snes):
    """HELI_GUN_RATE is 6, so 30 frames of held fire is exactly 5 rounds."""
    boot(snes, "harness").wait(10).b(30)
    v = shot(snes)
    assert v.heli_gun == 59


def test_holding_a_drops_one_bomb(snes):
    """Bombs are edge-triggered: holding A must not empty the rack."""
    boot(snes, "direct").wait(10).a(1)
    v = shot(snes)
    assert v.heli_bombs == 9


def test_two_presses_drop_two_bombs(snes):
    boot(snes, "harness").wait(10).a(1).wait(5).a(1)
    v = shot(snes)
    assert v.heli_bombs == 8


def test_firing_past_empty_stops_at_zero(snes):
    """Firing past empty must stop at zero, not wrap to 255."""
    boot(snes, "harness").wait(10).b(400)
    v = shot(snes)
    assert v.heli_gun == 0


def test_the_nose_follows_the_stick(snes):
    """The gun points where the nose points, and the nose follows the last
    commanded direction rather than the coasting velocity.
    """
    boot(snes, "direct").wait(10).left(20)
    v = shot(snes)
    assert v.heli_face_left == 1


# Pool lifecycle. A bomb falls to the ground in ~25 frames and retires on
# contact; a round retires on BULLET_LIFE, which is what stops sustained fire
# from starving the pool.

def test_a_dropped_bomb_is_live(snes):
    boot(snes, "direct").wait(10).a(1)
    v = shot(snes)
    assert v.muni_kind.u8[0] == BOMB


def test_a_bomb_is_live_while_falling(snes):
    boot(snes, "direct").wait(10).a(1).wait(10)
    v = shot(snes)
    assert v.muni_kind.u8[0] == BOMB


def test_a_bomb_retires_on_the_ground(snes):
    boot(snes, "harness").wait(10).a(1).wait(40)
    v = shot(snes)
    assert v.muni_kind.u8[0] == FREE


def test_a_fired_round_is_live(snes):
    boot(snes, "direct").wait(10).b(1)
    v = shot(snes)
    assert v.muni_kind.u8[0] == BULLET


def test_a_round_retires_at_the_end_of_its_range(snes):
    boot(snes, "direct").wait(10).b(1).wait(45)
    v = shot(snes)
    assert v.muni_kind.u8[0] == FREE


def test_a_round_leaves_at_muzzle_height(snes):
    """A round leaves at the airframe's 8.8 y plus 7 px.

    This once came out as 0x0200 - a compiler bug restored the argument
    through an 8-bit TYA - and every round spawned on the HUD row.
    """
    boot(snes, "direct").wait(10).b(1)
    v = shot(snes)
    assert v.muni_y.u16[0] == 103 * 256


def test_y_fires_nothing(snes):
    """The smart missile is out of the game.

    muni_up is a [u8; 2]; side 0's count is the player's munitions in flight.
    """
    boot(snes, "harness").wait(20).y(1).wait(20)
    shot(snes)
    assert snes.raw("muni_up").u8[0] == 0

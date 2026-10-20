"""Phases 1-4: boot, the scrolling battlefield, the airframe and its weapons."""

from shared import boot, read_snapshot, title_shot


# ---- Phase 1 - harness ------------------------------------------------------

def test_boot(snes, tmp_path):
    """The ROM boots, enables NMI, runs its loop and reaches snapshot_point.

    It opens on the title, and the frame must be the title's picture pixel
    for pixel (title.tilemap.bmp, at the PPU's 5-bit colours) but for the
    menu's text - this catches a failed palette or tile DMA, the wrong mode,
    or a layer left enabled over the screen.
    """
    boot(snes)
    read_snapshot(snes)
    same, _ = title_shot(snes, tmp_path)
    assert same >= 0.95 * 256 * 224, "the title's picture is on screen"


# ---- Phase 2 - scrolling battlefield ----------------------------------------
#
# The camera is a window follow: it holds still until the focus point leaves
# a CAM_DEAD (8px) window around screen centre, then closes at up to CAM_STEP
# px/frame, settling at a lag of +8 moving right, -8 moving left. The focus is
# the helicopter's centre led by vx/8: after 240 frames right the airframe is
# at 1221 doing 312/64 px/frame, so the focus is 1221 + 16 + 39 = 1276 and
# the camera settles at 1276 - 128 - 8 = 1140.

def test_camera_holds_still_at_rest(snes):
    boot(snes, "MISSION_CAKE_WALK")
    v = read_snapshot(snes)
    assert v.camera_x == 0


def test_camera_follows_30_frames_right(snes):
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(30)
    v = read_snapshot(snes)
    assert v.camera_x == 90


def test_camera_follows_120_frames_right(snes):
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(120)
    v = read_snapshot(snes)
    assert v.camera_x == 540


def test_camera_settles_8_px_behind_after_240_frames_right(snes):
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(240)
    v = read_snapshot(snes)
    assert v.camera_x == 1140


def test_camera_follows_back_left(snes):
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(240).left(90)
    v = read_snapshot(snes)
    assert v.camera_x == 813


# ---- Phase 3 - helicopter ---------------------------------------------------
#
# x is 16.8 (x_px + x_sub); y a u16 of 8.8 screen pixels; velocity Q10. The
# d-pad picks a target velocity and the airframe accelerates toward it, so
# the first ~20 frames of any direction are a ramp.

def test_airframe_spawns_at_rest(snes):
    """heli_init's spawn, untouched by a frame of no input."""
    boot(snes, "MISSION_CAKE_WALK")
    v = read_snapshot(snes)
    assert v.airframes__x_px.u16[0] == 64
    assert v.airframes__y.u16[0] == 112 * 256


def test_airframe_flies_right(snes):
    boot(snes, "MISSION_TEST_QUIET").wait(20).right(30)
    v = read_snapshot(snes)
    assert v.airframes__x_px.u16[0] == 171


def test_airframe_flies_back_left(snes):
    """Leftward travel exercises the borrow path in heli_move_x.

    `>>` is a logical shift even on signed types, so a round trip that lands
    mid-world proves the explicit sign branch, where a clamp at 0 would not.
    """
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(240).left(60)
    v = read_snapshot(snes)
    assert v.airframes__x_px.u16[0] == 1106


# All four clamps: the world edge, and the flyable box between the HUD strip
# and the ground at y=168.

def test_airframe_stops_at_the_west_edge(snes):
    boot(snes, "MISSION_CAKE_WALK").wait(20).left(60)
    v = read_snapshot(snes)
    assert v.airframes__x_px.u16[0] == 0


def test_airframe_stops_under_the_hud(snes):
    boot(snes, "MISSION_CAKE_WALK").wait(20).up(60)
    v = read_snapshot(snes)
    assert v.airframes__y.u16[0] == 16 * 256


def test_airframe_stops_on_the_ground(snes):
    boot(snes, "MISSION_TEST_QUIET").wait(20).down(30).wait(40)
    v = read_snapshot(snes)
    assert v.airframes__y.u16[0] == 168 * 256


# Tilt is cosmetic, from velocity ALONG THE NOSE: OAM sprite 0's tile picks
# the frame (0 nose-down, 4 level, 8 nose-up, 64 the nose dipping). The
# forward lean follows the stick, not the speed: it dips 2 frames into a
# push and is fully down at 10, and lets go the frame the stick does, at
# half that rate (the dip for 16 frames, then level) - so a
# case reading a lean holds the direction through the snapshot's Select. Flying left mirrors the
# airframe, which swaps the two cells as well as setting hflip - so sprite 0
# then holds the frame's far tile (+2) and its attribute byte gains $40.
# The attribute reads $37 (or $77 mirrored): priority 3, OBJ palette 3 and
# the 9th tile bit - the airframe's own sheet (HELI_PAGE / OBJ_PAL_HELI).
#
# Reversing is a turn: five drawings held three frames each, advancing only
# while the new direction is held.

def test_airframe_sits_level_at_rest(snes):
    boot(snes, "MISSION_TEST_QUIET")
    v = read_snapshot(snes)
    assert v.oam.u8[2] == 0x04
    assert v.oam.u8[3] == 0x37


def test_the_nose_dips_first_pulling_away(snes):
    """Six frames into a push: leaning in, not yet nose down."""
    boot(snes, "MISSION_TEST_QUIET").wait(20).right(6)
    v = read_snapshot(snes, "right")
    assert v.oam.u8[2] == 0x40
    assert v.oam.u8[3] == 0x37


def test_the_lean_comes_off_as_the_stick_is_let_go(snes):
    """At full speed, released: the frame after it is the dip again, held
    16 frames - the lean comes off at half the rate it went on - and then
    the airframe is level while still coasting right."""
    boot(snes, "MISSION_TEST_QUIET").wait(20).right(60)
    v = read_snapshot(snes)
    assert v.oam.u8[2] == 0x40
    snes.wait(8)
    v = read_snapshot(snes)
    assert v.oam.u8[2] == 0x40
    snes.wait(8)
    v = read_snapshot(snes)
    assert v.oam.u8[2] == 0x04
    assert 0 < v.airframes__vx.u16[0] < 0x8000          # Q10, signed: still going right


def test_airframe_tilts_nose_down_flying_right(snes):
    boot(snes, "MISSION_TEST_QUIET").wait(20).right(60)
    v = read_snapshot(snes, "right")
    assert v.oam.u8[2] == 0x00
    assert v.oam.u8[3] == 0x37


def test_airframe_is_mirrored_flying_left(snes):
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(120).left(60)
    v = read_snapshot(snes, "left")
    assert v.oam.u8[2] == 0x02
    assert v.oam.u8[3] == 0x77


def test_turn_shows_the_three_quarter_view(snes):
    """Ten frames in, the three-quarter view faces the new way.

    Its cells swap under hflip, so the first slot carries the right-hand
    cell, $22.
    """
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(120).left(10)
    v = read_snapshot(snes)
    assert v.oam.u8[2] == 0x22
    assert v.oam.u8[3] == 0x77


def test_turn_stalls_when_released(snes):
    """Six frames in and released, it stalls on the three-quarter view, still
    facing the old way ($20).
    """
    boot(snes, "MISSION_TEST_QUIET").wait(20).right(120).left(6).wait(20)
    v = read_snapshot(snes)
    assert v.oam.u8[2] == 0x20
    assert v.oam.u8[3] == 0x37


def test_turn_wound_back_never_changes_facing(snes):
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(120).left(6).right(6).wait(2)
    v = read_snapshot(snes)
    assert v.oam.u8[3] == 0x37


# ---- Phase 4 - weapons and munitions ----------------------------------------
#
# Gunfire and bombs share one pool with a rotating free cursor; slot 0 is the
# first one a cold pool hands out, so a single shot always lands there.

FREE, BULLET, BOMB = 0, 1, 2


def test_loadout_is_96_rounds_and_10_bombs(snes):
    boot(snes, "MISSION_CAKE_WALK")
    v = read_snapshot(snes)
    assert v.airframes__gun.u8[0] == 96
    assert v.airframes__bombs.u8[0] == 10


def test_30_frames_of_fire_is_5_rounds(snes):
    """HELI_GUN_RATE is 6, so 30 frames of held fire is exactly 5 rounds."""
    boot(snes, "MISSION_TEST_QUIET").wait(10).b(30)
    v = read_snapshot(snes)
    assert v.airframes__gun.u8[0] == 91


def test_holding_a_drops_one_bomb(snes):
    """Bombs are edge-triggered: holding A must not empty the rack."""
    boot(snes, "MISSION_CAKE_WALK").wait(10).a(1)
    v = read_snapshot(snes)
    assert v.airframes__bombs.u8[0] == 9


def test_two_presses_drop_two_bombs(snes):
    boot(snes, "MISSION_TEST_QUIET").wait(10).a(1).wait(5).a(1)
    v = read_snapshot(snes)
    assert v.airframes__bombs.u8[0] == 8


def test_firing_past_empty_stops_at_zero(snes):
    """Firing past empty must stop at zero, not wrap to 255.

    Three rounds in the air hold the trigger until the first runs out
    (GUN_LIFE, 20 frames), so a round every 6.7 frames: 96 take ~640.
    """
    boot(snes, "MISSION_TEST_QUIET").wait(10).b(700)
    v = read_snapshot(snes)
    assert v.airframes__gun.u8[0] == 0


def test_the_nose_follows_the_stick(snes):
    """The gun points where the nose points, and the nose follows the last
    commanded direction rather than the coasting velocity.
    """
    boot(snes, "MISSION_CAKE_WALK").wait(10).left(20)
    v = read_snapshot(snes)
    assert v.airframes__face_left.u8[0] == 1


# Pool lifecycle. A bomb falls to the ground in ~25 frames and retires on
# contact; a round retires on GUN_LIFE (a building's on BULLET_LIFE), which is
# what stops sustained fire from starving the pool.

def test_a_dropped_bomb_is_live(snes):
    boot(snes, "MISSION_CAKE_WALK").wait(10).a(1)
    v = read_snapshot(snes)
    assert v.muni_kind.u8[0] == BOMB


def test_a_bomb_is_live_while_falling(snes):
    boot(snes, "MISSION_CAKE_WALK").wait(10).a(1).wait(10)
    v = read_snapshot(snes)
    assert v.muni_kind.u8[0] == BOMB


def test_a_bomb_retires_on_the_ground(snes):
    boot(snes, "MISSION_TEST_QUIET").wait(10).a(1).wait(40)
    v = read_snapshot(snes)
    assert v.muni_kind.u8[0] == FREE


def test_a_fired_round_is_live(snes):
    boot(snes, "MISSION_CAKE_WALK").wait(10).b(1)
    v = read_snapshot(snes)
    assert v.muni_kind.u8[0] == BULLET


def test_a_round_flies_16_px_a_frame(snes):
    """The airframes' gun, GUN_SPEED: twice a building's 8 px/frame (Q10)."""
    boot(snes, "MISSION_CAKE_WALK").wait(10).b(1)
    v = read_snapshot(snes)
    assert v.muni_vx.u16[0] == 16 * 64


def test_three_rounds_are_in_the_air_at_most(snes):
    """Held fire settles at three rounds up - a round every 6 frames and
    GUN_LIFE 20 would carry a fourth for two frames in every six."""
    boot(snes, "MISSION_TEST_QUIET").wait(10).b(60)
    v = read_snapshot(snes, "b")
    assert [v.muni_kind.u8[i] for i in range(16)].count(BULLET) == 3
    assert v.airframes__gun.u8[0] == 86


def test_the_third_round_holds_the_trigger(snes):
    """The fourth round waits for the first to run out, so the gun fires a
    round every 6.7 frames rather than every 6: 400 frames fire 60 rounds
    of the 96, where without the cap they fired 67."""
    boot(snes, "MISSION_TEST_QUIET").wait(10).b(400)
    v = read_snapshot(snes)
    assert v.airframes__gun.u8[0] == 36


def test_a_round_into_the_ground_kicks_up_dirt(snes):
    """Strafing nose down from low, the rounds reach the dirt on screen and
    each puts up an impact (fx.r65's FX_HIT, kind 4): obj.bmp's 8x8 tile
    224, the spark, then 225, the dust."""
    boot(snes, "MISSION_TEST_QUIET").wait(20).down(14).wait(30).right(20).press("right", "b", frames=26)
    v = read_snapshot(snes, "right", "b")
    hits = [i for i in range(8) if v.fx_kind.u8[i] == 4]
    assert hits
    assert {v.fx_attr.u16[i] & 0x1FF for i in hits} == {224}
    assert {v.fx_y.u8[i] for i in hits} == {184 - 8}


def test_a_round_retires_at_the_end_of_its_range(snes):
    boot(snes, "MISSION_CAKE_WALK").wait(10).b(1).wait(45)
    v = read_snapshot(snes)
    assert v.muni_kind.u8[0] == FREE


def test_a_round_leaves_at_muzzle_height(snes):
    """A round leaves at the airframe's 8.8 y plus 7 px.

    This once came out as 0x0200 - a compiler bug restored the argument
    through an 8-bit TYA - and every round spawned on the HUD row.
    """
    boot(snes, "MISSION_CAKE_WALK").wait(10).b(1)
    v = read_snapshot(snes)
    assert v.muni_y.u16[0] == 119 * 256


def test_y_fires_nothing(snes):
    """The smart missile is out of the game.

    muni_up is a [u8; 2]; side 0's count is the player's munitions in flight.
    """
    boot(snes, "MISSION_TEST_QUIET").wait(20).y(1).wait(20)
    read_snapshot(snes)
    assert snes.raw("muni_up").u8[0] == 0

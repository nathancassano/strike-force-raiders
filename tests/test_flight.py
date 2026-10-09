"""Phases 1-4: boot, the scrolling battlefield, the airframe and its weapons."""

import pytest

from harness import boot, expect, screen_colour, shot, tool

case = pytest.param


# ---- Phase 1 - harness ------------------------------------------------------

def test_boot(snes, tmp_path):
    # The ROM boots, enables NMI, runs its loop and reaches snapshot_point.
    # The sky backdrop must still dominate the frame - this catches a failed
    # palette DMA or a layer left enabled over the whole screen.
    boot(snes)
    shot(snes)
    assert screen_colour(snes, tmp_path, (33, 49, 115)) >= 40


# ---- Phase 2 - scrolling battlefield ----------------------------------------
#
# The camera is a window follow: it holds still until the focus point leaves
# a CAM_DEAD (8px) window around screen centre, then closes at up to CAM_STEP
# px/frame, settling at a lag of +8 moving right, -8 moving left. The focus is
# the helicopter's centre led by vx/8: at cam_r240 the airframe is at 1221
# doing 312/64 px/frame, so the focus is 1221 + 16 + 39 = 1276 and the camera
# settles at 1276 - 128 - 8 = 1140 = $0474.

@pytest.mark.parametrize("script, camera_x", [
    case(lambda s: boot(s, "direct"), 0x0000, id="cam_rest"),
    case(lambda s: boot(s, "direct").wait(20).right(30), 0x005A, id="cam_r30"),
    case(lambda s: boot(s, "direct").wait(20).right(120), 0x021C, id="cam_r120"),
    case(lambda s: boot(s, "direct").wait(20).right(240), 0x0474, id="cam_r240"),
    case(lambda s: boot(s, "direct").wait(20).right(240).left(90), 0x032D, id="cam_back"),
])
def test_camera(snes, script, camera_x):
    script(snes)
    shot(snes)
    expect(snes, {"v.camera_x": camera_x})


def test_parallax(rom, tmp_path):
    # Four layers at four rates, and eight equal HDMA ground bands, of which
    # the tool can measure six: the first is the plain ground line under the
    # units' feet, and the airframe's HUD strip on the last tile row cuts the
    # seventh and covers the eighth. A short move: the near band runs at
    # 1.875x and the tool correlates each row wrapped at the screen width.
    shots = []
    for script in (lambda s: boot(s, "direct"), lambda s: boot(s, "direct").wait(20).right(40)):
        with rom.session() as s:
            script(s)
            shot(s)
            shots.append(s.screenshot(tmp_path / f"parallax-{len(shots)}.png"))
    # Rows 216-223 are the airframe's HUD strip; below is past the screen.
    tool("parallax.py", *shots, "--assert-bands", 6, "--ignore-rows", "216-238")


# ---- Phase 3 - helicopter ---------------------------------------------------
#
# x is 16.8 (x_px + x_sub); y a u16 of 8.8 screen pixels; velocity Q10. The
# d-pad picks a target velocity and the airframe accelerates toward it, so
# the first ~20 frames of any direction are a ramp.

@pytest.mark.parametrize("script, checks", [
    # Rest: heli_init's spawn, untouched by a frame of no input.
    case(lambda s: boot(s, "direct"), {"v.heli_x_px": 0x0040, "v.heli_y": 0x6000}, id="heli_rest"),
    case(lambda s: boot(s, "harness").wait(20).right(30), {"v.heli_x_px": 0x00AB}, id="heli_right"),
    # Leftward travel exercises the borrow path in heli_move_x: `>>` is a
    # logical shift even on signed types, so a round trip that lands
    # mid-world proves the explicit sign branch, where a clamp at 0 would not.
    case(lambda s: boot(s, "direct").wait(20).right(240).left(60), {"v.heli_x_px": 0x0452}, id="heli_back"),
    # All four clamps: the world edge, and the flyable box between the HUD
    # strip and the ground at y=168.
    case(lambda s: boot(s, "direct").wait(20).left(60), {"v.heli_x_px": 0x0000}, id="heli_wall"),
    case(lambda s: boot(s, "direct").wait(20).up(60), {"v.heli_y": 0x1000}, id="heli_ceil"),
    case(lambda s: boot(s, "harness").wait(20).down(30).wait(40), {"v.heli_y": 0x9800}, id="heli_floor"),
])
def test_heli(snes, script, checks):
    script(snes)
    shot(snes)
    expect(snes, checks)


# Tilt is cosmetic, from velocity ALONG THE NOSE: OAM sprite 0's tile picks
# the frame (0 nose-down, 4 level, 8 nose-up). Flying left mirrors the
# airframe, which swaps the two cells as well as setting hflip - so sprite 0
# then holds the frame's far tile (+2) and its attribute byte gains $40.
# The attribute reads $37 (or $77 mirrored): priority 3, OBJ palette 3 and
# the 9th tile bit - the airframe's own sheet (HELI_PAGE / OBJ_PAL_HELI).
#
# Reversing is a turn: five drawings held three frames each, advancing only
# while the new direction is held. Ten frames in, the three-quarter view
# faces the new way (its cells swap under hflip, so the first slot carries
# the right-hand cell, $22); six frames in and released, it stalls on the
# three-quarter view still facing the old way ($20); wound back to nothing,
# the facing never changed.
TILE, ATTR = "s.raw('oam').u8[2]", "s.raw('oam').u8[3]"


@pytest.mark.parametrize("script, checks", [
    case(lambda s: boot(s, "harness"), {TILE: 0x04, ATTR: 0x37}, id="heli_tilt_level"),
    case(lambda s: boot(s, "harness").wait(20).right(60), {TILE: 0x00, ATTR: 0x37}, id="heli_tilt_right"),
    case(lambda s: boot(s, "direct").wait(20).right(120).left(60), {TILE: 0x02, ATTR: 0x77}, id="heli_tilt_left"),
    case(lambda s: boot(s, "direct").wait(20).right(120).left(10), {TILE: 0x22, ATTR: 0x77}, id="heli_turn_mid"),
    case(lambda s: boot(s, "harness").wait(20).right(120).left(6).wait(20), {TILE: 0x20, ATTR: 0x37}, id="heli_turn_stall"),
    case(lambda s: boot(s, "direct").wait(20).right(120).left(6).right(6).wait(2), {ATTR: 0x37}, id="heli_turn_back"),
])
def test_heli_sprite(snes, script, checks):
    script(snes)
    shot(snes)
    expect(snes, checks)


def test_heli_drawn(snes, tmp_path):
    # The airframe is actually drawn, not just positioned. Canopy and rotor
    # are the two OBJ colours that appear nowhere else on screen, so finding
    # them proves the OBJ CHR reached VRAM and the palette reached CGRAM.
    boot(snes, "harness").wait(20).right(60)
    shot(snes)
    assert screen_colour(snes, tmp_path, (14, 22, 28), snes_colour=True) >= 0.02   # canopy
    assert screen_colour(snes, tmp_path, (21, 22, 24), snes_colour=True) >= 0.05   # rotor disc


# ---- Phase 4 - weapons and munitions ----------------------------------------
#
# Gunfire and bombs share one pool with a rotating free cursor; slot 0 is the
# first one a cold pool hands out, so a single shot always lands there.
# Kinds: 0 free, 1 bullet, 2 bomb.

@pytest.mark.parametrize("script, checks", [
    # The plan's loadout: 64 rounds, 10 bombs.
    case(lambda s: boot(s, "direct"), {"v.heli_gun": 0x40, "v.heli_bombs": 0x0A}, id="ammo_rest"),
    # HELI_GUN_RATE is 6, so 30 frames of held fire is exactly 5 rounds.
    case(lambda s: boot(s, "harness").wait(10).b(30), {"v.heli_gun": 0x3B}, id="ammo_burst"),
    # Bombs are edge-triggered: holding A must not empty the rack.
    case(lambda s: boot(s, "direct").wait(10).a(1), {"v.heli_bombs": 0x09}, id="ammo_bomb"),
    case(lambda s: boot(s, "harness").wait(10).a(1).wait(5).a(1), {"v.heli_bombs": 0x08}, id="ammo_bomb2"),
    # Firing past empty must stop at zero, not wrap to 255.
    case(lambda s: boot(s, "harness").wait(10).b(400), {"v.heli_gun": 0x00}, id="ammo_empty"),
    # The gun points where the nose points, and the nose follows the last
    # commanded direction rather than the coasting velocity.
    case(lambda s: boot(s, "direct").wait(10).left(20), {"v.heli_face_left": 0x01}, id="ammo_face"),
    # Pool lifecycle. A bomb falls to the ground in ~25 frames and retires on
    # contact; a round retires on BULLET_LIFE, which is what stops sustained
    # fire from starving the pool.
    case(lambda s: boot(s, "direct").wait(10).a(1), {"s.raw('muni_kind').u8[0]": 0x02}, id="muni_bomb_live"),
    case(lambda s: boot(s, "direct").wait(10).a(1).wait(10), {"s.raw('muni_kind').u8[0]": 0x02}, id="muni_bomb_fall"),
    case(lambda s: boot(s, "harness").wait(10).a(1).wait(40), {"s.raw('muni_kind').u8[0]": 0x00}, id="muni_bomb_ground"),
    case(lambda s: boot(s, "direct").wait(10).b(1), {"s.raw('muni_kind').u8[0]": 0x01}, id="muni_gun_live"),
    case(lambda s: boot(s, "direct").wait(10).b(1).wait(45), {"s.raw('muni_kind').u8[0]": 0x00}, id="muni_gun_range"),
    # A round leaves at muzzle height: the airframe's 8.8 y plus 7 px. This
    # once came out as 0x0200 - a compiler bug restored the argument through
    # an 8-bit TYA - and every round spawned on the HUD row.
    case(lambda s: boot(s, "direct").wait(10).b(1), {"s.raw('muni_y').u16[0]": 0x6700}, id="muni_gun_muzzle"),
    # Y fires nothing: the smart missile is out of the game. muni_up is a
    # [u8; 2]; side 0's count is the player's munitions in flight.
    case(lambda s: boot(s, "harness").wait(20).y(1).wait(20), {"s.raw('muni_up').u8[0]": 0x00}, id="y_inert"),
])
def test_weapons(snes, script, checks):
    script(snes)
    shot(snes)
    expect(snes, checks)

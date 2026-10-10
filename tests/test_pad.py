"""Phase 5: landing pad, rearm and fuel.

The player's deck spans world x 1024..1071, so the airframe's centre has to
be inside it - x 1008..1055 - when it touches the floor. Since the airlift a
powered descent lands anywhere on the ground; only a deck rearms
(heli_on_pad). Touching down faster than HELI_CRASH_VY (2.5 px/frame) is a
crash, so every landing here eases off: 30 frames of Down from hover height
and a coast arrives under it; 32 does not, and a full-stick descent hits at
4. right180 and a 60-frame coast puts the airframe at x 1014.
"""

from shared import boot, read_snapshot


def test_landing_on_the_deck(snes):
    """Descending onto the deck lands on it."""
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(180).wait(60).down(30).wait(40)
    v = read_snapshot(snes)
    assert v.heli_landed == 1
    assert v.heli_on_pad == 1


def test_landing_short_of_the_deck_is_open_ground(snes):
    """Stopping short (x 714) lands on open ground - down, but no deck."""
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(120).wait(60).down(30).wait(40)
    v = read_snapshot(snes)
    assert v.heli_landed == 1
    assert v.heli_on_pad == 0
    assert v.heli_y == 152 * 256


def test_landing_past_the_deck_is_open_ground(snes):
    """Overshooting (x 1314) lands on open ground - down, but no deck."""
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(240).wait(60).down(30).wait(40)
    v = read_snapshot(snes)
    assert v.heli_landed == 1
    assert v.heli_on_pad == 0


def test_a_landed_airframe_does_not_slide(snes):
    """Down at the start, then held right for 190 frames, it is still at x 64
    on open ground, not on the deck.
    """
    boot(snes, "MISSION_CAKE_WALK").wait(20).down(30).wait(40).right(190)
    v = read_snapshot(snes)
    assert v.heli_landed == 1
    assert v.heli_on_pad == 0
    assert v.heli_x_px == 64


def test_taking_off_from_the_deck(snes):
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(180).wait(60).down(30).wait(40).up(20)
    v = read_snapshot(snes)
    assert v.heli_landed == 0


def test_a_full_stick_landing_crashes(snes):
    """Too fast: a full-stick descent onto the deck is a crash - a life gone."""
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(180).wait(60).down(80)
    v = read_snapshot(snes)
    assert v.heli_lives == 3
    assert v.heli_landed == 0


def test_the_deck_rearms_and_refuels(snes):
    """Fuel back to 100, and the reload countdowns give back rounds at 20
    frames each and bombs at 10 while the airframe sits.
    """
    boot(snes, "MISSION_TEST_QUIET").wait(20).b(60).a(1).right(180).wait(60).down(30).wait(40).wait(120)
    v = read_snapshot(snes)
    assert v.heli_landed == 1
    assert v.heli_fuel == 100
    assert v.heli_gun == 61
    assert v.heli_bombs == 10


def test_fuel_burns_one_unit_per_64_frames(snes):
    boot(snes, "MISSION_TEST_QUIET").wait(20).right(240)
    v = read_snapshot(snes)
    assert v.heli_fuel == 96


def test_a_dry_tank_sinks_and_crashes(snes):
    """Gravity is allowed in exactly one place, and this is it.

    The airframe sinks with no input, and open ground is not a deck: touching
    it on a dead stick is a crash landing - a life gone, and by 7200 frames
    the next airframe is up at hover height.
    """
    boot(snes, "MISSION_TEST_QUIET").wait(7200)
    v = read_snapshot(snes)
    assert v.heli_lives == 3
    assert v.heli_y == 96 * 256
    assert v.heli_landed == 0

"""Phase 5: landing pad, rearm and fuel.

The player's deck spans world x 472..519, beside its base (400..463), so the
airframe's left edge has to be at x 456..503 - its centre on the deck - when
it touches the floor. Since the airlift a
powered descent lands anywhere on the ground; only a deck rearms
(player.on_pad). Touching down is a crash only flat out on both axes - the top
descent rate and the top horizontal speed (heli_crashes) - which a dive from
hover height cannot build, so any descent from there lands. right70 and a
60-frame coast puts the airframe at x 464.
"""

from shared import boarded, boot, read_snapshot

INFANTRY = 4                    # units__kind__tag


def test_landing_on_the_deck(snes):
    """Descending onto the deck lands on it."""
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(70).wait(60).down(30).wait(40)
    v = read_snapshot(snes)
    assert v.airframes__landed.u8[0] == 1
    assert v.player__on_pad.u8[0] == 1


def test_landing_short_of_the_deck_is_open_ground(snes):
    """Stopping short (x 314) lands on open ground - down, but no deck."""
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(40).wait(60).down(30).wait(40)
    v = read_snapshot(snes)
    assert v.airframes__landed.u8[0] == 1
    assert v.player__on_pad.u8[0] == 0
    assert v.airframes__y.u16[0] == 168 * 256


def test_landing_past_the_deck_is_open_ground(snes):
    """Overshooting (x 1314) lands on open ground - down, but no deck."""
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(240).wait(60).down(30).wait(40)
    v = read_snapshot(snes)
    assert v.airframes__landed.u8[0] == 1
    assert v.player__on_pad.u8[0] == 0


def test_a_landed_airframe_does_not_slide(snes):
    """Down at the start, then held right for 190 frames, it is still at x 64
    on open ground, not on the deck.
    """
    boot(snes, "MISSION_CAKE_WALK").wait(20).down(30).wait(40).right(190)
    v = read_snapshot(snes)
    assert v.airframes__landed.u8[0] == 1
    assert v.player__on_pad.u8[0] == 0
    assert v.airframes__x_px.u16[0] == 64


def test_taking_off_from_the_deck(snes):
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(70).wait(60).down(30).wait(40).up(20)
    v = read_snapshot(snes)
    assert v.airframes__landed.u8[0] == 0


def test_a_full_stick_descent_onto_the_deck_lands(snes):
    """Straight down at full stick from hover height lands on the deck."""
    boot(snes, "MISSION_CAKE_WALK").wait(20).right(70).wait(60).down(80)
    v = read_snapshot(snes)
    assert v.airframes__lives.u8[0] == 4
    assert v.airframes__landed.u8[0] == 1
    assert v.player__on_pad.u8[0] == 1


def test_a_straight_dive_from_altitude_lands(snes):
    """Full Down from near the ceiling reaches the top descent rate, but with
    no horizontal speed it is still a landing.
    """
    boot(snes, "MISSION_CAKE_WALK").wait(20).up(60).down(90)
    v = read_snapshot(snes)
    assert v.airframes__lives.u8[0] == 4
    assert v.airframes__landed.u8[0] == 1


def test_a_flat_out_dive_crashes(snes):
    """Down and Right from near the ceiling meets the ground at the top
    speed on both axes: a crash - a life gone.
    """
    boot(snes, "MISSION_CAKE_WALK").wait(20).up(60).downright(90)
    v = read_snapshot(snes)
    assert v.airframes__lives.u8[0] == 3
    assert v.airframes__landed.u8[0] == 0


def test_the_deck_rearms_and_refuels(snes):
    """Fuel back to 100, and the reload countdowns give back rounds eight
    every 21 frames and bombs one every 11 while the airframe sits: emptied
    first, the gun has had seven refills by the snapshot (it had seven
    single rounds when they came back one at a time).
    """
    boot(snes, "MISSION_TEST_QUIET").wait(20).b(660).a(1).right(70).wait(60).down(30).wait(40).wait(120)
    v = read_snapshot(snes)
    assert v.airframes__landed.u8[0] == 1
    assert v.airframes__fuel.u8[0] == 100
    assert v.airframes__gun.u8[0] == 56
    assert v.airframes__bombs.u8[0] == 10


def test_fuel_burns_one_unit_per_96_frames(snes):
    """A unit every 97 frames (the countdown from 96, then the burn): about
    162 s on a full tank. It was 64, 108 s."""
    boot(snes, "MISSION_TEST_QUIET").wait(20).right(240)
    v = read_snapshot(snes)
    assert v.airframes__fuel.u8[0] == 98


def test_a_dry_tank_sinks_and_crashes(snes):
    """The tank runs dry at hover and the airframe sinks with no input;
    touching the ground on a dead stick is the loss - a life gone, and by
    10400 frames the next airframe is up at hover height (the tank lasts
    9700).
    """
    boot(snes, "MISSION_TEST_QUIET").wait(10400)
    v = read_snapshot(snes)
    assert v.airframes__lives.u8[0] == 3
    assert v.airframes__y.u16[0] == 112 * 256
    assert v.airframes__landed.u8[0] == 0


# A dry tank is a slow forced descent (heli.r65 HELI_SINK, 0.5 px/frame in
# Q10: 32) that left and right still steer: a deck under it saves it, open
# ground ends it.

def dry(snes):
    """At hover, the tank emptied by hand."""
    boot(snes, "MISSION_TEST_QUIET").wait(20)
    snes.write("airframes__fuel", 0, 1)
    return snes


def test_a_dry_tank_sinks_slowly(snes):
    """Half a pixel a frame, steady, with the stick ignored: Up does not hold
    it, and 40 frames on it is 20 px lower and still in the air."""
    y0 = int.from_bytes(dry(snes).read("airframes__y", 2), "little")
    snes.up(40)
    v = read_snapshot(snes, "up")
    assert v.airframes__vy.u16[0] == 32
    assert v.airframes__lives.u8[0] == 4
    assert 18 * 256 <= v.airframes__y.u16[0] - y0 <= 22 * 256


def test_a_dry_tank_still_steers(snes):
    """Right still flies it: 40 frames of it on a dry tank, and it is going
    right at speed, still coming down."""
    x0 = int.from_bytes(dry(snes).read("airframes__x_px", 2), "little")
    snes.right(40)
    v = read_snapshot(snes, "right")
    assert v.airframes__x_px.u16[0] > x0 + 60
    assert v.airframes__vy.u16[0] == 32


def test_a_dry_tank_on_the_deck_is_saved(snes):
    """Come down dry on the player's deck (x 472): it lands, and the deck
    starts filling the tank."""
    dry(snes)
    snes.write("airframes__x_px", 472, 2)
    snes.wait(200)
    v = read_snapshot(snes)
    assert v.airframes__lives.u8[0] == 4
    assert v.airframes__landed.u8[0] == 1
    assert v.player__on_pad.u8[0] == 1
    assert v.airframes__fuel.u8[0] > 0


def test_a_dry_tank_on_the_enemy_deck_is_lost(snes):
    """The enemy's deck (x 7672) is open ground to the player: come down dry
    on it and the pilot gets out, the airframe on its fuse."""
    boot(snes, "MISSION_TEST_QUIET").wait(20)
    snes.write("airframes__x_px", 7672, 2)
    hold_enemy_base(snes)
    touch_down_dry(snes).wait(5)
    v = read_snapshot(snes)
    assert v.airframes__landed.u8[0] == 1
    assert v.player__on_pad.u8[0] == 0
    assert v.airframes__fuel.u8[0] == 0
    assert v.airframes__fuse.u8[0] > 0


def test_the_enemy_deck_does_not_refit_the_player(snes):
    """A powered landing on the enemy's deck lands, but nothing is refilled:
    fuel, hp and rounds planted low stay where they were."""
    boot(snes, "MISSION_TEST_QUIET").wait(20)
    snes.write("airframes__x_px", 7672, 2)
    hold_enemy_base(snes)
    snes.write("airframes__fuel", 20, 1)
    snes.write("airframes__hp", 10, 1)
    snes.write("airframes__gun", 5, 1)
    snes.down(80).wait(150)
    v = read_snapshot(snes)
    assert v.airframes__landed.u8[0] == 1
    assert v.player__on_pad.u8[0] == 0
    assert v.airframes__fuel.u8[0] <= 20
    assert v.airframes__hp.u8[0] <= 10
    assert v.airframes__gun.u8[0] == 5


def hold_enemy_base(snes):
    """The enemy's deck is beside its base, under its missiles: hold the
    base's launcher for 255 frames (its countdown, structs__t, planted) so a
    case about the deck is not one about the missiles."""
    kind, owner = snes.raw("structs__kind").u8, snes.raw("structs__owner").u8
    base = next(i for i in range(16) if kind[i] == 3 and owner[i] == 1)   # StructKind::Base, the enemy's
    snes.write(snes.rom.symbols["structs__t"].addr + base, 255)


def touch_down_dry(snes):
    """From hover over open ground, the tank emptied: down to the touchdown."""
    snes.write("airframes__fuel", 0, 1)
    for _ in range(200):
        snes.wait(1)
        if snes.raw("airframes__landed").u8[0]:
            break
    return snes


def our_infantry(v):
    return sum(1 for i in range(32)
               if v.units__kind__tag.u8[i] == INFANTRY and v.units__owner.u8[i] == 0)


def test_the_men_aboard_walk_away_from_a_dry_tank(state):
    """Five aboard, lifted off, flown clear of the deck and run dry: the
    pilot and the five get out where it comes down, a convoy space apart
    behind it, and are on the field at once as six infantrymen - the
    airframe still sitting there on its fuse."""
    snes = state(boarded)
    snes.up(10).right(40)
    touch_down_dry(snes).wait(5)
    v = read_snapshot(snes)
    assert v.airframes__lives.u8[0] == 4
    assert v.player__men.u8[0] == 0
    assert our_infantry(v) == 6
    assert v.para_live == 0


def test_an_empty_airframe_puts_its_pilot_out(snes):
    """Nobody aboard, down dry on open ground: the pilot walks away, one
    infantryman (the design's no-ejection holds in the air only)."""
    boot(snes, "MISSION_TEST_QUIET").wait(20).right(100).wait(60)
    touch_down_dry(snes).wait(5)
    v = read_snapshot(snes)
    assert v.airframes__landed.u8[0] == 1
    assert v.player__on_pad.u8[0] == 0
    assert our_infantry(v) == 1


def test_down_dry_it_waits_then_goes_up(state):
    """Down dry off a deck, the men get out at once and the airframe sits
    there 60 frames (HELI_DRY_FUSE) before it goes up: half a second on it
    is still landed, its life still in hand, the men on their way onto the
    field; a second on it is gone."""
    snes = state(boarded)
    snes.up(10).right(40)
    snes.write("airframes__fuel", 0, 1)
    for _ in range(200):
        snes.wait(1)
        if snes.raw("airframes__landed").u8[0]:
            break
    snes.wait(30)
    v = read_snapshot(snes)
    assert v.airframes__landed.u8[0] == 1
    assert v.airframes__lives.u8[0] == 4
    assert v.player__men.u8[0] == 0
    ours = sum(1 for i in range(32) if v.units__kind__tag.u8[i] == INFANTRY and v.units__owner.u8[i] == 0)
    assert v.para_live + ours == 6
    snes.wait(40)
    v = read_snapshot(snes)
    assert v.airframes__lives.u8[0] == 3

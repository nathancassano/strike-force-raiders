"""The airlift (design.md, decided after phase 9).

Five men are bought and the airframe lands on the player's pad facing east,
and the men walk up from the west: each boards under its middle, within 5 px
of its centre. Lifted off, X drops one per press; a chute takes ~20 frames
from this height, and a landed man is an infantryman again. The RNG is
consumed by nothing else, so from a cold boot the sequence is fixed: the
third and fourth chutes are the ones in ten that fail, so three men of five
reach the ground, in the pool slots the cursor hands out.

Most cases start from the `boarded` state (shared.py): the men bought, the
airframe landed on the pad and all five aboard.
"""

from shared import boarded, boot, read_snapshot

FREE, INFANTRY = 0, 4      # unit kinds
PLAYER = 0


def test_board(state):
    """All five men aboard, and their pool slots free again."""
    snes = state(boarded)
    v = read_snapshot(snes)
    assert v.player__men.u8[0] == 5
    assert v.airframes__landed.u8[0] == 1
    assert v.units__kind__tag.u8[0] == FREE
    assert v.units__kind__tag.u8[4] == FREE


def test_field(snes):
    """In the field: landed on open ground at x 714 facing east, the men walk
    up under it from the base and board there too; no deck needed.
    """
    boot(snes, "MISSION_TEST_QUIET")
    snes.press("l", "down", frames=3).wait(3)
    snes.press("l", "a", frames=3).wait(20)
    snes.right(120).wait(60).down(30).wait(40).wait(1600)
    v = read_snapshot(snes)
    assert v.player__men.u8[0] == 5
    assert v.airframes__landed.u8[0] == 1
    assert v.player__on_pad.u8[0] == 0


def test_lost(state):
    """Men aboard go down with the airframe: five aboard, then a balloon (the
    neutral bunker's, at x=3072 - the player's own at 2048 lets it by) and
    the next airframe has none.
    """
    snes = state(boarded)
    snes.upright(36).right(384)
    v = read_snapshot(snes)
    assert v.player__men.u8[0] == 0
    assert v.airframes__lives.u8[0] == 3


def test_bail(state):
    """Lost a third of the band up or higher, one man bails out first: the
    balloon catches it at hover height, so a paratrooper is in the air ten
    frames on.
    """
    snes = state(boarded)
    snes.upright(36).right(384).wait(10)
    v = read_snapshot(snes)
    assert v.para_live == 1
    assert v.player__men.u8[0] == 0
    assert v.airframes__lives.u8[0] == 3


def test_crash(state):
    """A crash at the ground line from the same load drops nobody."""
    snes = state(boarded)
    snes.up(60).downright(100).wait(5)
    v = read_snapshot(snes)
    assert v.para_live == 0
    assert v.player__men.u8[0] == 0
    assert v.airframes__lives.u8[0] == 3


def test_drop(state):
    """Five drops, forty frames apart: three men reach the ground."""
    snes = state(boarded)
    snes.up(20).right(40)
    for i in range(5):
        snes.x(3).wait(40 if i < 4 else 0)
    snes.wait(140)
    v = read_snapshot(snes)
    assert v.player__men.u8[0] == 0
    assert v.units__kind__tag.u8[21] == INFANTRY
    assert v.units__kind__tag.u8[22] == INFANTRY
    assert v.units__kind__tag.u8[23] == INFANTRY
    assert v.units__kind__tag.u8[24] == FREE
    assert v.units__owner.u8[21] == PLAYER


def test_a_drop_needs_room_on_the_field(state):
    """Men on their way down count against the side's 16 units (unit.r65
    unit_side_held), so a drop with no room left is refused and the man
    stays aboard, rather than landing to stand there unhittable until
    something of his side dies. With room for one: the first X drops a
    man, the second, while he is still in the air, does not."""
    snes = state(boarded)
    snes.up(30)
    snes.write("unit_side_count", 15, 1)
    snes.x(1).wait(10).x(1).wait(10)
    v = read_snapshot(snes)
    assert v.para_live == 1
    assert v.player__men.u8[0] == 4
    assert v.unit_side_held & 0xFF == 1            # [u8; 2], the player's first


def test_engineers_board_and_rearm(snes):
    """Engineers board as infantry do and, as Armor Alley's, partially
    re-arm the airframe on the way in: half the hull, an eighth of the tank,
    a bomb and half the rounds each, capped at a full load. Two bought, the
    airframe landed on open ground ahead of them (x 664, where no deck
    refills anything), run down by hand: both board, and the load is 0+48+48
    rounds, 2 bombs, 4+10+10 hp capped at 20, 50+12+12 fuel."""
    boot(snes, "MISSION_TEST_QUIET").press("l", "down", frames=3).wait(3)
    snes.press("l", "down", frames=3).wait(3).press("l", "a", frames=3).wait(20)
    snes.right(110).wait(60).down(30).wait(40)
    snes.write("airframes__gun", 0, 1)
    snes.write("airframes__bombs", 0, 1)
    snes.write("airframes__hp", 4, 1)
    snes.write("airframes__fuel", 50, 1)
    snes.wait(200)
    v = read_snapshot(snes)
    assert v.player__on_pad.u8[0] == 0
    assert v.player__men.u8[0] == 2
    assert (v.airframes__gun.u8[0], v.airframes__bombs.u8[0]) == (96, 2)
    assert (v.airframes__hp.u8[0], v.airframes__fuel.u8[0]) == (20, 74)


def test_men_step_out_of_a_landed_airframe(state):
    """Landed, X puts a man out onto the ground ahead of the airframe - an
    infantryman at once, marching away from the pickup window - but not
    while one of ours is within a convoy space of the spot: a second X at
    once is refused, one after the first has walked clear is not."""
    snes = state(boarded)
    snes.x(3).wait(3)
    v = read_snapshot(snes)
    assert v.player__men.u8[0] == 4
    out = [v.units__x_px.u16[i] for i in range(32)
           if v.units__kind__tag.u8[i] == INFANTRY and v.units__owner.u8[i] == PLAYER]
    assert len(out) == 1
    assert 1014 + 32 <= out[0] < 1014 + 32 + 8      # put out at the right edge, walking on
    snes.x(3).wait(3)
    assert read_snapshot(snes).player__men.u8[0] == 4
    snes.wait(70).x(3).wait(3)
    assert read_snapshot(snes).player__men.u8[0] == 3

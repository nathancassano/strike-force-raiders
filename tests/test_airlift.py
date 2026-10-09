"""The airlift (design.md, decided after phase 9).

Five men are bought and the airframe lands on the player's pad facing east,
and the men walk up from the west: each boards under its middle, within 5 px
of its centre. Lifted off, X drops one per press; a chute takes ~20 frames
from this height, and a landed man is an infantryman again. The RNG is
consumed by nothing else, so from a cold boot the sequence is fixed: the
third and fourth chutes are the ones in ten that fail, so three men of five
reach the ground, in the pool slots the cursor hands out.

Most cases start from the `boarded` state (conftest.py): the men bought, the
airframe landed on the pad and all five aboard.
"""

from harness import boot, expect, shot

INFANTRY = 4


def test_board(state):
    snes = state("boarded")
    shot(snes)
    expect(snes, {"v.heli_men": 0x05, "v.heli_landed": 0x01,
                  "v.units__kind__tag.u8[0]": 0, "v.units__kind__tag.u8[4]": 0})


def test_field(snes):
    # In the field: landed on open ground at x 714 facing east, the men walk
    # up under it from the base and board there too; no deck needed.
    boot(snes, "l").press("l", "right", frames=3).wait(3).press("l", "a", frames=3).wait(20).right(120).wait(60).down(30).wait(40).wait(1600)
    shot(snes)
    expect(snes, {"v.heli_men": 0x05, "v.heli_landed": 0x01, "v.heli_on_pad": 0x00})


def test_lost(state):
    # Men aboard go down with the airframe: five aboard, then a balloon (the
    # player's own bunker's, at x=2048) and the next airframe has none.
    snes = state("boarded")
    snes.upright(36).right(220)
    shot(snes)
    expect(snes, {"v.heli_men": 0x00, "v.heli_lives": 0x03})


def test_bail(state):
    # Lost a third of the band up or higher, one man bails out first: the
    # balloon catches it at hover height, so a paratrooper is in the air ten
    # frames on.
    snes = state("boarded")
    snes.upright(36).right(220).wait(10)
    shot(snes)
    expect(snes, {"v.para_live": 0x01, "v.heli_men": 0x00, "v.heli_lives": 0x03})


def test_crash(state):
    # A crash at the ground line from the same load drops nobody.
    snes = state("boarded")
    snes.up(40).wait(60).down(80).wait(5)
    shot(snes)
    expect(snes, {"v.para_live": 0x00, "v.heli_men": 0x00, "v.heli_lives": 0x03})


def test_drop(state):
    snes = state("boarded")
    snes.up(20).right(40)
    for i in range(5):                  # five drops, forty frames apart
        snes.x(3).wait(40 if i < 4 else 0)
    snes.wait(140)
    shot(snes)
    expect(snes, {"v.heli_men": 0x00,
                  "v.units__kind__tag.u8[21]": INFANTRY, "v.units__kind__tag.u8[22]": INFANTRY,
                  "v.units__kind__tag.u8[23]": INFANTRY, "v.units__kind__tag.u8[24]": 0,
                  "v.units__owner.u8[21]": 0x00})

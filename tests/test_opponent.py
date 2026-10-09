"""Phases 9-10: win and loss, the CPU's purse, the enemy airframe and pilot."""

import pytest

from harness import boot, expect, shot

case = pytest.param
GAME_PLAYING, GAME_LOST = 0, 2


# ---- Phase 9 - win and loss ---------------------------------------------------
#
# Two ends only: a van at the other side's base, or no helicopters left. The
# van cannot be scripted from the pad in useful time - it was checked by
# planting one at the enemy base with the debugger - so these cover the other
# end and the way back. Both start from `five_passes` (conftest.py): five
# pushes into the enemy base's missiles, which lose all four airframes.

def test_game_lost(state):
    # The match ends (2 = DEFEAT) and the last airframe is not replaced.
    snes = state("five_passes")
    shot(snes)
    expect(snes, {"v.game_state": GAME_LOST, "v.heli_lives": 0x00})


def test_game_reset(state):
    # Start begins a fresh match: playing, four lives, the airframe at the
    # start, the camera at the west edge.
    snes = state("five_passes")
    snes.start().wait(10)
    shot(snes)
    expect(snes, {"v.game_state": GAME_PLAYING, "v.heli_lives": 0x04,
                  "v.heli_x_px": 0x0040, "v.camera_x": 0x0000})


# ---- Phase 10 - the CPU's purse and convoys -----------------------------------

def test_cpu_purse(snes):
    # The enemy earns as the player does, from its airframe's distance into
    # the player's half. It buys a random convoy it can afford once the last
    # has left the gate and the row's pause has run. On the quiet row the
    # first buy at frame 64 is I - five men for 5 - so by loop frame 315 the
    # purse reads 29 with no income yet, the queue is drained, and the fifth
    # man is waiting on the gate. The sequence from a cold boot is fixed by
    # the seed and the airframe's flight, so any change to the tables, the
    # pause or the pilot moves every column-dependent case.
    boot(snes, "harness").wait(300)
    shot(snes)
    expect(snes, {"v.cpu_funds": 0x1D, "s.raw('cpu_q').u8[0]": 0x03,
                  "v.cpu_head": 0x01, "v.cpu_tail": 0x01, "v.cpu_men": 0x01})


# ---- Phase 10 - the enemy airframe and its pilot ------------------------------
#
# The player's physics and loadout on its own state, and a pilot adapted from
# Armor Alley's: refit, dodge, hunt, bomb, wander, in that order. On the quiet
# row it only wanders and refits; `"harness_hot"` takes the hot one, where it hunts the
# player's airframe and bombs. foe_state: 0 wander, 1 pad, 2 dodge, 3 hunt.

@pytest.mark.parametrize("script, checks", [
    # Wander: from the far edge it flies west toward the player's end on the
    # weave (four heights, one every 64 frames); at frame 1215 it is at 4768,
    # full.
    case(lambda s: boot(s, "harness").wait(1200), {"v.foe_x_px": 0x12A0, "v.foe_hp": 0x14, "v.foe_state": 0x00,
                              "v.foe_lives": 0x04}, id="foe_patrol"),
    # The pad. Fuel drains a unit every 64 frames; low enough for the trip
    # home it turns for its own deck (x 7072), comes down, lands at ~5780 and
    # refuels and repairs before leaving full at ~6220.
    case(lambda s: boot(s, "harness").wait(6000), {"v.foe_x_px": 0x1BA3, "v.foe_y": 0x9800, "v.foe_landed": 0x01,
                              "v.foe_state": 0x01}, id="foe_pad"),
    # The player's turret at 1536 fires on it as on the player's: the wander
    # takes it through the turret's 340 px on every lap, jinking, and it
    # comes out about ten points down each time - here 10 at frame 3000, and
    # alive; the deck repairs it.
    case(lambda s: boot(s, "harness").wait(3000), {"v.foe_hp": 0x0A, "v.foe_lives": 0x04}, id="foe_turret"),
    # The player's gun. The airframe waits at x~764, where the wander's west
    # turn (900) brings the enemy into the gun's 320 px, and fires for 150
    # frames: four rounds land, a point each, and the enemy fires back on the
    # way past - it shoots whatever is level, in reach and faced.
    case(lambda s: boot(s, "harness").wait(20).right(130).wait(2400).b(150), {"v.foe_hp": 0x10, "v.foe_lives": 0x04,
                                                   "v.heli_hp": 0x11}, id="foe_gun"),
    # The hunt (hot row). Flown out to ~3100 and left hovering: the enemy,
    # hunting, arrives at a standoff, level, and fires until the player's
    # airframe is lost, then goes on to its next target with all four lives.
    case(lambda s: boot(s, "harness_hot").wait(20).right(600).wait(900), {"v.heli_lives": 0x03, "v.foe_lives": 0x04}, id="foe_hunt"),
    # Avoidance on both airframes' closing speed: the player hovers in the
    # wander's path at x 989 and the pilot steps out of its plane on every
    # pass. Counting only the player's speed, it flew into the hover and both
    # were lost by frame 1500.
    case(lambda s: boot(s, "harness").right(175).wait(1500), {"v.heli_lives": 0x04, "v.foe_lives": 0x04}, id="foe_avoid"),
    # The bombs (hot row). A bought tank marching east is found by the pilot
    # on its way in and bombed from a hover over it: by frame 3000 the slot is
    # free.
    case(lambda s: boot(s, "harness_hot").press("l", "a", frames=3).wait(3000), {"v.units__kind__tag.u8[0]": 0, "v.heli_lives": 0x04}, id="foe_bomb"),
])
def test_foe(snes, script, checks):
    script(snes)
    shot(snes)
    expect(snes, checks)

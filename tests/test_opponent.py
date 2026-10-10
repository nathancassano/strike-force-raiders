"""Phases 9-10: win and loss, the CPU's purse, the enemy airframe and pilot."""

from harness import boot, read_snapshot
from states import five_passes

GAME_PLAYING, GAME_LOST = 0, 2
FREE = 0                                    # an empty unit slot's kind


# ---- Phase 9 - win and loss ---------------------------------------------------
#
# Two ends only: a van at the other side's base, or no helicopters left. The
# van cannot be scripted from the pad in useful time - it was checked by
# planting one at the enemy base with the debugger - so these cover the other
# end and the way back. Both start from `five_passes` (states.py): five
# pushes into the enemy base's missiles, which lose all four airframes.

def test_game_lost(state):
    """The match ends in defeat and the last airframe is not replaced."""
    snes = state(five_passes)
    v = read_snapshot(snes)
    assert v.game_state == GAME_LOST
    assert v.heli_lives == 0


def test_game_reset(state):
    """Start begins a fresh match: playing, four lives, the airframe at the
    start, the camera at the west edge.
    """
    snes = state(five_passes)
    snes.start().wait(10)
    v = read_snapshot(snes)
    assert v.game_state == GAME_PLAYING
    assert v.heli_lives == 4
    assert v.heli_x_px == 64
    assert v.camera_x == 0


# ---- Phase 10 - the CPU's purse and convoys -----------------------------------

def test_cpu_purse(snes):
    """The enemy earns as the player does, from its airframe's distance into
    the player's half.

    It buys a random convoy it can afford once the last has left the gate and
    the row's pause has run. On the quiet row the first buy at frame 64 is I -
    five men for 5 - so by loop frame 315 the purse reads 29 with no income
    yet, the queue is drained, and the fifth man is waiting on the gate. The
    sequence from a cold boot is fixed by the seed and the airframe's flight,
    so any change to the tables, the pause or the pilot moves every
    column-dependent case.
    """
    boot(snes, "MISSION_TEST_QUIET").wait(300)
    v = read_snapshot(snes)
    assert v.cpu_funds == 29
    assert v.cpu_q.u8[0] == 3
    assert v.cpu_head == 1
    assert v.cpu_tail == 1
    assert v.cpu_men == 1


# ---- Phase 10 - the enemy airframe and its pilot ------------------------------
#
# The player's physics and loadout on its own state, and a pilot adapted from
# Armor Alley's: refit, dodge, hunt, bomb, wander, in that order. On the quiet
# row (MISSION_TEST_QUIET) it only wanders and refits; the hunter row
# (MISSION_TEST_HUNTER) hunts the player's airframe and bombs.

def test_the_hot_pilot_hunts_the_player(snes):
    """Flown out to ~3100 and left hovering: the enemy, hunting, arrives at a
    standoff, level, and fires until the player's airframe is lost, then goes
    on to its next target with all four lives.
    """
    boot(snes, "MISSION_TEST_HUNTER").wait(20).right(600).wait(900)
    v = read_snapshot(snes)
    assert v.heli_lives == 3
    assert v.foe_lives == 4


def test_the_pilot_steps_out_of_a_hover(snes):
    """Avoidance on both airframes' closing speed: the player hovers in the
    wander's path at x 989 and the pilot steps out of its plane on every pass.

    Counting only the player's speed, it flew into the hover and both were
    lost by frame 1500.
    """
    boot(snes, "MISSION_TEST_QUIET").right(175).wait(1500)
    v = read_snapshot(snes)
    assert v.heli_lives == 4
    assert v.foe_lives == 4


def test_the_hot_pilot_bombs_a_tank(snes):
    """A bought tank marching east is found by the pilot on its way in and
    bombed from a hover over it: by frame 3000 the slot is free.
    """
    boot(snes, "MISSION_TEST_HUNTER").press("l", "a", frames=3).wait(3000)
    v = read_snapshot(snes)
    assert v.units__kind__tag.u8[0] == FREE
    assert v.heli_lives == 4

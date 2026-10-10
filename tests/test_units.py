"""Phase 6: ground units - the pool, the march, traffic, the frame budget.

The player's base sends only what is ordered (phase 7); the enemy's sends the
CPU's convoys (phase 10). On the quiet row (MISSION_TEST_QUIET) the first
buy, at frame 64, is I - five men - so the first unit out is an infantryman
marching west from x=7680; the pool is a tagged enum, so slot 0's kind is its tag. Every unit
walks half a pixel a frame - a pixel on each odd frame - so at loop frame
615 (a wait of 600 plus the movie's lead-in) he is at 7405. `tools/poolstat.py
--brief` on a WRAM dump shows the column's shape at any frame; every figure
below came from that.

Kinds: 0 free, 1 tank, 2 van, 3 launcher, 4 infantry, 5 engineer.
"""

from shared import boot, eight_tanks, read_snapshot

TANK, VAN, LAUNCHER, INFANTRY, ENGINEER = 1, 2, 3, 4, 5
PLAYER, ENEMY = 0, 1


def test_the_enemys_first_unit_is_an_infantryman(snes):
    boot(snes, "MISSION_TEST_QUIET").wait(200)
    v = read_snapshot(snes)
    assert v.units__kind__tag.u8[0] == INFANTRY
    assert v.units__owner.u8[0] == ENEMY


def test_infantry_march_half_a_pixel_a_frame(snes):
    boot(snes, "MISSION_TEST_QUIET").wait(600)
    v = read_snapshot(snes)
    assert v.units__x_px.u16[0] == 7405


def test_each_kind_takes_its_hit_points_from_unit_stats(snes):
    """A spawn order becomes a variant, and the hit points come from that
    variant's row of unit_stats.

    The hunter row (MISSION_TEST_HUNTER) buys IMEV and nothing else - five
    men, a missile truck, two engineers and a van - so by frame 2400 the column is
    one of every kind but the tank; the launcher's payload is `armed`, 1 until
    it fires.
    """
    boot(snes, "MISSION_TEST_HUNTER").wait(2401)
    v = read_snapshot(snes)
    assert v.units__kind__tag.u8[0] == INFANTRY
    assert v.units__hp.u8[0] == 5
    assert v.units__kind__tag.u8[5] == LAUNCHER
    assert v.units__hp.u8[5] == 8
    assert v.units__kind__Launcher__armed.u8[5] == 1
    assert v.units__kind__tag.u8[6] == ENGINEER
    assert v.units__hp.u8[6] == 5
    assert v.units__kind__tag.u8[8] == VAN
    assert v.units__hp.u8[8] == 12


def test_a_column_packs_up_behind_a_halted_lead(snes):
    """March order (phase 10). One speed for every unit means nothing
    overtakes, so each side's column is a list from its lead back, and a
    follower halts only behind a halted unit ahead.

    Three bought tanks (slots 0, 2, 4) cross the field a convoy space apart;
    the lead holds 117 px short of the bunker at 5120 to shell it, and the two
    behind pack up at exactly width + gap (31 px) and halt in turn - every
    flag set. The column is halted from frame 10000 to past 10600, so the wait
    sits mid-window, where a faster or slower loop does not move the snapshot
    before the column has arrived.
    """
    boot(snes, "MISSION_TEST_QUIET")
    snes.press("l", "a", frames=3).wait(3)
    snes.press("l", "a", frames=3).wait(3)
    snes.press("l", "a", frames=3).wait(10200)
    v = read_snapshot(snes)
    assert v.units__block.u8[0] == 1
    assert v.units__x_px.u16[0] == 5003
    assert v.units__block.u8[2] == 1
    assert v.units__x_px.u16[2] == 4972
    assert v.units__block.u8[4] == 1
    assert v.units__x_px.u16[4] == 4941


def test_unit_budget(state):
    """Frame budget. The NMI counts real frames and the loop counts ticks it
    finished; a full field must still keep up.

    The opening buys the whole purse in tanks so the player's half is there to
    meet the enemy column, and by the snapshot all 32 slots are live. The pair
    is pinned exactly: this run sits on the budget line, so any change to
    per-frame cost moves frames_loop. Its history - what each feature cost -
    is in the comment on this case in the retired tests/run.sh (git history);
    the ratio is now 0.835.
    """
    snes = state(eight_tanks)
    v = read_snapshot(snes)
    assert v.frames_nmi == 3664
    assert v.frames_loop == 3061

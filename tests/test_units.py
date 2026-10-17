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
    flag set. The column is halted from frame 9050 to past 9800 (10000 to
    10600 before FastROM: a faster loop shells the bunker down sooner), so
    the wait sits mid-window, where a faster or slower loop does not move the
    snapshot before the column has arrived.
    """
    boot(snes, "MISSION_TEST_QUIET")
    snes.press("l", "a", frames=3).wait(3)
    snes.press("l", "a", frames=3).wait(3)
    snes.press("l", "a", frames=3).wait(9450)
    v = read_snapshot(snes)
    assert v.units__block.u8[0] == 1
    assert v.units__x_px.u16[0] == 5003
    assert v.units__block.u8[2] == 1
    assert v.units__x_px.u16[2] == 4972
    assert v.units__block.u8[4] == 1
    assert v.units__x_px.u16[4] == 4941


def test_a_man_killed_lies_where_he_fell(snes):
    """A bomb on the quiet row's first infantryman leaves him down for two
    seconds: an FX_MAN effect (fx.r65), tile 76 in the enemy palette and
    mirrored, a hair east of where he stood (his centre, x + 5, less 8).
    """
    boot(snes, "MISSION_TEST_QUIET").wait(200)
    snes.write("airframes__x_px", snes.raw("units__x_px").u16[0] - 40, 2)
    snes.wait(90).a(4).wait(30)
    v = read_snapshot(snes)
    assert v.fx_kind.u8[3] == 3
    assert v.fx_attr.u16[3] == 0x724C          # hflip, priority 3, enemy palette, tile 76
    assert v.fx_x.u16[3] == 7578


# ---- ramming ------------------------------------------------------------------
#
# An airframe flown into the other side's vehicle is lost, and takes the
# vehicle with it (unit_ram, the remake's rule). The quiet row fields only
# men, so slot 0 - its first infantryman, at x 6200 by frame 3000 - is
# turned into a van, and the airframe planted on him at landed height
# (HELI_Y_MAX, 168).

def test_flying_into_an_enemy_van_loses_both(snes):
    boot(snes, "MISSION_TEST_QUIET").wait(3000)
    snes.write("units__kind__tag", VAN, 1)
    snes.write("units__hp", 12, 1)
    snes.write("airframes__x_px", snes.raw("units__x_px").u16[0] - 4, 2)
    snes.write("airframes__y", 168 * 256, 2)
    snes.wait(2)
    v = read_snapshot(snes)
    assert v.units__kind__tag.u8[0] == 0
    assert v.units__kind__tag.u8[1] == INFANTRY      # the man behind, 32 px back, untouched
    assert v.airframes__lives.u8[0] == 3


def test_a_man_is_not_rammed(snes):
    """Men are flown over and landed among - that is the airlift - so the
    same plant on the quiet row's first infantryman, left a man, costs
    nothing."""
    boot(snes, "MISSION_TEST_QUIET").wait(3000)
    snes.write("airframes__x_px", snes.raw("units__x_px").u16[0] - 4, 2)
    snes.write("airframes__y", 168 * 256, 2)
    snes.wait(2)
    v = read_snapshot(snes)
    assert v.units__kind__tag.u8[0] == INFANTRY
    assert v.airframes__lives.u8[0] == 4


def test_unit_budget(state):
    """Frame budget. The NMI counts real frames and the loop counts ticks it
    finished; a full field must still keep up.

    The opening buys the whole purse in tanks so the player's half is there to
    meet the enemy column, and by the snapshot all 32 slots are live. The pair
    is pinned exactly: this run sits on the budget line, so any change to
    per-frame cost moves frames_loop. Its history - what each feature cost -
    is in the comment on this case in the retired tests/run.sh (git history);
    the ratio is now 0.813: moving the ground line to 184 lengthened a lofted
    round's climb to the top edge by 16 px (0.836), and Mode 1's sky split
    is a second HDMA channel, which costs CPU time on every line it runs
    (0.831). The last step is not a cost: the clouds' art made the boot's
    upload a frame longer, and a minute of this run from a boot one frame
    later is a different battle - the same code with the old sky art still
    gives 3664/3043. So a change to boot length moves this pin too. Then
    the rotor (0.807): one effect queued and sent every 4 frames is ~50
    cycles a frame on average, and on the budget line that drops 21 ticks
    a minute; without it the run gives 2976. The explosions and smoke
    (src/fx.r65) cost one more (2954): their pool is skipped from main
    while empty - called idle every frame it cost ten. A bomb landing on a
    vehicle now goes off rather than vanishing on its roof, which is a
    different battle at the same ratio (3662/2953, from 3663/2954). The
    missile alarm's per-frame check costs two ticks (3663/2951), and the
    enemy airframe's wreck - its two per-frame gates, and the burst where
    it lands - two more (3662/2949). The wrecks' drift as they fall
    gives one back (3662/2950): it keeps half the airframe's speed rather
    than decaying it, which was a far call to approach() each frame of a
    fall. Then 21 ticks faster (3663/2971): the two airframes became one
    #[soa] pool whose per-frame methods are inlined at their constant
    element and folded to absolute addressing (R65's const_index pass),
    leaving no call at all where each side used to call its own copy.
    The enemy's paratrooper steering - off on this test mission - moved
    the layout a tick (3662/2970), and the bank raid's checks in the
    pilot's decisions - off here too - four more (3662/2966). Then
    FastROM, 0.81 -> 0.96 (3663/3529): code and ROM tables read from the
    $80-$BF mirror at 6 master clocks a byte rather than 8. Then 39 ticks
    faster (3662/3568): R65 keeps an unsigned u8 -> u16 widening in A
    rather than spilling it through the stack. Then 73 more (3662/3641):
    R65 records a branch's CFG edge from the block that really jumps, which
    lets loop register promotion keep more counters in X/Y. Then the alert
    avatar, 11 slower (3662/3630): idle it costs nothing (measured with
    every push suppressed), but the opponent's five ENEMY CONVOY alerts
    keep the portrait's four sprites and the queue's tick up for a quarter
    of the run. Then 10 faster (3662/3640) on R65's 10-14/15 codegen fixes,
    measured apart from boot_load's NMITIMEN write that went in with them.
    Then 1 slower (3662/3639) for the airframes' lean following the stick,
    a counter stepped each frame for both. Then 1 slower (3662/3638) for the
    order menu's icons: the eight purchases show and hide the taller menu,
    and the alert box goes up a row at a time, clear of the menu's columns.
    Then 12 faster (3662/3650): ENEMY CONVOY is announced for the first
    convoy only, so the run's other four no longer bring the portrait up -
    less one for unit_spawn counting the men on their way down (measured
    3637 before the convoy change). Then 1 slower (3662/3649): the balloons'
    chains are tested at hover height too, on alternate frames (every
    frame cost 5). Then 2 faster (3662/3651): the tanks last half as long
    again (a fuel unit per 96 frames), which moves the enemy airframe's trips
    home to refit. Then 3 faster (3662/3654) on R65 folding a constant index
    offset into the address (`radar_buf[i + 1]` as `radar_buf+1,X`), the
    radar base's 256-pass rebuild among them.
    """
    snes = state(eight_tanks)
    v = read_snapshot(snes)
    assert v.frames_nmi == 3662
    assert v.frames_loop == 3654

"""Phase 6: ground units - the pool, the march, traffic, the frame budget.

The player's base sends only what is ordered (phase 7); the enemy's sends the
CPU's convoys (phase 10). On the quiet row (`"harness"`) the first buy, at frame 64,
is I - five men - so the first unit out is an infantryman marching west from
x=7680; the pool is a tagged enum, so slot 0's kind is its tag. Every unit
walks half a pixel a frame - a pixel on each odd frame - so at loop frame
615 (a wait of 600 plus the movie's lead-in) he is at 7405. `tools/poolstat.py
--brief` on a WRAM dump shows the column's shape at any frame; every figure
below came from that.

Kinds: 0 free, 1 tank, 2 van, 3 launcher, 4 infantry, 5 engineer.
"""

import pytest

from harness import boot, expect, shot, tool

case = pytest.param
TANK, VAN, LAUNCHER, INFANTRY, ENGINEER = 1, 2, 3, 4, 5


@pytest.mark.parametrize("script, checks", [
    case(lambda s: boot(s, "harness").wait(200), {"v.units__kind__tag.u8[0]": INFANTRY, "v.units__owner.u8[0]": 0x01}, id="unit_spawn"),
    case(lambda s: boot(s, "harness").wait(600), {"v.units__x_px.u16[0]": 0x1CED}, id="unit_march"),
    # A spawn order becomes a variant, and the hit points come from that
    # variant's row of unit_stats. The hot row ("harness_hot") buys IMEV and nothing
    # else - five men, a missile truck, two engineers and a van - so by frame
    # 2400 the column is one of every kind but the tank; the launcher's
    # payload is `armed`, 1 until it fires. (The tank is tank_crush's.)
    case(lambda s: boot(s, "harness_hot").wait(2401), {
        "v.units__kind__tag.u8[0]": INFANTRY, "v.units__hp.u8[0]": 0x05,
        "v.units__kind__tag.u8[5]": LAUNCHER, "v.units__hp.u8[5]": 0x08, "v.units__kind__Launcher__armed.u8[5]": 0x01,
        "v.units__kind__tag.u8[6]": ENGINEER, "v.units__hp.u8[6]": 0x05,
        "v.units__kind__tag.u8[8]": VAN, "v.units__hp.u8[8]": 0x0C,
    }, id="unit_kinds"),
    # March order (phase 10). One speed for every unit means nothing
    # overtakes, so each side's column is a list from its lead back, and a
    # follower halts only behind a halted unit ahead. Three bought tanks
    # (slots 0, 2, 4) cross the field a convoy space apart; the lead holds
    # 117 px short of the bunker at 5120 to shell it, and the two behind pack
    # up at exactly width + gap (31 px) and halt in turn - every flag set.
    # The column is halted from wait10000 to past wait10600, so the wait sits
    # mid-window, where a faster or slower loop does not move the snapshot
    # before the column has arrived.
    case(lambda s: boot(s, "harness").press("l", "a", frames=3).wait(3).press("l", "a", frames=3).wait(3).press("l", "a", frames=3).wait(10200), {
        "v.units__block.u8[0]": 0x01, "v.units__x_px.u16[0]": 0x138B,
        "v.units__block.u8[2]": 0x01, "v.units__x_px.u16[2]": 0x136C,
        "v.units__block.u8[4]": 0x01, "v.units__x_px.u16[4]": 0x134D,
    }, id="march_order"),
])
def test_units(snes, script, checks):
    script(snes)
    shot(snes)
    expect(snes, checks)


def test_unit_budget(state):
    # Frame budget. The NMI counts real frames and the loop counts ticks it
    # finished; a full field must still keep up. The opening buys the whole
    # purse in tanks so the player's half is there to meet the enemy column,
    # and by the snapshot all 32 slots are live. The pair is pinned exactly:
    # this movie sits on the budget line, so any change to per-frame cost
    # moves frames_loop. Its history - what each feature cost - is in
    # run.sh's comment on this case; the ratio is now 0.835.
    snes = state("eight_tanks")
    shot(snes)
    expect(snes, {"v.frames_nmi": 0x0E50, "v.frames_loop": 0x0BF5})


def test_unit_oam(state, tmp_path):
    # The headline constraint: at a bunched column the PPU must still be able
    # to draw everything standing on those scanlines - 32 sprites and 34
    # tiles a line. The sprite budget, not the CPU, is what a bigger front
    # runs into.
    snes = state("eight_tanks")
    snes.right(520).wait(60)
    shot(snes)
    oam = tmp_path / "oam.bin"
    snes.dump("oam", oam)
    tool("oamstat.py", oam)

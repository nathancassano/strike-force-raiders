"""Phase 7: economy and ordering.

Funds grow with the helicopter's distance from the west edge; with L held,
Left/Right walk the order ring and A buys. Every check is on the ROM's own
state: the purse, the selection, and what came out of the base.
"""

from shared import boot, read_snapshot

TANK, VAN, INFANTRY = 1, 2, 4


def seven_vans(s):
    """Seven van orders, three frames apart; the seventh is over the cap."""
    for i in range(7):
        s.press("l", "a", frames=3).wait(3 if i < 6 else 0)
    return s


def test_the_opening_purse_and_selection(snes):
    """32 funds, the tank selected, four lives."""
    boot(snes, "MISSION_TEST_QUIET").wait(60)
    v = read_snapshot(snes)
    assert v.funds == 32
    assert v.order_sel == 2
    assert v.heli_lives == 4


def test_one_press_buys_one_tank(snes):
    """It comes out of the player's base at x=512 marching east, and the cost
    comes off at once.
    """
    boot(snes, "MISSION_TEST_QUIET").press("l", "a", frames=3).wait(30)
    v = read_snapshot(snes)
    assert v.funds == 28
    assert v.units__kind__tag.u8[0] == TANK
    assert v.units__owner.u8[0] == 0
    assert v.units__x_px.u16[0] == 529


def test_infantry_leave_the_gate_one_at_a_time(snes):
    """Right moves the ring to infantry; one order is five men.

    The gate lets the next out only when the last is a convoy space (32 px,
    64 frames at a man's half pixel a frame) clear of it: 40 frames on, one
    is on the field and four still wait in the emitter. (It used to look at
    60, a frame or two short of the second man - on the edge, so a boot one
    frame longer let him out.)
    """
    boot(snes, "MISSION_TEST_QUIET")
    snes.press("l", "right", frames=3).wait(3)
    snes.press("l", "a", frames=3).wait(40)
    v = read_snapshot(snes)
    assert v.funds == 27
    assert v.units__kind__tag.u8[0] == INFANTRY
    assert v.order_men == 4


def test_the_seventh_van_is_refused(snes):
    """Left twice wraps to the van. Its cap is six, counted on the field and
    in the queue: the seventh press is refused and costs nothing, so the
    purse is 32 - 6*2, and the first van is out.
    """
    boot(snes, "MISSION_TEST_QUIET")
    snes.press("l", "left", frames=3).wait(3)
    snes.press("l", "left", frames=3).wait(3)
    seven_vans(snes).wait(80)
    v = read_snapshot(snes)
    assert v.funds == 20
    assert v.order_sel == 0
    assert v.units__kind__tag.u8[0] == VAN


def test_buying_a_helicopter_adds_a_life(snes):
    """Right three times from the tank is the helicopter: an extra life for 20."""
    boot(snes, "MISSION_TEST_QUIET")
    for _ in range(3):
        snes.press("l", "right", frames=3).wait(3)
    snes.press("l", "a", frames=3).wait(10)
    v = read_snapshot(snes)
    assert v.funds == 12
    assert v.heli_lives == 5
    assert v.order_sel == 5

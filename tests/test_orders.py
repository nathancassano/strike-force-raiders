"""Phase 7: economy and ordering.

Funds grow with the helicopter's distance from the west edge; with L held,
Left/Right walk the order ring and A buys. Every check is on the ROM's own
state: the purse, the selection, and what came out of the base.
"""

import pytest

from harness import boot, expect, shot

case = pytest.param
TANK, VAN, INFANTRY = 1, 2, 4


def seven_vans(s):
    """Seven van orders, three frames apart; the seventh is over the cap."""
    for i in range(7):
        s.press("l", "a", frames=3).wait(3 if i < 6 else 0)
    return s


@pytest.mark.parametrize("script, checks", [
    # 32 funds, the tank selected, four lives.
    case(lambda s: boot(s, "l").wait(60), {"v.funds": 0x20, "v.order_sel": 0x02, "v.heli_lives": 0x04}, id="order_boot"),
    # One press buys one tank: it comes out of the player's base at x=512
    # marching east, and the cost comes off at once.
    case(lambda s: boot(s, "l").press("l", "a", frames=3).wait(30), {"v.funds": 0x1C, "v.units__kind__tag.u8[0]": TANK,
                                 "v.units__owner.u8[0]": 0x00, "v.units__x_px.u16[0]": 0x0211}, id="order_tank"),
    # Right moves the ring to infantry; one order is five men, and the gate
    # lets the next out only when the last is a convoy space (32 px, 128
    # frames at a man's pace) clear of it: a minute in, one is on the field
    # and four still wait in the emitter.
    case(lambda s: boot(s, "l").press("l", "right", frames=3).wait(3).press("l", "a", frames=3).wait(60),
         {"v.funds": 0x1B, "v.units__kind__tag.u8[0]": INFANTRY, "v.order_men": 0x04}, id="order_infantry"),
    # Left twice wraps to the van. Its cap is six, counted on the field and
    # in the queue: the seventh press is refused and costs nothing, so the
    # purse is 32 - 6*2, and the first van is out.
    case(lambda s: seven_vans(boot(s, "l").press("l", "left", frames=3).wait(3)
                              .press("l", "left", frames=3).wait(3)).wait(80),
         {"v.funds": 0x14, "v.order_sel": 0x00, "v.units__kind__tag.u8[0]": VAN}, id="order_cap"),
    # Right three times from the tank is the helicopter: an extra life for 20.
    case(lambda s: boot(s, "l").press("l", "right", frames=3).wait(3).press("l", "right", frames=3).wait(3).press("l", "right", frames=3).wait(3).press("l", "a", frames=3).wait(10),
         {"v.funds": 0x0C, "v.heli_lives": 0x05, "v.order_sel": 0x05}, id="order_heli"),
    # Income. A push to the far end and a wait there pays out; the exact
    # figure is the threshold's - and the no-fly zone's: the enemy base's
    # missiles send the airframe home part way.
    case(lambda s: boot(s, "l").right(1500).wait(300), {"v.funds": 0x2A}, id="econ_income"),
])
def test_orders(snes, script, checks):
    script(snes)
    shot(snes)
    expect(snes, checks)

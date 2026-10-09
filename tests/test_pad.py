"""Phase 5: landing pad, rearm and fuel.

The player's deck spans world x 1024..1071, so the airframe's centre has to
be inside it - x 1008..1055 - when it touches the floor. Since the airlift a
powered descent lands anywhere on the ground; only a deck rearms
(heli_on_pad). Touching down faster than HELI_CRASH_VY (2.5 px/frame) is a
crash, so every landing here eases off: 30 frames of Down from hover height
and a coast arrives under it; 32 does not, and a full-stick descent hits at
4. right180 and a 60-frame coast puts the airframe at x 1014.
"""

import pytest

from harness import boot, expect, shot

case = pytest.param


@pytest.mark.parametrize("script, checks", [
    # Descending onto the deck lands on it; stopping short (x 714) or
    # overshooting (x 1314) lands on open ground - down, but no deck.
    case(lambda s: boot(s, "direct").wait(20).right(180).wait(60).down(30).wait(40),
         {"v.heli_landed": 0x01, "v.heli_on_pad": 0x01}, id="pad_land"),
    case(lambda s: boot(s, "direct").wait(20).right(120).wait(60).down(30).wait(40),
         {"v.heli_landed": 0x01, "v.heli_on_pad": 0x00, "v.heli_y": 0x9800}, id="pad_short"),
    case(lambda s: boot(s, "direct").wait(20).right(240).wait(60).down(30).wait(40),
         {"v.heli_landed": 0x01, "v.heli_on_pad": 0x00}, id="pad_over"),
    # A landed airframe does not slide: down at the start, then held right
    # for 190 frames, it is still at x 64 on open ground, not on the deck.
    case(lambda s: boot(s, "direct").wait(20).down(30).wait(40).right(190),
         {"v.heli_landed": 0x01, "v.heli_on_pad": 0x00, "v.heli_x_px": 0x0040}, id="pad_slide"),
    case(lambda s: boot(s, "direct").wait(20).right(180).wait(60).down(30).wait(40).up(20),
         {"v.heli_landed": 0x00}, id="pad_takeoff"),
    # Too fast: a full-stick descent onto the deck is a crash - a life gone.
    case(lambda s: boot(s, "direct").wait(20).right(180).wait(60).down(80),
         {"v.heli_lives": 0x03, "v.heli_landed": 0x00}, id="pad_crash"),
    # Full rearm: fuel back to 100, and the reload countdowns give back
    # rounds at 20 frames each and bombs at 10 while the airframe sits.
    case(lambda s: boot(s, "harness").wait(20).b(60).a(1).right(180).wait(60).down(30).wait(40).wait(120),
         {"v.heli_landed": 0x01, "v.heli_fuel": 0x64, "v.heli_gun": 0x3D, "v.heli_bombs": 0x0A},
         id="pad_rearm"),
    # One unit per 64 frames aloft.
    case(lambda s: boot(s, "harness").wait(20).right(240), {"v.heli_fuel": 0x60}, id="fuel_burn"),
    # Dry tank: gravity is allowed in exactly one place, and this is it. The
    # airframe sinks with no input, and open ground is not a deck: touching
    # it on a dead stick is a crash landing - a life gone, and by 7200
    # frames the next airframe is up at hover height.
    case(lambda s: boot(s, "harness").wait(7200),
         {"v.heli_lives": 0x03, "v.heli_y": 0x6000, "v.heli_landed": 0x00}, id="fuel_dry"),
])
def test_pad(snes, script, checks):
    script(snes)
    shot(snes)
    expect(snes, checks)

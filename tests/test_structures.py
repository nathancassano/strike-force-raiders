"""Phase 8: structures - turrets, balloons, bunkers, the bases' missiles.

Fifteen buildings from the level table. Turrets fire at the other side's
units and, if the enemy's, at the helicopter; gunfire wears them down.
`structs` is a #[soa] pool in west-to-east order, so `structs[9]` is level
entry 9.
"""

import pytest

from harness import boot, expect, screen_colour, shot

case = pytest.param
TANK, LAUNCHER, INFANTRY = 1, 3, 4
MUNI_MISSILE = 5
CANOPY = (14, 22, 28)          # the airframe's canopy, BGR555 components


# ---- the enemy turret at x=6656 (level entry 12) ----------------------------

def test_turret_heli(state):
    # It lofts rounds at an approaching airframe: 20 hp becomes 17 on the way
    # in (15 before the enemy airframe took the player's inertia).
    snes = state("at_turret")
    snes.wait(90)
    shot(snes)
    expect(snes, {"v.heli_hp": 0x11})


def test_turret_gunfire(state):
    # Land in front of it and fire back: a round is a point off its 62 -
    # three of the fifteen fired land in this time (the rest are in flight or
    # lost to its self-repair between), and its fire keeps coming. How many
    # have landed by this frame is a phase; re-baseline it if a change shifts
    # the run by a frame, but do not delete it.
    snes = state("at_turret")
    snes.down(30).wait(40).b(90)
    shot(snes)
    expect(snes, {"v.structs__hp.u8[12]": 0x3B, "v.heli_hp": 0x10})


# ---- the balloon over the player's own bunker (x=2048) ----------------------
#
# It kills the airframe on contact at frame 421 of this climb: a life gone, the
# airframe back at the start but hidden for HELI_RESPAWN (120) frames, and the
# camera - 1945 at the loss - panning home at 1945/120+1 = 17 px a frame on top
# of the follow's 6. Sixty frames on it is 565 and the canopy is nowhere on
# screen; at 120 the view is home and the next airframe starts rising out of
# the ground at a pixel a frame from the ground line (168) to hover height (96),
# behind the dirt, the stick dead meanwhile; at 192 it is there and the stick
# works again: ten frames of thrust from rest is 13 px.

def test_balloon_kill(state):
    snes = state("balloon_hit")
    shot(snes)
    expect(snes, {"v.heli_lives": 0x03, "v.heli_x_px": 0x0040, "v.heli_dead": 0x78,
                  "v.camera_x": 0x0799})


def test_balloon_pan(state, tmp_path):
    snes = state("balloon_hit")
    snes.wait(60)
    shot(snes)
    expect(snes, {"v.heli_x_px": 0x0040, "v.heli_dead": 0x3C, "v.camera_x": 0x0235})
    assert screen_colour(snes, tmp_path, CANOPY, snes_colour=True) == 0


def test_balloon_rise(state):
    snes = state("balloon_hit")
    snes.wait(120).right(10)
    shot(snes)
    expect(snes, {"v.heli_x_px": 0x0040, "v.heli_dead": 0x00, "v.heli_rising": 0x01,
                  "v.heli_y": 0x9E00, "v.camera_x": 0x0000})


def test_balloon_respawn(state, tmp_path):
    snes = state("balloon_hit")
    snes.wait(192).right(10)
    shot(snes)
    expect(snes, {"v.heli_x_px": 0x004D, "v.heli_rising": 0x00, "v.heli_y": 0x6000})
    assert screen_colour(snes, tmp_path, CANOPY, snes_colour=True) >= 0.02


# ---- long field cases ---------------------------------------------------------

@pytest.mark.parametrize("script, checks", [
    # An enemy infantryman walking into the neutral bunker at x=5120 (level
    # entry 9) takes it and is spent doing so. The CPU's first man is out at
    # frame 64 and covers 2560 px at half a pixel a frame: by 5300 the bunker
    # is the enemy's and slot 0 is free.
    case(lambda s: boot(s, "l").wait(5300), {"v.structs__owner.u8[9]": 0x01, "v.units__kind__tag.u8[0]": 0}, id="bunker_capture"),
    # Tanks shell the other side's turrets and bunkers, holding in place until
    # the building falls. Two bought tanks crush the column's men at the front
    # around frame 7400 (tank_crush), take its first tank between them, and
    # roll on to the bunker at 5120 - the enemy's since ~5250 - hold short of
    # it and bring its 69 hp down at 8 a shell, one every 90 frames: by 10600
    # it is rubble and nobody's.
    case(lambda s: boot(s, "l").press("l", "a", frames=3).wait(3).press("l", "a", frames=3).wait(10600),
         {"v.structs__hp.u8[9]": 0x00, "v.structs__owner.u8[9]": 0x02}, id="tank_bunker"),
    # Infantry gunfire: no round, the sweep that finds a target lands the hit.
    # Five men are ordered (the CPU's first man takes slot 0 at frame 64, so
    # they are slots 2, 4, 6, 8 and 9); they meet the column's leading men at
    # x~4100 around loop frame 7210. A hundred frames on, the exchange has
    # gone both ways: the player's first two men (2, 4) and the enemy's first
    # (3) are gone, and the pair now facing each other - the enemy's 5 and the
    # player's 6 - are down to their last point, with 7 and 8 untouched behind
    # them. The meeting drifts with every heavier build; re-measure when it
    # moves.
    case(lambda s: boot(s, "l").press("l", "right", frames=3).wait(3).press("l", "a", frames=3).wait(8200), {
        "v.units__kind__tag.u8[2]": 0, "v.units__kind__tag.u8[3]": 0, "v.units__kind__tag.u8[4]": 0,
        "v.units__hp.u8[5]": 0x01, "v.units__hp.u8[6]": 0x01, "v.units__hp.u8[7]": 0x05, "v.units__hp.u8[8]": 0x05,
    }, id="rifle_fire"),
    # ... and a tank does not stop for the other side's men: it drives over
    # them. A bought tank (slot 0) meets the column at x~4190 around loop
    # frame 7300 and has rolled through its five leading men a hundred frames
    # later - slots 1-5 free, the tank untouched - while the next squad's
    # first man (slot 6) is 200 px ahead of it. Its gun reload cycles 16..0
    # with nothing in range - a phase; re-baseline it, but do not delete it.
    case(lambda s: boot(s, "l").press("l", "a", frames=3).wait(7492), {
        "v.units__kind__tag.u8[1]": 0, "v.units__kind__tag.u8[2]": 0, "v.units__kind__tag.u8[3]": 0,
        "v.units__kind__tag.u8[4]": 0, "v.units__kind__tag.u8[5]": 0, "v.units__hp.u8[0]": 0x19,
        "v.units__kind__tag.u8[6]": INFANTRY, "v.units__x_px.u16[6]": 0x1137,
        "v.units__kind__Tank__reload.u8[0]": 0x10,
    }, id="tank_crush"),
    # The enemy base's missiles: an airframe pushed into its 320 px is lost
    # inside two hundred frames and comes back at the start with a life gone.
    # The push is held to 1520 vblanks: at 1500 the run coasts to a stop just
    # outside.
    case(lambda s: boot(s, "l").wait(20).right(1520).wait(300), {"v.heli_lives": 0x03, "v.heli_hp": 0x14}, id="base_missile"),
    # The enemy column's launcher fires its one homing missile at an airframe
    # inside LAUNCHER_RANGE (224 px) and is spent doing so: the slot is free,
    # the missile lands for 10 of the 20 hp, and no life is lost. The third
    # harness row (@l+r) buys MIVV, so the truck is the column's lead and slot
    # 0, and its pilot hunts nothing, so the airframe can cross the field.
    case(lambda s: boot(s, "l", "r").wait(20).up(40).right(1400).wait(120),
         {"v.units__kind__tag.u8[0]": 0, "v.heli_hp": 0x0A, "v.heli_lives": 0x04}, id="launcher_fire"),
    # Only one missile truck of a side fires at a time. Two bought launchers
    # (slots 0 and 2) march east 32 px apart and the enemy airframe's wander
    # passes over both at x~1850 around loop frame 2280: the lead fires - its
    # slot free, its missile up - and the second, inside the 224 px too,
    # holds, still armed, until that missile is spent.
    case(lambda s: boot(s, "l").press("l", "left", frames=3).wait(3).press("l", "a", frames=3).wait(3).press("l", "a", frames=3).wait(2262), {
        "v.units__kind__tag.u8[0]": 0, "v.units__kind__tag.u8[2]": LAUNCHER, "v.units__kind__Launcher__armed.u8[2]": 0x01,
        "s.raw('muni_kind').u8[5]": MUNI_MISSILE,
    }, id="launcher_one"),
    # The super bunker (level entry 7, dead centre) starts empty and nobody's.
    # The CPU's first squad walks the field - its first man spent on the
    # bunker at 5120 - and the other four, with the first man of the next
    # squad, go inside one after another from frame ~7300: five men, full,
    # and it is the enemy's.
    case(lambda s: boot(s, "l").wait(8200), {"v.structs__men.u8[7]": 0x05, "v.structs__owner.u8[7]": 0x01}, id="super_manned"),
])
def test_field(snes, script, checks):
    script(snes)
    shot(snes)
    expect(snes, checks)

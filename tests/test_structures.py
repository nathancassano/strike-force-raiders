"""Phase 8: structures - turrets, balloons, bunkers, the bases' missiles.

Fifteen buildings from the level table. Turrets fire at the other side's
units and, if the enemy's, at the helicopter; gunfire wears them down.
`structs` is a #[soa] pool in west-to-east order, so `structs[9]` is level
entry 9.
"""

from harness import boot, read_snapshot, screen_colour
from states import balloon_hit

FREE = 0                       # an empty unit slot's kind
ENEMY, NOBODY = 1, 2           # owners
CANOPY = (14, 22, 28)          # the airframe's canopy, BGR555 components


# ---- the balloon over the player's own bunker (x=2048) ----------------------
#
# It kills the airframe on contact at frame 421 of this climb: a life gone, the
# airframe back at the start but hidden for HELI_RESPAWN (120) frames, and the
# camera - 1945 at the loss - panning home at 1945/120+1 = 17 px a frame on top
# of the follow's 6. Sixty frames on it is 565 and the canopy is nowhere on
# screen; at 120 the view is home and the next airframe starts rising out of
# the ground at a pixel a frame from the ground line (168) to hover height (96),
# behind the dirt, the stick dead meanwhile.

def test_balloon_kill(state):
    snes = state(balloon_hit)
    v = read_snapshot(snes)
    assert v.heli_lives == 3
    assert v.heli_x_px == 64
    assert v.heli_dead == 120
    assert v.camera_x == 1945


def test_balloon_pan(state, tmp_path):
    snes = state(balloon_hit)
    snes.wait(60)
    v = read_snapshot(snes)
    assert v.heli_x_px == 64
    assert v.heli_dead == 60
    assert v.camera_x == 565
    assert screen_colour(snes, tmp_path, CANOPY, snes_colour=True) == 0, "the canopy is nowhere on screen"


def test_balloon_rise(state):
    snes = state(balloon_hit)
    snes.wait(120).right(10)
    v = read_snapshot(snes)
    assert v.heli_x_px == 64
    assert v.heli_dead == 0
    assert v.heli_rising == 1
    assert v.heli_y == 158 * 256
    assert v.camera_x == 0


# ---- long field cases ---------------------------------------------------------

def test_infantry_capture_a_neutral_bunker(snes):
    """An enemy infantryman walking into the neutral bunker at x=5120 (level
    entry 9) takes it and is spent doing so.

    The CPU's first man is out at frame 64 and covers 2560 px at half a pixel
    a frame: by 5300 the bunker is the enemy's and slot 0 is free.
    """
    boot(snes, "harness").wait(5300)
    v = read_snapshot(snes)
    assert v.structs__owner.u8[9] == ENEMY
    assert v.units__kind__tag.u8[0] == FREE


def test_tanks_shell_a_bunker_to_rubble(snes):
    """Tanks shell the other side's turrets and bunkers, holding in place until
    the building falls.

    Two bought tanks crush the column's men at the front around frame 7400,
    take its first tank between them, and roll on to the bunker at 5120 - the
    enemy's since ~5250 - hold short of it and bring its 69 hp down at 8 a
    shell, one every 90 frames: by 10600 it is rubble and nobody's.
    """
    boot(snes, "harness")
    snes.press("l", "a", frames=3).wait(3)
    snes.press("l", "a", frames=3).wait(10600)
    v = read_snapshot(snes)
    assert v.structs__hp.u8[9] == 0
    assert v.structs__owner.u8[9] == NOBODY


def test_the_enemy_bases_missiles_down_an_airframe(snes):
    """An airframe pushed into the base's 320 px is lost inside two hundred
    frames and comes back at the start with a life gone.

    The push is held to 1520 vblanks: at 1500 the run coasts to a stop just
    outside.
    """
    boot(snes, "harness").wait(20).right(1520).wait(300)
    v = read_snapshot(snes)
    assert v.heli_lives == 3
    assert v.heli_hp == 20


def test_a_launcher_fires_its_one_missile(snes):
    """The enemy column's launcher fires its one homing missile at an airframe
    inside LAUNCHER_RANGE (224 px) and is spent doing so: the slot is free, the
    missile lands for 10 of the 20 hp, and no life is lost.

    The third harness row ("harness_col") buys MIVV, so the truck is the
    column's lead and slot 0, and its pilot hunts nothing, so the airframe can
    cross the field.
    """
    boot(snes, "harness_col").wait(20).up(40).right(1400).wait(120)
    v = read_snapshot(snes)
    assert v.units__kind__tag.u8[0] == FREE
    assert v.heli_hp == 10
    assert v.heli_lives == 4


def test_the_enemy_mans_the_super_bunker(snes):
    """The super bunker (level entry 7, dead centre) starts empty and nobody's.

    The CPU's first squad walks the field - its first man spent on the bunker
    at 5120 - and the other four, with the first man of the next squad, go
    inside one after another from frame ~7300: five men, full, and it is the
    enemy's.
    """
    boot(snes, "harness").wait(8200)
    v = read_snapshot(snes)
    assert v.structs__men.u8[7] == 5
    assert v.structs__owner.u8[7] == ENEMY

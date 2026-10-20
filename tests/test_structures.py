"""Phase 8: structures - turrets, balloons, bunkers, the bases' missiles.

Fifteen buildings from the level table. Turrets fire at the other side's
units and, if the enemy's, at the helicopter; gunfire wears them down.
`structs` is a #[soa] pool in west-to-east order, so `structs[9]` is level
entry 9.
"""

from shared import balloon_hit, boot, read_snapshot, screen_colour

FREE = 0                       # an empty unit slot's kind
ENEMY, NOBODY = 1, 2           # owners
CANOPY = (14, 22, 28)          # the airframe's canopy, BGR555 components


# ---- the balloon over the neutral bunker (x=3072) -------------------------------
#
# A balloon is a danger to every side's airframe but its owner's: the player's
# own at 2048 lets it by, and the neutral one kills it on contact at frame 803
# of this climb: a life gone, the airframe back at the start but hidden. The
# camera - 2964 at the loss - stays
# on the wreck as it falls (~28 frames) and for a second after it goes up on
# the ground, then pans home in HELI_PAN (72) frames at camera_x/72+1 a frame
# on top of the follow's 6. 167 frames on the view is home and the next
# airframe starts rising out of the ground at a pixel a frame from the ground
# line to hover height, behind the dirt, the stick dead meanwhile.

def test_balloon_kill(state):
    snes = state(balloon_hit)
    v = read_snapshot(snes)
    assert v.airframes__lives.u8[0] == 3
    assert v.airframes__x_px.u16[0] == 64
    assert v.airframes__dead.u8[0] == 72              # HELI_PAN: the pan home is all still to come
    # On the wreck, which has lost the airframe's lead; 2964 when CAM_STEP
    # was 6 - at 8 (the afterburner's speed needs it) it closes 4 px more.
    assert v.camera_x == 2960


def test_balloon_pan(state, tmp_path):
    """The camera stays on the wreck while it falls, and for a second
    (HELI_GROUND_PAUSE) after it goes up on the ground, before the pan
    home. Lost at full speed to the right, the wreck kept half that speed
    all the way down, landing ~27 frames on: 60 frames after the loss it is
    33 frames into its second, the camera still on it.
    """
    snes = state(balloon_hit)
    snes.wait(60)
    v = read_snapshot(snes)
    assert v.airframes__x_px.u16[0] == 64
    assert v.airframes__dead.u8[0] == 72
    assert v.player__pause.u8[0] == 33
    assert v.camera_x == 3023
    assert screen_colour(snes, tmp_path, CANOPY, snes_colour=True) == 0, "the canopy is nowhere on screen"


def test_balloon_rise(state):
    """The next airframe rises once the wreck has fallen (~28 frames), had
    its second on the ground (60) and the camera has panned home (72).
    """
    snes = state(balloon_hit)
    snes.wait(167).right(10)
    v = read_snapshot(snes)
    assert v.airframes__x_px.u16[0] == 64
    assert v.airframes__dead.u8[0] == 0
    assert v.airframes__rising.u8[0] == 1
    assert v.airframes__y.u16[0] == 172 * 256
    assert v.camera_x == 0


# ---- long field cases ---------------------------------------------------------

def test_infantry_capture_a_neutral_bunker(snes):
    """An enemy infantryman walking into the neutral bunker at x=5120 (level
    entry 9) takes it and is spent doing so.

    The CPU's first man is out at frame 64 and covers 2560 px at half a pixel
    a frame: by 5300 the bunker is the enemy's and slot 0 is free.
    """
    boot(snes, "MISSION_TEST_QUIET").wait(5300)
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
    boot(snes, "MISSION_TEST_QUIET")
    snes.press("l", "a", frames=3).wait(3)
    snes.press("l", "a", frames=3).wait(10600)
    v = read_snapshot(snes)
    assert v.structs__hp.u8[9] == 0
    assert v.structs__owner.u8[9] == NOBODY


def test_the_enemy_bases_missiles_down_an_airframe(snes):
    """An airframe pushed into the base's 320 px is lost inside two hundred
    frames and comes back at the start with a life gone.

    It climbs first, over the balloons: at hover height the chains of the
    neutral and enemy bunkers (3072, 5120, 6144) are across its way, and
    take it long before the base does.
    """
    boot(snes, "MISSION_TEST_QUIET").wait(20).up(30).right(1520).wait(300)
    v = read_snapshot(snes)
    assert v.airframes__lives.u8[0] == 3
    assert v.airframes__hp.u8[0] == 20


def test_a_launcher_fires_its_one_missile(snes):
    """The enemy column's launcher fires its one homing missile at an airframe
    inside LAUNCHER_RANGE (224 px) and is spent doing so: the slot is free, the
    missile lands for 10 of the 20 hp, and no life is lost.

    The convoy row (MISSION_TEST_CONVOY) buys MIVV, so the truck is the
    column's lead and slot 0, and its pilot hunts nothing, so the airframe can
    cross the field.
    """
    boot(snes, "MISSION_TEST_CONVOY").wait(20).up(40).right(1400).wait(120)
    v = read_snapshot(snes)
    assert v.units__kind__tag.u8[0] == FREE
    assert v.airframes__hp.u8[0] == 10
    assert v.airframes__lives.u8[0] == 4


def test_the_enemy_mans_the_super_bunker(snes):
    """The super bunker (level entry 7, dead centre) starts empty and nobody's.

    The CPU's first squad walks the field - its first man spent on the bunker
    at 5120 - and the other four, with the first man of the next squad, go
    inside one after another from frame ~7300: five men, full, and it is the
    enemy's.
    """
    boot(snes, "MISSION_TEST_QUIET").wait(8200)
    v = read_snapshot(snes)
    assert v.structs__men.u8[7] == 5
    assert v.structs__owner.u8[7] == ENEMY


# ---- ramming ------------------------------------------------------------------
#
# A building's roof is 24 px off the ground line (BUNKER_ROOF_Y, 160) and an
# airframe's drawing its top 14 rows, so an airframe with its top under 146
# is into a bunker or the super bunker it is over. A standing bunker not its
# side's goes up with it; the super bunker, which only a tank can hurt, is
# crashed on and stands; its own side's is flown through. Each case plants
# the airframe over the building at frame 30, before anything has marched.

def test_flying_into_an_enemy_bunker_brings_it_down(snes):
    """The enemy's bunker at 6144 is structs[11]."""
    boot(snes, "MISSION_TEST_QUIET").wait(30)
    snes.write("airframes__x_px", 6144, 2)
    snes.write("airframes__y", 150 * 256, 2)
    snes.wait(2)
    v = read_snapshot(snes)
    assert v.structs__hp.u8[11] == 0
    assert v.structs__owner.u8[11] == NOBODY
    assert v.airframes__lives.u8[0] == 3


def test_skimming_a_bunkers_roof_is_not_a_ram(snes):
    """At 146 the airframe's drawing ends on the row above the roof."""
    boot(snes, "MISSION_TEST_QUIET").wait(30)
    snes.write("airframes__x_px", 6144, 2)
    snes.write("airframes__y", 146 * 256, 2)
    snes.wait(2)
    v = read_snapshot(snes)
    assert v.structs__hp.u8[11] == 69
    assert v.airframes__lives.u8[0] == 4


def test_the_players_own_bunker_is_flown_through(snes):
    """The player's bunker at 2048 is structs[3]."""
    boot(snes, "MISSION_TEST_QUIET").wait(30)
    snes.write("airframes__x_px", 2048, 2)
    snes.write("airframes__y", 150 * 256, 2)
    snes.wait(2)
    v = read_snapshot(snes)
    assert v.structs__hp.u8[3] == 69
    assert v.airframes__lives.u8[0] == 4


def test_the_super_bunker_is_crashed_on(snes):
    """Nobody's at the start (structs[7], x 4076): the airframe is lost and
    the bunker stands, still nobody's and empty."""
    boot(snes, "MISSION_TEST_QUIET").wait(30)
    snes.write("airframes__x_px", 4076, 2)
    snes.write("airframes__y", 150 * 256, 2)
    snes.wait(2)
    v = read_snapshot(snes)
    assert v.airframes__lives.u8[0] == 3
    assert v.structs__owner.u8[7] == NOBODY
    assert v.structs__men.u8[7] == 0

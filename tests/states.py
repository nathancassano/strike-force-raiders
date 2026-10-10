"""The states several cases share: `@rom_state` builders.

Each is built once per ROM and cached as a save state in build/.rom_driver;
a test imports the builder and starts there with `state(boarded)`.
"""

from harness import boot
from mesen_gdb.rom_driver import rom_state


@rom_state
def boarded(s):
    """Five infantry bought, the airframe landed on the pad, all five aboard."""
    boot(s, "MISSION_TEST_QUIET").press("l", "right", frames=3).wait(3).press("l", "a", frames=3).wait(20)
    s.right(180).wait(60).down(30).wait(40).wait(2800)


@rom_state
def eight_tanks(s):
    """The whole purse in tanks, then a minute of play: every pool slot live."""
    boot(s, "MISSION_TEST_QUIET")
    for _ in range(8):
        s.press("l", "a", frames=3).wait(3)
    s.wait(3600)


@rom_state
def five_passes(s):
    """Five pushes into the enemy base's missiles: all four airframes lost."""
    boot(s, "MISSION_TEST_QUIET")
    for _ in range(5):
        s.wait(20).right(1500).wait(300)


@rom_state
def campaign_lost(s):
    """A campaign boot through title and briefing, four crash landings, Start."""
    boot(s).start().wait(10).start().wait(20)
    for frames in (200, 200, 200, 240):
        s.down(40).wait(frames)
    s.start().wait(20)


@rom_state
def balloon_hit(s):
    """Climbed into the player's own bunker's balloon (x=2048), frame 421."""
    boot(s, "MISSION_TEST_QUIET").up(20).right(401)

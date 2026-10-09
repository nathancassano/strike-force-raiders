"""ROM tests for rotor_raiders, on mesen_gdb.rom_driver.

Build first (`make`); run with `pytest tests`, or `pytest tests -n auto` to
spread the cases over the cores. They began as the old shell suite's cases,
ported with its expected values.

A case drives the ROM with mesen_gdb.rom_driver's chainable input -
`boot(s, "harness").wait(20).right(30)` - and reads memory by name at the
snapshot (harness.py). `boot`'s pick chooses the mission at power-on, by
jumping from boot_mission to the ROM's boot_<pick>:

  "harness"      the quiet opponent - its pilot only wanders and refits,
                 and it buys what its purse and its tier allow, which at
                 that row is men. Nearly every case is written against this.
  "harness_hot"  the hot one - it hunts, bombs and fires missiles, and buys
                 IMEV: five men, a missile truck, two engineers, a van.
  "harness_col"  the quiet pilot with that column's vehicles, buying MIVV,
                 the truck leading - for a case that has to fly out and
                 meet one.
  "direct"       not a harness mission: the campaign's first, front end
                 skipped, the world the oldest cases were written against.

No pick at all gets the campaign proper, title page and all.

A setup several cases share is a named state below (`@rom_state`): built
once per ROM by its builder and cached as a save state in build/.rom_driver,
and a test starts there with `state("boarded")`.
"""

from pathlib import Path

import pytest

from harness import boot
from mesen_gdb.rom_driver import Rom, rom_state
from mesen_gdb.rom_driver.pytest_plugin import snes, state  # noqa: F401  (the fixtures)

PROJECT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def rom():
    path = PROJECT / "build" / "ROTOR_RAIDERS.smc"
    if not path.is_file():
        pytest.skip(f"{path.name} not built - run make")
    return Rom(path)


@rom_state
def boarded(s):
    """Five infantry bought, the airframe landed on the pad, all five aboard."""
    boot(s, "harness").press("l", "right", frames=3).wait(3).press("l", "a", frames=3).wait(20)
    s.right(180).wait(60).down(30).wait(40).wait(2800)


@rom_state
def eight_tanks(s):
    """The whole purse in tanks, then a minute of play: every pool slot live."""
    boot(s, "harness")
    for _ in range(8):
        s.press("l", "a", frames=3).wait(3)
    s.wait(3600)


@rom_state
def five_passes(s):
    """Five pushes into the enemy base's missiles: all four airframes lost."""
    boot(s, "harness")
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
    boot(s, "harness").up(20).right(401)


@rom_state
def at_turret(s):
    """Flown east to the enemy turret at x=6656."""
    boot(s, "harness").wait(20).right(1290)

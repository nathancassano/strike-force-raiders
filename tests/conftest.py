"""ROM tests for rotor_raiders, on mesen_gdb.rom_driver.

Build first (`make`); run with `pytest tests`, or `pytest tests -n auto` to
spread the cases over the cores. They began as the old shell suite's cases,
ported with its expected values.

A case drives the ROM with mesen_gdb.rom_driver's chainable input -
`boot(s, "MISSION_TEST_QUIET").wait(20).right(30)` - and reads memory by name
at the snapshot (harness.py). `boot` takes the name of one of the ROM's
mission constants and boots that mission at power-on, front end skipped,
by writing it to the ROM's boot_pick at boot_load's entry:

  MISSION_TEST_QUIET   the quiet opponent - its pilot only wanders and
                       refits, and it buys what its purse and its tier
                       allow, which at that row is men. Nearly every case
                       is written against this.
  MISSION_TEST_HUNTER  the hunter - it hunts, bombs and fires missiles,
                       and buys IMEV: five men, a missile truck, two
                       engineers, a van.
  MISSION_TEST_CONVOY  the quiet pilot with that column's vehicles, buying
                       MIVV, the truck leading - for a case that has to fly
                       out and meet one.
  MISSION_CAKE_WALK    not a test mission: the campaign's first, the
                       world the oldest cases were written against. Every
                       campaign mission is MISSION_ and its briefing name.

The three MISSION_TEST_ rows sit past the campaign's ten, out of the
game's reach, with their tuning frozen so a case does not move when the
campaign is tuned.

No mission at all gets the campaign proper, title page and all.

A setup several cases share is a state in states.py: a `@rom_state` builder,
built once per ROM and cached as a save state in build/.rom_driver, and a
test starts there with `state(boarded)`.
"""

from pathlib import Path

import pytest

from mesen_gdb.rom_driver import Rom
from mesen_gdb.rom_driver.pytest_plugin import snes, state  # noqa: F401  (the fixtures)

PROJECT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def rom():
    path = PROJECT / "build" / "ROTOR_RAIDERS.smc"
    if not path.is_file():
        pytest.skip(f"{path.name} not built - run make")
    return Rom(path)

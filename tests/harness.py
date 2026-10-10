"""Helpers the rotor_raiders ROM tests share.

`boot` is the power-on: thirty frames for snes_init and boot_load to
settle, with the mission picked by writing the ROM's boot_pick at
boot_load's entry (main.r65). `read_snapshot` is the moment every case
reads its values at: Select pressed, which calls the ROM's snapshot_point
from the main loop. It returns the session's memory by name, so a case
reads `v = read_snapshot(snes)` and asserts on `v.heli_x_px`. The colour
checks are the old shell suite's.
"""

from PIL import Image

BOOT_FRAMES = 30


def boot(s, mission=None):
    """Power-on: run to frame BOOT_FRAMES, booting *mission*.

    *mission* names one of the ROM's mission constants: a test row -
    MISSION_TEST_QUIET, MISSION_TEST_HUNTER or MISSION_TEST_CONVOY
    (conftest.py) - or a campaign mission by its name, MISSION_CAKE_WALK
    to MISSION_MIDNIGHT_OASIS. The power-on sets boot_pick to the campaign
    just before calling boot_load, so stopped at boot_load's entry the
    session writes the mission there, with BOOT_DIRECT to skip the front
    end, and boot_load reads it. None boots the campaign proper, title page
    and all.
    """
    if mission:
        s.until("boot_load", max_frames=BOOT_FRAMES)
        s.var.boot_pick = getattr(s.var, mission) | s.var.BOOT_DIRECT
    return s.wait(BOOT_FRAMES - s.frame)


def read_snapshot(s, *holding):
    """Press Select (with *holding*, if any), stop at snapshot_point, and
    return the memory there by name (`s.var`)."""
    s.until("snapshot_point", max_frames=s.tap_down + s.tap_up, holding=("select", *holding))
    return s.var


def snes8(v):
    """A 5-bit SNES colour component as the PPU expands it (bit replication)."""
    return (v << 3) | (v >> 2)


def colour_pct(png, rgb, snes=False):
    """Percent of the frame in exactly *rgb* (5-bit components if *snes*)."""
    want = tuple(snes8(c) for c in rgb) if snes else tuple(rgb)
    im = Image.open(png).convert("RGB")
    counts = {c: n for n, c in im.getcolors(im.width * im.height)}
    return 100.0 * counts.get(want, 0) / (im.width * im.height)


def screen_colour(snes, tmp_path, rgb, snes_colour=False):
    """Screenshot now and return how much of it is *rgb*."""
    return colour_pct(snes.screenshot(tmp_path / "screen.png"), rgb, snes=snes_colour)

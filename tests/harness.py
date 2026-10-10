"""Helpers the rotor_raiders ROM tests share.

`boot` is the power-on: thirty frames for snes_init and boot_load to
settle, with the mission picked by writing the ROM's boot_pick at
boot_load's entry (main.r65). `shot` is the
moment every case reads its values at: Select pressed, which calls the ROM's
snapshot_point from the main loop. It returns the session's memory by name,
so a case reads `v = shot(snes)` and asserts on `v.heli_x_px`. The colour
checks and the OAM and parallax tool runs are the old shell suite's.
"""

import subprocess
import sys
from pathlib import Path

from PIL import Image

TOOLS = Path(__file__).resolve().parent.parent / "tools"


BOOT_FRAMES = 30


# The ROM constant naming each pick's mission. "direct" also sets BOOT_DIRECT,
# which skips the front end.
MISSIONS = {
    "harness":     "MISSION_HARNESS",
    "harness_hot": "MISSION_HARNESS_HOT",
    "harness_col": "MISSION_HARNESS_COL",
    "direct":      "MISSION_START",
}


def boot(s, pick=None):
    """Power-on: run to frame BOOT_FRAMES, booting the mission *pick* names.

    *pick* is "harness", "harness_hot", "harness_col" or "direct"
    (conftest.py). The power-on sets boot_pick to the campaign just before
    calling boot_load, so stopped at boot_load's entry the session writes
    the pick's mission there, and boot_load reads it. None boots the
    campaign proper.
    """
    if pick:
        s.until("boot_load", max_frames=BOOT_FRAMES)
        mission = getattr(s.var, MISSIONS[pick])
        if pick == "direct":
            mission |= s.var.BOOT_DIRECT
        s.var.boot_pick = mission
    return s.wait(BOOT_FRAMES - s.frame)


def shot(s, *holding):
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


def tool(name, *args):
    """Run tools/NAME; fail the test with its output unless it exits 0."""
    r = subprocess.run([sys.executable, str(TOOLS / name), *map(str, args)],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"{name} failed:\n{r.stdout}{r.stderr}"
    return r.stdout

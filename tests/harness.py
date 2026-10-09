"""Helpers the rotor_raiders ROM tests share.

`boot` is the power-on: thirty frames for snes_init and boot_load to
settle, with the mission picked by swapping boot_load's call to
boot_mission for one of the ROM's boot_* picks (main.r65). `shot` is the moment every case
reads its values at: Select pressed, which calls the ROM's snapshot_point
from the main loop. `expect` checks a table of expressions against it and
reports every mismatch at once. The colour checks and the OAM and parallax
tool runs are the old shell suite's.
"""

import subprocess
import sys
from pathlib import Path

from PIL import Image

TOOLS = Path(__file__).resolve().parent.parent / "tools"


BOOT_FRAMES = 30


def boot(s, pick=None):
    """Power-on: run to frame BOOT_FRAMES, booting the mission *pick* names.

    *pick* is "harness", "harness_hot", "harness_col" or "direct"
    (conftest.py): stopped at boot_mission's entry, the session jumps to
    boot_<pick>, which returns that mission in its place. None boots the
    campaign proper.
    """
    if pick:
        s.until("boot_mission", max_frames=BOOT_FRAMES).jump(f"boot_{pick}")
    return s.wait(BOOT_FRAMES - s.frame)


def shot(s, *holding):
    """Press Select (with *holding*, if any) and stop at snapshot_point."""
    return s.until("snapshot_point", max_frames=s.tap_down + s.tap_up, holding=("select", *holding))


def expect(snes, checks):
    """Assert each ``{expression: value}``; ``v`` is ``snes.var``, ``s`` the session."""
    env = {"v": snes.var, "s": snes}
    bad = []
    for expr, want in checks.items():
        got = eval(expr, {}, env)   # the table is ours: plain attribute and index reads
        if got != want:
            bad.append(f"{expr} = {int(got):#06x}, want {want:#06x}")
    assert not bad, "\n".join(bad)


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

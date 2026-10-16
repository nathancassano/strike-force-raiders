"""What the rotor_raiders ROM tests share: the helpers and the states.

`boot` is the power-on: run to the ROM's main loop, then BOOT_SETTLE frames,
with the mission picked by writing the ROM's boot_pick at boot_load's entry
(main.r65). `read_snapshot` is the moment every case
reads its values at: Select pressed, which calls the ROM's snapshot_point
from the main loop. It returns the session's memory by name, so a case
reads `v = read_snapshot(snes)` and asserts on `v.airframes__x_px.u16[0]`. The colour
checks are the old shell suite's.

The states several cases share are `@rom_state` builders, at the bottom:
each is built once per ROM and cached as a save state in build/.rom_driver,
and a test imports the builder and starts there with `state(boarded)`.
"""

from PIL import Image

from mesen_gdb.rom_driver import rom_state

# Power-on to main: the sound driver's upload (spc_init, ~156 frames) and
# the inits. Generous, so a slower upload fails a test rather than hanging.
BOOT_MAX_FRAMES = 600
# Frames from main to where a case starts. The suite was calibrated booting
# to frame 30 when a mission boot reached main at frame 17, before the
# sound driver; counting from main instead keeps that timeline whatever
# the boot costs.
BOOT_SETTLE = 13


def boot(s, mission=None):
    """Power-on: run to the main loop, then BOOT_SETTLE frames, booting
    *mission*.

    *mission* names one of the ROM's mission constants: a test row -
    MISSION_TEST_QUIET, MISSION_TEST_HUNTER or MISSION_TEST_CONVOY
    (conftest.py) - or a campaign mission by its name, MISSION_CAKE_WALK
    to MISSION_MIDNIGHT_OASIS. The power-on sets boot_pick to the campaign
    just before calling boot_load, so stopped at boot_load's entry the
    session writes the mission there, with BOOT_DIRECT to skip the front
    end, and boot_load reads it. None boots the campaign proper, title page
    and all - but for the power-on BubbleZap intro, which BOOT_NO_INTRO
    skips: it is ten seconds a case, and test_campaign.py covers it.
    """
    s.until("boot_load", max_frames=BOOT_MAX_FRAMES)
    if mission:
        s.var.boot_pick = getattr(s.var, mission) | s.var.BOOT_DIRECT
    else:
        s.var.boot_pick = s.var.boot_pick | s.var.BOOT_NO_INTRO
    s.until("main", max_frames=BOOT_MAX_FRAMES)
    return s.wait(BOOT_SETTLE)


class Snapshot:
    """`s.var`, but an #[soa] plane - any name with `__` in it - always reads
    as an array (`s.raw`), whatever its size. `s.var` reads anything of one
    to three bytes as a number, and the two airframes' planes are two
    elements: `airframes__gun` is two bytes, one per side, not a u16. So a
    plane is always read with its width and index, `v.airframes__gun.u8[1]`,
    a one-element pool's (`player`, `pilot`) included."""

    def __init__(self, s):
        object.__setattr__(self, "_s", s)

    def __getattr__(self, name):
        if "__" in name:
            return self._s.raw(name)
        return getattr(self._s.var, name)


def read_snapshot(s, *holding):
    """Press Select (with *holding*, if any), stop at snapshot_point, and
    return the memory there by name (a Snapshot of `s.var`)."""
    s.until("snapshot_point", max_frames=s.tap_down + s.tap_up, holding=("select", *holding))
    return Snapshot(s)


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


# Mesen's screenshot is the 239-line overscan frame: picture line 0 is its 7th.
OVERSCAN_TOP = 7


def title_shot(snes, tmp_path):
    """Screenshot now, and how many of the title's pixels match its picture:
    (matching, the menu rows' pixels that do not match). The picture is
    title.tilemap.bmp as the PPU shows it - each component cut to 5 bits
    and expanded, since the bitmap's palette need not be in the PPU's steps.
    The menu rows are screen.r65's SCREEN_CODE_ROW (19) to
    SCREEN_TITLE_PROMPT (25)."""
    shot = Image.open(snes.screenshot(tmp_path / "screen.png")).convert("RGB")
    art = Image.open("assets/src/title.tilemap.bmp").convert("RGB")
    art = art.point(lambda v: snes8(v >> 3))
    same = menu = 0
    for y in range(art.height):
        for x in range(art.width):
            if shot.getpixel((x, y + OVERSCAN_TOP)) == art.getpixel((x, y)):
                same += 1
            elif 19 * 8 <= y < 26 * 8:
                menu += 1
    return same, menu


# ---- states ------------------------------------------------------------------

@rom_state
def boarded(s):
    """Five infantry bought, the airframe landed on the pad, all five aboard."""
    boot(s, "MISSION_TEST_QUIET").press("l", "down", frames=3).wait(3).press("l", "a", frames=3).wait(20)
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
        s.up(60).downright(90).wait(frames)
    s.start().wait(20)


@rom_state
def balloon_hit(s):
    """Climbed past the player's own balloon (x=2048), which is no danger to
    it, and into the neutral bunker's (x=3072), frame 803."""
    boot(s, "MISSION_TEST_QUIET").up(20).right(609)

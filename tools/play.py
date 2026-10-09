#!/usr/bin/env python3
"""play.py OUT.png [ACTION,...] [--dump REGION FILE]... - one scripted run.

Boots ROTOR_RAIDERS in Mesen-GDB, plays the actions, and screenshots at the
ROM's snapshot_point hook (fired by Select) - the same boot and the same
instant the pytest suite reads at (tests/harness.py).

    ./play.sh build/boot.png shot
    ./play.sh build/fly.png @harness,wait60,right90,shot
    ./play.sh build/x.png @harness,wait600,shot --dump wram build/x.wram

Actions
  @PICK                    first, if at all: boot that mission - harness,
                           harness_hot, harness_col or direct (conftest.py).
                           Without one, the campaign proper, title and all.
  waitN                    N idle frames
  shot                     tap Select and stop at snapshot_point; the run
                           ends there
  start / select / a ...   tap a button (3 frames down, 3 up)
  upN downN leftN rightN   hold a direction for N frames
  aN bN xN yN lN rN        hold a face or shoulder button for N frames
  up+a30                   several buttons together

With no `shot` the screenshot is taken where the actions end. Each --dump
saves a memory region (wram, vram, oam, ...) there too.
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "tests"))

from harness import boot, shot                      # noqa: E402
from mesen_gdb.rom_driver import NotReached, Rom    # noqa: E402
from mesen_gdb.rom_driver.backend import BUTTONS    # noqa: E402

ROM = HERE / "build" / "ROTOR_RAIDERS.smc"


def split_action(act):
    """'up+a30' -> (['up', 'a'], 30); a tap has no count."""
    i = len(act)
    while i > 0 and act[i - 1].isdigit():
        i -= 1
    buttons = [b for b in act[:i].split("+") if b]
    for b in buttons:
        if b not in BUTTONS:
            raise SystemExit(f"unknown button {b!r} in action {act!r}")
    return buttons, int(act[i:]) if act[i:] else None


def play(s, actions):
    """Run *actions* on a fresh session; returns once the run is over."""
    pick = actions.pop(0)[1:] if actions and actions[0].startswith("@") else None
    boot(s, pick)
    for act in actions:
        if act.startswith("wait"):
            s.wait(int(act[4:] or 1))
        elif act == "shot":
            shot(s)
            return
        else:
            buttons, frames = split_action(act)
            s.press(*buttons, frames=frames)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("out", type=Path)
    p.add_argument("actions", nargs="?", default="shot")
    p.add_argument("--dump", nargs=2, action="append", default=[], metavar=("REGION", "FILE"))
    args = p.parse_args()

    if not ROM.is_file():
        raise SystemExit(f"ROM not built: {ROM} (run make)")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with Rom(ROM).session() as s:
        try:
            play(s, [a for a in args.actions.split(",") if a])
        except NotReached as e:
            raise SystemExit(f"play.py: {e}")
        s.screenshot(args.out.resolve())
        for region, path in args.dump:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            s.dump(region, Path(path).resolve())
        print(f"{args.out}: frame {s.frame}")


if __name__ == "__main__":
    main()

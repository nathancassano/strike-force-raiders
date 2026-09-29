#!/usr/bin/env python3
"""
Build a Mesen .mmo movie to drive the ROTOR_RAIDERS ROM.

Input.txt is one line per frame: '|..|' + 12 button columns, in the order
A B X Y L R Select Start Up Down Left Right.

Usage: mkmovie.py OUT.mmo ROMNAME SHA1 ACTION[,ACTION...]

Actions
  waitN                    N idle frames
  start / select           tap the button (3 frames)
  shot                     tap Select - fires the ROM's snapshot_point hook
  upN downN leftN rightN   hold a direction for N frames
  aN bN xN yN lN rN        hold a face/shoulder button for N frames
  up+leftN                 hold several buttons together for N frames
  @l @r @l+r               hold at power-on: the button is down for the whole
                           boot prefix and costs no frames of its own, which
                           is how the ROM's boot-time mission select is
                           reached without moving any timing after it

Any action may combine buttons with '+', e.g. 'up+a30' or 'left+b12'.
"""

import sys
import zipfile

# Column order in a Mesen SNES input line.
NAMES = ['a', 'b', 'x', 'y', 'l', 'r', 'select', 'start',
         'up', 'down', 'left', 'right']
COLS = {n: i for i, n in enumerate(NAMES)}
LETTER = 'ABXYLRSTUDLR'

IDLE = '|..|' + '.' * 12
BOOT_FRAMES = 30      # let snes_init and boot_load settle before any input
TAIL_FRAMES = 60      # keep emulating past the last action


def hold(buttons):
    """One input line with the named buttons held."""
    row = list('.' * 12)
    for b in buttons:
        col = COLS[b]
        row[col] = LETTER[col]
    return '|..|' + ''.join(row)


def split_action(act):
    """'up+a30' -> (['up', 'a'], 30). Trailing digits are the frame count."""
    i = len(act)
    while i > 0 and act[i - 1].isdigit():
        i -= 1
    name, count = act[:i], act[i:]
    buttons = [b for b in name.split('+') if b]
    for b in buttons:
        if b not in COLS:
            raise SystemExit(f"unknown button {b!r} in action {act!r}")
    return buttons, int(count) if count else None


def build(actions):
    frames = [IDLE] * BOOT_FRAMES
    actions = list(actions)
    # A power-on hold. boot_load reads the pad by hand to pick its mission -
    # the harness's mission select - and that happens inside the first frame,
    # before the boot prefix has run. So '@l' holds L across the whole prefix
    # instead of adding frames after it, and every timing in the run is the
    # same as one without it.
    while actions and actions[0].startswith('@'):
        buttons, _ = split_action(actions.pop(0)[1:])
        frames = [hold(buttons)] * len(frames)
    for act in actions:
        if act.startswith('wait'):
            frames += [IDLE] * int(act[4:] or 1)
            continue
        if act == 'shot':
            act = 'select'
        buttons, count = split_action(act)
        if count is None:
            # A tap: 3 frames down, 3 up, so edge-detection sees exactly one.
            frames += [hold(buttons)] * 3 + [IDLE] * 3
        else:
            frames += [hold(buttons)] * count
    frames += [IDLE] * TAIL_FRAMES
    return '\n'.join(frames) + '\n'


SETTINGS = """MesenVersion 2.0.0
MovieFormatVersion 2
GameFile {rom}
SHA1 {sha1}
emu.consoleType Snes
video.integerFpsMode false
emulation.runAheadFrames 0
game.dipSwitches 0
snes.ramPowerOnState Random
snes.enableRandomPowerOnState false
snes.region Auto
snes.port1.type SnesController
snes.port2.type None
"""


def main():
    if len(sys.argv) < 5:
        raise SystemExit(__doc__.strip())
    out, rom, sha1, script = sys.argv[1:5]
    actions = [a for a in script.split(',') if a]
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('Input.txt', build(actions))
        z.writestr('GameSettings.txt', SETTINGS.format(rom=rom, sha1=sha1))
    print(f"{out}: {len(actions)} actions")


if __name__ == '__main__':
    main()

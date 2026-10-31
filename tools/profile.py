#!/usr/bin/env python3
"""profile.py TRACE.txt [build/STRIKE_FORCE_RAIDERS.sym] - where the frame goes.

Attributes every PC in a Mesen-GDB `trace` log to the function whose label
precedes it in the .sym, and prints instruction counts per function, most
first. Take the trace at the snapshot:

    printf 'break $%s\\ncontinue\\ntrace t.txt\\nframes 4\\ntrace off\\nquit\\n' \\
        $SNAPSHOT | mesen-gdb ROM --headless --movie build/play.mmo
    tools/profile.py t.txt

Instruction counts, not cycles - a rough guide to what to look at, not a
measurement; the frame-budget probe (frames_nmi vs frames_loop) is that.
Local labels (`__`, `_L`, `.`) fold into the function above them.
"""
import bisect
import collections
import re
import sys


def main():
    trace = sys.argv[1]
    sym = sys.argv[2] if len(sys.argv) > 2 else "build/STRIKE_FORCE_RAIDERS.sym"
    labels = []
    section = None
    for line in open(sym):
        line = line.strip()
        if line.startswith("["):
            section = line
            continue
        if section != "[labels]" or not line:
            continue
        m = re.match(r"([0-9a-f]{2}):([0-9a-f]{4})\s+(\S+)", line)
        if not m:
            continue
        name = m.group(3)
        if name.startswith(("__", "_L", ".")) or "__" in name[1:]:
            continue                    # local: folds into the function above
        labels.append(((int(m.group(1), 16) << 16) | int(m.group(2), 16), name))
    labels.sort()
    addrs = [a for a, _ in labels]

    counts = collections.Counter()
    total = 0
    for line in open(trace):
        m = re.match(r"([0-9A-Fa-f]{6})", line)
        if not m:
            continue
        pc = int(m.group(1), 16)
        i = bisect.bisect_right(addrs, pc) - 1
        counts[labels[i][1] if i >= 0 else "?"] += 1
        total += 1

    print(f"{total} instructions")
    for name, n in counts.most_common(40):
        print(f"{n:8d} {100.0 * n / total:5.1f}%  {name}")


if __name__ == "__main__":
    main()

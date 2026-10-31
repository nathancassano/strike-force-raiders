#!/usr/bin/env bash
# timeline.sh OUTDIR ACTIONS FRAME [FRAME...] - WRAM dumps along one run.
#
# Plays ACTIONS (mkmovie syntax, usually a long wait) in the debugger and
# dumps WRAM at each FRAME given, ascending, to OUTDIR/fNNNNN.wram - one
# emulator run instead of one per snapshot. Read them with poolstat.py.
#
#   tools/timeline.sh build/tl wait20000 2000 4000 8000
#   for f in build/tl/*.wram; do echo "== $f"; tools/poolstat.py $f | head -20; done
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
MESEN="$HERE/../Mesen-GDB/bin/linux-x64/Release/mesen-gdb"
ROM="$HERE/build/STRIKE_FORCE_RAIDERS.smc"
OUT="$1"; ACTIONS="$2"; shift 2
mkdir -p "$OUT"
SHA=$(sha1sum "$ROM" | cut -d' ' -f1 | tr 'a-z' 'A-Z')
MOVIE="$OUT/timeline.mmo"
python3 "$HERE/tools/mkmovie.py" "$MOVIE" "STRIKE_FORCE_RAIDERS.smc" "$SHA" "$ACTIONS" >/dev/null
{
    at=0
    for f in "$@"; do
        printf 'frames %d\ndump wram %s/f%05d.wram\n' $((f - at)) "$OUT" "$f"
        at=$f
    done
    echo quit
} | "$MESEN" "$ROM" --headless --movie "$MOVIE" >/dev/null 2>&1
ls "$OUT"/f*.wram

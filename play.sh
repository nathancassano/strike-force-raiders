#!/usr/bin/env bash
# Drive ROTOR_RAIDERS through a scripted input sequence and screenshot when
# the ROM reaches its snapshot_point hook (fired by Select).
#
#   ./play.sh OUT.png [ACTION,...] [extra mesen-gdb args...]
#
#   ./play.sh build/boot.png shot
#   ./play.sh build/fly.png  wait60,right90,shot --check-mem16 0x20=0x0140
#
# Actions: waitN | start | shot | upN/downN/leftN/rightN | aN/bN/xN/yN/lN/rN
#          combine with '+', e.g. up+a30
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
MESEN="$ROOT/Mesen-GDB/bin/linux-x64/Release/mesen-gdb"

PROJECT=ROTOR_RAIDERS
ROM="$HERE/build/$PROJECT.smc"
SYM="$HERE/build/$PROJECT.sym"

OUT="${1:?usage: play.sh OUT.png [actions] [mesen args...]}"
ACTIONS="${2:-shot}"

[ -x "$MESEN" ] || { echo "mesen-gdb not found at $MESEN" >&2; exit 2; }
[ -f "$ROM" ]   || { echo "ROM not built: $ROM (run make)" >&2; exit 2; }

SHA=$(sha1sum "$ROM" | cut -d' ' -f1 | tr 'a-z' 'A-Z')
MOVIE="$HERE/build/play.mmo"
python3 "$HERE/tools/mkmovie.py" "$MOVIE" "$PROJECT.smc" "$SHA" "$ACTIONS" >/dev/null

# Re-look-up the address every run: it moves whenever code before it changes.
SP=$(grep -E ' snapshot_point$' "$SYM" | cut -d: -f2 | cut -d' ' -f1)
[ -n "$SP" ] || { echo "snapshot_point not found in $SYM" >&2; exit 2; }

mkdir -p "$(dirname "$OUT")"
"$MESEN" "$ROM" --batch --headless --turbo \
    --movie "$MOVIE" --timeout 120000 --break "\$$SP" \
    --screenshot "$OUT" "${@:3}"

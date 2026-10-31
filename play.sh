#!/usr/bin/env bash
# Drive STRIKE_FORCE_RAIDERS through a scripted input sequence and screenshot when
# the ROM reaches its snapshot_point hook (fired by Select). See tools/play.py.
#
#   ./play.sh OUT.png [ACTION,...] [--dump REGION FILE]...
#
#   ./play.sh build/boot.png shot
#   ./play.sh build/fly.png  @MISSION_TEST_QUIET,wait60,right90,shot
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/tools/play.py" "$@"

#!/usr/bin/env bash
# Scripted-input regression suite.
#
# Every completed implementation phase leaves a case here; the whole suite
# re-runs after each new phase so regressions surface immediately.
#
#   ./tests/run.sh            run all cases
#   ./tests/run.sh boot       run cases whose name matches 'boot'
#
# Every movie starts with a power-on hold that picks one of the three
# harness missions (src/mission.r65), which exist so a case does not move
# when the campaign's difficulty curve is tuned:
#
#   @l     the quiet opponent - its pilot only wanders and refits, and it
#          buys what its purse and its tier allow, which at that row is
#          men. Nearly every case is written against this.
#   @r     the hot one - it hunts, bombs and fires missiles, and buys
#          IMEV: five men, a missile truck, two engineers, a van.
#   @l+r   the quiet pilot with that column's vehicles, buying MIVV, the
#          truck leading - for a case that has to fly out and meet one.
#   @x     not a harness mission at all: the campaign's first, with the
#          front end skipped, which is the world the oldest cases here
#          were written against.
#
# A movie with no hold gets the campaign proper, title page and all, which
# is what the phase 11 cases at the bottom drive.
#
# The hold costs no frames: it sits inside the boot prefix mkmovie.py puts
# in front of every script, and boot_load reads the pad by hand.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(cd "$HERE/.." && pwd)"
SHOTS="$PROJ/build/shots"
FILTER="${1:-}"

mkdir -p "$SHOTS"
pass=0; fail=0; skipped=0

# case NAME ACTIONS [mesen args...]
#   Runs the ROM under the scripted input, breaking at snapshot_point.
#   Screenshot lands in build/shots/NAME.png.
run_case() {
    local name="$1" actions="$2"; shift 2
    if [ -n "$FILTER" ] && [[ "$name" != *"$FILTER"* ]]; then
        skipped=$((skipped+1)); return
    fi
    local out="$SHOTS/$name.png"
    local log
    if ! log=$("$PROJ/play.sh" "$out" "$actions" --timeout 30000 "$@" 2>&1); then
        echo "FAIL $name (emulator)"; echo "$log" | tail -5; fail=$((fail+1)); return
    fi
    if ! grep -q "Screenshot saved" <<<"$log"; then
        echo "FAIL $name (no screenshot - breakpoint never reached)"
        echo "$log" | tail -3; fail=$((fail+1)); return
    fi
    echo "PASS $name"; pass=$((pass+1))
}

# ramaddr NAME - look up a RAM symbol's address from the generated asm.
# Auto-allocated addresses move whenever declarations change, so tests must
# resolve them at run time rather than hard-coding.
ramaddr() {
    awk -v n="$1" '$1==".DEFINE" && $2==n { gsub(/[$]/,"",$3); print $3; exit }' \
        "$PROJ/build/main.asm"
}

# expect NAME R,G,B [MIN_PCT]  - assert the captured frame's dominant colour
expect_colour() {
    local name="$1" colour="$2" pct="${3:-50}"
    if [ -n "$FILTER" ] && [[ "$name" != *"$FILTER"* ]]; then return; fi
    if python3 "$PROJ/tools/pngstat.py" "$SHOTS/$name.png" \
            --expect "$colour" --min-pct "$pct" >/dev/null 2>&1; then
        echo "PASS $name:colour"; pass=$((pass+1))
    else
        echo "FAIL $name:colour"
        python3 "$PROJ/tools/pngstat.py" "$SHOTS/$name.png" --expect "$colour" --min-pct "$pct"
        fail=$((fail+1))
    fi
}

# budget_case NAME ACTIONS - run the ROM, dump OAM at the snapshot and assert
#   the per-scanline sprite and tile load stays inside what the PPU can draw.
#   Ground units all stand on the same few scanlines, so this is the check
#   that matters most as the field fills.
budget_case() {
    local name="$1" actions="$2"
    if [ -n "$FILTER" ] && [[ "$name" != *"$FILTER"* ]]; then
        skipped=$((skipped+1)); return
    fi
    local oam="$SHOTS/$name.oam"
    if ! "$PROJ/play.sh" "$SHOTS/$name.png" "$actions" --timeout 300000 \
            --dump oam "$oam" >/dev/null 2>&1; then
        echo "FAIL $name (emulator)"; fail=$((fail+1)); return
    fi
    local out
    if out=$(python3 "$PROJ/tools/oamstat.py" "$oam"); then
        echo "PASS $name  ($(echo "$out" | grep -c peak) peaks inside budget)"
        pass=$((pass+1))
    else
        echo "FAIL $name"; echo "$out"; fail=$((fail+1))
    fi
}

# expect_snes NAME R,G,B MIN_PCT - assert a 5-bit BGR555 palette colour is
#   actually on screen. The PPU expands 5->8 bits by replication, not by
#   scaling, so --snes does the conversion; comparing against round(v/31*255)
#   misses every pixel by one. This is the only kind of check that catches a
#   sprite which failed to render at all - RAM assertions cannot.
expect_snes() {
    local name="$1" colour="$2" pct="$3"
    if [ -n "$FILTER" ] && [[ "$name" != *"$FILTER"* ]]; then return; fi
    if python3 "$PROJ/tools/pngstat.py" "$SHOTS/$name.png" --expect "$colour" \
            --snes --min-pct "$pct" >/dev/null 2>&1; then
        echo "PASS $name:snes $colour"; pass=$((pass+1))
    else
        echo "FAIL $name:snes $colour"
        python3 "$PROJ/tools/pngstat.py" "$SHOTS/$name.png" --expect "$colour" \
            --snes --min-pct "$pct"
        fail=$((fail+1))
    fi
}

# expect_snes_none NAME R,G,B - the SNES colour is nowhere in the frame
expect_snes_none() {
    local name="$1" colour="$2"
    if [ -n "$FILTER" ] && [[ "$name" != *"$FILTER"* ]]; then return; fi
    if python3 "$PROJ/tools/pngstat.py" "$SHOTS/$name.png" --expect "$colour" \
            --snes --min-pct 0 --max-pct 0 >/dev/null 2>&1; then
        echo "PASS $name:snes-none $colour"; pass=$((pass+1))
    else
        echo "FAIL $name:snes-none $colour"
        python3 "$PROJ/tools/pngstat.py" "$SHOTS/$name.png" --expect "$colour" \
            --snes --min-pct 0 --max-pct 0
        fail=$((fail+1))
    fi
}

# parallax NAME BASE_ACTIONS MOVED_ACTIONS BANDS
#   Capture two frames at different camera positions and assert that each
#   layer moved at its own rate and the ground shows the expected number of
#   equal-height HDMA bands.
parallax_case() {
    local name="$1" a="$2" b="$3" bands="$4"
    if [ -n "$FILTER" ] && [[ "$name" != *"$FILTER"* ]]; then
        skipped=$((skipped+1)); return
    fi
    "$PROJ/play.sh" "$SHOTS/$name-a.png" "$a" --timeout 40000 >/dev/null 2>&1
    "$PROJ/play.sh" "$SHOTS/$name-b.png" "$b" --timeout 40000 >/dev/null 2>&1
    local out
    # Rows 216-223 are the airframe's HUD strip, a fixed layer across the
    # ground; the rows below are past the 224-line screen.
    out=$(python3 "$PROJ/tools/parallax.py" "$SHOTS/$name-a.png" \
                  "$SHOTS/$name-b.png" --assert-bands "$bands" --ignore-rows 216-238 2>&1)
    if grep -q "^ok " <<<"$out"; then
        echo "PASS $name  ($(grep '^ok ' <<<"$out" | sed 's/^ok  *//'))"
        pass=$((pass+1))
    else
        echo "FAIL $name"; echo "$out" | tail -6; fail=$((fail+1))
    fi
}

# ---------------------------------------------------------------------------
# Phase 1 - harness. The ROM boots, enables NMI, runs its loop, and reaches
# snapshot_point on Select. The sky backdrop proves the frame actually
# rendered rather than the breakpoint firing on a blank screen.
# ---------------------------------------------------------------------------
run_case    boot  "shot"
# The sky backdrop no longer fills the frame now that the BG layers render,
# but it must still dominate - this catches a failed palette DMA or a
# layer left enabled over the whole screen.
expect_colour boot "33,49,115" 40

# ---------------------------------------------------------------------------
# Phase 2 - scrolling battlefield.
#
# The camera is a window follow: it holds still until the focus point leaves
# a CAM_DEAD (8px) window around screen centre, then closes at up to
# CAM_STEP px/frame, settling at a lag of +8 moving right, -8 moving left.
#
# Recalibrated in phase 3. These figures were set against the 4 px/frame
# focus_move stand-in; the camera now follows the helicopter's centre, which
# accelerates up to 5 px/frame, so every moving case travels further - and
# since the inertia rework the centre is led by vx/8 (design.md's lookahead).
# The relation still holds exactly - at cam_r240 the airframe is at 1221
# doing 312/64 px/frame, so the focus is 1221 + 16 + 39 = 1276 and the
# camera settles at 1276 - 128 - 8 = 1140 = $0474.
# ---------------------------------------------------------------------------
CAM=$(ramaddr camera_x)
if [ -z "$CAM" ]; then
    echo "FAIL cam:addr (camera_x not found in build/main.asm)"; fail=$((fail+1))
else
    run_case cam_rest   "@x,shot"                        --check-mem16 0x$CAM=0x0000
    run_case cam_r30    "@x,wait20,right30,shot"         --check-mem16 0x$CAM=0x005A
    run_case cam_r120   "@x,wait20,right120,shot"        --check-mem16 0x$CAM=0x021C
    run_case cam_r240   "@x,wait20,right240,shot"        --check-mem16 0x$CAM=0x0474
    run_case cam_back   "@x,wait20,right240,left90,shot" --check-mem16 0x$CAM=0x032D
fi

# Four layers at four rates, and eight equal HDMA ground bands, of which
# the tool can measure six: the first is the plain ground line under the
# units' feet (no texture, so no correlation), and the airframe's HUD
# strip on the last tile row cuts the seventh and covers the eighth. A
# short move: the near band runs at 1.875x, and the tool correlates each
# row wrapped at the screen width, so a long one leaves it nothing to
# match.
parallax_case parallax "@x,shot" "@x,wait20,right40,shot" 6

# ---------------------------------------------------------------------------
# Phase 3 - helicopter.
#
# Position is 16.8 (x_px + x_sub) because a 4096px world fits no 16-bit fixed
# type; y is a u16 holding 8.8 screen pixels; velocity is Q10 (signed 10.6).
# The d-pad picks a target velocity and the airframe accelerates toward it at
# HELI_ACC, so the first ~20 frames of any direction are a ramp.
# ---------------------------------------------------------------------------
HX=$(ramaddr heli_x_px)
HY=$(ramaddr heli_y)
OAMB=$(ramaddr oam)
if [ -z "$HX" ] || [ -z "$HY" ] || [ -z "$OAMB" ]; then
    echo "FAIL heli:addr (heli_x_px/heli_y/oam not found in build/main.asm)"
    fail=$((fail+1))
else
    # Rest: heli_init's spawn, untouched by a frame of no input.
    run_case heli_rest  "@x,shot"                --check-mem16 0x$HX=0x0040 \
                                              --check-mem16 0x$HY=0x6000
    run_case heli_right "@l,wait20,right30,shot" --check-mem16 0x$HX=0x00AB

    # Leftward travel exercises the borrow path in heli_move_x. `>>` is a
    # logical shift even on signed types, so a negative delta cannot be
    # shifted apart - a round trip that lands mid-world proves the explicit
    # sign branch, where a clamp at 0 would not.
    run_case heli_back  "@x,wait20,right240,left60,shot" --check-mem16 0x$HX=0x0452

    # All four clamps: world edge, and the flyable box between the HUD strip
    # and the ground at y=168.
    run_case heli_wall  "@x,wait20,left60,shot"  --check-mem16 0x$HX=0x0000
    run_case heli_ceil  "@x,wait20,up60,shot"    --check-mem16 0x$HY=0x1000
    run_case heli_floor "@l,wait20,down30,wait40,shot"  --check-mem16 0x$HY=0x9800

    # Tilt is cosmetic and derived from velocity ALONG THE NOSE: OAM sprite
    # 0's tile selects the frame (0 nose-down, 4 level, 8 nose-up). Using the
    # raw sign of vx instead double-flips against hflip and pitches the nose
    # up under forward acceleration - verified on screen, not just in RAM.
    #
    # Phase 4 added facing. Flying left mirrors the airframe, which swaps the
    # two cells as well as setting hflip - so sprite 0 then holds the frame's
    # *far* tile (+2) and its attribute byte gains $40. Asserting both is what
    # tells a correct mirror from a frame picked at random.
    #
    # The attribute byte reads $37 (or $77 mirrored): priority 3, OBJ palette
    # 3 and the 9th tile bit, which is the airframe's own sheet - it is
    # loaded into the second OBJ name block with a palette of its own
    # (heli.bmp, HELI_PAGE / OBJ_PAL_HELI), so a tile number here is the
    # sheet's and the page bit says which sheet.
    TILT=$(printf '%04X' $((0x$OAMB + 2)))
    ATTR=$(printf '%04X' $((0x$OAMB + 3)))
    run_case heli_tilt_level "@l,shot"                --check-mem 0x$TILT=0x04 \
                                                   --check-mem 0x$ATTR=0x37
    run_case heli_tilt_right "@l,wait20,right60,shot" --check-mem 0x$TILT=0x00 \
                                                   --check-mem 0x$ATTR=0x37
    run_case heli_tilt_left  "@x,wait20,right120,left60,shot" \
                                                   --check-mem 0x$TILT=0x02 \
                                                   --check-mem 0x$ATTR=0x77
    # Reversing is a turn: five drawings held three frames each, advancing
    # only while the new direction is held. Ten frames in, the three-quarter
    # view faces the new way (its cells swap under hflip, so the first slot
    # carries the right-hand cell, $22); six frames in and released, it
    # stalls on the three-quarter view still facing the old way ($20); and
    # wound back to nothing, the facing never changed. The nose-up flare the
    # reversal used to show is out of reach now - the swing outlasts the
    # velocity decay - so the tilt cases stop at nose-down and level.
    run_case heli_turn_mid   "@x,wait20,right120,left10,shot" \
                                                   --check-mem 0x$TILT=0x22 \
                                                   --check-mem 0x$ATTR=0x77
    run_case heli_turn_stall "@l,wait20,right120,left6,wait20,shot" \
                                                   --check-mem 0x$TILT=0x20 \
                                                   --check-mem 0x$ATTR=0x37
    run_case heli_turn_back  "@x,wait20,right120,left6,right6,wait2,shot" \
                                                   --check-mem 0x$ATTR=0x37

    # The airframe is actually drawn, not just positioned. Canopy and rotor
    # are the two OBJ colours that appear nowhere else on screen, so finding
    # them proves the OBJ CHR reached VRAM and the palette reached CGRAM 128.
    expect_snes heli_tilt_right "14,22,28" 0.02      # canopy
    expect_snes heli_tilt_right "21,22,24" 0.05      # rotor disc
fi

# ---------------------------------------------------------------------------
# Phase 4 - weapons and munitions.
#
# Gunfire and bombs share one pool with a rotating free cursor; slot 0 is the
# first one a cold pool hands out, so a single shot always lands there.
# Kinds: 0 free, 1 bullet, 2 bomb.
# ---------------------------------------------------------------------------
GUN=$(ramaddr heli_gun)
BOMBS=$(ramaddr heli_bombs)
FACE=$(ramaddr heli_face_left)
KIND=$(ramaddr muni_kind)
if [ -z "$GUN" ] || [ -z "$BOMBS" ] || [ -z "$FACE" ] || [ -z "$KIND" ]; then
    echo "FAIL muni:addr (weapon symbols not found in build/main.asm)"
    fail=$((fail+1))
else
    # The plan's loadout: 64 rounds, 10 bombs.
    run_case ammo_rest  "@x,shot"              --check-mem 0x$GUN=0x40 \
                                            --check-mem 0x$BOMBS=0x0A
    # HELI_GUN_RATE is 6, so 30 frames of held fire is exactly 5 rounds.
    run_case ammo_burst "@l,wait10,b30,shot"   --check-mem 0x$GUN=0x3B
    # Bombs are edge-triggered: holding A must not empty the rack.
    run_case ammo_bomb  "@x,wait10,a1,shot"    --check-mem 0x$BOMBS=0x09
    run_case ammo_bomb2 "@l,wait10,a1,wait5,a1,shot" --check-mem 0x$BOMBS=0x08
    # Firing past empty must stop at zero, not wrap to 255.
    run_case ammo_empty "@l,wait10,b400,shot"  --check-mem 0x$GUN=0x00

    # The gun points where the nose points, and the nose follows the last
    # commanded direction rather than the coasting velocity.
    run_case ammo_face  "@x,wait10,left20,shot" --check-mem 0x$FACE=0x01

    # Pool lifecycle. A bomb falls from the airframe to the ground in ~25
    # frames and retires on contact; a round retires on BULLET_LIFE instead,
    # which is what stops sustained fire from starving the pool.
    run_case muni_bomb_live   "@x,wait10,a1,shot"          --check-mem 0x$KIND=0x02
    run_case muni_bomb_fall   "@x,wait10,a1,wait10,shot"   --check-mem 0x$KIND=0x02
    run_case muni_bomb_ground "@l,wait10,a1,wait40,shot"   --check-mem 0x$KIND=0x00
    run_case muni_gun_live    "@x,wait10,b1,shot"          --check-mem 0x$KIND=0x01
    run_case muni_gun_range   "@x,wait10,b1,wait45,shot"   --check-mem 0x$KIND=0x00
    # A round leaves at muzzle height: the airframe's 8.8 y plus 7 px. This
    # once came out as 0x0200 - a compiler bug restored the argument through
    # an 8-bit TYA - and every round spawned on the HUD row.
    MY=$(ramaddr muni_y)
    run_case muni_gun_muzzle  "@x,wait10,b1,shot"          --check-mem16 0x$MY=0x6700
fi

# ---------------------------------------------------------------------------
# Phase 5 - landing pad and rearm.
#
# The player's deck spans world x 1024..1071, so the airframe's centre has
# to be inside that window - x 1008..1055 - when it touches the floor.
# Since the airlift, a powered descent lands anywhere on the ground; only
# a deck rearms (heli_on_pad). Touching down faster than HELI_CRASH_VY
# (2.5 px/frame) is a crash, so every landing here eases off: 30 frames
# of Down from hover height and a coast arrives under it; 32 does not,
# and a full-stick descent hits at 4. The flight figures are the inertia
# rework's: right180 and a 60-frame coast puts the airframe at x 1014.
# ---------------------------------------------------------------------------
LAND=$(ramaddr heli_landed)
ONPAD=$(ramaddr heli_on_pad)
FUEL=$(ramaddr heli_fuel)
if [ -z "$LAND" ] || [ -z "$FUEL" ]; then
    echo "FAIL pad:addr (heli_landed/heli_fuel not found in build/main.asm)"
    fail=$((fail+1))
else
    # Descending onto the deck lands on it; stopping short (x 714) or
    # overshooting (x 1314) lands on open ground - down, but no deck.
    run_case pad_land      "@x,wait20,right180,wait60,down30,wait40,shot"  --check-mem 0x$LAND=0x01 \
                                                                 --check-mem 0x$ONPAD=0x01
    run_case pad_short     "@x,wait20,right120,wait60,down30,wait40,shot"  --check-mem 0x$LAND=0x01 \
                                     --check-mem 0x$ONPAD=0x00 --check-mem16 0x$HY=0x9800
    run_case pad_over      "@x,wait20,right240,wait60,down30,wait40,shot"  --check-mem 0x$LAND=0x01 \
                                                                 --check-mem 0x$ONPAD=0x00

    # A landed airframe does not slide: down at the start, then held right
    # for 190 frames, it is still at x 64 on open ground, not on the deck.
    run_case pad_slide     "@x,wait20,down30,wait40,right190,shot"  --check-mem 0x$LAND=0x01 \
                                     --check-mem 0x$ONPAD=0x00 --check-mem16 0x$HX=0x0040

    run_case pad_takeoff   "@x,wait20,right180,wait60,down30,wait40,up20,shot" --check-mem 0x$LAND=0x00

    # Too fast: a full-stick descent onto the deck is a crash - a life gone.
    LIVES=$(ramaddr heli_lives)
    run_case pad_crash     "@x,wait20,right180,wait60,down80,shot" --check-mem 0x$LIVES=0x03 \
                                                                --check-mem 0x$LAND=0x00

    # Full rearm: fuel back to 100, and the reload countdowns give back rounds
    # at 20 frames each and bombs at 10 while the airframe sits.
    run_case pad_rearm "@l,wait20,b60,a1,right180,wait60,down30,wait40,wait120,shot" \
                                             --check-mem 0x$LAND=0x01 \
                                             --check-mem 0x$FUEL=0x64 \
                                             --check-mem 0x$GUN=0x3D \
                                             --check-mem 0x$BOMBS=0x0A

    # One unit per 64 frames aloft.
    run_case fuel_burn "@l,wait20,right240,shot" --check-mem 0x$FUEL=0x60

    # Dry tank: gravity is allowed in exactly one place in the plan and this
    # is it. The airframe sinks with no input at all, and open ground is not
    # a deck: touching it on a dead stick is a crash landing - a life gone,
    # and by 7200 frames the next airframe is up at hover height with a
    # full tank less the few units it has burned since.
    LIVES=$(ramaddr heli_lives)
    run_case fuel_dry "@l,wait7200,shot" --check-mem 0x$LIVES=0x03 \
                                      --check-mem16 0x$HY=0x6000 \
                                      --check-mem 0x$LAND=0x00
fi

# ---------------------------------------------------------------------------
# Phase 6 - ground units.
#
# Both bases send a rotating column; the two meet mid-field and stop, because
# traffic control blocks on any unit ahead in the lane, not only a friendly.
# ---------------------------------------------------------------------------
# A unit is a `#[soa] struct Unit`, so every field is its own plane: x_px at
# two bytes per slot, hp at one, and the kind's own tag and payload planes at
# one byte per slot each.
UK=$(ramaddr units__kind__tag)
UD=$(ramaddr units__kind__data)
UX=$(ramaddr units__x_px)
UHP=$(ramaddr units__hp)
FNMI=$(ramaddr frames_nmi)
FLOOP=$(ramaddr frames_loop)
if [ -z "$UK" ] || [ -z "$UX" ] || [ -z "$FNMI" ]; then
    echo "FAIL unit:addr (unit/frame symbols not found in build/main.asm)"
    fail=$((fail+1))
else
    # The player's base only sends what is ordered (phase 7); the enemy's
    # sends the CPU's convoys (phase 10). Most cases run on the quiet
    # harness mission (`@l`: single-unit convoys, launchers and engineers
    # bought as men, a pilot that only wanders and refits); the other two
    # holds take the rows with a forced column and, for `@r`, a pilot
    # that hunts and bombs. On the quiet row the
    # first buy, at frame 64, is I - five men - so the first unit out is
    # an infantryman marching west from x=7680: the pool is a tagged
    # enum, so slot 0's kind is the first byte of its tag plane. Every
    # unit walks at half a pixel a frame - a pixel on each odd frame - so
    # at loop frame 615 (a wait of 600 plus the movie's lead-in) he is at
    # 7405. The column's whole shape at any frame is `./play.sh x.png
    # waitN,shot --dump wram x.wram` and `tools/poolstat.py --brief
    # x.wram`; every figure below came from that.
    UO=$(ramaddr units__owner)
    run_case unit_spawn "@l,wait200,shot"  --check-mem 0x$UK=0x04 --check-mem 0x$UO=0x01
    run_case unit_march "@l,wait600,shot"  --check-mem16 0x$UX=0x1CED

    # A spawn order of Kind values becomes a variant, and the hit points
    # come from that variant's row of unit_stats. The hot harness row (R
    # held) buys IMEV and nothing else - five men, a missile truck, two
    # engineers and a van - so by frame 2400 the column is one of every
    # kind but the tank, each checked against its tag and its hp; the
    # launcher's payload is `armed`, 1 until it fires. The tank's row is
    # covered by tank_crush, which buys one.
    at() { printf '%X' $((0x$1 + $2)); }            # tag plane: one byte per slot
    hp() { printf '%X' $((0x$UHP + $1)); }          # slot N's hit points
    run_case unit_kinds "@r,wait2401,shot" \
        --check-mem 0x$(at "$UK" 0)=0x04  --check-mem 0x$(hp 0)=0x05 \
        --check-mem 0x$(at "$UK" 5)=0x03  --check-mem 0x$(hp 5)=0x08 \
        --check-mem 0x$(at "$UD" 5)=0x01 \
        --check-mem 0x$(at "$UK" 6)=0x05  --check-mem 0x$(hp 6)=0x05 \
        --check-mem 0x$(at "$UK" 8)=0x02  --check-mem 0x$(hp 8)=0x0C

    # March order (phase 10). One speed for every unit means nothing
    # overtakes, so each side's column is a list from its lead back, and
    # a follower halts only behind a halted unit ahead. Three bought tanks
    # (slots 0, 2, 4) cross the field a convoy space apart; the lead holds
    # 117 px short of the bunker at 5120, the enemy's since its men took
    # it, to shell it, and the two behind pack up at exactly width + gap
    # (31 px, a pixel of it the odd-frame step) and halt in turn - every
    # flag set. The wait is in vblanks and the loop drops a few percent of
    # them by here; the snapshot is loop frame ~9330, the bunker at 37.
    UB=$(ramaddr units__block)
    run_case march_order "@l,l+a3,wait3,l+a3,wait3,l+a3,wait9600,shot" --timeout 600000 \
        --check-mem 0x$(at "$UB" 0)=0x01 --check-mem16 0x$(at "$UX" 0)=0x138B \
        --check-mem 0x$(at "$UB" 2)=0x01 --check-mem16 0x$(at "$UX" 4)=0x136C \
        --check-mem 0x$(at "$UB" 4)=0x01 --check-mem16 0x$(at "$UX" 8)=0x134D

    # Frame budget. The NMI counts real frames and the loop counts ticks it
    # finished; a full field must still keep up. The opening buys the whole
    # purse in tanks so the player's half of the field is there to meet the
    # enemy column, and by the snapshot all 32 slots are live.
    #
    # The pool was 16 until the compiler learned to keep an indexing loop
    # counter in Y (a const bound folded to a literal, a u16 counter for an
    # array index, and a scaled index no longer disqualifying it) and
    # oam_end stopped sweeping a hundred idle slots a frame. At 32 with the
    # traffic slice at 4 it was exact; the structures (phase 8: fifteen
    # buildings culled a frame, turrets, bunkers, the super bunker, bases
    # and banks all ticking, munitions tested against them, and sprites
    # straddling the left edge drawn at a negative 9-bit X rather than
    # culled, and the bases' van scan of phase 9) cost 178 frames in 3666
    # here - 0.951, accepted as the stress case, and what the pair pins.
    # The tanks' building sweep (a walk of the sorted structure pool from
    # the tank's own end, every sixteen idle frames) is another 50, and
    # the riflemen's sweep and pose 23 more, the camera lookahead and the
    # super bunker's ground gun 4, the riflemen's turret fallback 20, the
    # airlift's calls and the L overlay mask 5, and the eight order dialogs
    # this movie opens and closes (a compose and two 512-byte flushes each)
    # 12, the tanks' crush check (one remembered unit a frame) 31: 0.942;
    # the radar (a 512-byte copy, a plot per unit and a 512-byte DMA every
    # sixteenth frame, spread over four of them - about 2.5% of a frame on
    # average) 269: 0.868, and its camera bracket as a sprite - one OAM
    # entry a frame - another 67: 0.850; and the end of lanes, every unit
    # on one line halting for anything ahead, 102: 0.822 - the columns
    # bunch tighter at the front and more of the pool is on screen at
    # once. That last step is the nonlinearity of this
    # measure, not the radar's real cost: this movie sits on the budget
    # line, and a frame over it by a hair drops whole; an idle frame with
    # the radar drops nothing. (frames_nmi is two lower than it was: the
    # probe now resets right before the NMI is enabled, so the inits no
    # longer count.) Steady-state the dialog costs nothing.
    # The next cycles are in unit_advance's call and the traffic scan.
    EIGHT_TANKS="l+a3,wait3,l+a3,wait3,l+a3,wait3,l+a3,wait3,l+a3,wait3,l+a3,wait3,l+a3,wait3,l+a3,wait3"
    # Phase 10: the CPU column in place of the placeholder, one speed and
    # the march order in place of the sliced traffic scan, and a pixel on
    # odd frames in place of a sub-pixel add per unit: 0.896. (The CPU's
    # tick itself is under half a percent; the column's shape moves the
    # figure more than any code does.) The enemy airframe - its physics,
    # its collisions and its draw - 0.870, after gating both airframes'
    # munition walks on the other side's count in flight and the balloon
    # scan on height: this movie sits on the budget line, so a percent of
    # frame is a dozen frames. The pilot and the original's purchasing:
    # 0.824 - the first mission's column is three squads of men, fifteen
    # riflemen sweeping, against the eight tanks - and the smart missiles
    # 0.821. The rifle's timer as an Infantry method and its shot as pool
    # code, once a payload's self stopped being a pool index: 0.809.
    run_case unit_budget "@l,$EIGHT_TANKS,wait3600,shot" --check-mem16 0x$FNMI=0x0E50 \
                                                      --check-mem16 0x$FLOOP=0x0B93

    # The headline constraint: at a bunched column the PPU must still be able
    # to draw everything standing on those scanlines. Eight tanks in three
    # lanes measure 16 sprites / 32 tiles on one line against 32 / 34 - the
    # sprite budget, not the CPU, is what a bigger front runs into.
    budget_case unit_oam "@l,$EIGHT_TANKS,wait3600,right520,wait60,shot"
fi

# ---------------------------------------------------------------------------
# Phase 7 - economy and ordering.
#
# Funds grow with the helicopter's distance from the west edge; with L held,
# Left/Right walk the order ring and A buys (X is the paratroop drop). Every check is on the ROM's own state: the purse,
# the selection, and what came out of the base.
# ---------------------------------------------------------------------------
FUNDS=$(ramaddr funds)
SEL=$(ramaddr order_sel)
LIVES=$(ramaddr heli_lives)
QMEN=$(ramaddr order_men)
if [ -z "$FUNDS" ] || [ -z "$SEL" ] || [ -z "$LIVES" ]; then
    echo "FAIL order:addr (order symbols not found in build/main.asm)"
    fail=$((fail+1))
else
    # 32 funds, the tank selected, four lives.
    run_case order_boot "@l,wait60,shot" --check-mem 0x$FUNDS=0x20 --check-mem 0x$SEL=0x02 \
                                      --check-mem 0x$LIVES=0x04

    # One press buys one tank: it comes out of the player's base at x=512
    # marching east, and the cost comes off at once.
    run_case order_tank "@l,l+a3,wait30,shot" --check-mem 0x$FUNDS=0x1C \
        --check-mem 0x$(at "$UK" 0)=0x01 --check-mem 0x$UO=0x00 --check-mem16 0x$UX=0x0211

    # Right moves the ring to infantry; one order is five men, and the gate
    # lets the next out only when the last is a convoy space (32 px, 128
    # frames at a man's pace) clear of it: a minute in, one is on the field
    # and four still wait in the emitter.
    run_case order_infantry "@l,l+right3,wait3,l+a3,wait60,shot" --check-mem 0x$FUNDS=0x1B \
        --check-mem 0x$(at "$UK" 0)=0x04 --check-mem 0x$QMEN=0x04

    # Left twice wraps to the van. Its cap is six, counted on the field and
    # in the queue: the seventh press is refused and costs nothing, so the
    # purse is 32 - 6*2, and the first van is out.
    SEVEN="l+a3,wait3,l+a3,wait3,l+a3,wait3,l+a3,wait3,l+a3,wait3,l+a3,wait3,l+a3"
    run_case order_cap "@l,l+left3,wait3,l+left3,wait3,$SEVEN,wait80,shot" --check-mem 0x$FUNDS=0x14 \
        --check-mem 0x$SEL=0x00 --check-mem 0x$(at "$UK" 0)=0x02

    # Right three times from the tank is the helicopter: an extra life for 20.
    run_case order_heli "@l,l+right3,wait3,l+right3,wait3,l+right3,wait3,l+a3,wait10,shot" \
        --check-mem 0x$FUNDS=0x0C --check-mem 0x$LIVES=0x05 --check-mem 0x$SEL=0x05

    # Income. A push to the far end and a wait there pays out; the exact
    # figure is the threshold's - and, since phase 8, the no-fly zone's:
    # the enemy base's missiles send the airframe home part way, which is
    # why it is less than it was.
    run_case econ_income "@l,right1500,wait300,shot" --check-mem 0x$FUNDS=0x2A
fi

# ---------------------------------------------------------------------------
# Phase 8 - structures.
#
# Fifteen buildings from the level table. Turrets fire at the other side's
# units and, if the enemy's, at the helicopter; gunfire wears them down.
# ---------------------------------------------------------------------------
HHP=$(ramaddr heli_hp)
SHP=$(ramaddr structs__hp)
if [ -z "$HHP" ] || [ -z "$SHP" ]; then
    echo "FAIL struct:addr (structure symbols not found in build/main.asm)"
    fail=$((fail+1))
else
    # The enemy turret at x=6656 (level entry 12) lofts rounds at an
    # approaching airframe: 20 hp becomes 14 on the way in.
    run_case turret_heli "@l,wait20,right1290,wait90,shot" --check-mem 0x$HHP=0x0F

    # Land in front of it and fire back: a round is a point off its 62 -
    # four of the fifteen fired land in this time (the rest are still in
    # flight or lost to its self-repair between), and its fire keeps
    # coming. How many have landed by this frame is a phase; re-baseline
    # it if a change shifts the run by a frame, but do not delete it.
    run_case turret_gunfire "@l,wait20,right1290,down30,wait40,b90,shot" \
        --check-mem 0x$(at "$SHP" 12)=0x3A --check-mem 0x$HHP=0x0E

    # The balloon over the player's own bunker (x=2048) kills the airframe
    # on contact, at frame 421 of this climb: a life gone, the airframe
    # back at the start but hidden for HELI_RESPAWN (120) frames, and the
    # camera - 1945 at the loss, the lookahead included - panning home at
    # 1945/120+1 = 17 px a frame on top of the follow's 6. Sixty frames on
    # it is 565 and the
    # canopy colour is nowhere on screen (the screenshot trails the OAM
    # shadow by two frames, so the kill frame itself still shows it); at
    # 120 the view is home and the next airframe starts rising out of the
    # ground at the start - a pixel a frame from the ground line (168) to
    # hover height (96), behind the dirt until it has cleared it, the stick
    # dead meanwhile; at 192 it is there and the stick works again: ten
    # frames of thrust from rest is 13 px.
    HX=$(ramaddr heli_x_px)
    DEAD=$(ramaddr heli_dead)
    RISE=$(ramaddr heli_rising)
    run_case balloon_kill "@l,up20,right401,shot" --check-mem 0x$LIVES=0x03 \
        --check-mem16 0x$HX=0x0040 --check-mem 0x$DEAD=0x78 --check-mem16 0x$CAM=0x0799
    run_case balloon_pan "@l,up20,right401,wait60,shot" \
        --check-mem16 0x$HX=0x0040 --check-mem 0x$DEAD=0x3C --check-mem16 0x$CAM=0x0235
    expect_snes_none balloon_pan "14,22,28"                         # canopy
    run_case balloon_rise "@l,up20,right401,wait120,right10,shot" \
        --check-mem16 0x$HX=0x0040 --check-mem 0x$DEAD=0x00 --check-mem 0x$RISE=0x01 \
        --check-mem16 0x$HY=0x9E00 --check-mem16 0x$CAM=0x0000
    run_case balloon_respawn "@l,up20,right401,wait192,right10,shot" \
        --check-mem16 0x$HX=0x004D --check-mem 0x$RISE=0x00 --check-mem16 0x$HY=0x6000
    expect_snes balloon_respawn "14,22,28" 0.02

    # An enemy infantryman walking into the neutral bunker at x=5120 (level
    # entry 9) takes it and is spent doing so. The CPU's first man is out
    # at frame 64 and covers 2560 px at half a pixel a frame: by 5300 the
    # bunker is the enemy's and slot 0 is free.
    SOWN=$(ramaddr structs__owner)
    run_case bunker_capture "@l,wait5300,shot" --timeout 400000 \
        --check-mem 0x$(at "$SOWN" 9)=0x01 --check-mem 0x$(at "$UK" 0)=0x00

    # Tanks shell the other side's turrets and bunkers, holding in place
    # until the building falls. Two bought tanks crush the column's men at
    # the front around frame 7400 (tank_crush below), take the column's
    # first tank between them, and roll on to the bunker at x=5120 (level
    # entry 9) - the enemy's since its first man took it at ~5250 - hold
    # short of it and bring its 69 hp down at 8 a shell, one every 90
    # frames: by 10600 it is rubble and nobody's. (The column's own tanks
    # come behind its men, who take the player's bunker before any tank
    # could shell it; the enemy side of the rule was checked on an earlier
    # column, and by planting a tank with the debugger.)
    run_case tank_bunker "@l,l+a3,wait3,l+a3,wait10600,shot" --timeout 600000 \
        --check-mem 0x$(at "$SHP" 9)=0x00 --check-mem 0x$(at "$SOWN" 9)=0x02

    # Infantry gunfire: no round, the sweep that finds a target lands the
    # hit. Five men are ordered (the CPU's first man takes slot 0 at frame
    # 64, so they are slots 2, 4, 6, 8 and 9); they walk east at the
    # column's own pace and meet its leading men at x~4100 around loop
    # frame 7210. A hundred frames on, the exchange has gone both ways:
    # the player's first two men (slots 2 and 4) and the enemy's first
    # (slot 3) are gone, and the pair now facing each other - the enemy's
    # slot 5 and the player's slot 6 - are each down to their last point,
    # with the next of each (7 and 8) untouched behind them. The wait is
    # in vblanks and the loop drops some ten percent of them under fifteen
    # riflemen's sweeps by here, so the meeting drifts with every heavier
    # build; re-measure when it moves.
    run_case rifle_fire "@l,l+right3,wait3,l+a3,wait8200,shot" --timeout 400000 \
        --check-mem 0x$(at "$UK" 2)=0x00 --check-mem 0x$(at "$UK" 3)=0x00 \
        --check-mem 0x$(at "$UK" 4)=0x00 --check-mem 0x$(hp 5)=0x01 \
        --check-mem 0x$(hp 6)=0x01 --check-mem 0x$(hp 7)=0x05 \
        --check-mem 0x$(hp 8)=0x05
    # ... and a tank does not stop for the other side's men: it drives
    # over them. A bought tank (slot 0, out before the CPU's first man)
    # meets the column at x~4190 around loop frame 7300 and has rolled
    # through its five leading men a hundred frames later - slots 1-5
    # free, the tank untouched - while the next squad's first man (slot
    # 6) is 200 px ahead of it. Its payload is the gun reload, cycling
    # 16..0 with nothing in range - a phase; re-baseline it if a change
    # shifts the column by a frame, but do not delete it.
    run_case tank_crush "@l,l+a3,wait7492,shot" --timeout 400000 \
        --check-mem 0x$(at "$UK" 1)=0x00 --check-mem 0x$(at "$UK" 2)=0x00 \
        --check-mem 0x$(at "$UK" 3)=0x00 --check-mem 0x$(at "$UK" 4)=0x00 \
        --check-mem 0x$(at "$UK" 5)=0x00 --check-mem 0x$(hp 0)=0x19 \
        --check-mem 0x$(at "$UK" 6)=0x04 --check-mem16 0x$(at "$UX" 12)=0x1135 \
        --check-mem 0x$(at "$UD" 0)=0x0C
    # The super bunker as a tank target was checked with the debugger: a
    # bought tank planted at x=3968 before the bunker at 4076 given three
    # enemy men held, put them out one a shell, and moved on once it was
    # nobody's.

    # The enemy base's missiles: an airframe pushed into its 320 px is lost
    # inside two hundred frames and comes back at the start with a life gone.
    run_case base_missile "@l,wait20,right1500,wait300,shot" --check-mem 0x$LIVES=0x03 \
                                                          --check-mem 0x$HHP=0x14

    # The enemy column's launcher fires its one homing missile at an
    # airframe inside LAUNCHER_RANGE (224 px) and is spent doing so: the
    # slot is free, the missile lands for 10 of the 20 hp, and no life is
    # lost. The third harness row (L+R) is the one for this: it buys MIVV,
    # so the truck is the column's lead and slot 0, and its pilot hunts
    # nothing, so the airframe can cross the field. It climbs first, to
    # pass over the enemy airframe on the way, and stops at x~7080 with
    # the truck just ahead, short of the base's 320 px no-fly zone.
    run_case launcher_fire "@l+r,wait20,up40,right1400,wait120,shot" \
        --check-mem 0x$(at "$UK" 0)=0x00 --check-mem 0x$HHP=0x0A \
        --check-mem 0x$LIVES=0x04

    # Only one missile truck of a side fires at a time. Two bought
    # launchers (the ring's entry left of Tank; slots 0 and 2) march east
    # 32 px apart and the enemy airframe's wander passes over both at
    # x~1850 around loop frame 2280: the lead fires - its slot free, its
    # missile up with most of its 180 frames left - and the second, well
    # inside the 224 px too, holds, still armed (its payload 1), until
    # that missile is spent.
    MK=$(ramaddr muni_kind)
    run_case launcher_one "@l,l+left3,wait3,l+a3,wait3,l+a3,wait2262,shot" \
        --check-mem 0x$(at "$UK" 0)=0x00 --check-mem 0x$(at "$UK" 2)=0x03 \
        --check-mem 0x$(at "$UD" 2)=0x01 --check-mem 0x$(at "$MK" 5)=0x05

    # The super bunker (level entry 7, dead centre) starts empty and nobody's.
    # The CPU's first squad walks the field - its first man is spent on the
    # bunker at 5120 - and the other four, with the first man of the next
    # squad behind them, go inside one after another from frame ~7300:
    # five men, full, and it is the enemy's. The wait is in vblanks and the
    # loop drops a few percent of them under the column, so the margin here
    # is what keeps a build a few hundred cycles slower from failing the
    # case.
    SMEN=$(ramaddr structs__men)
    run_case super_manned "@l,wait8200,shot" --timeout 400000 \
        --check-mem 0x$(at "$SMEN" 7)=0x05 --check-mem 0x$(at "$SOWN" 7)=0x01
fi

# ---------------------------------------------------------------------------
# The HUD rows and the radar (design.md). The strip's rows are composed
# from the glyph rows so their tile IDs are whatever bmp2chr decided;
# the radar is the game's own bitmap and can be checked byte for byte.
# At boot, once it has drawn (every 16th frame): tile 0 carries the
# airframe's 2x2 (blue) at radar x 2-3 on rows 1-2 ($30 of each plane byte) and
# the bank's tick at x 3 on rows 3-5; row 0 is plain navy, and so is row 7,
# the vehicles' line, with none out. The camera
# window is a sprite over the row, in the slot after the airframe's two:
# at boot x 0, y 8 (the row's first scanline - the radar is map row 1
# since the airframe's gauges moved to the bottom row), the bracket tile.
# ---------------------------------------------------------------------------
RB=$(ramaddr radar_buf)
if [ -z "$RB" ]; then
    echo "FAIL radar:addr (radar_buf not found in build/main.asm)"; fail=$((fail+1))
else
    rb() { printf '%X' $((0x$RB + $1)); }
    run_case radar_boot "@l,wait16,shot" \
        --check-mem 0x$(rb 0)=0xFF --check-mem 0x$(rb 1)=0x00 \
        --check-mem 0x$(rb 2)=0xCF --check-mem 0x$(rb 3)=0x30 \
        --check-mem 0x$(rb 4)=0xCF --check-mem 0x$(rb 5)=0x30 \
        --check-mem 0x$(rb 6)=0xEF --check-mem 0x$(rb 7)=0x10 \
        --check-mem 0x$(rb 10)=0xEF --check-mem 0x$(rb 11)=0x10 \
        --check-mem 0x$(rb 14)=0xFF --check-mem 0x$(rb 15)=0x00 \
        --check-mem 0x$(printf '%X' $((0x$OAMB + 8)))=0x00 \
        --check-mem 0x$(printf '%X' $((0x$OAMB + 9)))=0x08 \
        --check-mem 0x$(printf '%X' $((0x$OAMB + 10)))=0x1F
    # Flown east 240 frames: the airframe's block has left tile 0, so the
    # bank's tick stands alone, and the bracket sprite is at camera_x/32.
    run_case radar_flown "@l,wait20,right240,wait20,shot" \
        --check-mem 0x$(rb 2)=0xFF --check-mem 0x$(rb 3)=0x00 \
        --check-mem 0x$(rb 6)=0xEF --check-mem 0x$(rb 7)=0x10 \
        --check-mem 0x$(printf '%X' $((0x$OAMB + 8)))=0x25
    # The strip itself: the two white gauges on row 0 are what puts this
    # much white across the top 8 lines of the screen.
    expect_snes radar_boot "28,30,31" 0.9
fi

# ---------------------------------------------------------------------------
# The order overlay (design.md): shown while L is held, on BG1 rows 3-10.
# Right with L down moves the highlight from the tank to the infantry and
# leaves the airframe where it was; letting go of L hides the box and
# keeps the selection. The snapshot itself is taken with L still down in
# the first case (Select combined with L).
# ---------------------------------------------------------------------------
OVS=$(ramaddr hud_ov_shown)
if [ -z "$OVS" ]; then
    echo "FAIL overlay:addr (hud_ov_shown not found in build/main.asm)"; fail=$((fail+1))
else
    run_case overlay_show "@l,wait30,l20,l+right3,l+select3" \
        --check-mem 0x$OVS=0x01 --check-mem 0x$SEL=0x03 --check-mem16 0x$HX=0x0040
    run_case overlay_hide "@l,wait30,l20,l+right3,l10,wait5,shot" \
        --check-mem 0x$OVS=0x00 --check-mem 0x$SEL=0x03 --check-mem16 0x$HX=0x0040
fi

# ---------------------------------------------------------------------------
# The airlift (design.md, decided after phase 9).
#
# Five men are bought and the airframe lands on the player's pad facing
# east and the men walk up from the west: each boards under its middle,
# within 5 px of its centre. Lifted off, X drops one per press; a chute
# takes ~20 frames from this height, and a landed man is an infantryman
# again. The RNG is consumed by nothing else, so from a cold boot the
# sequence is fixed: the third and fourth chutes are the ones in ten that
# fail (an unlucky stretch of the LFSR), so three men of five reach the
# ground, in the pool slots the cursor hands out.
# ---------------------------------------------------------------------------
MEN=$(ramaddr heli_men)
if [ -z "$MEN" ]; then
    echo "FAIL para:addr (heli_men not found in build/main.asm)"; fail=$((fail+1))
else
    BOARD="l+right3,wait3,l+a3,wait20,right180,wait60,down30,wait40,wait2800"
    run_case airlift_board "@l,$BOARD,shot" --timeout 200000 \
        --check-mem 0x$MEN=0x05 --check-mem 0x$LAND=0x01 \
        --check-mem 0x$(at "$UK" 0)=0x00 --check-mem 0x$(at "$UK" 4)=0x00
    # In the field: landed on open ground at x 714 facing east, the men walk
    # up under it from the base and board there too; no deck needed.
    run_case airlift_field "@l,l+right3,wait3,l+a3,wait20,right120,wait60,down30,wait40,wait1600,shot" \
        --timeout 200000 --check-mem 0x$MEN=0x05 --check-mem 0x$LAND=0x01 --check-mem 0x$ONPAD=0x00
    # Men aboard go down with the airframe: five aboard, then a balloon
    # (the player's own bunker's, at x=2048) and the next airframe has none.
    run_case airlift_lost "@l,$BOARD,up+right36,right220,shot" --timeout 200000 \
        --check-mem 0x$MEN=0x00 --check-mem 0x$LIVES=0x03
    # Lost a third of the band up or higher, one man bails out first: the
    # balloon catches it at hover height, so one paratrooper is in the air
    # ten frames on. A crash at the ground line from the same load drops
    # nobody.
    PL=$(ramaddr para_live)
    run_case airlift_bail "@l,$BOARD,up+right36,right220,wait10,shot" --timeout 200000 \
        --check-mem 0x$PL=0x01 --check-mem 0x$MEN=0x00 --check-mem 0x$LIVES=0x03
    run_case airlift_crash "@l,$BOARD,up40,wait60,down80,wait5,shot" --timeout 200000 \
        --check-mem 0x$PL=0x00 --check-mem 0x$MEN=0x00 --check-mem 0x$LIVES=0x03
    DROPS="x3,wait40,x3,wait40,x3,wait40,x3,wait40,x3"
    run_case airlift_drop "@l,$BOARD,up20,right40,$DROPS,wait140,shot" --timeout 200000 \
        --check-mem 0x$MEN=0x00 \
        --check-mem 0x$(at "$UK" 21)=0x04 --check-mem 0x$(at "$UK" 22)=0x04 \
        --check-mem 0x$(at "$UK" 23)=0x04 --check-mem 0x$(at "$UK" 24)=0x00 \
        --check-mem 0x$(at "$UO" 21)=0x00
fi

# ---------------------------------------------------------------------------
# Phase 9 - win and loss.
#
# Two ends only: a van at the other side's base, or no helicopters left.
# The van cannot be scripted from the pad in useful time - it was checked by
# planting one at the enemy base with the debugger - so the suite covers the
# other end and the way back.
# ---------------------------------------------------------------------------
GS=$(ramaddr game_state)
if [ -z "$GS" ]; then
    echo "FAIL game:addr (game_state not found in build/main.asm)"
    fail=$((fail+1))
else
    # Five passes into the enemy base's missiles lose all four airframes:
    # the match ends (2 = DEFEAT) and the last one is not replaced.
    PASS_="wait20,right1500,wait300"
    run_case game_lost "@l,$PASS_,$PASS_,$PASS_,$PASS_,$PASS_,shot" --timeout 300000 \
        --check-mem 0x$GS=0x02 --check-mem 0x$LIVES=0x00

    # Start begins a fresh match: playing, four lives, the airframe at the
    # start, the camera at the west edge.
    CAMX=$(ramaddr camera_x)
    run_case game_reset "@l,$PASS_,$PASS_,$PASS_,$PASS_,$PASS_,start,wait10,shot" --timeout 300000 \
        --check-mem 0x$GS=0x00 --check-mem 0x$LIVES=0x04 \
        --check-mem16 0x$HX=0x0040 --check-mem16 0x$CAMX=0x0000
fi

# ---------------------------------------------------------------------------
# Phase 10 - the CPU opponent. Its purse and its convoys (src/cpu.r65).
#
# The enemy earns as the player does, from its airframe's distance into
# the player's half against the 40000 threshold: slowly at first, the
# airframe leaving its start at the far edge, faster as it flies deeper.
# It buys as the original does: a random convoy it can afford, once the
# last has left the gate and the row's pause (22 s here) has run. On
# the quiet harness row (tier 1, so single units, with launchers and
# engineers bought as men) the first buy at frame 64 is I
# - five men for 5 - so by loop frame 315 the purse reads 29 with no
# income yet, the queue is drained, and the fifth man is waiting on the
# gate. The whole purchase sequence from a cold boot is fixed by the seed
# and the airframe's flight - I, I, I, T, ... - so any change to the
# tables, the pause, or the pilot moves every column-dependent case
# above; poolstat.py prints the purse and the queue.
# ---------------------------------------------------------------------------
CF=$(ramaddr cpu_funds)
CQ=$(ramaddr cpu_q)
CH=$(ramaddr cpu_head)
CT=$(ramaddr cpu_tail)
CM=$(ramaddr cpu_men)
if [ -z "$CF" ] || [ -z "$CQ" ]; then
    echo "FAIL cpu:addr (cpu_funds/cpu_q not found in build/main.asm)"
    fail=$((fail+1))
else
    run_case cpu_purse "@l,wait300,shot" --check-mem 0x$CF=0x1D \
        --check-mem 0x$(at "$CQ" 0)=0x03 \
        --check-mem 0x$CH=0x01 --check-mem 0x$CT=0x01 --check-mem 0x$CM=0x01
fi

# ---------------------------------------------------------------------------
# Phase 10 - the enemy airframe and its pilot (src/foe.r65). The player's
# physics and loadout on its own state, and a pilot adapted from Armor
# Alley's: refit, dodge, hunt, bomb, wander, in that order. On the quiet
# harness row it only wanders and refits; `@r` takes the hot one, where
# it hunts the player's airframe and bombs.
# ---------------------------------------------------------------------------
FX=$(ramaddr foe_x_px)
FY=$(ramaddr foe_y)
FHP=$(ramaddr foe_hp)
FL=$(ramaddr foe_lives)
FS=$(ramaddr foe_state)
FLAND=$(ramaddr foe_landed)
FGUN=$(ramaddr foe_gun)
FDEAD=$(ramaddr foe_dead)
if [ -z "$FX" ] || [ -z "$FL" ]; then
    echo "FAIL foe:addr (foe_x_px/foe_lives not found in build/main.asm)"
    fail=$((fail+1))
else
    # Wander: from the far edge it flies west at its row's clip speed
    # (176/64 = 2.75 px/frame) toward the player's end on the weave (four
    # heights, one every 64 frames); at frame 1215 it is at 4768, full.
    run_case foe_patrol "@l,wait1200,shot" --check-mem16 0x$FX=0x12A0 \
        --check-mem 0x$FHP=0x14 --check-mem 0x$FS=0x00 --check-mem 0x$FL=0x04

    # The pad. Fuel drains a unit every 64 frames; under 14 plus a unit
    # per 256 px of the trip home it turns for its own deck (x 7072, the
    # airframe centred at 7075), comes down at 2 px/frame easing to 0.75
    # for the last 24, lands at ~5780 and refuels a unit every 4 frames -
    # and repairs a point every 16 - before leaving full at ~6220.
    run_case foe_pad "@l,wait6000,shot" --check-mem16 0x$FX=0x1BA3 \
        --check-mem16 0x$FY=0x9800 --check-mem 0x$FLAND=0x01 --check-mem 0x$FS=0x01

    # The player's turret at 1536 fires on it as on the player's: the
    # wander takes it through the turret's 340 px on every lap, jinking
    # (the four-height, 16-frame weave at full vertical speed), and comes
    # out about seven points down each time - here 13 at frame 3000, and
    # alive; the deck repairs it.
    run_case foe_turret "@l,wait3000,shot" --check-mem 0x$FHP=0x0D --check-mem 0x$FL=0x04

    # The player's gun. The airframe waits at x~764, where the wander's
    # west turn (900) brings the enemy airframe into the gun's 320 px,
    # and fires for 150 frames: five rounds land, a point each, and the
    # enemy fires back on the way past - it shoots whatever is level, in
    # reach and faced, whether or not it hunts.
    run_case foe_gun "@l,wait20,right130,wait2400,b150,shot" --check-mem 0x$FHP=0x0F \
        --check-mem 0x$FL=0x04 --check-mem 0x$HHP=0x13

    # The hunt (hot harness row). Flown out to ~3100 and left hovering:
    # the enemy airframe, hunting, arrives at a standoff, level, and fires
    # until the player's airframe is lost - twenty points of gunfire and a
    # missile - then goes on to its next target with all four lives (what
    # the player's turret does to it on a bombing pass is foe_turret's).
    run_case foe_hunt "@r,wait20,right600,wait900,shot" --check-mem 0x$LIVES=0x03 \
        --check-mem 0x$FL=0x04

    # The bombs (eighth row). A bought tank, marching east from the base,
    # is found by the pilot on its way in - kill_tank and scatter_bomb are
    # on - and bombed from a hover over it: by frame 3000 the slot is
    # free, the tank having reached ~2000 otherwise (unit_budget's).
    run_case foe_bomb "@r,l+a3,wait3000,shot" --check-mem 0x$(at "$UK" 0)=0x00 \
        --check-mem 0x$LIVES=0x04

    # Smart missiles, the Y weapon: two per load, locked at launch on the
    # other side's airframe if it is in view, else on the nearest of its
    # vehicles, and whatever one hits is gone outright. With neither in
    # reach the press is refused and the missile is not spent - at boot
    # the enemy airframe is a world away and the first row's column is
    # all men.
    MISS=$(ramaddr heli_missiles)
    FMISS=$(ramaddr foe_missiles)
    run_case missile_hold "@l,wait20,y1,wait20,shot" --check-mem 0x$MISS=0x02

    # A vehicle: flown east to ~6700 against the third harness row's MIVV
    # column, one press takes the missile truck leading it at ~7100 -
    # slot 0 - and leaves the man behind it the new lead. The airframe
    # holds 400 px off, inside the missile's 640 but outside the truck's
    # own 224, so the empty slot can only be the missile's work; it takes
    # ~150 frames to cover the gap, and the men ahead of a mid-column
    # vehicle would otherwise take the hit first (which is why the column
    # for this one is led by the truck).
    run_case missile_unit "@l+r,wait20,right1330,y1,wait180,shot" \
        --check-mem 0x$MISS=0x01 --check-mem 0x$(at "$UK" 0)=0x00 \
        --check-mem 0x$(at "$UK" 1)=0x04

    # The other airframe: fired as it closes at ~2300 with the player at
    # 2114, it runs it down inside seventy frames - a life gone and the
    # next one waiting out its row's regen_time (30) at the far edge, four
    # frames into the count when the shot is taken.
    run_case missile_air "@r,wait20,right400,wait860,y1,wait70,shot" \
        --check-mem 0x$MISS=0x01 --check-mem 0x$FL=0x03 --check-mem 0x$FDEAD=0x1A

    # And the pilot's own, the original's `useMissile`: parked at the
    # ceiling mid-field, the player is out of the gun's line but not the
    # missile's - the hunting pilot climbs after it and spends one. The
    # player is lost with its health untouched, which is what tells a
    # missile from the gun; the shot is taken before the pilot is lost
    # itself, since a fresh airframe comes with a fresh pair of missiles.
    run_case missile_foe "@r,wait20,up40,right600,wait1400,shot" \
        --check-mem 0x$FMISS=0x01 --check-mem 0x$LIVES=0x03 --check-mem 0x$HHP=0x14

    # Two airframes that meet are both lost (foe_collide); the pilot
    # climbs or dives out of a closing airframe's plane (foe_evade), so
    # the meeting cannot be scripted in useful time - it was pinned here
    # before the pilot existed (a charge at the patrol: both lost, the
    # enemy's next airframe waiting out regen_time).
fi

# ---------------------------------------------------------------------------
# Phase 11 - the campaign (src/mission.r65). Every case above holds a
# shoulder button at power-on and so runs on a frozen harness row; this
# one boots with nothing held, which is the campaign's first mission, and
# checks that mission_set and the derived layout ran.
# ---------------------------------------------------------------------------
MISSION=$(ramaddr mission)
LCOUNT=$(ramaddr level_count)
SKIND=$(ramaddr structs__kind)
SX=$(ramaddr structs__x)
if [ -z "$MISSION" ] || [ -z "$SX" ]; then
    echo "FAIL mission:addr (mission symbols not found in build/main.asm)"
    fail=$((fail+1))
else
    sk() { printf '%X' $((0x$SKIND + $1)); }
    sx() { printf '%X' $((0x$SX + 2 * $1)); }
    # Cake Walk: row 0 asks for two turrets, one bunker and nothing
    # pre-owned, so the derived field is eight buildings west to east -
    # bank, base, turret, bunker, the super bunker dead centre, turret,
    # base, bank - with the middle three spaced through the contested
    # span. The pool must come out sorted: the draw cull and the munition
    # test both stop at the first building east of what they are asking
    # about. Kinds: 0 turret, 1 bunker, 2 super, 3 base, 4 bank.
    run_case mission_first "wait300,shot" \
        --check-mem 0x$MISSION=0x00 --check-mem 0x$LCOUNT=0x08 \
        --check-mem16 0x$(sx 2)=0x0600 --check-mem 0x$(sk 3)=0x01 \
        --check-mem16 0x$(sx 4)=0x0FEC --check-mem16 0x$(sx 7)=0x1F80

    # The front end (slice (b)): a campaign boot opens on the title page,
    # Start goes to the briefing and Start again into the battle. A page
    # is GAME_SCREEN with screen_kind saying which - 1 title, 2 briefing,
    # 3 after-action - and the field behind it is untouched, which is why
    # coming back is a BG1 map DMA and a hud_init rather than a reset.
    GSTATE=$(ramaddr game_state)
    SKIND2=$(ramaddr screen_kind)
    run_case screen_title "wait30,shot" \
        --check-mem 0x$GSTATE=0x03 --check-mem 0x$SKIND2=0x01
    run_case screen_brief "start,wait30,shot" \
        --check-mem 0x$GSTATE=0x03 --check-mem 0x$SKIND2=0x02
    # ... and the battle is the ordinary one: the page gone, the strip
    # back, the airframe flying (it has moved east of its start).
    run_case screen_battle "start,wait10,start,wait60,right60,shot" \
        --check-mem 0x$GSTATE=0x00 --check-mem 0x$SKIND2=0x00 \
        --check-mem16 0x$HX=0x0141

    # The continue code (slice (c)). The d-pad types four letters over the
    # title: Right moves the cursor, Up and Down run a letter through
    # A..P (a held direction repeats, a tap steps once - these movies tap).
    # Down from A wraps to P, which is letter 15.
    taps() { local o=""; local i=0; while [ $i -lt $2 ]; do o="$o$1,"; i=$((i+1)); done; printf '%s' "$o"; }
    CLET=$(ramaddr code_letters)
    CCUR=$(ramaddr code_cursor)
    SFUNDS=$(ramaddr start_funds)
    run_case code_type "wait20,down,right,wait10,shot" \
        --check-mem 0x$CLET=0x0F --check-mem 0x$CCUR=0x01

    # NKCH is mission 5 carrying 32: eleven bits of payload - four of
    # mission, seven of purse - and five of check, scrambled and cut into
    # four nibbles. Start takes what the page says it will, so the row's
    # own starting funds give way to the code's.
    NKCH="$(taps up 13)right,$(taps up 10)right,$(taps up 2)right,$(taps up 7)"
    run_case code_continue "wait20,${NKCH}start,wait20,shot" --timeout 200000 \
        --check-mem 0x$MISSION=0x04 --check-mem 0x$SFUNDS=0x20 \
        --check-mem 0x$SKIND2=0x02

    # One letter out is not a near miss, it is nothing: the check digits
    # reject it and Start begins a new campaign instead (1000 of the
    # 65536 spellings mean anything at all).
    NKCG="$(taps up 13)right,$(taps up 10)right,$(taps up 2)right,$(taps up 6)"
    run_case code_bad "wait20,${NKCG}start,wait20,shot" --timeout 200000 \
        --check-mem 0x$MISSION=0x00 --check-mem 0x$SKIND2=0x02

    # And the way out: four crash landings spend the four lives - 40
    # frames of Down from the hover is over HELI_CRASH_VY, and the next
    # airframe takes HELI_RESPAWN plus its climb - which ends the match,
    # and Start on the frozen field brings up the after-action page. It
    # spells the code for the next run - JKDG, this mission again with
    # the purse the row deals, since the match was lost - and leaves it
    # typed into the title's field. The salvage line reads 20: the
    # player's base, all the field it still holds with its airframes
    # gone and the middle of the first mission nobody's.
    LOSE_MOVIE="start,wait10,start,wait20,down40,wait200,down40,wait200,down40,wait200,down40,wait240,start,wait20"
    run_case screen_after "$LOSE_MOVIE,shot" \
        --check-mem 0x$GSTATE=0x03 --check-mem 0x$SKIND2=0x03 \
        --check-mem 0x$LIVES=0x00 \
        --check-mem 0x$(ramaddr after_salvage)=0x14 \
        --check-mem 0x$(ramaddr after_carry)=0x20 \
        --check-mem 0x$CLET=0x09 --check-mem 0x$(printf '%X' $((0x$CLET + 1)))=0x0A \
        --check-mem 0x$(printf '%X' $((0x$CLET + 2)))=0x03 \
        --check-mem 0x$(printf '%X' $((0x$CLET + 3)))=0x06
    # Slice (d), the campaign loop. Start on the after-action page goes on
    # to the next mission's briefing carrying what it settled - or back to
    # the same mission after a defeat, which is what this drives: mission
    # unchanged, and the purse the row deals rather than the carry.
    #
    # The winning side of the loop cannot be scripted in useful time (see
    # game_won: the van end takes a march across the world, and the enemy
    # airframe's four lives take as long). It was driven through the
    # debugger instead - `set` game_state to GAME_WON at a snapshot_point
    # break, then step the movie's Start presses:
    #   mission 1 won with 32 in hand -> salvage 20, carried 52, and the
    #   briefing that follows is mission 2 opening with 52;
    #   mission 10 won -> after_done, and Start brings up the end page.
    run_case campaign_retry \
        "$LOSE_MOVIE,start,wait20,shot" \
        --check-mem 0x$MISSION=0x00 --check-mem 0x$SKIND2=0x02 \
        --check-mem 0x$SFUNDS=0x20
fi

# ---------------------------------------------------------------------------
echo "---"
echo "$pass passed, $fail failed$([ $skipped -gt 0 ] && echo ", $skipped skipped")"
[ "$fail" -eq 0 ]

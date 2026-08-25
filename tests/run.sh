#!/usr/bin/env bash
# Scripted-input regression suite.
#
# Every completed implementation phase leaves a case here; the whole suite
# re-runs after each new phase so regressions surface immediately.
#
#   ./tests/run.sh            run all cases
#   ./tests/run.sh boot       run cases whose name matches 'boot'
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
    out=$(python3 "$PROJ/tools/parallax.py" "$SHOTS/$name-a.png" \
                  "$SHOTS/$name-b.png" --assert-bands "$bands" 2>&1)
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
# accelerates up to 5 px/frame, so every moving case travels further. The
# relation still holds exactly - at cam_r240 the airframe is at 1221, so the
# focus is 1237 and the camera settles at 1237 - 128 - 8 = 1101 = $044D.
# ---------------------------------------------------------------------------
CAM=$(ramaddr camera_x)
if [ -z "$CAM" ]; then
    echo "FAIL cam:addr (camera_x not found in build/main.asm)"; fail=$((fail+1))
else
    run_case cam_rest   "shot"                        --check-mem16 0x$CAM=0x0000
    run_case cam_r30    "wait20,right30,shot"         --check-mem16 0x$CAM=0x0033
    run_case cam_r120   "wait20,right120,shot"        --check-mem16 0x$CAM=0x01F5
    run_case cam_r240   "wait20,right240,shot"        --check-mem16 0x$CAM=0x044D
    run_case cam_back   "wait20,right240,left90,shot" --check-mem16 0x$CAM=0x0354
fi

# Four layers at four rates, and eight equal HDMA ground bands.
parallax_case parallax "shot" "wait20,right240,shot" 8

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
    run_case heli_rest  "shot"                --check-mem16 0x$HX=0x0040 \
                                              --check-mem16 0x$HY=0x6000
    run_case heli_right "wait20,right30,shot" --check-mem16 0x$HX=0x00AB

    # Leftward travel exercises the borrow path in heli_move_x. `>>` is a
    # logical shift even on signed types, so a negative delta cannot be
    # shifted apart - a round trip that lands mid-world proves the explicit
    # sign branch, where a clamp at 0 would not.
    run_case heli_back  "wait20,right240,left60,shot" --check-mem16 0x$HX=0x0452

    # All four clamps: world edge, and the flyable box between the HUD strip
    # and the ground at y=168.
    run_case heli_wall  "wait20,left30,shot"  --check-mem16 0x$HX=0x0000
    run_case heli_ceil  "wait20,up30,shot"    --check-mem16 0x$HY=0x1000
    run_case heli_floor "wait20,down60,shot"  --check-mem16 0x$HY=0x9800

    # Tilt is cosmetic and derived from velocity ALONG THE NOSE: OAM sprite
    # 0's tile selects the frame (0 nose-down, 4 level, 8 nose-up). Using the
    # raw sign of vx instead double-flips against hflip and pitches the nose
    # up under forward acceleration - verified on screen, not just in RAM.
    #
    # Phase 4 added facing. Flying left mirrors the airframe, which swaps the
    # two cells as well as setting hflip - so sprite 0 then holds the frame's
    # *far* tile (+2) and its attribute byte gains $40. Asserting both is what
    # tells a correct mirror from a frame picked at random.
    TILT=$(printf '%04X' $((0x$OAMB + 2)))
    ATTR=$(printf '%04X' $((0x$OAMB + 3)))
    run_case heli_tilt_level "shot"                --check-mem 0x$TILT=0x04 \
                                                   --check-mem 0x$ATTR=0x30
    run_case heli_tilt_right "wait20,right60,shot" --check-mem 0x$TILT=0x00 \
                                                   --check-mem 0x$ATTR=0x30
    run_case heli_tilt_left  "wait20,right120,left60,shot" \
                                                   --check-mem 0x$TILT=0x02 \
                                                   --check-mem 0x$ATTR=0x70
    # Reversing flips facing while vx is still positive, so the airframe is
    # briefly moving backwards along its own nose: it flares nose-up.
    # vx decays 16/frame from 320, so 10 frames leaves +160 against a -96
    # threshold. This is the only case that reaches the nose-up frame.
    run_case heli_tilt_flare "wait20,right120,left10,shot" \
                                                   --check-mem 0x$TILT=0x0A \
                                                   --check-mem 0x$ATTR=0x70

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
    run_case ammo_rest  "shot"              --check-mem 0x$GUN=0x40 \
                                            --check-mem 0x$BOMBS=0x0A
    # HELI_GUN_RATE is 6, so 30 frames of held fire is exactly 5 rounds.
    run_case ammo_burst "wait10,b30,shot"   --check-mem 0x$GUN=0x3B
    # Bombs are edge-triggered: holding A must not empty the rack.
    run_case ammo_bomb  "wait10,a1,shot"    --check-mem 0x$BOMBS=0x09
    run_case ammo_bomb2 "wait10,a1,wait5,a1,shot" --check-mem 0x$BOMBS=0x08
    # Firing past empty must stop at zero, not wrap to 255.
    run_case ammo_empty "wait10,b400,shot"  --check-mem 0x$GUN=0x00

    # The gun points where the nose points, and the nose follows the last
    # commanded direction rather than the coasting velocity.
    run_case ammo_face  "wait10,left20,shot" --check-mem 0x$FACE=0x01

    # Pool lifecycle. A bomb falls from the airframe to the ground in ~25
    # frames and retires on contact; a round retires on BULLET_LIFE instead,
    # which is what stops sustained fire from starving the pool.
    run_case muni_bomb_live   "wait10,a1,shot"          --check-mem 0x$KIND=0x02
    run_case muni_bomb_fall   "wait10,a1,wait10,shot"   --check-mem 0x$KIND=0x02
    run_case muni_bomb_ground "wait10,a1,wait40,shot"   --check-mem 0x$KIND=0x00
    run_case muni_gun_live    "wait10,b1,shot"          --check-mem 0x$KIND=0x01
    run_case muni_gun_range   "wait10,b1,wait45,shot"   --check-mem 0x$KIND=0x00
fi

# ---------------------------------------------------------------------------
echo "---"
echo "$pass passed, $fail failed$([ $skipped -gt 0 ] && echo ", $skipped skipped")"
[ "$fail" -eq 0 ]

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
    run_case cam_rest   "shot"                        --check-mem16 0x$CAM=0x0000
    run_case cam_r30    "wait20,right30,shot"         --check-mem16 0x$CAM=0x005A
    run_case cam_r120   "wait20,right120,shot"        --check-mem16 0x$CAM=0x021C
    run_case cam_r240   "wait20,right240,shot"        --check-mem16 0x$CAM=0x0474
    run_case cam_back   "wait20,right240,left90,shot" --check-mem16 0x$CAM=0x032D
fi

# Four layers at four rates, and eight equal HDMA ground bands.
# A short move: the near band runs at 1.875x, and the tool correlates each
# row wrapped at the screen width, so a long one leaves it nothing to match.
parallax_case parallax "shot" "wait20,right40,shot" 8

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
    run_case heli_wall  "wait20,left60,shot"  --check-mem16 0x$HX=0x0000
    run_case heli_ceil  "wait20,up60,shot"    --check-mem16 0x$HY=0x1000
    run_case heli_floor "wait20,down30,wait40,shot"  --check-mem16 0x$HY=0x9800

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
    # Reversing is a turn: five drawings held three frames each, advancing
    # only while the new direction is held. Ten frames in, the three-quarter
    # view faces the new way (its cells swap under hflip, so the first slot
    # carries the right-hand cell, $E2); six frames in and released, it
    # stalls on the three-quarter view still facing the old way ($E0); and
    # wound back to nothing, the facing never changed. The nose-up flare the
    # reversal used to show is out of reach now - the swing outlasts the
    # velocity decay - so the tilt cases stop at nose-down and level.
    run_case heli_turn_mid   "wait20,right120,left10,shot" \
                                                   --check-mem 0x$TILT=0xE2 \
                                                   --check-mem 0x$ATTR=0x70
    run_case heli_turn_stall "wait20,right120,left6,wait20,shot" \
                                                   --check-mem 0x$TILT=0xE0 \
                                                   --check-mem 0x$ATTR=0x30
    run_case heli_turn_back  "wait20,right120,left6,right6,wait2,shot" \
                                                   --check-mem 0x$ATTR=0x30

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
    # A round leaves at muzzle height: the airframe's 8.8 y plus 7 px. This
    # once came out as 0x0200 - a compiler bug restored the argument through
    # an 8-bit TYA - and every round spawned on the HUD row.
    MY=$(ramaddr muni_y)
    run_case muni_gun_muzzle  "wait10,b1,shot"          --check-mem16 0x$MY=0x6700
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
    run_case pad_land      "wait20,right180,wait60,down30,wait40,shot"  --check-mem 0x$LAND=0x01 \
                                                                 --check-mem 0x$ONPAD=0x01
    run_case pad_short     "wait20,right120,wait60,down30,wait40,shot"  --check-mem 0x$LAND=0x01 \
                                     --check-mem 0x$ONPAD=0x00 --check-mem16 0x$HY=0x9800
    run_case pad_over      "wait20,right240,wait60,down30,wait40,shot"  --check-mem 0x$LAND=0x01 \
                                                                 --check-mem 0x$ONPAD=0x00

    # A landed airframe does not slide: down at the start, then held right
    # for 190 frames, it is still at x 64 on open ground, not on the deck.
    run_case pad_slide     "wait20,down30,wait40,right190,shot"  --check-mem 0x$LAND=0x01 \
                                     --check-mem 0x$ONPAD=0x00 --check-mem16 0x$HX=0x0040

    run_case pad_takeoff   "wait20,right180,wait60,down30,wait40,up20,shot" --check-mem 0x$LAND=0x00

    # Too fast: a full-stick descent onto the deck is a crash - a life gone.
    LIVES=$(ramaddr heli_lives)
    run_case pad_crash     "wait20,right180,wait60,down80,shot" --check-mem 0x$LIVES=0x03 \
                                                                --check-mem 0x$LAND=0x00

    # Full rearm: fuel back to 100, and the reload countdowns give back rounds
    # at 20 frames each and bombs at 10 while the airframe sits.
    run_case pad_rearm "wait20,b60,a1,right180,wait60,down30,wait40,wait120,shot" \
                                             --check-mem 0x$LAND=0x01 \
                                             --check-mem 0x$FUEL=0x64 \
                                             --check-mem 0x$GUN=0x3D \
                                             --check-mem 0x$BOMBS=0x0A

    # One unit per 64 frames aloft.
    run_case fuel_burn "wait20,right240,shot" --check-mem 0x$FUEL=0x60

    # Dry tank: gravity is allowed in exactly one place in the plan and this
    # is it. The airframe sinks with no input at all, and open ground is not
    # a deck: touching it on a dead stick is a crash landing - a life gone,
    # and by 7200 frames the next airframe is up at hover height with a
    # full tank less the few units it has burned since.
    LIVES=$(ramaddr heli_lives)
    run_case fuel_dry "wait7200,shot" --check-mem 0x$LIVES=0x03 \
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
    # The player's base only sends what is ordered (phase 7), so the rotating
    # placeholder column comes from the enemy base alone until the CPU
    # opponent lands: a launcher first (the rotation is the launcher-heavy
    # one SPAWN_ORDER carries), marching west from x=7680. The pool is a
    # tagged enum, so slot 0's kind is the first byte of its tag plane.
    UO=$(ramaddr units__owner)
    run_case unit_spawn "wait200,shot"  --check-mem 0x$UK=0x03 --check-mem 0x$UO=0x01
    run_case unit_march "wait600,shot"  --check-mem16 0x$UX=0x1D08

    # A spawn order of Kind values becomes a variant, and the hit points
    # come from that variant's row of unit_stats. Slots 0..3 are the
    # launcher, tank, launcher and infantryman of the enemy rotation, one
    # every 120 frames; each is checked against its tag and its hp.
    #
    # The last check is the tank's payload: its gun reload lives in the
    # Tank variant, not in a pool-wide array, so units__data[1] is the only
    # place the countdown exists. With nothing in range it cycles 16..0
    # every seventeen frames (TANK_SCAN), which makes the value here a
    # phase - the frame is chosen so it reads TANK_SCAN, freshly reset,
    # rather than a 0 that an unwritten byte would also show. Re-baseline
    # it if a change shifts the pool by a frame, but do not delete it.
    at() { printf '%X' $((0x$1 + $2)); }            # tag plane: one byte per slot
    hp() { printf '%X' $((0x$UHP + $1)); }          # slot N's hit points
    run_case unit_kinds "wait601,shot" \
        --check-mem 0x$(at "$UK" 0)=0x03 --check-mem 0x$(hp 0)=0x08 \
        --check-mem 0x$(at "$UK" 1)=0x01 --check-mem 0x$(hp 1)=0x19 \
        --check-mem 0x$(at "$UK" 2)=0x03 --check-mem 0x$(hp 2)=0x08 \
        --check-mem 0x$(at "$UK" 3)=0x04 --check-mem 0x$(hp 3)=0x05 \
        --check-mem 0x$(at "$UD" 1)=0x10

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
    run_case unit_budget "$EIGHT_TANKS,wait3600,shot" --check-mem16 0x$FNMI=0x0E50 \
                                                      --check-mem16 0x$FLOOP=0x0BC9

    # The headline constraint: at a bunched column the PPU must still be able
    # to draw everything standing on those scanlines. Eight tanks in three
    # lanes measure 16 sprites / 32 tiles on one line against 32 / 34 - the
    # sprite budget, not the CPU, is what a bigger front runs into.
    budget_case unit_oam "$EIGHT_TANKS,wait3600,right520,wait60,shot"
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
    run_case order_boot "wait60,shot" --check-mem 0x$FUNDS=0x20 --check-mem 0x$SEL=0x02 \
                                      --check-mem 0x$LIVES=0x04

    # One press buys one tank: it comes out of the player's base at x=512
    # marching east, and the cost comes off at once.
    run_case order_tank "l+a3,wait30,shot" --check-mem 0x$FUNDS=0x1C \
        --check-mem 0x$(at "$UK" 0)=0x01 --check-mem 0x$UO=0x00 --check-mem16 0x$UX=0x0211

    # Right moves the ring to infantry; one order is five men, and the gate
    # lets the next out only when the last is a convoy space (32 px, 128
    # frames at a man's pace) clear of it: a minute in, one is on the field
    # and four still wait in the emitter.
    run_case order_infantry "l+right3,wait3,l+a3,wait60,shot" --check-mem 0x$FUNDS=0x1B \
        --check-mem 0x$(at "$UK" 0)=0x04 --check-mem 0x$QMEN=0x04

    # Left twice wraps to the van. Its cap is six, counted on the field and
    # in the queue: the seventh press is refused and costs nothing, so the
    # purse is 32 - 6*2, and the first van is out.
    SEVEN="l+a3,wait3,l+a3,wait3,l+a3,wait3,l+a3,wait3,l+a3,wait3,l+a3,wait3,l+a3"
    run_case order_cap "l+left3,wait3,l+left3,wait3,$SEVEN,wait80,shot" --check-mem 0x$FUNDS=0x14 \
        --check-mem 0x$SEL=0x00 --check-mem 0x$(at "$UK" 0)=0x02

    # Right three times from the tank is the helicopter: an extra life for 20.
    run_case order_heli "l+right3,wait3,l+right3,wait3,l+right3,wait3,l+a3,wait10,shot" \
        --check-mem 0x$FUNDS=0x0C --check-mem 0x$LIVES=0x05 --check-mem 0x$SEL=0x05

    # Income. A push to the far end and a wait there pays out; the exact
    # figure is the threshold's - and, since phase 8, the no-fly zone's:
    # the enemy base's missiles send the airframe home part way, which is
    # why it is less than it was.
    run_case econ_income "right1500,wait300,shot" --check-mem 0x$FUNDS=0x27
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
    run_case turret_heli "wait20,right1290,wait90,shot" --check-mem 0x$HHP=0x0F

    # Land in front of it and fire back: a round is a point off its 62 -
    # twelve of the fifteen fired land in this time (the rest are still in
    # flight or lost to its self-repair between), and its fire keeps coming.
    run_case turret_gunfire "wait20,right1290,down30,wait40,b90,shot" \
        --check-mem 0x$(at "$SHP" 12)=0x32 --check-mem 0x$HHP=0x0B

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
    run_case balloon_kill "up20,right401,shot" --check-mem 0x$LIVES=0x03 \
        --check-mem16 0x$HX=0x0040 --check-mem 0x$DEAD=0x78 --check-mem16 0x$CAM=0x0799
    run_case balloon_pan "up20,right401,wait60,shot" \
        --check-mem16 0x$HX=0x0040 --check-mem 0x$DEAD=0x3C --check-mem16 0x$CAM=0x0235
    expect_snes_none balloon_pan "14,22,28"                         # canopy
    run_case balloon_rise "up20,right401,wait120,right10,shot" \
        --check-mem16 0x$HX=0x0040 --check-mem 0x$DEAD=0x00 --check-mem 0x$RISE=0x01 \
        --check-mem16 0x$HY=0x9E00 --check-mem16 0x$CAM=0x0000
    run_case balloon_respawn "up20,right401,wait192,right10,shot" \
        --check-mem16 0x$HX=0x004D --check-mem 0x$RISE=0x00 --check-mem16 0x$HY=0x6000
    expect_snes balloon_respawn "14,22,28" 0.02

    # An enemy infantryman walking into the neutral bunker at x=5120 (level
    # entry 9) takes it. He spawns at frame ~270 and covers 2560 px at a
    # quarter pixel a frame, so this is the suite's longest wait.
    SOWN=$(ramaddr structs__owner)
    run_case bunker_capture "wait12500,shot" --timeout 400000 \
        --check-mem 0x$(at "$SOWN" 9)=0x01

    # Tanks shell the other side's turrets and bunkers, holding in place
    # until the building falls. The enemy column's tank (its second spawn,
    # slot 1) reaches the player's bunker at x=2048 (level entry 3) after
    # ~11200 frames and brings its 69 hp down at 8 a shell, one every 90
    # frames: by 12600 it is rubble and nobody's. The player's side of the
    # same rule was checked by planting a bought tank at x=6520 with the
    # debugger: the enemy turret at 6656 fell in four shells.
    run_case tank_bunker "wait12600,shot" --timeout 400000 \
        --check-mem 0x$(at "$SHP" 3)=0x00 --check-mem 0x$(at "$SOWN" 3)=0x02

    # Infantry gunfire: no round, the sweep that finds a target lands the
    # hit. Five men are ordered; the gate lets them out 128 frames apart,
    # so the first (slot 0) walks east alone and meets the enemy column's
    # first launcher (slot 1) around frame 10600 at x~2900 - past the
    # player's turret's reach, so nothing else can be shooting it - and
    # four hits of 2 finish its 8 hp. The column's tank (slot 3) is behind
    # it and is not scratched: rifle_dmg against armour is 0, and its 25 hp
    # say so. A launcher fires at nothing on the ground, so the second man
    # (slot 4, still on his way) is unhurt. The wait is in vblanks and the
    # loop drops a couple of percent of them under the enemy column, so the
    # meeting drifts later with every heavier build; re-measure when it
    # moves.
    run_case rifle_fire "l+right3,wait3,l+a3,wait10800,shot" --timeout 400000 \
        --check-mem 0x$(at "$UK" 1)=0x00 --check-mem 0x$(at "$UK" 3)=0x01 \
        --check-mem 0x$(hp 3)=0x19 --check-mem 0x$(hp 4)=0x05
    # ... and a tank does not stop for the other side's men: it drives
    # over them. Nine hundred frames on, the same tank has rolled through
    # the whole file of five - every one of their slots free, the tank
    # untouched and past them.
    run_case tank_crush "l+right3,wait3,l+a3,wait11700,shot" --timeout 400000 \
        --check-mem 0x$(at "$UK" 0)=0x00 --check-mem 0x$(at "$UK" 2)=0x00 \
        --check-mem 0x$(at "$UK" 4)=0x00 --check-mem 0x$(at "$UK" 6)=0x00 \
        --check-mem 0x$(at "$UK" 8)=0x00 --check-mem 0x$(hp 3)=0x19
    # The super bunker as a tank target was checked with the debugger: a
    # bought tank planted at x=3968 before the bunker at 4076 given three
    # enemy men held, put them out one a shell, and moved on once it was
    # nobody's.

    # The enemy base's missiles: an airframe pushed into its 320 px is lost
    # inside two hundred frames and comes back at the start with a life gone.
    run_case base_missile "wait20,right1500,wait200,shot" --check-mem 0x$LIVES=0x03 \
                                                          --check-mem 0x$HHP=0x14

    # The enemy column's first launcher (the rotation's first, slot 0)
    # fires its one homing missile at an airframe inside 224 px and is
    # spent doing so: the slot is free, and the missile lands for 10 of
    # the 20 hp. The stick is released just as it comes into range so the
    # second launcher (slot 2, 120 px behind) is still out of reach and
    # armed, and no life is lost. The turret at 6656 gets one round in on
    # the way past, three frames before the missile lands, hence 9.
    run_case launcher_fire "wait20,right1354,wait60,shot" \
        --check-mem 0x$(at "$UK" 0)=0x00 --check-mem 0x$HHP=0x09 \
        --check-mem 0x$(at "$UK" 2)=0x03 --check-mem 0x$(at "$UD" 2)=0x01 \
        --check-mem 0x$LIVES=0x04

    # The super bunker (level entry 7, dead centre) starts empty and nobody's.
    # The second enemy infantryman to walk the field - the first is spent on
    # the bunker at 5120 - goes inside: one man, and it is the enemy's. He
    # arrives around frame 16500, but the wait is in vblanks and the loop
    # drops 2-3% of them under the enemy column, so the margin here is what
    # keeps a build a few hundred cycles slower from failing the case.
    SMEN=$(ramaddr structs__men)
    run_case super_manned "wait18000,shot" --timeout 600000 \
        --check-mem 0x$(at "$SMEN" 7)=0x01 --check-mem 0x$(at "$SOWN" 7)=0x01
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
# at boot x 0, y 16 (the row's first scanline), the bracket tile.
# ---------------------------------------------------------------------------
RB=$(ramaddr radar_buf)
if [ -z "$RB" ]; then
    echo "FAIL radar:addr (radar_buf not found in build/main.asm)"; fail=$((fail+1))
else
    rb() { printf '%X' $((0x$RB + $1)); }
    run_case radar_boot "wait16,shot" \
        --check-mem 0x$(rb 0)=0xFF --check-mem 0x$(rb 1)=0x00 \
        --check-mem 0x$(rb 2)=0xCF --check-mem 0x$(rb 3)=0x30 \
        --check-mem 0x$(rb 4)=0xCF --check-mem 0x$(rb 5)=0x30 \
        --check-mem 0x$(rb 6)=0xEF --check-mem 0x$(rb 7)=0x10 \
        --check-mem 0x$(rb 10)=0xEF --check-mem 0x$(rb 11)=0x10 \
        --check-mem 0x$(rb 14)=0xFF --check-mem 0x$(rb 15)=0x00 \
        --check-mem 0x$(printf '%X' $((0x$OAMB + 8)))=0x00 \
        --check-mem 0x$(printf '%X' $((0x$OAMB + 9)))=0x10 \
        --check-mem 0x$(printf '%X' $((0x$OAMB + 10)))=0x1F
    # Flown east 240 frames: the airframe's block has left tile 0, so the
    # bank's tick stands alone, and the bracket sprite is at camera_x/32.
    run_case radar_flown "wait20,right240,wait20,shot" \
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
    run_case overlay_show "wait30,l20,l+right3,l+select3" \
        --check-mem 0x$OVS=0x01 --check-mem 0x$SEL=0x03 --check-mem16 0x$HX=0x0040
    run_case overlay_hide "wait30,l20,l+right3,l10,wait5,shot" \
        --check-mem 0x$OVS=0x00 --check-mem 0x$SEL=0x03 --check-mem16 0x$HX=0x0040
fi

# ---------------------------------------------------------------------------
# The airlift (design.md, decided after phase 9).
#
# Five men are bought and the airframe lands on the player's pad facing
# east, so its tail is west and the men walk up behind it: each boards
# within 5 px of the tail. Lifted off, X drops one per press; a chute
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
    run_case airlift_board "$BOARD,shot" --timeout 200000 \
        --check-mem 0x$MEN=0x05 --check-mem 0x$LAND=0x01 \
        --check-mem 0x$(at "$UK" 0)=0x00 --check-mem 0x$(at "$UK" 4)=0x00
    # In the field: landed on open ground at x 714 facing east, the men walk
    # up behind the tail from the base and board there too; no deck needed.
    run_case airlift_field "l+right3,wait3,l+a3,wait20,right120,wait60,down30,wait40,wait1600,shot" \
        --timeout 200000 --check-mem 0x$MEN=0x05 --check-mem 0x$LAND=0x01 --check-mem 0x$ONPAD=0x00
    # Men aboard go down with the airframe: five aboard, then a balloon
    # (the player's own bunker's, at x=2048) and the next airframe has none.
    run_case airlift_lost "$BOARD,up+right36,right220,shot" --timeout 200000 \
        --check-mem 0x$MEN=0x00 --check-mem 0x$LIVES=0x03
    DROPS="x3,wait40,x3,wait40,x3,wait40,x3,wait40,x3"
    run_case airlift_drop "$BOARD,up20,right40,$DROPS,wait140,shot" --timeout 200000 \
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
    run_case game_lost "$PASS_,$PASS_,$PASS_,$PASS_,$PASS_,shot" --timeout 300000 \
        --check-mem 0x$GS=0x02 --check-mem 0x$LIVES=0x00

    # Start begins a fresh match: playing, four lives, the airframe at the
    # start, the camera at the west edge.
    CAMX=$(ramaddr camera_x)
    run_case game_reset "$PASS_,$PASS_,$PASS_,$PASS_,$PASS_,start,wait10,shot" --timeout 300000 \
        --check-mem 0x$GS=0x00 --check-mem 0x$LIVES=0x04 \
        --check-mem16 0x$HX=0x0040 --check-mem16 0x$CAMX=0x0000
fi

# ---------------------------------------------------------------------------
echo "---"
echo "$pass passed, $fail failed$([ $skipped -gt 0 ] && echo ", $skipped skipped")"
[ "$fail" -eq 0 ]

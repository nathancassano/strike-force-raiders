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
# accelerates up to 5 px/frame, so every moving case travels further. The
# relation still holds exactly - at cam_r240 the airframe is at 1221, so the
# focus is 1237 and the camera settles at 1237 - 128 - 8 = 1101 = $044D.
# ---------------------------------------------------------------------------
CAM=$(ramaddr camera_x)
if [ -z "$CAM" ]; then
    echo "FAIL cam:addr (camera_x not found in build/main.asm)"; fail=$((fail+1))
else
    run_case cam_rest   "shot"                        --check-mem16 0x$CAM=0x0000
    run_case cam_r30    "wait20,right30,shot"         --check-mem16 0x$CAM=0x0005
    run_case cam_r120   "wait20,right120,shot"        --check-mem16 0x$CAM=0x01C3
    run_case cam_r240   "wait20,right240,shot"        --check-mem16 0x$CAM=0x041B
    run_case cam_back   "wait20,right240,left90,shot" --check-mem16 0x$CAM=0x03EA
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
    run_case heli_right "wait20,right30,shot" --check-mem16 0x$HX=0x007D

    # Leftward travel exercises the borrow path in heli_move_x. `>>` is a
    # logical shift even on signed types, so a negative delta cannot be
    # shifted apart - a round trip that lands mid-world proves the explicit
    # sign branch, where a clamp at 0 would not.
    run_case heli_back  "wait20,right240,left60,shot" --check-mem16 0x$HX=0x04D3

    # All four clamps: world edge, and the flyable box between the HUD strip
    # and the ground at y=168.
    run_case heli_wall  "wait20,left60,shot"  --check-mem16 0x$HX=0x0000
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
# ---------------------------------------------------------------------------
LAND=$(ramaddr heli_landed)
FUEL=$(ramaddr heli_fuel)
if [ -z "$LAND" ] || [ -z "$FUEL" ]; then
    echo "FAIL pad:addr (heli_landed/heli_fuel not found in build/main.asm)"
    fail=$((fail+1))
else
    # Descending onto the deck lands; stopping short or overshooting does not.
    run_case pad_land      "wait20,right190,down80,shot"  --check-mem 0x$LAND=0x01
    run_case pad_short     "wait20,right120,down80,shot"  --check-mem 0x$LAND=0x00 --check-mem16 0x$HY=0x9800
    run_case pad_over      "wait20,right210,down80,shot" --check-mem 0x$LAND=0x00

    # "Land only while descending." Reaching the floor first and then sliding
    # sideways onto the deck arrives with vy already zeroed by the clamp, so
    # it must not count - this is the case a naive overlap test gets wrong.
    run_case pad_slide     "wait20,down80,right190,shot"  --check-mem 0x$LAND=0x00

    run_case pad_takeoff   "wait20,right190,down80,up20,shot" --check-mem 0x$LAND=0x00

    # Full rearm: fuel back to 100, and the reload countdowns give back rounds
    # at 20 frames each and bombs at 10 while the airframe sits.
    run_case pad_rearm "wait20,b60,a1,right190,down80,wait120,shot" \
                                             --check-mem 0x$LAND=0x01 \
                                             --check-mem 0x$FUEL=0x64 \
                                             --check-mem 0x$GUN=0x3E \
                                             --check-mem 0x$BOMBS=0x0A

    # One unit per 64 frames aloft.
    run_case fuel_burn "wait20,right240,shot" --check-mem 0x$FUEL=0x60

    # Dry tank: gravity is allowed in exactly two places in the plan and this
    # is one. The airframe sinks to the floor with no input at all, and open
    # ground is not a deck, so it must not read as landed. ~7200 frames.
    run_case fuel_dry "wait7200,shot" --check-mem 0x$FUEL=0x00 \
                                      --check-mem16 0x$HY=0x9800 \
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
    # opponent lands: a tank first, marching west from x=7680. The pool is a
    # tagged enum, so slot 0's kind is the first byte of its tag plane.
    UO=$(ramaddr units__owner)
    run_case unit_spawn "wait200,shot"  --check-mem 0x$UK=0x01 --check-mem 0x$UO=0x01
    run_case unit_march "wait600,shot"  --check-mem16 0x$UX=0x1D07

    # A spawn order of Kind values becomes a variant, and the hit points
    # come from that variant's row of unit_stats. Slots 0..3 are the tank,
    # infantry, van and launcher of the enemy rotation, one every 120
    # frames; each is checked against its tag and its hp.
    #
    # The last check is the tank's payload: its gun reload lives in the
    # Tank variant, not in a pool-wide array, so units__data[0] is the only
    # place the countdown exists. With nothing in range it cycles 0..16
    # every seventeen frames (TANK_SCAN), which makes the value here a
    # phase - re-baseline it if a change shifts the pool by a frame, but do
    # not delete it.
    at() { printf '%X' $((0x$1 + $2)); }            # tag plane: one byte per slot
    hp() { printf '%X' $((0x$UHP + $1)); }          # slot N's hit points
    run_case unit_kinds "wait600,shot" \
        --check-mem 0x$(at "$UK" 0)=0x01 --check-mem 0x$(hp 0)=0x19 \
        --check-mem 0x$(at "$UK" 1)=0x04 --check-mem 0x$(hp 1)=0x05 \
        --check-mem 0x$(at "$UK" 2)=0x02 --check-mem 0x$(hp 2)=0x0C \
        --check-mem 0x$(at "$UK" 3)=0x03 --check-mem 0x$(hp 3)=0x08 \
        --check-mem 0x$(at "$UD" 0)=0x0D

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
    # the riflemen's sweep and pose 23 more: 0.961.
    # The next cycles are in unit_advance's call and the traffic scan.
    EIGHT_TANKS="x3,wait3,x3,wait3,x3,wait3,x3,wait3,x3,wait3,x3,wait3,x3,wait3,x3,wait3"
    run_case unit_budget "$EIGHT_TANKS,wait3600,shot" --check-mem16 0x$FNMI=0x0E51 \
                                                      --check-mem16 0x$FLOOP=0x0DC4

    # The headline constraint: at a bunched column the PPU must still be able
    # to draw everything standing on those scanlines. Eight tanks in three
    # lanes measure 16 sprites / 32 tiles on one line against 32 / 34 - the
    # sprite budget, not the CPU, is what a bigger front runs into.
    budget_case unit_oam "$EIGHT_TANKS,wait3600,right520,wait60,shot"
fi

# ---------------------------------------------------------------------------
# Phase 7 - economy and ordering.
#
# Funds grow with the helicopter's distance from the west edge; L/R walk the
# order ring and X buys. Every check is on the ROM's own state: the purse,
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
    run_case order_tank "x3,wait30,shot" --check-mem 0x$FUNDS=0x1C \
        --check-mem 0x$(at "$UK" 0)=0x01 --check-mem 0x$UO=0x00 --check-mem16 0x$UX=0x0211

    # R moves the ring to infantry; one order is five men, ten frames apart,
    # all out within the minute and the emitter idle again.
    run_case order_infantry "r3,wait3,x3,wait60,shot" --check-mem 0x$FUNDS=0x1B \
        --check-mem 0x$(at "$UK" 0)=0x04 --check-mem 0x$(at "$UK" 4)=0x04 \
        --check-mem 0x$(at "$UK" 5)=0x00 --check-mem 0x$QMEN=0x00

    # L twice wraps to the van. Its cap is six: the seventh press is refused
    # and costs nothing, so the purse is 32 - 6*2.
    SEVEN="x3,wait3,x3,wait3,x3,wait3,x3,wait3,x3,wait3,x3,wait3,x3"
    run_case order_cap "l3,wait3,l3,wait3,$SEVEN,wait80,shot" --check-mem 0x$FUNDS=0x14 \
        --check-mem 0x$SEL=0x00 --check-mem 0x$(at "$UK" 5)=0x02

    # R three times from the tank is the helicopter: an extra life for 20.
    run_case order_heli "r3,wait3,r3,wait3,r3,wait3,x3,wait10,shot" \
        --check-mem 0x$FUNDS=0x0C --check-mem 0x$LIVES=0x05 --check-mem 0x$SEL=0x05

    # Income. A push to the far end and a wait there pays out; the exact
    # figure is the threshold's - and, since phase 8, the no-fly zone's:
    # the enemy base's missiles send the airframe home part way, which is
    # why it is less than it was.
    run_case econ_income "right1500,wait300,shot" --check-mem 0x$FUNDS=0x29
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

    # Descend to its height and fire back: a round is a point off its 62.
    run_case turret_gunfire "wait20,right1290,down40,wait10,b90,shot" \
        --check-mem 0x$(at "$SHP" 12)=0x2F --check-mem 0x$HHP=0x09

    # The balloon over the player's own bunker (x=2048) kills the airframe
    # on contact, at frame 421 of this climb: a life gone, the airframe
    # back at the start but hidden for HELI_RESPAWN (120) frames, and the
    # camera - 1906 at the loss - panning home at 1906/120+1 = 16 px a
    # frame on top of the follow's 6. Sixty frames on it is 586 and the
    # canopy colour is nowhere on screen (the screenshot trails the OAM
    # shadow by two frames, so the kill frame itself still shows it); at
    # 120 the airframe is back on the start, the view with it, and the
    # stick works again: ten frames of thrust from rest is 13 px.
    HX=$(ramaddr heli_x_px)
    DEAD=$(ramaddr heli_dead)
    run_case balloon_kill "up20,right401,shot" --check-mem 0x$LIVES=0x03 \
        --check-mem16 0x$HX=0x0040 --check-mem 0x$DEAD=0x78 --check-mem16 0x$CAM=0x0772
    run_case balloon_pan "up20,right401,wait60,shot" \
        --check-mem16 0x$HX=0x0040 --check-mem 0x$DEAD=0x3C --check-mem16 0x$CAM=0x024A
    expect_snes_none balloon_pan "14,22,28"                         # canopy
    run_case balloon_respawn "up20,right401,wait120,right10,shot" \
        --check-mem16 0x$HX=0x004D --check-mem 0x$DEAD=0x00 --check-mem16 0x$CAM=0x0000
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
    # hit. Five men ordered at once walk east and meet the enemy column's
    # first launcher (slot 5) around frame 9640 at x~2900 - past the
    # player's turret's reach, so nothing else can be shooting it - and
    # four hits of 2 finish its 8 hp. The column's tank (slot 6) arrives
    # on their heels and is not scratched: rifle_dmg against armour is 0,
    # and its 25 hp say so while its shells start on the men. A launcher
    # fires at nothing on the ground, so the men it met are unhurt.
    run_case rifle_fire "r3,wait3,x3,wait9700,shot" --timeout 400000 \
        --check-mem 0x$(at "$UK" 5)=0x00 --check-mem 0x$(at "$UK" 6)=0x01 \
        --check-mem 0x$(hp 6)=0x19 --check-mem 0x$(hp 1)=0x05
    # The super bunker as a tank target was checked with the debugger: a
    # bought tank planted at x=3968 before the bunker at 4076 given three
    # enemy men held, put them out one a shell, and moved on once it was
    # nobody's.

    # The enemy base's missiles: an airframe pushed into its 320 px is lost
    # inside two hundred frames and comes back at the start with a life gone.
    run_case base_missile "wait20,right1500,wait200,shot" --check-mem 0x$LIVES=0x03 \
                                                          --check-mem 0x$HHP=0x14

    # The enemy column's launcher (the rotation's fourth, slot 3) fires its
    # one homing missile at an airframe inside 224 px and is spent doing
    # so: the slot is free, and the missile lands for 10 of the 20 hp.
    run_case launcher_fire "wait20,right1400,wait80,shot" \
        --check-mem 0x$(at "$UK" 3)=0x00 --check-mem 0x$HHP=0x0A

    # The super bunker (level entry 7, dead centre) starts empty and nobody's.
    # The second enemy infantryman to walk the field - the first is spent on
    # the bunker at 5120 - goes inside: one man, and it is the enemy's.
    SMEN=$(ramaddr structs__men)
    run_case super_manned "wait16200,shot" --timeout 500000 \
        --check-mem 0x$(at "$SMEN" 7)=0x01 --check-mem 0x$(at "$SOWN" 7)=0x01
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

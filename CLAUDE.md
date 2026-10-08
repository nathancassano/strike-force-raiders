# Rotor Raiders - AI Assistant Guide

A helicopter tug-of-war for the SNES, descended from *Rescue Raiders* (Apple II, 1984)
by way of *Armor Alley* (1991). Built with the R65 compiler. For the full R65 language
reference, see the main CLAUDE.md in the R65 repository.

The design and phase plan live in [design.md](design.md).

## Project-specific rules

**Never add an initialiser to a mutable static.** `static mut X: u16 = 5;` routes through
`__init_start`, which has an open MVN/DBR bug that can hang the ROM. Declare bare and
initialise in `boot_load()`. This is why `src/lib/rand.r65` diverges from `stdlib/rand.r65`.

**Never use `continue` inside an entity loop** - it trips a compiler region-spill bug.
Restructure as `if`/`else`.

**Always use `OamBuffer.set_full!`, never `set!`.** `set!` writes only an 8-bit X and leaves
a stale extended-X high bit, which renders a sprite 256px off - invisible but still active.
In a side-scroller every entity crosses a screen edge, so this applies everywhere.

**`*` only accepts power-of-two constants.** `mul8(i, 3)` costs ~57 cycles where `(i<<1)+i`
costs ~16. Pad tables to power-of-two strides rather than multiplying by 3, 5, 6...

**Never write `let x @ A = ...` if anything else touches A before its last use.** The alias
is silently clobbered and the compiler emits no diagnostic - it just generates wrong code.
This includes `let lo @ A = ...; let hi @ B = ...` (B is A's high byte), the idiom in
`astroids/src/input.r65`, which is why `src/input.r65` here does not use it. Compose through
plain locals instead: `let v: u16 = ((JOY1H as u16) << 8) | (JOY1L as u16);`

**The PPU expands 5-bit colour to 8-bit by bit replication** - `(v<<3)|(v>>2)`, not
`round(v/31*255)`. The two disagree by one on most values, which is enough for an exact-match
colour search to miss every sprite pixel in a screenshot. `tools/pngstat.py --snes` does it
correctly; use that rather than converting by hand.

**Name sprite frames for the subject, not the screen.** Facing-left renders hflipped, so a
frame called `LEFT` is ambiguous about whether it means the art or the result. Tilt frames are
`NOSE_DOWN`/`NOSE_UP`, and tilt is selected from velocity *along the nose* - using signed vX
double-flips against hflip.

**BG4HOFS is $2113.** `$210F` is BG2HOFS. Getting this wrong in an HDMA `BBAD` silently
drives the wrong layer and presents as "HDMA is not working".

**`src/lib/` is a vendored copy of `/home/nathan/R65/stdlib/`.** It currently matches upstream
except for the `rand.r65` change above. Check before copying code from another project - the
other projects' copies have drifted by 50-170 lines.

## Build Commands

```bash
make          # Build ROM
make verify   # Build and run the scripted-input regression suite
make lint     # Run the R65 linter (rules in r65-lint.toml)
make assets   # Just the art: assets/src/*.bmp -> SNES CHR (an ordinary build does this)
make play OUT=build/x.png ACTIONS=start,wait60,shot   # one ad-hoc scripted run
make run      # Build and launch in emulator
make clean    # Clean build artifacts
make syntax   # Compile only, no ROM
```

## Testing

Do not ask a human to look at the screen - drive the ROM yourself.

`./play.sh OUT.png ACTIONS [mesen args...]` builds a Mesen input movie from an action
script, runs the ROM headless, breaks at the ROM's `snapshot_point()` hook (fired by
Select), and screenshots.

    ./play.sh build/fly.png wait60,right90,shot --check-mem16 0x20=0x0140

Actions: `waitN`, `start`, `shot`, `upN`/`downN`/`leftN`/`rightN`, `aN`/`bN`/`xN`/`yN`/`lN`/`rN`.
Combine with `+`, e.g. `up+a30`. Built by `tools/mkmovie.py`. A leading `@l`, `@r`, `@l+r` or
`@x` is a **power-on hold**: it holds that button through the boot prefix, costing no frames,
and `boot_load` reads the pad by hand (`pad_read_manual`, before the auto-read is on). L, R and
L+R pick one of the three harness missions; X takes the campaign's first mission with the front
end skipped, and no hold at all gets the campaign proper, title page and all.
`tests/run.sh`'s header says what each opponent is.

`tools/pngstat.py shot.png [--expect R,G,B] [--min-pct N]` inspects what actually rendered -
use it to assert on frames instead of trusting a clean exit code.

`tools/parallax.py BASE.png MOVED.png [--assert-bands N]` cross-correlates two frames row by
row and reports each layer's horizontal displacement, plus the HDMA ground bands. This is how
scrolling is verified - pixel-eyeballing a periodic pattern will mislead you, and a
horizontally uniform (or short-period) row correlates at 100% for *any* shift, so every row
you intend to measure needs a feature with a unique phase. The ground gets that from a
pseudo-random pebble field painted by `tools/ground_texture.py` (the same field on both
256 px halves, so the tool's wrap at the screen width stays exact) rather than from marker
bars, which read as vertical artifacts. The sky's bars are gone too; the hills still carry their posts.

`tests/run.sh` is the regression suite; every completed phase leaves a case behind and the
whole suite re-runs after each new phase. `./tests/run.sh NAME` filters.

A state a movie cannot reach - a won match, a planted unit - is driven through the interactive
debugger instead: pipe `break $<snapshot_point>`, `continue`, `set <addr> <val>`, `continue`,
`screenshot <file>` / `dump wram <file>` into `mesen-gdb ROM --headless --turbo --movie x.mmo`.
The REPL screenshots and dumps as batch mode does, and the movie keeps supplying input across
the `set`, so the press *after* the planted state still lands.

Trust VRAM/OAM dumps (`--dump`) over screenshots when debugging graphics. Measure performance
in scanlines via the V-counter, not Mesen's "Cycles:" counter, which is blind to memory speed.

## Project Structure

```
rotor_raiders/
├── src/
│   ├── main.r65              # Entry, boot_load, NMI handler, game loop, snapshot_point
│   ├── input.r65             # Joypad: pad_read_ports / pad_poll / pad_poll_trigger
│   ├── video.r65             # Mode 0 layers, HDMA ground parallax, camera
│   ├── unit.r65              # Ground-unit pool, march, traffic control, tank fire, rifles
│   ├── para.r65              # The airlift: men aboard, paratroopers
│   ├── struct.r65            # Buildings: level table, turrets, bunkers, balloons, super bunker, bases, banks
│   ├── order.r65             # Funds, the L/R order ring, the order queue
│   ├── cpu.r65               # The opponent: capability rows, convoy table, its purse and queue
│   ├── mission.r65           # The campaign: one row per mission, the derived battlefield, the harness rows
│   ├── screen.r65            # The front end: title, briefing and after-action pages on BG1
│   ├── foe.r65               # The enemy airframe: its state, pad, patrol, and the world against it
│   ├── hud.r65               # BG1 strip rows 0-1 (purse, lives, gauges, ammo, men); the battle-over line; the order dialog
│   ├── radar.r65             # BG1 strip row 2: the radar, a 256x8 bitmap the game draws
│   ├── game.r65              # Match state: the two ends, the reset
│   ├── assets.r65            # GENERATED by make from assets/gfx - not in git, do not edit
│   └── lib/                  # Standard libraries
│       ├── 65816.r65         # CPU register definitions
│       ├── sneslib.r65       # SNES hardware registers and helpers
│       └── math.r65          # Math functions (mul8, div8, etc.)
├── assets/
│   ├── src/                  # Source art (indexed BMP; %.tilemap.bmp also emits a tilemap)
│   ├── gfx/                  # Generated .chr / .pal / .tilemap - build output, not in git
│   ├── sound/                # snesgss exports (spc700.bin, music_*.bin)
│   └── levels/               # Battlefield placement lists
├── tools/                    # mkmovie.py, pngstat.py, poolstat.py, profile.py, timeline.sh, asset generators
├── design.md                 # Design and phase plan (Part 1 design, Part 2 technical, Part 3 phases)
├── tests/run.sh              # Scripted-input regression suite
├── play.sh                   # One-shot scripted run + screenshot
├── build/                    # Compiled output (.asm, .smc, .sym, .dbg)
└── Makefile                  # Build system for WLA-DX
```

## Graphics architecture

Mode 0 throughout, four 2bpp BG layers, all repeating 512px patterns that wrap in hardware -
so there is **no column refill anywhere**. Everything world-specific is a sprite.

| Layer | Contents | Scroll | VRAM map (words) |
|---|---|---|---|
| BG1 | HUD strip, top | fixed | $7800 (32x32) |
| BG2 | near clouds | `camera_x >> 2` | $7000 (64x32) |
| BG3 | distant hills | `camera_x >> 3` | $6800 (64x32) |
| BG4 | ground band, bottom quarter | per-scanline HDMA ch6 | $6000 (64x32) |
| OBJ | units, buildings, munitions | camera-relative | $4000 (4bpp, tiles 0-255) |
| OBJ | the two airframes, their own sheet | camera-relative | $5000 (4bpp, tiles 256+) |

Shared 2bpp tileset at $0000. Mode 0 gives each layer its own 32-colour CGRAM block
(BG1 0-31, BG2 32-63, BG3 64-95, BG4 96-127); sprites get 128-255.

All art is indexed BMP in `assets/src`, and **that is the only art in git**. **The file name
says what a bitmap produces**: `%.tilemap.bmp` is de-duplicated into a tileset *and* the map that
names its tiles back (`assets/gfx/%.chr`, `%.pal`, `%.tilemap`), a plain `%.bmp` gets the tileset
alone, and the Makefile has one multi-target pattern rule for each - make decides between them by
which source exists. Bit depth is the other axis and is a target-specific variable (`-b2`, with
`obj` set to `-b4`), since it has nothing to do with whether a sheet carries a map.
Everything runs through `r65x bmp2chr`,
`src/assets.r65` is generated from whatever those files turned out to be, and the ROM depends on
the lot - so editing a bitmap and running `make` is the whole pipeline; `make assets` is just a
name for its art half. Both are build products, `.gitignore`d, and removed by `make clean`.
`tools/{hud_glyphs,ground_texture,struct_art,heli_art}.py` stamp pixels *into the bitmaps*
(sharing `tools/bmp4.py`, which writes the 4-bit BMPs `bmp2chr -b4` insists on and PIL cannot);
they are authoring helpers run by hand, outside the chain, and phase 12 replaces what they drew.
Nothing generates graphics from code at build time. **bg2/3/4 are stored
folded** - 32 tiles wide by 64 tall, right-hand screen below the left - because a 64x32 SNES
tilemap is two 32x32 screens and bmp2chr emits row-major at bitmap width. Each BG layer has its
own de-duplicated tileset and its own CGRAM block; only sub-palette 0 (4 colours) is used.

Sprites are 4bpp with OBSEL small=8x8 / large=16x16, so a unit is 16x16 and a munition 8x8.
**There are two sprite sheets.** `obj.bmp` holds the units, the buildings, the decks and the
munitions at $4000 (tiles 0-255); `heli.bmp` holds the two airframes' six frames alone, loaded
into the second OBJ name block at $5000, so its tile numbers are 256 + the sheet's and the 9th
tile bit (`HELI_PAGE`) rides in the attribute word. It has its own CGRAM palette as well
(`OBJ_PAL_HELI`, palette 3, and palette 4 for the enemy's), so the airframes can be redrawn or
recoloured without touching anything the ground shares. Either sheet must be 16 tiles wide
whatever it holds: the hardware reads a 16x16 sprite as tiles T, T+1, T+16, T+17.
A 24-px vehicle is one 16x16 cell plus its second cell's left half drawn as **two 8x8s** - three
tiles on a scanline, not four, which is what keeps eight bunched tanks and a bunker (28) under
the PPU's 34 (`unit_draw_one`; the sheet's fourth tile column of every vehicle is blank).
A marching man (infantry or engineer) alternates his standing frame with a stride frame
(`UNIT_TILE_MAN_WALK`, tile 74) every 4 px, picked from `x_px & 4`: no state, and a halted man stands.
The 544-byte OAM shadow lives in lowram and is DMA'd by `oam_flush` in vblank; it sets the
channel registers directly because `#:` resolves the wrong bank for WRAM symbols.

Ground units (`src/unit.r65`) are a 32-slot pool. **32 is a measured limit, not a guess**: with
every slot live the loop holds 1.00 ticks per vblank (one frame short in 3665). It was 16 until
the compiler kept an indexing loop counter in Y and `oam_end` stopped sweeping idle slots;
`frames_nmi` vs `frames_loop` is the frame-budget probe - the V-counter cannot be used because
latching it needs a discarded read of $2137 and the compiler eliminates unused hardware reads.
A tank shells the other side's units ahead and its standing turrets, bunkers and manned super
bunker (`struct_tank_target`, a walk of the sorted structure pool from the tank's own end),
holding in place until the building falls. It does not stop for the other side's men
(`unit_traffic_tank` - a copy of the traffic test, because any extra shape in `unit_traffic`'s
lead scan cost it 340 frames): it drives over them, testing its sweep's remembered nearest
opposing unit for overlap each frame (a pool scan per tank per frame measured 15% of the frame). A rifleman's shot is not a munition: the sweep that
finds a target within `INF_RANGE` lands `rifle_dmg` there and then (0 against a tank) and sets
the pose for the frame it is drawn; with no unit in reach an enemy turret ahead takes the point
instead. Both sweep every 16 idle frames.
Every unit stands on the one ground line - there are no lanes (there were three 4 px ones; they
let opposing columns walk through each other and went) - and **every unit marches at the one
speed**, a pixel on each odd frame (`UNIT_SPEED` is gone with the per-kind speeds: any column
with a man near its front crawled at his quarter pixel). Nothing overtakes, so each side's
column is a fixed **march order** kept as a list through the `ahead`/`behind` planes from
`unit_head` (the lead) to `unit_tail` (the rearmost): `unit_spawn` inserts by x - at the tail
for a base spawn, wherever a paratrooper lands - refusing a spot within a convoy space of its
neighbours (that is the base's gate: men leave one at a time), and `unit_free` unlinks.
**Traffic control is then one question of the unit ahead** (`unit_traffic`: halted, and within
width + gap?) and only the two leads scan the pool for the nearest of the other side; flags are
refreshed every frame in march order, lead first. Liveness is the tag plane (`Free` is 0).
Collision rejects a munition against the whole pool with one scanline-band test. **The sprite
budget holds by spacing**: at width + gap a window carries at most eight vehicles, 24 sprites /
24 tiles on the line against the PPU's 32 / 34, leaving room for a building on the same line.

A unit is three declarations. **Unit** is a `#[soa]` struct holding what every unit has -
position, hp, owner, lane, block, rank - plus its `kind`, so `units[i].hp` is one
`LDA units__hp,X`. **UnitType** is that `kind`: a tagged enum contributing a tag plane that
doubles as the free marker (`Free` is variant 0) and a payload plane for what only one kind
carries - `Tank(Tank)` holds the gun reload and the hold that parks it in front of a building;
`Infantry(Infantry)` its rifle reload and the one-frame firing pose; `Launcher(Launcher)` its one
missile; `Van` and `Engineer` have nothing of their own and are plain variants. **UnitStat**
is what is fixed about a kind: `unit_stats` is a `#[soa]` immutable static, one ROM table per
column with one entry per variant in tag order. Three rules come out of it:

- **Read a kind's constants straight out of the table by tag**:
  `unit_stats[units[i].kind as u16].width`. The cast is the bare tag-plane read and each
  column is its own table, so a read is one `LDA.l unit_stats__width_data,X` with the index
  scaled by the column width (none for a `u8`). Do not route them through a method on the
  enum: both the `*UnitBase` accessor and per-column `match self` methods were measured at
  0.85 and 0.94 ticks/frame against 1.00 for the table.
- **A variant has no value form** - it cannot sit in a local, a parameter or a table - so the
  spawn order is a separate fieldless `enum Order` that `unit_spawn` maps to a variant. The
  pool takes no initializer either, so `unit_init` writes every element before anything
  matches on it.

OAM slots come from `oam_begin`/`oam_take`/`oam_end` in draw order - airframe, munitions,
buildings, units from the camera centre out - because the PPU drops what it evaluates last.
`tools/oamstat.py oam.bin` reads a `--dump oam` and reports peak sprites and tiles per scanline
against the 32 / 34 hardware limits. `oam_end` parks only up to last frame's high-water mark.

Structures (`src/struct.r65`) are a `#[soa]` pool filled from `level_layout`, a `#[soa]` ROM
table in west-to-east order - **keep it sorted**: the draw cull and the munition test both stop
at the first building east of the camera or the round. Per-frame geometry (width, cells, box
top, first tile, attribute) is precomputed into the pool at init and on `struct_set_owner`.
Ownership is an OBJ palette: 0 the sheet's greens, 1 enemy (red-brown), 2 nobody (grey) - and
3, 4 the same two for the airframe sheet - built at boot by `struct_palettes` from the one
palette each sheet carries (it runs in bank 2: boot-only code, and bank 0 is full). Enemy units
wear palette 1 and the enemy airframe palette 4; the red-brown is one list of colours, so a
tank and an airframe of the same side match. Turrets and the super bunker loft rounds at the helicopter along the line to it; bunkers
moor a balloon on a chain that kills any helicopter on contact (a bunker shelled to 0 hp is nobody's
and balloonless but still capturable - the man who takes it restores it); a manned super bunker also fires
along the ground at units of any other side outside its box; the base fires homing missiles
(`MUNI_MISSILE`) inside 320 px; the bank's gun falls silent after two shells and an enemy
infantryman at the player's bank halves the purse. Per-unit scans (capture, claim, entry, robbery)
run on a stagger of one structure per frame in sixteen - a man covers eight pixels in that time.
`tools/struct_art.py` stamps the building sprites onto rows 6-13 of `obj.bmp`; the airframe's
own sheet is drawn by `tools/heli_art.py`, and both write their 4-bit BMP through
`tools/bmp4.py`, since PIL only writes 8-bit and `bmp2chr -b4` refuses that.

The match (`src/game.r65`) ends two ways only: a van of either side inside the other's base
(`struct_base_van`, scanned every 32 frames - a van is in the window ~75 frames) or the
player's last helicopter (`heli_lost`). Any other loss hides the airframe for `HELI_RESPAWN`
(120) frames while `camera_pan` brings the view home at a pace sized at the loss
(`camera_x / 120 + 1`, so the far end of the world arrives inside the delay); the next
airframe then rises out of the ground at the start, a pixel a frame from the ground line to
hover height, drawn at OBJ priority 0 behind the dirt until it has cleared it (the BG4 tilemap
carries the tile priority bit for exactly this - see the Makefile). The stick, gun and hit test
are off until it is up. A dead stick touching open ground is a crash landing and a loss too;
only a deck saves it - and any touchdown over `HELI_CRASH_VY` (2.5 px/frame) is a crash, deck or
not: 30 frames of Down from hover and a coast lands, 32 does not. `game_state` gates the whole simulation; the draw
still runs so the field freezes on screen, `hud_message` puts VICTORY/DEFEAT on map row 10
from a letter row (`HUD_LETTER_ROW`, stamped by `tools/hud_glyphs.py` below the visible
screen like the glyph strip), and Start calls `game_reset`, which re-runs every `*_init`.
The van end cannot be scripted in useful time; plant one with the debugger
(`set` the tag/owner/x planes of a slot at the enemy base and step a few dozen frames).

**The frame is now the binding constraint.** With the field full and every structure ticking, the
stress movie (eight tanks bought at once against the CPU's column) runs at 0.896 ticks per
vblank, pinned by `unit_budget`. Anything new that runs per unit or per frame has to be measured
against it. `tools/profile.py` is the profiler: a Mesen-GDB `trace` from the snapshot attributed
to functions through the `.sym` (the docstring has the incantation). `tools/poolstat.py` prints
the field from a `--dump wram` - every unit with its links and flags, the munitions, the
structures, the CPU's purse and queue (`--brief` for one line per dump) - and
`tools/timeline.sh` takes those dumps at several frames of one run.

**The campaign** (`src/mission.r65`, phase 11, bank 2) is ten missions, `mission_stats` one
row each: the opponent's `cpu_row` and every number that used to be a constant - the turrets'
rate and range, the income threshold, the starting purse and lives - plus how many turrets,
bunkers and pre-owned buildings the battlefield carries. `mission_set` writes the live values
and calls `mission_layout`, which *derives* the field from those counts (the banks and bases
fixed at the world's ends, the super bunker dead centre, turrets and bunkers alternating
through the contested middle either side of it) rather than transcribing the original's
fifteen levels; `LAYOUT_MIDDLE_MAX` keeps the derived buildings inside the 16-slot pool.
Rows 10-12 are the **harness missions**: the hand-made pre-campaign field with frozen tuning,
reachable only by holding a shoulder button at power-on, and the whole suite runs on them -
see `tests/run.sh`'s header. Treat their rows, their convoys and their layout as part of the
tests.

**The front end** (`src/screen.r65`, phase 11, bank 2) is three pages - title, briefing,
after-action - and they are all one mechanism: BG1 written as a full 32x28 page of text with
`TM` naming BG1 alone, so the field behind is not hidden but simply not drawn, keeping its
state and its registers. A page costs one 1792-byte DMA of the map in force blank when it goes
up and nothing per frame; coming back restores the map from ROM and re-runs `hud_init` and
`radar_init`, the page having written over the rows they own. `GAME_SCREEN` is a game state
like the two battle-over ones, so `main` runs neither the tick nor the draw while one shows.
**Progress between missions is a typed code, not a save file** (`code_*`): four letters
carrying eleven bits of payload - four of mission, seven of purse - and five of check,
scrambled and cut into nibbles, each a letter A..P, so 1000 of the 65536 spellings mean
anything and a mistyped one is rejected rather than silently starting the wrong mission. The
d-pad types it over the title (a held direction repeats), the line under it says live what the
code reads as - the mission it opens, or NEW GAME - and Start takes exactly that, the code's
purse displacing the row's `start_funds`. The after-action page settles the mission and spells the code for the next
run, leaving it typed in so continuing is one press: **a won mission carries its purse plus
what survived it** (`campaign_salvage` - a ground unit at what order.r65 charged for it, a held
building at the design's value, the base 20), a lost one is fought again with the purse its row
deals. The airframes deliberately do *not* convert: the original pays 20 a surviving
helicopter, which against a two-digit purse saturates the carry on any win at all. Start on
that page goes straight to the next mission's briefing, or to the end page once the tenth is
taken. Typing redraws only the five rows the
field occupies, DMA'd from the page shadow in vblank (`screen_flush`); everything else about a
page is composed once. The glyphs are the HUD's - capitals, digits and
spaces, nothing else, which is why the mission names spell their hyphens as spaces. **The front
end is the campaign's**: a harness mission boots straight into its battle and its Start
restarts it, so no suite movie has to press past a page it did not ask for.

**The CPU opponent** (`src/cpu.r65`, phase 10, in bank 2 with `hud.r65` and `order.r65` -
bank 0 is full) is the 1991 game's: a capability row per mission (`cpu_stats`, picked by the
mission's `cpu_row`) and the convoy strings verbatim (`convoy_data`, gated by tier, priced by
`convoys`). `cpu_level` is set by `mission_set` at boot and survives a reset. On the first
mission's row the pilot only wanders and refits; `scatter_bomb` (from mission 8) is what lets it bomb at all, and `kill_*`
say at what. It earns as the player does from its airframe's distance into
the player's half, and - the original's rule, from the remake's `Inventory.js` - once the last
convoy has left the gate and the row's `order_delay` (22 s, shorter past tier 5, plus up to a
quarter at random, halved after a single unit) has run, buys one convoy it can afford at
random with its own xorshift, so `rand()`'s parachute sequence stays put; broke, it waits a
whole pause. `fund_min`/`fund_max` are the player's purse at which it will raid the bank (not a
reserve; the original has none). The convoy drains through `cpu_tick`'s emitter under the same
gate rules as the player's orders. Its purchase sequence from a cold boot is fixed by
`cpu_seed` and the airframe's flight - but *only* by those: the pilot draws the same
`cpu_rand`, so how often it has tossed a coin before the first purchase decides what the purse
can reach, and any change to `foe.r65` re-deals the whole army. That is what `cpu_forced` is
for: a harness mission names the convoy to buy (the tier gate does not apply to a forced pick,
the purse still does), so the dozen cases calibrated to a column stay put.

**The enemy airframe** (`src/foe.r65`) is a second helicopter on its own `foe_*` statics with
copies of the player's physics, loadout, fuel, pad and loss rules (a second copy of a few
routines beats routing both airframes through a pointer, and leaves the tuned code alone). It
starts hovering at the far edge, facing the player. It is lost to a bomb outright, to 20 points
of gunfire or two missiles, to a balloon, and to contact with the player's airframe (both go);
the next one comes after the row's `regen_time`, rising out of the ground at the far edge, and
the last one is the player's win.

**The pilot** (`foe_think`, every 8 frames; `foe_fire` every frame) is an adaptation of Armor
Alley's `Helicopter-AI.js` - its priority list, not its steering-force model. In order: **refit**
(fuel under 10 plus a unit per 256 px of the trip home, or two of gun < 6 / no bombs / hp < 5 -
one on the first two rows) → the pad; **dodge** the nearest opposing round within 192 px and
two heights - a round from the ground gets the jink (`foe_jink`, four heights every 16 frames),
one from the air a step over or under, and the spot flown to stays what it was; **hunt** the
player's airframe when `foe_hunt` and it is within 512 px and not landed - a standoff off it,
level, for the gun, or two heights above it for a bomb once the gun is dry; **bomb** the nearest
player unit the row's `kill_*` flags allow within 512 px (from a hover over it), then the
nearest player turret or bunker on a **pass** - `FOE_PASS` (192 px) beyond it, since a bomb
from a hover falls straight down the turret's own stream of rounds; a turret only with hp ≥
`FOE_HP_PASS` (16), a pass costing about ten - released when the bomb's landing spot (centre
plus vx × the fall, `mul16` on the height) is over the target, one bomb per target, three per
tank, any number per turret, 40 frames apart; else **wander** toward the player's end on the
weave (`foe_weave`, four heights every 64 frames), turning at `FOE_WEST` (900, short of the
base's missiles) and 128 px from the far edge. After every decision `foe_under_balloons` pins
the height to hover within 224 px of a balloon, and every frame `foe_evade` overrides the
height only: a round from the ground gets the jink (`foe_jink`, four heights every 16 frames at
full vertical speed with four times the thrust), one from the air a step over or under, and the
player's airframe about to overlap gets a climb or dive out of its plane (`foe_avoid_due`: within a
standoff, or closing - both airframes' speed, the pilot's own not counted in a hunt - fast enough to
cover the gap in 16 frames, a shift of the speed). It is deliberately imperfect: it looks every
fourth frame, and one encounter in four it is blind for `FOE_BLIND` frames, chosen from the frame
count rather than `cpu_rand` so the purchases stay put; a head-on charge gets through about one
time in sixteen. The gun fires at
the player's airframe within 320 px, more than a width off, within 1.5 heights and faced. Modes
as the original's: every ~34 s `foe_attack` (7 in 8) and `foe_hunt` (attack and
`kill_copter`); a point of gunfire with the player's airframe in view tosses a coin, at most
once a second, to start hunting. Not adapted: clouds, paratroopers, the kamikaze run, and the
smart-missile counter-measures (slice (d)). Both decks now repair (`HELI_HP_REPAIR`, a point
per 16 frames), which the refit rule assumes. A bomb's blast reaches buildings -
`struct_collide` runs before `unit_collide`, which spends the blast, and the blast is snapped
to the ground line - so four bombs take a turret and three a bunker; and a climbing round (a
turret's, lofted at an airframe) no longer shoots bombs down. **Only one missile truck of a
side fires at a time** (`launcher_shot`): while its missile is up the rest hold. Both airframes' collision walks are gated on `muni_up[side]`, the count of the
other side's munitions in flight kept by `muni_update` - not on distance from the other
airframe, since turrets, bases and launchers fire a side's rounds too. `air_target(mine, x, range)` is how a gun of either side, or a hostile-neutral
one, finds the airframe it may shoot (centre x back, centre y in `air_ty`); turrets, the super
bunker, the bases and launchers all go through it, and a missile homes on the airframe of the
side that did not fire it. The CPU's purse reads its real position, and the radar plots it red.

Munitions are 8x8 sprites from a 16-slot struct-of-arrays pool with a rotating free cursor
(`src/muni.r65`). Two kinds home: `MUNI_MISSILE`, the buildings' and the launchers'
anti-air missile, which steers at the other side's airframe and does 10 of its 20 points;
and `MUNI_SMART`, either airframe's Y weapon, which locks its target at launch (`smart_spawn`:
the other side's airframe within 640 px, else the nearest of its vehicles - never a man, and
never nothing, since a press with neither in reach is refused rather than spend one of the
two it carries) and kills what it hits outright, airframe or unit. Buildings keep their own
rules, which is to say a smart missile passes them. `muni_tgt` holds the lock; a target that
dies mid-flight leaves it flying on to expire. Both airframes reload one per 128 frames on
the deck, and the pilot fires one (`CPU_USE_MISSILE`, four seconds apart) while hunting or
once it is down to 8 points - the original's retaliation.
 OAM order follows the plan's importance rule: the helicopter takes slots 0-1
and munitions in flight take the slots straight after, with anything outside the visible 256 px
culled rather than parked off-screen.

The HUD is BG1 rows 0-1 at the top and row 27 at the bottom. Row 0 (`src/hud.r65`: `$` purse,
lives, men aboard) and row 27 (the airframe: H and F gauges of six bar cells, G rounds, B
bombs, M missiles - over the dirt, the last visible row in 224-line mode, where nothing else is
drawn) are composed into one 64-word shadow and DMA'd in vblank, 64 bytes each, when a shown
value changes; row 2, navy in the art, is cleared once at boot. Their glyphs (digits, `$`, brackets, six unit icons on **map row 28
of `bg1.bmp`**, capitals on 29, the dialog's box/cursor/bar cells on 30 - all below the 224
visible scanlines) are read back out of `BG1_MAP` at runtime by position, so bmp2chr's
de-duplicated IDs never appear in code. The glyph *order* is the contract; `tools/hud_glyphs.py`
stamps them and is the place to edit them.

Row 1 is the radar (`src/radar.r65`): 32 tiles past the art's (`RADAR_TILE = BG1_CHR_SIZE/16`)
mapped in order, so the row is a 256x8 bitmap - 32 world px per pixel - drawn into a 512-byte
2bpp shadow and DMA'd to the BG1 tileset every 16th frame, in its own BG sub-palette (CGRAM 4-7:
navy, blue, red - written at boot by `radar_palette`) so a side reads by colour: blue the
player's, red the enemy's (no white: 2bpp is three colours and transparent). Vehicles only - men are not shown. Buildings are ticks in a base image
rebuilt when `struct_set_owner` flags it (MVN-copied into the shadow each redraw); units and
the airframe are plotted over it, and the camera window is an 8x8 sprite (`radar_draw`, OBJ
tile 31, the slot after the airframe's) so it follows the camera every frame. An enemy van within `RADAR_JAM` px of
the airframe turns the redraw into noise. It costs ~2.5% of a frame on average; `unit_budget`'s
pinned figure dropped more than that because that movie sits on the budget line and a frame
over it by a hair drops whole.

The airlift (`src/para.r65`): a powered descent lands anywhere on the ground (`heli_landed`;
`heli_on_pad` says whether it rearms), and a player infantryman within 5 px of a landed
airframe's middle boards it (five at most, and they count against the infantry cap); X drops one as a paratrooper
from an 8-slot pool of its own - units have no y - who sinks at 0.75 px/frame under a canopy
cell drawn over the standing man's, or at 3 px/frame with none when the chute fails (one in ten,
`rand()`'s only consumer, so the sequence from a cold boot is fixed), and becomes an infantryman
the frame the unit pool has room. An airframe lost a third of its flight band up or higher
(`HELI_Y_BAIL`) with men aboard drops one of them first; the rest go with it. Draw order: after the munitions.

Controls: on the title, the d-pad types the continue code and Start takes what the page says;
Start goes on from the briefing and the after-action page. In the battle, hold L for the order
dialog - Left/Right move the highlight, A buys - and the d-pad
and A do not reach the airframe while L is down; B gun, A bomb, Y smart missile, X drop, Up
lifts off a deck.
The dialog (`hud_overlay`) is a box on BG1 rows 2-9 composed once at init into an 8-row
shadow (composing it on the press cost a frame) and DMA'd as one 512-byte block on show and
cursor move, with an all-transparent twin DMA'd on hide; its border and cursor tiles are stamped
on map row 30 by `tools/hud_glyphs.py`, the names come from the letter row. `game_over` hides
it before writing the battle-over line on row 10, from when they shared that row.

Funds (`src/order.r65`) accumulate `heli_x_px >> 4` per frame against `ECON_THRESH`; that
threshold is the pace knob and `econ_income` in the suite pins its current value. Orders go
through an eight-deep queue that lets the next man out once the last has cleared the gate by a
convoy space (`unit_spawn`'s spacing test), holding him when the pool is full rather than dropping him. Caps count men on the field plus men queued, and
infantry and engineers share one cap.

The ground parallax is 8 HDMA bands of 7 scanlines. `gnd_table_build` computes
`d = camera_x >> GND_SHIFT` once then accumulates - one shift, seven adds, no multiplies.
`GND_SHIFT` is the depth knob; raising it narrows the spread and shrinks band seams.

## Key R65 Patterns for SNES

### Register Binding

```rust
let value @ A = 42;           // Bind variable to A register
fn process(x @ A: u8);        // Parameter in A register
fn indexed(idx @ X: u16);     // X/Y parameters must be u16
```

### Hardware Register Access

```rust
INIDISP = 0x0F;               // Direct write to PPU register
let status = HVBJOY;          // Read from hardware
```

### VBlank Synchronization

```rust
loop {
    wait_nmi();               // Wait for VBlank interrupt
    // Update game state here
}
```

### DMA Transfers

```rust
dma_vram(0, &DATA, dest_addr, size);  // Transfer to VRAM
```

### Memory Storage Classes

```rust
static ROM_DATA: [u8; 16] = [0; 16];  // Immutable = ROM (no attribute)

#[zeropage]
static mut FAST_VAR: u8;              // Zero page (fastest access)

#[lowram]
static mut LOW_VAR: u16;              // Low RAM ($0000-$1FFF)

#[ram]
static mut BUFFER: [u8; 256];         // Main RAM ($7E2000+)

#[hw(0x2100)]
static mut INIDISP: u8;               // Hardware register (volatile)
```

## Common Pitfalls

- Always call `snes_init()` before accessing PPU registers
- Screen must be off (`INIDISP = 0x80`) during VRAM writes outside VBlank
- X/Y registers are always 16-bit (u16), never use u8 for X/Y parameters
- Use `#[ram]` for mutable statics, `#[zeropage]` for fast access variables
- No implicit type conversions - use explicit `as` casts
- Multiply/divide operators only work with constants 1, 2, 4, 8 - use `mul8()`, `div8()` for variables
- Shift operators require constant amounts - use `shl()`, `shr()` for variable shifts

## Debugging

- Build with `--dbg` flag (default in Makefile) for Mesen source debugging
- Load `.dbg` file alongside ROM in Mesen for source-level breakpoints
- Use `asm!("BRK")` to trigger a breakpoint in emulators

## R65 vs Rust Quick Reference

| Rust | R65 | Notes |
|------|-----|-------|
| `fn foo(x: u8)` | `fn foo(x @ A: u8)` | Register binding for parameters |
| `let x = 5;` | `let x @ A = 5;` | Optional register binding |
| `x * y` | `mul8(x, y)` | Variable multiplication |
| `x << n` | `shl(x, n)` | Variable shift amount |
| `unsafe { }` | *(not needed)* | All code has hardware access |
| `Option<T>` | *(not available)* | Use sentinel values |
| `Result<T, E>` | *(not available)* | Use return codes |

## Hardware References

- [65816 Programming Manual](http://archive.6502.org/datasheets/wdc_65816_programming_manual.pdf)
- [Super Famicom Development Wiki](https://wiki.superfamicom.org/)
- [WLA-DX Documentation](https://wla-dx.readthedocs.io/)

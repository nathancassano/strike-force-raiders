# Rotor Raiders - AI Assistant Guide

A helicopter tug-of-war for the SNES, descended from *Rescue Raiders* (Apple II, 1984)
by way of *Armor Alley* (1991). Built with the R65 compiler. For the full R65 language
reference, see the main CLAUDE.md in the R65 repository.

The design and phase plan live in [design.md](design.md).

## Project-specific rules

**Always use `OamBuffer.set_full!`, never `set!`.** `set!` writes only an 8-bit X and leaves
a stale extended-X high bit, which renders a sprite 256px off - invisible but still active.
In a side-scroller every entity crosses a screen edge, so this applies everywhere.

**`*` only accepts power-of-two constants.** `mul8(i, 3)` costs ~57 cycles where `(i<<1)+i`
costs ~16. Pad tables to power-of-two strides rather than multiplying by 3, 5, 6...

**A `let x @ A` (or `@ X`, `@ Y`) alias is not preserved.** The compiler rejects one whose
register is overwritten before its last use - the `let lo @ A = JOY1L; let hi = JOY1H;` pad
idiom among them - so compose through plain locals instead:
`let v: u16 = ((JOY1H as u16) << 8) | (JOY1L as u16);`. `@ B` (A's high byte) is not checked
yet: it is clobbered just as silently.

**The PPU expands 5-bit colour to 8-bit by bit replication** - `(v<<3)|(v>>2)`, not
`round(v/31*255)`. The two disagree by one on most values, which is enough for an exact-match
colour search to miss every sprite pixel in a screenshot. `tools/pngstat.py --snes` does it
correctly; use that rather than converting by hand.

**Name sprite frames for the subject, not the screen.** Facing-left renders hflipped, so a
frame called `LEFT` is ambiguous about whether it means the art or the result. Tilt frames are
`NOSE_DIP`/`NOSE_DOWN`/`NOSE_UP`. The forward lean follows the stick held *along the nose*
(`Airframe::lean`, from `turn_step`'s `want`), and nose-up follows velocity along the nose. Using
the signed vX, or the raw Right bit, double-flips against hflip.

**BG1HOFS is $210D, BG2HOFS $210F** (BG4HOFS, $2113, is gone with Mode 0). Getting one wrong
in an HDMA `BBAD` silently drives the wrong layer and presents as "HDMA is not working".

**`HDMAEN` takes every channel at once.** `dma_set_hdma!` writes the register outright, so the
ground (channel 6) and the sky (channel 5) are enabled together, `0x60`; enabling one later
switches the other off. And an HDMA channel costs CPU time on every scanline until its table
ends, so a table that has nothing left to write ends rather than holding to the foot of the
screen (the sky's stops at its split; run to 224 it cost `unit_budget` 29 ticks).

**Write `NMITIMEN` whole, with `set_nmitimen!`.** It is write-only, and sneslib's
`enable_nmi!`/`enable_autojoy!`/`disable_nmi!` are read-modify-writes, so they OR into open bus.
Two in a row in `boot_load` dropped the auto joypad read, and the pad went dead. An older R65
happened to hide this by forwarding the stored value instead of re-reading the register.

**Bank 0 is full, and wlalink does not say so.** An over-full bank is linked over whatever
follows it - the ROM header and vectors at the top of bank 0 - with an `Overwrite at` line and
exit status 0, and the ROM crashes on its first frame. The Makefile fails the link on that line
(`build/link.log`). Code that does not have to be in bank 0 (anything not calling `oam_take` or
another near bank-0 routine) goes to bank 3 as a `far fn`, as `fx.r65` and `Pilot::lost` do.

**`src/lib/` is a vendored copy of `/home/nathan/R65/stdlib/`.** It currently matches upstream.
Check before copying code from another project - the
other projects' copies have drifted by 50-170 lines.

## Build Commands

```bash
make          # Build ROM
make verify   # Build and run the ROM test suite (pytest tests -n auto)
make lint     # Run the R65 linter (rules in r65-lint.toml)
make assets   # Just the art: assets/src/*.bmp -> SNES CHR (an ordinary build does this)
make play OUT=build/x.png ACTIONS=@MISSION_TEST_QUIET,wait60,shot   # one ad-hoc scripted run
make run      # Build and launch in emulator
make clean    # Clean build artifacts
make syntax   # Compile only, no ROM
```

## Testing

Do not ask a human to look at the screen - drive the ROM yourself.

**The regression suite is pytest** on `mesen_gdb.rom_driver` (`/home/nathan/R65/Mesen-GDB/python/README.md`):
`pytest tests -n auto` (about 70-80 s on 8 cores; `pytest tests -k airlift` filters). It began as
the old shell suite's cases, ported with their expected values, one file per phase (`test_flight.py`,
`test_pad.py`, `test_units.py`, ... `test_campaign.py`); every completed phase leaves a case
behind and the whole suite re-runs after each new one. Each case is one plain test function named
in words, its explanation as the docstring - no parametrize tables, no lambdas:

    def test_camera_follows_30_frames_right(snes):
        boot(snes, "direct").wait(20).right(30)      # chained input, run as it is called
        v = read_snapshot(snes)                      # Select to snapshot_point; memory by name
        assert v.camera_x == 90

Names are exactly as the `.sym`/`.dbg` spell them, with an array's width stated
(`v.units__kind__tag.u8[3]`); an `#[soa]` plane is always read that way, even a two-element one -
`v.airframes__x_px.u16[0]` the player's, `[1]` the enemy's, `v.player__men.u8[0]` - since
`read_snapshot` returns a `Snapshot` (`tests/shared.py`) that gives any name with `__` as an
array (plain `s.var` reads anything of one to three bytes as a number); values are decimal (8.8 heights as `96 * 256`), hex only for bit
patterns. `boot` takes a mission by its ROM constant's name - a test row,
`boot(snes, "MISSION_TEST_QUIET")` (also `MISSION_TEST_HUNTER`, `MISSION_TEST_CONVOY`), or a
campaign mission, `MISSION_` and its briefing name, `boot(snes, "MISSION_CAKE_WALK")`
(`src/mission.r65`) - and boots it without input: `boot_load` boots the mission in `boot_pick`
(main.r65), which the power-on sets to the campaign just before calling it; a test stops at
`boot_load`'s entry and writes the constant's value there, plus `BOOT_DIRECT` to skip the front
end.
`conftest.py`'s header says what each opponent is. A setup several cases share is a state
in `tests/shared.py`, beside `boot` and `read_snapshot` (`@rom_state` builders: `boarded`,
`eight_tanks`, `five_passes`, `balloon_hit`, `campaign_lost`), built once, cached in
`build/.rom_driver/`, and opened by passing the builder: `from shared import boarded`, then
`state(boarded)`.

**`boot` syncs on `main`, not on a frame number**: it runs the power-on to the ROM's main loop and
then `BOOT_SETTLE` (13) frames, which is where a mission boot stood when the suite was calibrated
(main at 17, inputs from 30). So the boot can cost what it likes - the sound driver's upload is
~156 frames - without moving a case. A boot of the campaign proper (no mission) also sets
`BOOT_NO_INTRO` in `boot_pick`, skipping the power-on BubbleZap intro, which `test_campaign.py`
covers on its own. `tools/mkmovie.py` cannot sync or skip, so its `BOOT_FRAMES` idle (686) has to
cover the intro, the upload running under it - main is at 670 - and must grow with them.

`./play.sh OUT.png ACTIONS [--dump REGION FILE]...` (`tools/play.py`) runs the actions on
`mesen_gdb.rom_driver` with the suite's own `boot` and `read_snapshot`, and screenshots at the
ROM's `snapshot_point()` hook (fired by Select).

    ./play.sh build/fly.png @MISSION_TEST_QUIET,wait60,right90,shot --dump wram build/fly.wram

Actions: `waitN`, `start`, `shot`, `upN`/`downN`/`leftN`/`rightN`, `aN`/`bN`/`xN`/`yN`/`lN`/`rN`.
Combine with `+`, e.g. `up+a30`. A leading `@MISSION_TEST_QUIET`, or any mission constant, is
the mission `boot` boots; without one the run boots the campaign proper, title page and all.
`tools/mkmovie.py` still builds Mesen movies (`tools/timeline.sh` uses one); a movie cannot
write `boot_pick`, so it always boots the campaign proper.

`tools/pngstat.py shot.png [--expect R,G,B] [--min-pct N]` inspects what actually rendered -
use it to assert on frames instead of trusting a clean exit code.

`tools/parallax.py BASE.png MOVED.png [--assert-bands N]` cross-correlates two frames row by
row and reports each layer's horizontal displacement, plus the HDMA ground bands. This is how
scrolling is verified - pixel-eyeballing a periodic pattern will mislead you, and a
horizontally uniform (or short-period) row correlates at 100% for *any* shift, so every row
you intend to measure needs a feature with a unique phase. The ground gets that from a
pseudo-random pebble field painted by `tools/ground_texture.py` (the same field on both
256 px halves, so the tool's wrap at the screen width stays exact) rather than from marker
bars, which read as vertical artifacts. The sky's bars and the hills' posts are gone too: the
mountains' own texture gives their rows a unique phase.

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
│   ├── video.r65             # Mode 1 layers, HDMA ground and sky parallax, camera
│   ├── unit.r65              # Ground-unit pool, march, traffic control, tank fire, rifles
│   ├── para.r65              # The airlift: men aboard, paratroopers
│   ├── struct.r65            # Buildings: level table, turrets, bunkers, balloons, super bunker, bases, banks
│   ├── order.r65             # Funds, the L/R order ring, the order queue
│   ├── cpu.r65               # The opponent: capability rows, convoy table, its purse and queue
│   ├── mission.r65           # The campaign: one row per mission, the derived battlefield, the test rows
│   ├── screen.r65            # The front end: the Mode 3 title, briefing and after-action pages on BG3
│   ├── intro.r65             # The power-on BubbleZap logo: hindstrike's Mode 7 spin-in (bank 2)
│   ├── heli.r65              # The airframes: the #[soa] pool (Airframe, both sides' methods) and the player's (Player)
│   ├── foe.r65               # The enemy's pilot (Pilot): its decisions, and the world against its airframe
│   ├── fx.r65                # Explosions and smoke: hindstrike's particle animations (bank 3, draw in 0)
│   ├── hud.r65               # BG3 strip rows 0-1 (purse, lives, gauges, ammo, men); the battle-over line; the order menu of unit icons
│   ├── alert.r65             # The alert queue and the avatar: a portrait and a typed two-line message, bottom right
│   ├── radar.r65             # BG3 strip row 2: the radar, a 256x8 bitmap the game draws
│   ├── game.r65              # Match state: the two ends, the reset
│   ├── sound.r65             # SNES GSS sound driver: upload, commands, sfx_play, music_play (bank 3)
│   ├── assets.r65            # GENERATED by make from assets/gfx - not in git, do not edit
│   └── lib/                  # Standard libraries
│       ├── 65816.r65         # CPU register definitions
│       ├── sneslib.r65       # SNES hardware registers and helpers
│       ├── math.r65          # Math functions (mul8, div8, etc.)
│       ├── string.r65        # format!, number-to-text
│       ├── console.r65       # Console: text into a tilemap buffer (screen.r65's pages)
│       └── default_font.r65  # The console's font, ASCII 32-126
├── assets/
│   ├── src/                  # Source art (indexed BMP; %.tilemap.bmp also emits a tilemap)
│   ├── gfx/                  # Generated .chr / .pal / .tilemap - build output, not in git
│   ├── sound/                # SNES GSS export from hindstrike (pitch edits: tools/sfx_transpose.py): spc700.bin (driver + effects), music_*.bin, hindstrike.gsm (the project), sounds.asm/.h (names)
│   └── levels/               # Battlefield placement lists
├── tools/                    # play.py, mkmovie.py, pngstat.py, poolstat.py, profile.py, timeline.sh, asset generators (sky_art.py, ...)
├── design.md                 # Design and phase plan (Part 1 design, Part 2 technical, Part 3 phases)
├── tests/                    # pytest ROM suite (conftest.py, shared.py, test_*.py)
├── play.sh                   # One-shot scripted run + screenshot
├── build/                    # Compiled output (.asm, .smc, .sym, .dbg)
└── Makefile                  # Build system for WLA-DX
```

## Graphics architecture

Mode 1 throughout, three BG layers, all repeating 512px patterns that wrap in hardware - so
there is **no column refill anywhere**. Everything world-specific is a sprite.

| Layer | Sheet | Contents | Scroll | Tiles / VRAM map (words) |
|---|---|---|---|---|
| BG1 | `ground` | dirt, rows 179-223 | per-scanline HDMA ch6, eight bands | 4bpp $0000 / $6000 (64x32) |
| BG2 | `sky` + `mountains` | stratus clouds rows 16-91; mountains 135-178 (muted desert rock, hazed toward the sky) | HDMA ch5: clouds `camera_x >> 5` above `SKY_SPLIT` (104), mountains `>> 3` below - the clouds are the farthest layer | 4bpp $1000-$3FFF (clouds' tiles, then mountains') / $6800 (64x32) |
| BG3 | `hud` + `icons` + `status` | status rows, radar, order menu, front-end pages | fixed | 2bpp $7000 / $7800 (32x32) |
| OBJ | `obj` | units, buildings, munitions | camera-relative | $4000 (4bpp, tiles 0-255) |
| OBJ | `heli` | the two airframes, their own sheet | camera-relative | $5000 (4bpp, tiles 256+) |
| OBJ | `fx` | explosions and smoke, from hindstrike | camera-relative | after `heli` (4bpp, `FX_TILE0` on) |
| OBJ | `avatar` | the alert portrait, two 32x32 frames | fixed, bottom right | after `fx` (4bpp, `ALERT_TILE0` on) |

The clouds and the mountains share BG2 because they never share a scanline: one HDMA split
gives each its own scroll. **They are two sheets**, `sky.tilemap.bmp` and
`mountains.tilemap.bmp`, each an ordinary one-palette bitmap, and BG2 has one map and one tile
area: the mountains' tiles go up straight after the clouds' (the Makefile offsets their map by
the clouds' tile count, `tilemap_attr.py --tile-offset`), and `video_upload` lays the
mountains' tile rows (`MOUNTAIN_ROW`.., 16-22) over the clouds' map in both screens. So each
sheet draws only in its own band - `sky_art.py` checks it. **Priority does the layering**: BG1 draws over BG2 (the mountains
end on the scanline above the dirt, so nothing of them is hidden under it); `BGMODE`'s BG3 bit (`set_bgmode!(1, 0x08)`) plus the priority
bit on the HUD's tiles puts the HUD over everything, sprites included - except the radar row,
written without the bit so the camera bracket sprite shows over it, and the blank HUD cell,
`HUD_BLANK`, which carries the bit by hand (a bare 0 lets the dirt through). The ground's tiles
carry the bit as well, so an airframe rising out of it at OBJ priority 2 is behind the dirt and
in front of the mountains.

**CGRAM**: BG1 and BG2 draw 16-colour palettes from 0-127, and BG3's eight 4-colour ones are the
first 32 of those. So the HUD keeps 0-31 (CGRAM 0 is also the backdrop - the sky, #3d9aec, the clouds' art drawn against it):
BG3 sub-palette 0 the HUD art, 1 the radar, 2 the front end's font, 3-4 the order menu's icons, and
5-7 (CGRAM 20-31) the status rows' gold, red and white;
the ground is palette 2 (32-47), the clouds 3 (48-63), the mountains 4 (64-79), 5-7 are free,
and sprites get 128-255. Every 4bpp sheet is one palette, drawn as palette 0 in its bitmap and
moved up by `tools/tilemap_attr.py --pal` in the Makefile; `CGRAM_GROUND`/`CGRAM_SKY`/
`CGRAM_MOUNTAINS` in `video.r65` say where its `.pal` is uploaded. Change one, change both.

All art is indexed BMP in `assets/src`, and **that is the only art in git**. **The file name
says what a bitmap produces**: `%.tilemap.bmp` is de-duplicated into a tileset *and* the map that
names its tiles back (`assets/gfx/%.chr`, `%.pal`, `%.tilemap`), a plain `%.bmp` gets the tileset
alone, and the Makefile has one multi-target pattern rule for each - make decides between them by
which source exists. Bit depth is the other axis and is a target-specific variable (`-b2`, with
`obj`, `heli`, `fx`, `sky`, `mountains` and `ground` set to `-b4`), since it has nothing to do with whether a sheet
carries a map. So are the tilemap attributes bmp2chr has no flag for - palette offset and
priority bit, set afterwards by `tools/tilemap_attr.py`. The art depends on the Makefile, so
editing either reconverts it.
Everything runs through `r65x bmp2chr`,
`src/assets.r65` is generated from whatever those files turned out to be, and the ROM depends on
the lot - so editing a bitmap and running `make` is the whole pipeline; `make assets` is just a
name for its art half. Both are build products, `.gitignore`d, and removed by `make clean`.
`tools/{hud_glyphs,ground_texture,sky_art,struct_art,muni_art,heli_art,fx_art,avatar_art,icon_art,base_art,title_art,status_art}.py` stamp pixels *into the bitmaps*
(sharing `tools/bmp4.py`, which writes the 4-bit BMPs `bmp2chr -b4` insists on and PIL cannot);
they are authoring helpers run by hand, outside the chain, and phase 12 replaces what they drew.
`sky_art.py` and `title_art.py` are the exceptions that already are final art (the title's is below). It paints the sky's two sheets from
ComfyUI renders (`pixel_art_sdxl` with comfyui-seamless-tiling's `x_only` tiling, so they wrap).
`sky_art.py mountains` takes a render's pixels: gimp crops, squashes to 512x44 and indexes it
(the script-fu is in the file, `--scm`), then the tool keys the sky by silhouette (its bottom row
sits on the dirt and must be solid) and fits it one 15-colour palette. **`sky_art.py clouds` takes only a render's
shapes**: the model's "pixels" are irregular 5-8 px blocks on no grid, and shrinking them 3x
leaves streaky noise - tolerable on rock, junk on cloud - so the tool blurs the blocks away,
averages the crop down and thresholds clean silhouettes, then draws them itself in a 15-step
ramp (`CLOUD_LOW`..`CLOUD_HIGH`), lit along each band's top edge and darker toward its
underside. Options: `--key-grey` when a mountain render's clouds touch its peaks (not for snow
caps), `--threshold T` to move the cloud/sky line, and `--haze N` on either to blend toward the
backdrop colour `main.r65` sets, which is what makes a band read as distant. The current art is
mountains `--key-grey --haze 0.3` (rows 135-178) and clouds from render `rotor_clouds_e_00001_`
rows 30-480 at `--threshold 40 --haze 0.15` (rows 16-91, from right under the HUD, where a cloud cut flat at the
top reads as running on behind it). The two sheets share BG2's 768 tiles (537 now); the
Makefile stops the build past it, since they would overwrite the sprites' at $4000. **Bigger sky art lengthens the boot** (its tiles upload in force blank), and a boot a frame longer shifts every
suite movie: the clouds' did, and moved `test_unit_budget`'s pin.
Nothing generates graphics from code at build time. **`sky`, `mountains` and `ground` are drawn
512x256, as they appear** across the layer's two screens, and the Makefile folds each on its way
into bmp2chr (`tools/fold.py`, into `build/fold/`): a 64x32 SNES tilemap is two 32x32 screens one
after the other and bmp2chr emits row-major at bitmap width, so it is fed the strip 32 tiles wide
and 64 tall, right-hand screen below the left. Each BG layer has its
own de-duplicated tileset (BG2's two sheets each have theirs, loaded one after the other). A
sheet's `.pal` is its BMP's colour count: every BG sheet has 16 entries, one 32-byte palette,
saved 8-bit or 4-bit as the editor likes (`fold.py` and bmp2chr take either).

Sprites are 4bpp with OBSEL small=8x8 / large=16x16, so a unit is 16x16 and a munition 8x8.
**There are two sprite sheets.** `obj.bmp` holds the units, the buildings, the decks and the
munitions at $4000 (tiles 0-255); `heli.bmp` holds the two airframes' frames alone - three
flight, three turn, and the wreck's two in each row's last four columns, crashing (tile 12) and
crashed (44), plus the nose dipping on a third row (tile 64, `HELI_TILE_NOSE_DIP`, derived from the level
frame by `tools/heli_art.py dip`). The lean is the stick's, not the speed's. `Airframe::tilt`
counts up `HELI_LEAN_RISE` (2) a frame while the direction along the nose is held, to
`HELI_LEAN_FULL` (20), and back down one a frame otherwise (released, reversing, dead stick; a
landing zeroes it). So a push dips 2 frames in and is nose-down at 10, and letting go is the dip
on the next frame, held 16 frames, then level, however fast the airframe still coasts. The rise
is the knob for how much slower the lean comes off than it goes on. The gun's downward angle
follows the same count. The
sheet is loaded into the second OBJ name block at $5000, so its tile numbers are 256 + the sheet's and the 9th
tile bit (`HELI_PAGE`) rides in the attribute word. It has its own CGRAM palette as well
(`OBJ_PAL_HELI`, palette 3, and palette 4 for the enemy's), so the airframes can be redrawn or
recoloured without touching anything the ground shares. **That block is full**: the airframe's
96 tiles, the explosions' 96 and the avatar's 64 are its 256 exactly, so a bigger sheet in it needs
a row given up first (a sheet's tile count moves every sheet after it). Either sheet must be 16 tiles wide
whatever it holds: the hardware reads a 16x16 sprite as tiles T, T+1, T+16, T+17.
A 24-px vehicle is one 16x16 cell plus its second cell's left half drawn as **two 8x8s** - three
tiles on a scanline, not four, which is what keeps eight bunched tanks and a bunker (28) under
the PPU's 34 (`unit_draw_one`; the sheet's fourth tile column of every vehicle is blank).
A marching man (infantry or engineer) alternates his standing frame with a stride frame
(`UNIT_TILE_MAN_WALK`, tile 74) every 4 px, picked from `x_px & 4`: no state, and a halted man stands.
A man killed - shot, bombed, shelled, run over or a failed chute - lies where he fell for two
seconds (`UNIT_TILE_MAN_DOWN`, tile 76), drawn by `fx` rather than kept in the unit pool.
The 544-byte OAM shadow lives in lowram and is DMA'd by `oam_flush` in vblank.

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
Collision rejects a munition against the whole pool with one scanline-band test - all but a bomb,
which falls through a unit's box and goes off on the ground, so its blast is what hits the vehicle it
lands on (caught in the band it was spent on the roof for nothing). **The sprite
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
moor a balloon on a chain, a danger only to a helicopter of another side - Armor Alley's rule
(`struct_balloon_at`): the balloon ends it on contact, the chain (from the balloon's foot to the
roof, across hover height) takes `CHAIN_DMG` (18 of 20, the original's) and snaps, the balloon going
with it; a neutral bunker's is everyone's danger. Both airframes test them on alternate frames,
each its own parity - flat out an airframe overlaps even the 4 px chain for 7 (a bunker shelled to 0 hp is nobody's
and balloonless but still capturable - the man who takes it restores it); a manned super bunker also fires
along the ground at units of any other side outside its box; the base fires homing missiles
(`MUNI_MISSILE`) inside 320 px, from a launcher on its tower that shows the reload - a missile
on the rails when ready, empty for the `BASE_RATE` countdown after a shot (tiles 236/238, drawn
inline in `struct_draw` behind the bunker test, since the stress movie sits on the budget line
and even a per-building compare cost it frames); the bank's gun falls silent after two shells and an enemy
infantryman at the player's bank - or a paratrooper landing in its doorway - halves the purse. Per-unit scans (capture, claim, entry, robbery)
run on a stagger of one structure per frame in sixteen - a man covers eight pixels in that time.
`tools/struct_art.py` stamps the building sprites onto rows 6-13 of `obj.bmp` - but the home base,
which `tools/base_art.py` stamps from a ComfyUI render (a hangar, its control tower and a flagged
tower; the launcher on the roof between them, `BASE_LAUNCHER_DX`/`_DY`), fitted to the sheet's
palette with the greens as the owner's colour and two extra entries (12, 13) of its own; the airframe's
own sheet is drawn by `tools/heli_art.py`, and both write their 4-bit BMP through
`tools/bmp4.py`, since PIL only writes 8-bit and `bmp2chr -b4` refuses that.

Explosions and smoke (`src/fx.r65`) are hindstrike's particles (`game_particles.asm`): one
16x16 sprite stepping along a row of `fx.bmp` a frame every 6 ticks, retired at the row's end,
smoke rising a pixel every other tick. `tools/fx_art.py` copies the three rows out of
hindstrike's `gfx/sprites1.bmp` with its own 16 colours (OBJ palette 5, CGRAM 208); the sheet
loads straight after `heli`'s in the second name block, so its attribute carries `HELI_PAGE`.
A bomb on the ground is a big blast; a lost airframe and a falling turret or bunker a big one
with a smoke ring after it (`fx_burst`); a destroyed tank, van or launcher a small one with
smoke; a man killed, `FX_MAN` - not hindstrike's: `obj.bmp`'s man down held one 120-tick frame
in his side's palette and facing (`fx_man`), each slot carrying its own tile and attribute
(`fx_attr`); a round of gunfire into the dirt, `FX_HIT` (`fx_hit`, from `muni_update`) -
`obj.bmp`'s two 8x8 impact tiles at 224, a spark then its dust, 4 ticks each - the one
effect `fx_draw` sizes small (art by
`tools/muni_art.py`, which also draws the round, a 3x3 cross at tile 12). Eight slots, taken in
turn but passing over a running one, so only a ninth replaces anything (strafing puts up an
impact every few frames, and strictly in turn they cut a man down's two seconds short); an explosion's flip is
from the frame count, never `rand()`. `main` calls `fx_update`/`fx_draw` only while `fx_live` is set - called
idle every frame they cost `unit_budget` ten ticks.

The match (`src/game.r65`) ends two ways only: a van of either side inside the other's base
(`struct_base_van`, scanned every 32 frames - a van is in the window ~75 frames) or the
player's last helicopter (`Player::lost`). Any other loss runs in three steps (`Player::dead_tick`):
the camera stays on the wreck (`airframes[HELI].wreck_x`) while it falls, and for `HELI_GROUND_PAUSE` (a
second) after it goes up on the ground - from the loss itself, when that was on the ground -
then `camera_pan` brings the view home in `HELI_PAN` (72) frames at a pace sized as it starts
(`camera_x / 72 + 1`, so the far end of the world arrives inside it). `airframes[HELI].dead`
counts the pan, and is non-zero throughout. The wreck
falls out of it under gravity (`HELI_GRAVITY`), spinning through the crashing frame and the turn's
drawings (`WRECK_SPIN_TILE`, a turn's 3 frames each), keeping half the airframe's way on
(`Airframe::half`) the whole way down - straight down instead when the two airframes went into
each other (`Airframe::collided`) - and goes up where it hits: a second big explosion, and it is
gone (`Airframe::wreck_start`/`wreck_tick`/`wreck_draw`, drawing only - the loss is counted at
once; `wreck_up` says one is falling). One lost on the ground leaves no wreck. The enemy's is the
same code on `airframes[FOE]`, ticked by `Pilot::update` whether or not its next airframe is up
(a row with no `regen_time` puts it up at once), in its palette. Nothing draws the crashed frame
(`HELI_TILE_CRASHED`, tile 44) now. Both sides' falls and `Player::lost`/`Pilot::lost` are in
bank 3. The last airframe of either side leaves no wreck: the field freezes
as it stands. The next
airframe then rises out of the ground at the start, a pixel a frame from the ground line to
hover height, drawn at OBJ priority 2 behind the dirt until it has cleared it (the ground's
tilemap carries the tile priority bit for exactly this - see the Makefile). The stick, gun and hit test
are off until it is up. **A dry tank is a slow forced descent**: the vertical speed goes to a
steady `HELI_SINK` (0.5 px/frame - a dive or a climb is arrested within a second; from hover about
two seconds down) whatever the stick says, while left and right still fly it - the player's; the
enemy's way on just bleeds off. Touching down on its own deck saves it (it lands and the deck refuels
it - each side's deck only: the other side's is open ground, no refuel, no repair), and open ground is the loss: the pilot and the men aboard
get out at once, and the airframe sits there `HELI_DRY_FUSE` (60) frames (`Airframe::fuse`,
landed, nothing picked up, no lift-off) before it goes up. They become infantry
(`para_disembark`): already down in the para pool, a convoy space apart behind the airframe
(`PARA_OUT_GAP`, `unit_spawn`'s spacing) so each goes onto the field at once - all at the one spot
they stood in a heap and went one a walk-clear apart - and they take no `rand()`. The enemy's do so
only on the campaign's rows (`cpu_paras`), as its drops, so a test mission's battle stays put. And a touchdown flat out
on both axes, at `HELI_VY_MAX` down and
`HELI_VX_MAX` either way, is a crash, deck or not (`Airframe::crashes`, the enemy airframe's rule too).
Anything slower lands: the descent rate takes ~88 px of dive to build, so from hover height every
descent lands, and a crash has to start from above y 80 with Down and a direction held. `game_state` gates the whole simulation; the draw
still runs so the field freezes on screen, `hud_message` puts VICTORY/DEFEAT on map row 10
from a letter row (`HUD_LETTER_ROW`, stamped by `tools/hud_glyphs.py` below the visible
screen like the glyph strip), and Start calls `game_reset`, which re-runs every `*_init`.
In battle Start pauses (`GAME_PAUSED`, `game_pause`/`game_pause_tick`): no tick, the screen
fading to brightness 7 a step every `PAUSE_FADE` (2) frames and PAUSED on the same row; Start
again fades it back up, still paused - so the fade costs a battle frame nothing - and carries on
at 15. `frames_loop` runs on while paused (only the
simulation reads it) and resume puts it back, so a pause does not re-deal the battle - keep it
that way: anything new keyed off `frames_loop` must be simulation, not draw.
`hud_message` takes a `far *u8`: its strings live in the caller's bank, and a near pointer
read them through the wrong data bank.
The van end cannot be scripted in useful time; plant one with the debugger
(`set` the tag/owner/x planes of a slot at the enemy base and step a few dozen frames).

**The frame is now the binding constraint.** With the field full and every structure ticking, the
stress movie (eight tanks bought at once against the CPU's column) runs at 0.96 ticks per
vblank, pinned by `unit_budget` - with **FastROM** (`#[snesrom(..., fastrom)]`, main.r65): the
compiler runs code from the $80-$BF mirror, 6 master clocks a ROM byte rather than 8, which took
it from 0.81. Anything new that runs per unit or per frame has to be measured
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
Rows 10-12 are the **test missions** (`MISSION_TEST_QUIET`, `_HUNTER`, `_CONVOY`): the
hand-made pre-campaign field with frozen tuning, reachable only by a test writing `boot_pick`,
and the whole suite runs on them - see `tests/conftest.py`'s header. Treat their rows, their convoys and their layout as part of the
tests.

**The power-on intro** (`src/intro.r65`, bank 2) is hindstrike's `screen_bubblezap`: the
BubbleZap logo in Mode 7, spinning in from far away, flashing white, settling to 1:1, a shine
sweeping across it, then a fade - 640 frames, Start skipping to the fade. It runs from
`boot_load` while the sound driver uploads - `spc_upload_step`, 128 bytes a frame, the 56K up by
~frame 440; what a skip leaves goes up after - and before `video_load` (its map and 8bpp tiles fill VRAM's
first 16K words; `clear_vram` follows), only on a power-on into the campaign proper. The art is
`assets/src/bubblezap.tilemap.bmp` - the logo's strip of the 1024x1024 plane, a blank column first
so tile 0 is blank - converted `-m7` (bank 4). Two changes from the original: no DSP-1 here, so
the rotation (sixteenths of a turn only) is a 16-entry sine table times the scale on the PPU's
Mode 7 multiplier in vblank; and the fades are colour math (COLDATA's intensity added, capped at
white), not stepping 192 colours a frame, which overran the frame by half.

**The front end** (`src/screen.r65`, phase 11, bank 2) is three pages - title, briefing,
after-action - and they are all one mechanism: BG3 written as a full 32x28 page of text with
`TM` naming BG3 alone, so the field behind is not hidden but simply not drawn, keeping its
state and its registers. A page costs one 1792-byte DMA of the map in force blank when it goes
up and nothing per frame; coming back restores the map from ROM and re-runs `hud_init` and
`radar_init`, the page having written over the rows they own. **The title is the exception: Mode
3**, a 256-colour picture on BG1 (`assets/src/title.tilemap.bmp`, 8bpp, `-b8` in the Makefile)
with the menu on BG2 in the same console font widened to 4bpp at load - Mode 3 has no BG3. The
picture's tiles fill VRAM $0000-$6FFF (896, a whole screen's, so any picture fits; BG1's map at
$7000 under BG2's never-named first 96 tiles, BG2's map at $7C00), so `title_load` loads over the
field's VRAM and CGRAM and switches HDMA off (it would shear the picture), and leaving the title for
any page runs `video_restore` - the boot's uploads again, Mode 1's registers and the HDMA - before
the next page goes up. The font's two colours are entries 34 and 35 of the picture's palette (BG2
palette 2, CGRAM 32-47, is BG1's too), and its map entries carry the priority bit, without which a
BG2 tile draws behind all of BG1 in Mode 3; the code cursor is the font's caret, the HUD's box
pieces being BG3's. `tools/title_art.py` paints the picture from a ComfyUI render
(`pixelArtDiffusionXL_pixelWorld`, render, prompt and seed in its docstring): scaled to 256x224,
the ROTOR RAIDERS logo lettered over the sky, a darkened panel under the menu rows (keep it on
`SCREEN_CODE_ROW`..`SCREEN_TITLE_PROMPT`), one palette with those two entries fixed. The bitmap
in git was edited by hand after that - no panel, its palette reordered and off the PPU's 5-bit
steps (bmp2chr cuts each component), so the menu draws in whatever 34 and 35 now are - and
re-running the tool would lose the edit; the title's tests compare at 5 bits. Its tiles are
up to 56K, more than a LoROM bank, so the Makefile cuts `title.chr` at 32K into banks 7 and 8
(`TITLE_CHR_1`/`_2`), as the sound driver is; `title_load` lives in bank 8 beside them, which is
also what makes the ROM 512K - R65 sizes the ROM from the banks holding code or tables, and
`include_bytes!` data alone does not count. `GAME_SCREEN` is a game state
like the two battle-over ones, so `main` runs neither the tick nor the draw while one shows.
**Progress between missions is a typed code, not a save file** (`code_*`): four letters
carrying eleven bits of payload - four of mission, seven of purse - and five of check,
scrambled and cut into nibbles, each a letter A..P, so 1000 of the 65536 spellings mean
anything and a mistyped one is rejected rather than silently starting the wrong mission. The
title opens on a menu, NEW GAME then ENTER CODE (`title_mode`/`title_sel`; Up/Down pick, Start
or A takes it, and the menu comes back each time the title goes up); ENTER CODE swaps the
same rows for the code field, where the d-pad types it (a held direction repeats), the line under
it says live what the code reads as - the mission it opens, or INVALID CODE - and Start takes
the code, the code's purse displacing the row's `start_funds`, or does nothing on an invalid
one; B goes back to the menu. The after-action page settles the mission and spells the code for the next
run, leaving it typed in so continuing is one press: **a won mission carries its purse plus
what survived it** (`campaign_salvage` - a ground unit at what order.r65 charged for it, a held
building at the design's value, the base 20), a lost one is fought again with the purse its row
deals. The airframes deliberately do *not* convert: the original pays 20 a surviving
helicopter, which against a two-digit purse saturates the carry on any win at all. Start on
that page goes straight to the next mission's briefing, or to the end page once the tenth is
taken. Typing redraws only the five rows the
field occupies, DMA'd from the page shadow in vblank (`screen_flush`); everything else about a
page is composed once. The text goes through the stdlib console (`lib/console.r65`, buffer mode
into the page shadow, its area the inside of the frame) in the stdlib's default font, DMA'd at
boot to BG3 tile 96 (past the art and the radar) on BG3 sub-palette 2 - only ASCII 32-95, the
capitals and the code cursor's `^`, 64 tiles, since nothing prints lowercase - by DMA, not
`Console::upload_font`, whose register-at-a-time loop costs a frame of boot and shifts every
suite movie. The border and code cursor are still the HUD's box pieces. **The front
end is the campaign's**: a test mission boots straight into its battle and its Start
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
whole pause. `fund_min`/`fund_max` are the player's purse at which its airframe raids the bank
(see the pilot below; not a reserve - the original has none). The convoy drains through `cpu_tick`'s emitter under the same
gate rules as the player's orders. Its purchase sequence from a cold boot is fixed by
`cpu_seed` and the airframe's flight - but *only* by those: the pilot draws the same
`cpu_rand`, so how often it has tossed a coin before the first purchase decides what the purse
can reach, and any change to `foe.r65` re-deals the whole army. That is what `cpu_forced` is
for: a test mission names the convoy to buy (the tier gate does not apply to a forced pick,
the purse still does), so the dozen cases calibrated to a column stay put.

**The two airframes are one `#[soa]` pool**, `airframes: [Airframe; 2]` (`src/heli.r65`):
element `HELI` (0) the player's, `FOE` (1) the enemy's. What both have - position, speed,
facing, turn, ammo, fuel, hp, the landed/dead/rising flags, lives, the wreck - is an `Airframe`
field, and what both do the same way is an `impl Airframe` method taking the element as `self`
in X: `init`, `fly`, `burn`, `turn_step`, `rearm`, `draw`, the wreck's start/tick/draw, and
`crashes`. What only the player's has is the one-element pool `player: Player` (on a deck, men
aboard, the pan home), with its routines as associated functions in `impl Player`
(`Player::update`, `fire`, `collide`, `lost`, ...); the enemy's pilot is `pilot: Pilot` and
`impl Pilot` (`src/foe.r65`). Associated functions, not methods: there is one of each, and a
receiver would pin X, which their loops want. **The per-frame methods are
`#[inline(always)]`**, and every call names its element with a constant
(`airframes[HELI].fly()`), so the inlined body's `airframes__f,X` folds to the absolute
`airframes__f` (R65's `optimize/const_index.py`): one copy of the code compiles to what two
hand-written per-side copies did, with no call left - the stress run got 21 ticks a minute
faster for it. Not inlined, an index method reloads X at every switch between a u8 and a u16
field and builds a stack frame: the shared draw alone cost 14 ticks that way. Keep a new
per-frame `Airframe` method `#[inline(always)]`, and call it on `HELI` or `FOE`, not a variable.
The pilot's decisions (`Pilot::think`, `choose` and the target pickers, every 8 frames) are in
bank 3 to keep room in bank 0, with a bank-3 copy of `unit_apart` (`Pilot::apart`).

**The enemy airframe** is `airframes[FOE]` with the player's physics, loadout, fuel, pad and
loss rules - the same methods. It starts hovering at the far edge, facing the player. It is lost to a bomb outright, to 20 points
of gunfire or two missiles, to a balloon not its own (or a chain, with 18 hp or less left), to contact with the player's airframe (both go), and to
flying into the player's ground (`unit_ram`, either airframe's rule);
the next one comes after the row's `regen_time`, rising out of the ground at the far edge, and
the last one is the player's win.

**The pilot** (`Pilot::think`, every 8 frames; `Pilot::fire` every frame) is an adaptation of Armor
Alley's `Helicopter-AI.js` - its priority list, not its steering-force model. In order: **refit**
(fuel under 10 plus a unit per 256 px of the trip home, or two of gun < 6 / no bombs / hp < 5 -
one on the first two rows) → the pad; **dodge** the nearest opposing round within 192 px and
two heights - a round from the ground gets the jink (`foe_jink`, four heights every 16 frames),
one from the air a step over or under, and the spot flown to stays what it was; **hunt** the
player's airframe when `pilot.hunt` and it is within 512 px and not landed - a standoff off it,
level, for the gun, or two heights above it for a bomb once the gun is dry - or when it sits on
its own deck (`pilot.deck`: any `CPU_KILL_COPTER` row with bombs aboard, mood or not), from hover
height over it, bombs whatever the gun holds; **bomb** the nearest
player unit the row's `kill_*` flags allow within 512 px (from a hover over it), then the
nearest player turret or bunker on a **pass** - `FOE_PASS` (192 px) beyond it, since a bomb
from a hover falls straight down the turret's own stream of rounds; a turret only with hp ≥
`FOE_HP_PASS` (16), a pass costing about ten - released when the bomb's landing spot (centre
plus vx × the fall, `mul16` on the height) is over the target, one bomb per target, three per
tank, any number per turret, 40 frames apart; else **wander** toward the player's end on the
weave (`foe_weave`, four heights every 64 frames), turning at `FOE_WEST` (900, short of the
base's missiles) and 128 px from the far edge. `FOE_WEST` bounds every mode but the bank raid, not just the
wander: `Pilot::think` clamps the chosen spot to it (a hunt that follows the player home stops
at the edge), and the bomb pickers skip a unit west of it or a building whose pass would end
west of it. After every decision `Pilot::over_balloons` holds it at `FOE_OVER_Y` (48) or higher
within `FOE_BALLOON_X` (512) of a balloon not its own - the chain under it rules out going
beneath, and at 320 px the gap between two bunkers let it sink into the next chain - and every
frame `Pilot::evade` overrides the
height only: a round from the ground gets the jink (`foe_jink`, four heights every 16 frames,
asking full vertical speed - on the player's thrust and drag, like every other move: the two
airframes carry the same inertia on both axes), one from the air a step over or under, and the
player's airframe about to overlap gets a climb or dive out of its plane (`Pilot::avoid_due`: within a
standoff, or closing - both airframes' speed, the pilot's own not counted in a hunt - fast enough to
cover the gap in 16 frames, a shift of the speed). It is deliberately imperfect: it looks every
fourth frame, and one encounter in four it is blind for `FOE_BLIND` frames, chosen from the frame
count rather than `cpu_rand` so the purchases stay put; a head-on charge gets through about one
time in sixteen. The gun fires at
the player's airframe within 320 px, more than a width off, within 1.5 heights and faced. Modes
as the original's: every ~34 s `pilot.attack` (7 in 8) and `pilot.hunt` (attack and
`kill_copter`); a point of gunfire with the player's airframe in view tosses a coin, at most
once a second, to start hunting. **Paratroopers**, the original's (campaign missions only,
`cpu_paras` - the test missions' battles would re-deal): five aboard each airframe, no pickup;
on a decision (`Pilot::maybe_drop`) over a bunker or the super bunker not its side's, or coming
up on a player turret from the east within 64 px, it drops one - all of them on the super bunker
or under half its health or bombs - unless its own men in view are already heading there; one
drop per 30 s, the men 12 frames apart, their chutes failing on the frame count rather than
`rand()` (the player's sequence) or `cpu_rand` (the purchases). With men aboard and a drop
allowed it flies to the nearest bunker or super bunker in view that is not its own
(`Pilot::para_target`, the `FOE_PARA` mode, after refit, dodge and hunt, before bombing) and
hovers over it - over the balloon, if the bunker is the player's - until they go: not the original's, whose steering leaves
buildings alone, but carrying men is for that. **The bank raid** (`FOE_RAID`, campaign missions
only) is the original's maybeTakeOutEndBunker: with men aboard, in its 1-in-4 steal window
(`pilot.steal`, rolled with the mode roll on the frame count, not `cpu_rand`), and the player's
purse over `fund_min` on a `CPU_ROB_BANK` row (the last three missions, the original's easy
`killEndB`) or over `fund_max` on any - the original's `fund_max` never fires on its own - and a
purse paying for the distance (each unit 64 px: `Pilot::raid_wanted`), it flies first after
refit, through the base's missiles (`think` lifts `FOE_WEST` for it), to the player's bank, and
within 16 px puts every man out. At hover height, but over each balloon not its own on the way,
as `over_balloons` holds it. A man who lands in a bank's
doorway robs it as he touches down (`struct_bank_rob_at`, from `para_update`), so a raid works
with the enemy's units at their cap: the raid's drop (`pilot.robbing`, set as it begins and
cleared when its men are out) skips `para_drop`'s room check. One who lands short of the door
waits for room on the field, then walks in and robs it again. The raider usually goes down to the
missiles on the way out.
Not adapted: clouds, the kamikaze run, and the
smart missile with its counter-measures (slice (d), built and then taken out of the game). Both decks now repair (`HELI_HP_REPAIR`, a point
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
(`src/muni.r65`). **The airframes' gun is its own**: rounds at `GUN_SPEED` (16 px/frame, the
buildings' `BULLET_SPEED` is 8) living `GUN_LIFE` (20 frames, the same ~320 px), at most
`GUN_ROUNDS` (3) of one airframe's in the air - the trigger waits on `muni_gun_rounds`, which
tells them from a building's by that speed - and nose down at `HELI_GUN_DROP` (5 px/frame,
~17 degrees). A round that fast steps over a man (8 px), so `unit_collide` also tests it half a
step back (`muni_mid`). One kind homes: `MUNI_MISSILE`, the buildings' and the launchers'
anti-air missile, which steers at the other side's airframe and does 10 of its 20 points.
**Neither airframe carries a missile**: the smart missile (Y, `MUNI_SMART`, kind 6) was built
and then removed - Y does nothing in battle, kind 6 is unused, and bit 0x40 of the CPU rows'
flags (the original's `useMissile`) is now `CPU_ROB_BANK`, the bank raid's. OAM order follows the plan's importance rule: the helicopter takes slots 0-1
and munitions in flight take the slots straight after, with anything outside the visible 256 px
culled rather than parked off-screen.

The HUD is BG3 rows 0-1 at the top and row 27 at the bottom. Row 0 (`src/hud.r65`: `$` purse,
lives, men aboard) and row 27 (the airframe: H and F meters, the gun's rounds and the bombs, each
behind its icon - over the dirt, the last visible row in 224-line mode, where nothing else is
drawn) are composed into one 64-word shadow and DMA'd in vblank, 64 bytes each, when a shown
value changes; row 2, navy in the art, is cleared once at boot. **These two status rows have a
sheet of their own**, `status.tilemap.bmp` (`tools/status_art.py`, after
`assets/reference/hud.png`): a bold font in two tones with a drop shadow - the labels gold, the
digits white - the icons, and the meters, all transparent around the ink so the rows float over
the sky and the dirt with no strip behind them. **It uses BG3's tile palettes**: the bitmap is
8-bit, its pixels CGRAM indices, and bmp2chr names each tile's sub-palette from them (5 gold,
6 red, 7 white, sharing one dark for the shadow, the meters' rim and their empty part), so the
palette rides in the map words `hud_stat` reads back. A meter is six cells and each cell is its
own row of the sheet in its own palette - red, red/orange dithered, orange, orange/yellow,
yellow, white - which is the gradient: three colours a cell, six steps across. Its tiles go up
past the order menu's icons (the Makefile offsets its map from there and stops the build past
BG3's 256 tiles). Everything else on BG3 - the alert box, the order menu, the battle-over line -
draws from the HUD art: its glyphs (digits, `$`, six unit icons on **map row 28
of `hud.tilemap.bmp`**, capitals on 29, the dialog's box/cursor pieces on 30 - all below the
224 visible scanlines; the strip's old brackets and bar cells there are unused now) are read back
out of `HUD_MAP` at runtime by position, so bmp2chr's de-duplicated IDs never appear in code. The
glyph *order* is the contract; `tools/hud_glyphs.py` stamps them and is the place to edit them.

Row 1 is the radar (`src/radar.r65`): 32 tiles past the art's (`RADAR_TILE = HUD_CHR_SIZE/16`)
mapped in order, so the row is a 256x8 bitmap - 32 world px per pixel - drawn into a 512-byte
2bpp shadow and DMA'd to the HUD's tileset every 16th frame, in its own BG sub-palette (CGRAM 4-7:
navy, blue, red - written at boot by `radar_palette`) so a side reads by colour: blue the
player's, red the enemy's (no white: 2bpp is three colours and transparent). Vehicles only - men are not shown. Buildings are ticks in a base image
rebuilt when `struct_set_owner` flags it (MVN-copied into the shadow each redraw); units and
the airframe are plotted over it, and the camera window is an 8x8 sprite (`radar_draw`, OBJ
tile 31, the slot after the airframe's) so it follows the camera every frame. An enemy van jams it wherever the airframe
is: from the westmost enemy van's tile to the east end the redraw is blank navy (`radar_blank`), so
the edge follows the van. It costs ~2.5% of a frame on average; `unit_budget`'s
pinned figure dropped more than that because that movie sits on the budget line and a frame
over it by a hair drops whole.

**Alerts** (`src/alert.r65`, bank 2) are the avatar pop-in design.md planned: an event calls
`alert_push(code)`, and the queue (four deep; a code already showing or queued, or anything
pushed while the battle is not on, is dropped) plays out one at a time - the portrait, four
16x16 sprites of `avatar.bmp` (OBJ palette 6, after `fx` in the second name block; programmer
art from `tools/avatar_art.py`), slides in at x 224, y 184; a box in the HUD's box pieces
goes up beside it on BG3 rows 23-26 (cols 10-27, under the units' band, over the dirt; cols
28-31 stay transparent or they would hide the portrait), and the code's two lines type out in the
HUD capitals a letter every 2 frames, the mouth working; it holds 120 frames (48 with another
waiting), the next types into the same box, and the last clears it and slides out. A code is two
indexes into `alert_lines`, so captures and losses (`alert_owner`, from `struct_set_owner`: kind
times who took it from whom - a base never changes hands mid-battle, so there is no "base taken")
share their halves. The pushes: `struct_set_owner`; both bank robberies (`alert_robbed`); a van
starting to jam the radar (`radar_jammed`, `radar_update`); fuel crossing 25 and 10, hp 5 and the
last airframe (in `hud_update`'s existing change branches); an order short of funds or over its
cap (`order_place`); the CPU buying its first convoy (`cpu_buy`, once a battle: `cpu_told`); its paratroopers (`Pilot::maybe_drop`)
and its bank raid (`Pilot::choose`); an engineer boarding (`para_refit`). **Idle it costs nothing** - one byte test in `hud_update`
(`alert_busy`, which ticks the queue) and one in `main`'s draw (`alert_up`) - measured with every
push suppressed, the stress run did not move; while one is up the portrait and the tick cost it
11 ticks a minute, when every convoy was announced and kept one up a quarter of that run. `alert_draw` claims
its four OAM slots through `oam_next` itself, so it lives in bank 2 rather than calling bank 0's
near `oam_take`, and it draws straight after the radar bracket (slot 2 is pinned). The tick is
the battle's, in `hud_update`, so an alert freezes with a pause or the match's end, and nothing
the simulation reads is touched: a push never re-deals a battle. `hud_init` calls `alert_init`,
so a reset or a page coming down clears it.

The airlift (`src/para.r65`): a powered descent lands anywhere on the ground (`airframes[HELI].landed`;
`player.on_pad` says whether it rearms), and a player infantryman or engineer within 5 px of a
landed airframe's middle boards it (five at most, and they count against the infantry cap). An
engineer, as Armor Alley's, cannot take his equipment aboard - he is one more man, dropped as an
infantryman - but uses it on the way in: half the hull, an eighth of the tank, a bomb and half the
rounds, each capped at a full load (`para_refit`, with the ENGINEER ABOARD alert). Landed, X puts a
man out onto the ground at the airframe's right edge - ahead of it, so he marches away rather than
back through the pickup window - straight onto the field through `unit_spawn`, whose spacing
refuses it while one of ours is within a convoy space of the spot (he stays aboard). In the air, X
drops one as a paratrooper from an 8-slot pool both sides drop into - units have no y; when it is full, or the side has no
room left for him on the field (`para_drop` returns 0), the man stays aboard. The men on their way
down count against `UNIT_SIDE_MAX` (`unit_side_held`, which `unit_spawn` adds to the side's
count): a man who landed with no room used to stand where he landed, unhittable, until something
of his side died. Sixteen slots cost the frame enough to move `test_drop`. A man sinks at 0.75 px/frame under a canopy
cell drawn over the standing man's, or at 3 px/frame with none when the chute fails (one in ten,
`rand()`'s only consumer, so the sequence from a cold boot is fixed), and becomes an infantryman
the frame the unit pool has room. An airframe lost a third of its flight band up or higher
(`HELI_Y_BAIL`) with men aboard drops one of them first; the rest go with it. Draw order: after the munitions.

Controls: on the title, Up/Down and Start (or A) pick NEW GAME or ENTER CODE; in the code
field the d-pad types the continue code, Start takes it and B goes back to the menu;
Start goes on from the briefing and the after-action page. In the battle, hold L for the order
menu - Up/Down move the highlight, wrapping, A buys - and the d-pad
and A do not reach the airframe while L is down; B gun, A bomb, X drop (or, landed, step out), Up lifts off a deck;
Start pauses and resumes; Y is unassigned. **Start acts on release, everywhere**: `pad_read_ports`
reports it in the trigger mask as it comes up (`PAD_PREV` holds the pad with Start's bit
inverted, so that costs one EOR), and the intro's skip reads the trigger too.
The menu (`hud_overlay`) is a column of six 32x32 icons, one per order in ring order, down the
left edge of BG3: map rows 2-25, four apiece, columns 1-4. The selected icon is on a brighter
panel (BG3 sub-palette 4, the rest 3: CGRAM 12-19), with its name and cost beside it on its top
row. The icons are BG3 tiles, 2bpp, from `icons.tilemap.bmp`, de-duplicated by the build, and
uploaded at boot past the front end's font (`ICON_TILE0`, 160; 44 tiles, the status rows' 32
after them, 20 of BG3's 256 left).
`tools/icon_art.py` derives them from the units' own sprites in two tones.
The menu is composed once at init into a 24-row shadow and a transparent twin, both `#[ram]`
(composing it on the press cost a frame). Showing and hiding flush all of it. A move rewrites the
two icons and the labels and flushes only the rows from the old icon to the new. Rows 23-25 are the
alert box's too, from column 10, so there both sides write only their own columns: the menu its
first ten, `alert_flush` its box, a row per DMA and only the rows that changed. The labels sit on
an icon's top row, so the last one's is row 22, clear of the box. The names come from the letter
row. `game_over` and the pause hide the menu before writing their line on row 10. A purchase
that goes through flashes its icon (`hud_ov_bought`, from `order_input`): unselected and selected
by turns, `MENU_BLINK` (2) frames each for `MENU_FLASH` (16), unselected first, ending lit; the
label stays put. A move or letting go of L ends it; a refused order does not flash.

Funds (`src/order.r65`) accumulate `airframes[HELI].x_px >> 4` per frame against `ECON_THRESH`; that
threshold is the pace knob. Orders go
through an eight-deep queue that lets the next man out once the last has cleared the gate by a
convoy space (`unit_spawn`'s spacing test), holding him when the pool is full rather than dropping him. Caps count men on the field plus men queued, and
infantry and engineers share one cap.

The screen is laid out on the reference shot `assets/reference/chopper.png`: sky to row 134,
the mountains 135-178, sitting on the dirt from `GND_TOP` (179). **`GROUND_Y` (184) is
the unit plane, not the dirt's top**: everything stands, lands and explodes 5 px into the
dirt, so a unit or building overlaps its edge. Every flight height below the ceiling is
measured from the ground (hover 112, the foe's weave and jink, the balloons at 72), so moving
`GROUND_Y` means moving those with it; the ceiling `HELI_Y_MIN` (16) belongs to the HUD.

The ground parallax is 8 HDMA bands of 5 scanlines from `GND_TOP`, the last one's scroll
holding under the HUD's bottom row. `gnd_table_build` computes
`d = camera_x >> GND_SHIFT` once then accumulates - one shift, seven adds, no multiplies.
`GND_SHIFT` is the depth knob; raising it narrows the spread and shrinks band seams.

## Sound

`src/sound.r65` (bank 3) drives Shiru's **SNES GSS** sound driver, ported from the 65816 side
of `~/hindstrike` (`sneslib.asm`/`sneslib.h`), whose sound `assets/sound` is: `spc700.bin` is the
SPC700 driver with every instrument and effect built in, `music_N.bin` one tune each, and
`hindstrike.gsm` the GSS project they were exported from (`sounds.asm` lists the names, ported by
hand into `SFX_*`/`MUS_*` - re-export and re-port them together).

- `spc_init()` uploads the driver through the SPC700's boot loader (IPL), 56K a byte at a time,
  ~156 frames (the IPL
  handshake, not the CPU loop, is the limit). The IPL waits as long as it is left between bytes,
  so the upload is in pieces (`spc_upload_begin`, `spc_upload_step(n)`, `spc_upload_finish`):
  on a power-on into the campaign it goes up under the intro, a slice a frame, rather than on a
  black screen first; a test boot, which skips the intro, sends it in one go. A LoROM
  bank is 32K, so the Makefile cuts `spc700.bin` into `build/sound/spc700_{1,2}.bin` for banks 5
  and 6, uploaded as two loads with `SCMD_LOAD` between, as hindstrike does.
- `sfx_play(chn, sfx, vol, pan)` - an effect on a driver channel (0-7), volume 0-127, pan 0-255
  (128 centre, heard only after `spc_stereo(1)`); queued, see below. Music takes the low channels
  its tune needs, so effects belong on the free high ones (hindstrike: menus on 7).
- `music_play(MUS_*)` uploads a tune (0.4-3.6K, several frames - a screen change, not
  mid-battle) and starts it; `music_stop`, `music_pause(1|0)`, `sound_stop_all`,
  `spc_global_volume(vol, speed)`, `spc_channel_volume(mask, vol)`.
- Every call waits on the driver's acknowledgement in an APU port, so a dead driver hangs where
  it is called - at boot, before `main`, which every test would see. The emulator cannot dump
  sound RAM, so that handshake is the check that the driver runs.
- Not ported: hindstrike's BRR streaming (`spc_stream_*`, channels 6-7), which it never uses.

What plays: the title page starts `MUS_OPERATION_HINDSTRIKE` (`screen_show`, through
`music_start`, which does not reload a tune already playing), carrying on into the briefing;
`screen_hide`, back to the battle, stops it. In battle, `sfx_at(chn, sfx, x)` plays an effect for
something at world x - silent off screen, panned by screen position (`spc_stereo(1)` at boot) -
one kind a channel (`SFX_CHN_*`), so gunfire cannot cut an explosion short: the player's gun
(`SFX_PLAYER_GUN1`), the enemy airframe's and the turrets' (`SFX_ENEMY_GUN`), tank shells
(`SFX_ENEMY_CANNON`), a bomb going off or a vehicle destroyed (`SFX_EXPLODE_1`), a lost
airframe of either side or a turret or bunker falling (`SFX_EXPLODE_2`), a missile launched by a base or a truck (`sfx_missile`: `SFX_PLAYER_MISSILE`
or `SFX_ENEMY_MISSILE` by its side), the missile alarm (`SFX_MISSILE_WARNING`, centred, every 32
frames while a missile homes on the player's airframe - `muni_update`, on the loss channel as
`SFX_CHN_WARN`, so a hit cuts it), an alert's chime (`SFX_MESSAGE`, centred, on the launch
channel as `SFX_CHN_MSG` - launches are the rarest sound), and the player's **rotor** - `SFX_HELI_1..4` restarted in turn
every 4 frames on channel 7 while the airframe is up (`sfx_rotor`, from `Player::update`; 19 in the
air, 11 idling on a deck - a fifth of where it started, which ran over everything - jittered by 1
from the frame count, never `rand()`). Its four effects are pitched down a fourth, B-4 to F#4, by
`tools/sfx_transpose.py SEMITONES SFX...`: the GSS tool has no command-line export, so the tool
moves the notes in both `spc700.bin` (the compiled effect streams) and `hindstrike.gsm` (their
song rows), and a re-export from GSS keeps the change.

**Effects are queued, not sent.** hindstrike's `sfx_play` waits for the driver to acknowledge the
command (250-360 CPU cycles); a rotor every 4 frames on top of the guns pushed busy frames past
vblank, and a dropped tick re-deals the simulation (it turned `test_the_hot_pilot_hunts_the_player`'s
dogfight). Here `sfx_play` fills its channel's slot (`sfx_want`/`sfx_vol`/`sfx_pan`, a bit in
`sfx_mask`; a newer effect on the channel replaces it) and `sound_flush` - called from `main` before
the tick and before the draw, only when `sfx_mask` is set - sends one per call, round robin, if the
driver reads idle, and does not wait: the driver takes a command in microseconds and clears its
own command latch (`setReady` in `snesgss/snes/spc700.asm`), so nothing is replayed. Checked by a
probe in the ROM: a send is echoed after 7 polls and done 12 later. Music and the other commands
still go through the waiting `spc_command`, at screen changes only. The rotor costs the
`unit_budget` stress run 21 ticks a minute (it writes its slot directly, skipping two far calls)
and is pinned there. Test missions have no front end, so no tune is uploaded under the suite.

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

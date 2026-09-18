# Rotor Raiders - AI Assistant Guide

A helicopter tug-of-war for the SNES, descended from *Rescue Raiders* (Apple II, 1984)
by way of *Armor Alley* (1991). Built with the R65 compiler. For the full R65 language
reference, see the main CLAUDE.md in the R65 repository.

The design and phase plan live at `~/.claude/plans/going-to-make-a-jolly-pudding.md`.

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
make assets   # Convert assets/src/*.bmp to SNES CHR + palettes
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
Combine with `+`, e.g. `up+a30`. Built by `tools/mkmovie.py`.

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

Trust VRAM/OAM dumps (`--dump`) over screenshots when debugging graphics. Measure performance
in scanlines via the V-counter, not Mesen's "Cycles:" counter, which is blind to memory speed.

## Project Structure

```
rotor_raiders/
├── src/
│   ├── main.r65              # Entry, boot_load, NMI handler, game loop, snapshot_point
│   ├── input.r65             # Joypad: pad_read_ports / pad_poll / pad_poll_trigger
│   ├── video.r65             # Mode 0 layers, HDMA ground parallax, camera
│   ├── unit.r65              # Ground-unit pool, march, traffic control, tank fire
│   ├── order.r65             # Funds, the L/R order ring, the order queue
│   ├── hud.r65               # BG1 strip: purse, ring, cost
│   ├── assets.r65            # GENERATED by `make assets` - do not edit
│   └── lib/                  # Standard libraries
│       ├── 65816.r65         # CPU register definitions
│       ├── sneslib.r65       # SNES hardware registers and helpers
│       └── math.r65          # Math functions (mul8, div8, etc.)
├── assets/
│   ├── src/                  # Source art (indexed BMP - bmp2chr takes BMP, not PNG)
│   ├── gfx/                  # Generated .chr / .pal
│   ├── sound/                # snesgss exports (spc700.bin, music_*.bin)
│   └── levels/               # Battlefield placement lists
├── tools/                    # mkmovie.py, pngstat.py, asset generators
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
| OBJ | helicopter and, later, every unit | camera-relative | $4000 (4bpp) |

Shared 2bpp tileset at $0000. Mode 0 gives each layer its own 32-colour CGRAM block
(BG1 0-31, BG2 32-63, BG3 64-95, BG4 96-127); sprites get 128-255.

All art is indexed BMP in `assets/src`, converted by `r65x bmp2chr` via `make assets`, which
also regenerates `src/assets.r65`. Nothing generates graphics from code. **bg2/3/4 are stored
folded** - 32 tiles wide by 64 tall, right-hand screen below the left - because a 64x32 SNES
tilemap is two 32x32 screens and bmp2chr emits row-major at bitmap width. Each BG layer has its
own de-duplicated tileset and its own CGRAM block; only sub-palette 0 (4 colours) is used.

Sprites are 4bpp with OBSEL small=8x8 / large=16x16, so a unit is 16x16 and a munition 8x8.
The 544-byte OAM shadow lives in lowram and is DMA'd by `oam_flush` in vblank; it sets the
channel registers directly because `#:` resolves the wrong bank for WRAM symbols.

Ground units (`src/unit.r65`) are a 16-slot pool. **16 is a measured limit, not a guess**: at 32
the frame loop ran at 0.45 ticks per vblank. `frames_nmi` vs `frames_loop` is the frame-budget
probe - the V-counter cannot be used because latching it needs a discarded read of $2137 and the
compiler eliminates unused hardware reads. Traffic control is O(n^2) and re-evaluates 4 units a
frame; collision rejects a munition against the whole pool with one scanline-band test.

A unit is three declarations. **Unit** is a `#[soa]` struct holding what every unit has -
position, hp, owner, lane, block, rank - plus its `kind`, so `units[i].hp` is one
`LDA units__hp,X`. **UnitType** is that `kind`: a tagged enum contributing a tag plane that
doubles as the free marker (`Free` is variant 0) and a payload plane for what only one kind
carries - `Tank(Tank)` holds the gun reload that used to be a pool-wide `unit_timer[16]` four
kinds never touched; `Van`, `Launcher` and `Infantry` have nothing of their own and are plain
variants. **UnitStat**
is what is fixed about a kind: `unit_stats` is a `#[soa]` immutable static, one ROM table per
column with one entry per variant in tag order. Three rules come out of it:

- **Read a kind's constants straight out of the table by tag**:
  `unit_stats[units[i].kind as u16].speed`. The cast is the bare tag-plane read and each
  column is its own table, so a read is one `LDA.l unit_stats__speed_data,X` with the index
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
against the 32 / 34 hardware limits.

Munitions are 8x8 sprites from a 16-slot struct-of-arrays pool with a rotating free cursor
(`src/muni.r65`). OAM order follows the plan's importance rule: the helicopter takes slots 0-1
and munitions in flight take the slots straight after, with anything outside the visible 256 px
culled rather than parked off-screen.

The HUD is BG1 row 0, composed into a 32-word shadow and DMA'd in vblank when it changes.
Its glyphs (digits, `$`, brackets, six unit icons) sit on **map row 28 of `bg1.bmp`** - below
the 224 visible scanlines - and `hud_glyph(n)` reads tile *n* of that row back out of
`BG1_MAP` at runtime, so bmp2chr's de-duplicated IDs never appear in code. The glyph
*order* is the contract; `tools/hud_glyphs.py` stamps them and is the place to edit them.

Funds (`src/order.r65`) accumulate `heli_x_px >> 4` per frame against `ECON_THRESH`; that
threshold is the pace knob and `econ_income` in the suite pins its current value. Orders go
through an eight-deep queue that lets one man out every ten frames, holding at the gate when
the pool is full rather than dropping him. Caps count men on the field plus men queued, and
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

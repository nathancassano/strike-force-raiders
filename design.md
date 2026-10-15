# Rotor Raiders — SNES Design & Implementation Plan

## Context

`rotor_raiders/` was created from `r65x init --platform snes` and currently holds only the
template: `src/main.r65` is 34 lines (`init_reset` → `snes_init()` → an empty `wait_nmi!()`
loop) plus stock `lib/` copies of `65816.r65`, `sneslib.r65`, `math.r65`. It builds to a valid
256 KB LoROM (`build/ROTOR_RAIDERS.smc`, 99.84% free) that boots to a black screen.

The goal is a SNES game descended from **Rescue Raiders** (Apple II, 1984) by way of
**Armor Alley** (1991). Scott Schiller's open-source browser remake
(https://github.com/scottschiller/ArmorAlley) is the mechanics reference — it ports the
original 1991 AI tuning tables verbatim, which makes it a usable spec rather than just an
homage.

The genre is an action/RTS hybrid: a wide side-view battlefield, friendly base at one end,
enemy base at the other. The player flies the only directly-controlled unit. Both sides spend
accumulating funds on autonomous ground units that march toward the opposing base. You cannot
steer ground units — only clear their path, bomb the opposing column, and airlift infantry past
the front line.

## Locked decisions

| Question | Decision | Consequence |
|---|---|---|
| Fidelity | **SNES-native redesign** | Armor Alley is ancestor, not spec. Roster, economy, and scale designed for controller play and 65816 budgets. |
| Ordering UI | **Shoulder-button quick order** | L/R cycle the unit type in the HUD; a face button orders. No pause, no mode switch. |
| Scope | **Full campaign** | 10 missions, escalating difficulty. Needs a mission table, progression, SRAM persistence, and a front-end. |
| Art | **Original pixel art, AA-styled** | Fresh sprites drawn to SNES limits. The remake's ISC-licensed art is *proportional reference only* — not shipped. |
| Sprite scale | **Readable, 32-screen world** | Helicopter ~32 px, tank ~24 px on a 256 px screen; world 8192 px (raised from 4096 in phase 6 - see Shape of a match). |
| Sound | **snesgss** (`/home/nathan/R65/snesgss/`) | SPC700 driver + tracker. The R65 binding already exists — see Sound below. |

---

# Part 1 — Game design

## Shape of a match

A single horizontal lane, no vertical scroll. Left to right from the player's side:
**bank → base → landing pad → open field → enemy landing pad → enemy base → enemy bank.**

| Property | Armor Alley | Rotor Raiders | Rationale |
|---|---|---|---|
| World width | 8192 px | **8192 px** (32 screens) | Matches the original exactly. Decided in phase 6, overriding the earlier 4096. Our sprites are smaller, so this is a *larger* field in helicopter-lengths (~256 vs AA's ~164) and a traverse takes ~27 s against AA's ~11 s. Sets the radar scale at 32 world px per HUD px. |
| World height | 380 px | **200 px play + 24 px HUD** | Fits one 224-line screen. No vertical scroll — this is why the game suits the SNES. |
| Traverse time | ~11 s | **~27 s** at 5 px/frame | Follows from matching the original width at smaller sprite sizes. |
| Camera | Centered, leads by velocity | Same + deadzone | AA's `halfWidth * 0.4 * (vX/vXMax)` lookahead, taken as `vx / 8` - 40 px at top speed - plus kungfu's 8 px deadzone so a turn pans rather than snaps. *Decided: the lookahead is in; `Player::update` sets `focus_x`.* |
| Match timer | None | None | Matches end on a win condition only. |

## Sprite sizes

Sized natively for SNES rather than scaled from the originals. AA's 1× dimensions are listed
only to preserve proportion.

| Entity | AA 1× | Rotor Raiders | Notes |
|---|---|---|---|
| Helicopter | 50×16 | **32×16** | 4 flight frames + 3 turn frames, each direction |
| Tank | 58×19 | **24×16** | 3 frames |
| Van | 38×16 | **24×16** | 3 frames |
| Missile launcher | 54×18/frame | **24×16** | 4 frames |
| Infantry | 11×11 | **8×16** | 5-frame walk |
| Parachute infantry | 14×20 | **8×24** | 5 frames |
| Turret | 18×16/frame | **16×16** | 4 frames |
| Bunker | 53×26 | **32×24** | Sprite (2× 32×32 cells) |
| Super bunker | 66×28 | **40×24** | Sprite (2× 32×32) |
| Base | 102×25 | **64×32** | Sprite (4× 32×32) |
| Landing pad | 81×7 | **48×8** | Sprite (3× 16×16) |
| Balloon | 38×16 | **16×16** | + 8×8 chain segments |
| Munitions | 13×5 / 15×4 | **8×8** | bomb, missile, gunfire |

Palette: the original game's entire art set is 13 colors, ≤10 per sprite. Sprites are 4bpp in
every BG mode, so budget **one 16-color sprite palette for units** and a second for structures.
BG art is 4bpp in Mode 1 — 15 colors plus transparent per tile — except the HUD's 2bpp. See
Graphics architecture.

## Win and loss — keep exactly

Two terminal conditions, no others:

1. **A Van reaches the enemy base** → that base is destroyed → its owner loses. The base is
   **immune to all conventional weapons**; a 2-fund unarmed van is the only way to win.
2. **A side runs out of helicopters.** Start with 4; more cost 20 funds.

This is the identity of the game — it is what makes it a tug-of-war rather than a shooter, and
it is why killing enemy vans is non-negotiable defense.

## Unit roster

Costs are the 1984/1991 values, unchanged across both games — strong evidence of good tuning.
**Inventory limits are cut roughly in half** for the sprite-per-scanline reason below.

| Unit | Cost | Per order | HP | Limit (AA) | Role |
|---|---|---|---|---|---|
| Van | 2 | 1 | 12 | **6** (10) | Unarmed. Win condition. Jams enemy radar by proximity. |
| Missile Launcher | 3 | 1 | 8 | **4** (6) | AA only. Self-destructs on firing. |
| Tank | 4 | 1 | 25 | **8** (15) | Main line. Only unit that can damage super/end bunkers. |
| Infantry | 5 | 5 men | 5 ea | **16** (30) | Captures bunkers, mans super bunkers, robs the bank. |
| Engineer | 5 | 2 men | 5 ea | shared 16 | Repairs and claims turrets only. |
| Helicopter | 20 | 1 | 20 | — | Extra life. |

**Damage asymmetries — preserve these, they are what make composition matter:**
- Infantry gunfire cannot hurt tanks at all, and **a tank that touches the other side's men
  kills them** - it does not stop for them. *Decided:* infantry fire at opposing ground units
  and turrets (the 0.5 below), never at helicopters. A man's shot is instant - no round, a
  one-frame firing pose - 64 px reach, one shot per 48 frames, 2 damage.
- Helicopter gunfire cannot hurt end/super bunkers — only tanks can.
- Tank fire does 8 damage to turrets; helicopter/infantry fire does 0.5. **Tanks are the
  anti-turret tool.** (In code the turret scale is doubled - hp 62, shell 16, gunfire 1 - so
  the half point is an integer.)
- A single bomb kills a helicopter outright.
- Bombs do nothing to infantry until they hit the ground.
- Bombs can be shot down by gunfire.

**Engineer trim:** in the original, engineers only repair AA guns. Bunker repair, bank robbery,
and turret *claiming* are all remake additions behind toggleable prefs. Keep turret
repair/claim; drop the rest.

## Economy

Every frame, add the helicopter's distance from your own end of the map to an accumulator. When
it crosses a threshold, gain **1 fund** and subtract the threshold. Deeper into enemy territory
= faster income. On 65816 this is a 24-bit add and a compare per frame.

Start with **32 funds**. Drop AA's wealth-penalty shift (`funds/20 + chopperCount`) as needless
complexity — scale the threshold by difficulty tier instead. *Decided:* the enemy earns the
same way, from its own helicopter's distance into the player's half.

## Ordering — the order overlay

The 6 unit types sit in a fixed ring. **Holding L shows the order overlay** over the field;
while it is held the **d-pad moves the highlight** between unit types and **A buys** the
highlighted one; releasing L hides it. The battle keeps running underneath - the d-pad steers
the overlay, not the airframe, for as long as L is down. *Decided after phase 9, replacing L/R
cycling with X to buy (X is now the paratroop drop).* Cost deducted immediately; insufficient funds = order ignored with a click. Units
emerge from the base in sequence, each waiting for the last to clear the gate by a convoy
space — a "convoy" is emergent from queuing several in a row. *(Was 10 frames apart; at a
man's pace that put five in a heap.)*

## Helicopter

- Max speed **5 px/frame** horizontal, ~4 vertical, 8.8 fixed point.
- **No gravity while powered.** Gravity applies only at zero fuel. **No ejection** - the pilot
  goes with the airframe.
- **Zero fuel is a crash landing**: the dead-stick descent ends on ground contact with the
  airframe lost, a life gone. So is **touching down flat out on both axes** - the top descent
  rate and the top horizontal speed (`Airframe::crashes`) - deck or not; anything slower lands.
- Tilt is cosmetic, derived from vX — not simulated. Damage shake below ~70% health.
- Ammo: **64 rounds, 10 bombs, up to 5 men.** No smart missiles: they were built (phase 10,
  slice (d)) and then removed from the game, for both airframes.
- Reload while landed: +8 gun/20f, +1 bomb/10f. Ammo is the real bottleneck
  (~21 s from empty) — that gating is deliberate, keep it.
- **Men are not restored by the pad** — you pick them up off the ground: a friendly infantryman
  **within 5 px of a landed airframe's middle** boards it, five aboard at most. **X drops them as
  paratroopers** (parachute sprite, the ~10 % failure below), one per press; a man who lands
  walks on as ordered infantry would.
- **Losing an airframe**: the wreck falls and goes up, the view holds a second on it and then pans
  home inside 72 frames, and the next
  airframe **rises out of the ground** at the start with a full load.
- **Ramming** (the remake's rule, either airframe): flown into the other side's tank, van or
  launcher, or a standing bunker not its own, the airframe is lost and takes it with it; into the
  super bunker unless its own, it is lost and the bunker stands (only a tank hurts it). Men are
  not hit - the airlift lands among them - and turrets, banks and bases are flown through.
  Heights are the art's: an airframe's top 14 rows, a vehicle 13 tall, a roof at 160
  (`unit_ram`).
- AA's mouse-seeking control becomes d-pad acceleration toward a target velocity.

### Controller map

| Button | Action |
|---|---|
| D-pad | Fly (Up also lifts off a deck) |
| B | Gun (held) |
| A | Bomb (per press) |
| Y | — (unassigned; was the smart missile, removed) |
| X | Drop a paratrooper (per press) |
| L (held) | Order overlay: d-pad highlights a unit type, A buys |
| R | *(free)* |
| Start | Pause / resume in battle (dims the screen); start / reset after a battle |
| Select | Test-harness snapshot hook (debug) |

## Structures

| Structure | HP | Rules |
|---|---|---|
| Bunker | 69 | Captured by **infantry** on contact (not engineers). Moors a barrage balloon on a chain. Tank shells bring it down; at 0 hp it is nobody's and balloonless, but **still capturable** - the man who takes it brings it back. |
| Super Bunker | 5 | **HP literally = infantry inside.** Cannot be destroyed — at 0 it goes *hostile-neutral*. Its gun fires on **all opposing units** — helicopters and ground units of any other side — faster the more men it holds. *Decided:* an empty one fires on helicopters only, or nobody could ever walk in and man it; a manned one fires on the ground too, so it is taken by shelling the garrison out with tanks first. Only tank fire damages it. Units inside its box are immune to its fire (ground rounds leave from the wall facing the target). |
| Turret | 62 (AA's 31, doubled) | 340 px scan, self-repairs unless fully destroyed. Fire rate is **the difficulty dial**: 15/12/6/2/1 frames across tiers — a 12× swing. *Decided:* the rate is **capped at 6 frames** - the two hottest tiers would need more rounds than the 16-slot shared munition pool holds; difficulty above that comes from the other dials. |
| Landing Pad | — | Land only while descending. Full rearm. *Decided with the airlift:* a powered descent **lands anywhere** on the ground (that is how men are picked up in the field); only a deck rearms, and a dead stick on open ground is the crash above. |
| Base | — | Fires smart missiles at helicopters within 320 px every 2 frames — a genuine no-fly zone. Immune to everything but a van. |
| End Bunker (bank) | 10 | Holds your funds. Two tank hits silence its guns. Enemy infantry steals 50%. |

## Campaign — data-driven, 10 missions

The backbone is AA's own tuning data, which is already ROM-shaped.

**Per-mission AI capability table.** The CPU starts with almost nothing enabled and unlocks
capabilities across the campaign — on mission 1 literally only `killTank` is set; by mission 10
everything is on and CPU helicopter respawn is instant. As SNES data this is **~2 bytes of
bitflags + ~5 scalars per mission**:

| Field | Range | Meaning |
|---|---|---|
| `vanJamming` | 255→4095 | Radar jam radius |
| `clipSpeed` | 8→14 | CPU helicopter velocity cap |
| `fundMin`/`fundMax` | 99/200 → 40/100 | CPU spend thresholds |
| `convoyLevel` | 1→10 | Which convoy patterns the CPU may build |
| `regenTime` | 48→0 frames | CPU helicopter respawn delay |
| flags | — | `dumbMissiles`, `napalm`, `flameThrower`, `buildTruck`, `buildEngineers`, `useMissile`, `useMen`, `killCopter`, `killVan`, `killTank`, `killMen`, `killMissile`, `killEnd`, `suicide`, `stealth`, `jamming`, `scatterBomb` |

**Convoy build-order table.** The CPU's entire economy is a list of strings gated by tier —
`M`=launcher, `I`=infantry, `E`=engineer, `T`=tank, `V`=van:

```
tier 0:  V, M, T, I, E
tier 3:  TI, TT, IV
tier 5:  MIIM, TTMI, TEV, IMEV, MIVV, TMV
tier 7:  TMIVIM, TTVEVEMM, MIVVTMMI
tier 9:  TVVV, TMMMMM, TTTTEEEM, TVEMIVTV
tier 10: MTIMTMIME, TEEMIVVTMM, TTTMMMIIETM, TMTMIMTMIEV
```

Selection: filter to convoys affordable at current funds, pick at random, deduct. Substitute
`M→I` if `buildTruck` is off, `E→I` if `buildEngineers` is off or the map has no turrets.
**This is a complete RTS opponent in ~300 bytes of ROM** — no pathfinding, no planner.

**CPU helicopter AI:** do *not* port the remake's steering-behavior force-vector model — that's
a modern rewrite, not the 1991 AI. Write a priority state machine: seek pad (fuel < 30 or
ammo < 6) > attack enemy helicopter > bomb tanks > attack bunkers > patrol. Use vote counters
rather than instant transitions to avoid twitchy flip-flopping.

*Decided after phase 9:* the enemy helicopter **exists** - which mission it first appears in is
TBD. It brings with it: the player's gun, bombs and missiles against it (a bomb kills it
outright), helicopter-vs-helicopter contact, the player's base and bank firing at it, its use
of the enemy pad for fuel and ammo, and enemy lives as a second way to **win**. The state
machine's exact priorities and thresholds, and which of the AI flags below are in scope, are
*deferred* until phase 10 starts.

**Tier mapping** *(decided)*: mission *n* (1-10) uses convoy tier *n* and turret tier *n/2*;
the economy threshold scales with the same turret tier. One row per mission holds all of it.

**Mission names** (original, in order): Cake Walk, One-Gun, Sucker Punch, Airborne, Two-Gun,
Super Bunker, Scrapyard, Blind Spot, Wasteland, Midnight Oasis.

**Between missions:** surviving equipment converts to starting funds (helicopter 20, van 15,
end bunker 20, tank 5, bunker 4, turret 3, infantry 2, launcher 2). *Revised in slice (d):*
that list is on the original's money scale, not ours - `ECON_MAX` is 99 and the continue code
carries seven bits, and four surviving airframes alone are 80, so any win at all saturated the
carry. The airframes now do not convert (the next mission deals its row's lives anyway) and a
ground unit converts at what it cost to buy; the buildings keep the values above. ~~Persist to SRAM.~~
*Decided: no SRAM.* Progress is a **continue code** shown after each mission and typed in from
the title screen; it encodes the mission index and the carried funds.

**Front end** *(decided)*: title → mission briefing (name and a line) → battle → after-action
(the conversion above) → the continue code → next mission.

## HUD *(decided after phase 9)*

The strip is 16 lines - two tile rows of 32 on BG1 - and the order ring leaves it for the
L overlay; the airframe's own gauges are on a third row along the bottom of the screen
*(moved there in phase 10)*:

| Row | Contents |
|---|---|
| 0 | `$` purse · lives · men aboard |
| 27 (bottom) | health bar · fuel bar · gun / bombs counts |
| 1 | **the radar**: 256 px = the whole 8192 px world at 32 world px per pixel, **pixel-plotted into a row of 2bpp tiles** redrawn from a shadow each frame it changes. Friendly and enemy dots, buildings as ticks; a jammed span reads as static. *Amended:* a jammed span is blank, from the jamming van's tile to the east end; *Amended:* the camera window is the one OAM sprite on the row, so it tracks the camera every frame without a redraw; vehicles only, no men; blue ours, red theirs. |

Plus an **avatar pop-in at the bottom right** of the screen: a character portrait that slides in
to deliver briefings and in-battle warnings (van approaching, bank robbed, low fuel).
*Amended:* built for the battle only (`alert.r65`), not the briefings: a 32x32 portrait slides
in and a two-line message types out in a box beside it on BG3 rows 23-26, one alert at a time
from a four-deep queue - buildings changing hands, either bank robbed, a van jamming the radar,
fuel low and critical, heavy damage, the last airframe, an order refused, and the opponent's
convoys, paratroopers and bank raid.

## Original quirks worth keeping

- **Parachutes fail ~10% of the time** and the man splats. Present in both 1984 and 1991.
- **Barrage balloons kill helicopters on contact**. ~~A *detached* chain is neutral and
  dangerous to both sides.~~ *Dropped after phase 9: the balloon is shot down and regrows; the
  chain never detaches.*
- **Landing next to friendly infantry picks them up** (max 5, within 5 px of the airframe's middle).
  This is the "rescue" the title descends from, and the reason to airlift men to forward bunkers
  rather than walk them across.
- ~~**Enemy infantry touching your landed helicopter destroys it.**~~ *Dropped after phase 9:
  no effect.*
- **Ground unit traffic control** — units stop rather than pile up (look-ahead ≈ ⅓ unit width).
  A remake addition, but it's what makes a convoy read as a convoy. *Decided:* only a tank
  parks to shell a building; everything else in the column keeps advancing past it. A column
  that walks past the far base goes on to the world edge and is freed there - the van end
  fires before that needs defining. *Decided in phase 10:* **every unit marches at the one
  speed** (half a pixel a frame) and collision is a front-line affair - a follower only ever
  halts behind a halted unit of its own side, and only the lead of a column looks at the other
  side. With per-kind speeds any column with a man near its front crawled at his pace.

---

# Part 2 — Technical plan

## Graphics architecture

**Mode 1 throughout — two 4bpp BG layers and a 2bpp one, no mode switching.** The ground
parallax comes from per-scanline HDMA on a BG's horizontal scroll register, not Mode 7.
(Phases 1-12 ran in Mode 0, four 2bpp layers; Mode 1 traded the fourth layer for 15 colours a
tile, and the clouds and mountains now share one.)

| Layer | Contents | Scroll |
|---|---|---|
| BG1 (4bpp) | Dirt, rows 179-223 (units stand at 184) | **Per-scanline HDMA** — see below |
| BG2 (4bpp) | Clouds (rows 16-91) and distant mountains (135-178) | HDMA split at line 104: clouds `camera_x >> 5` above (the farthest layer), mountains `>> 3` below |
| BG3 (2bpp) | HUD / radar strip, order dialog, front-end pages | Fixed; over everything by `BGMODE`'s BG3 bit and the tiles' priority bit (the battle-over line borrows row 10) |

Sky is the backdrop colour (CGRAM 0), optionally graded with an HDMA on `COLDATA`.

**All BG layers are repeating.** Every layer's tilemap is a 512 px (64×32-tile) pattern that
wraps in hardware, so scrolling is one register write per layer per frame and **no column refill
is needed anywhere**. This is the single most important property of this architecture — it is
what keeps the riskiest part of the original plan out of the project.

### The ground parallax

The bottom third sits *in front of* the play plane: below the ground line the terrain scrolls
progressively **faster** than the world, selling foreground depth toward the viewer.

Naïvely this is one H-offset per scanline — ~75 multiplies per frame, which the 65816 cannot
afford. Instead use **8 HDMA bands** of 9 scanlines each, and build them by accumulation:

```
d = camera_x >> GND_SHIFT      // one shift
band[0] = camera_x
band[k] = band[k-1] + d        // seven adds
```

One shift and seven adds for the whole table — no multiplies, and the ramp is uniform.
`GND_SHIFT` is the single tuning knob: 5 gives 1.000×…1.219×, 3 gives 1.000×…1.875×.

**Implemented and measured** (phase 2): `src/video.r65`, `gnd_table_build`. Verified on
hardware timing at `camera_x = 948` — eight bands of exactly 9 scanlines stepping 29 px
(`948>>5`), with BG2 at `cx>>2` = 237 and BG3 at `cx>>3` = 118.

Eight values, rebuilt into a `#[lowram]` HDMA table each frame, one HDMA channel to feed
the ground's H-offset (`BG4HOFS` in Mode 0, `BG1HOFS` now). Reversing the ramp (slower toward a horizon instead of faster toward the viewer) is
a one-table change if it reads better in motion.

**Band seams are the risk here.** The texture-space discontinuity between adjacent bands is
exactly `d = camera_x >> GND_SHIFT`, so at `camera_x = 3840` and SHIFT 5 the step is 120 px.
Two levers: raise `GND_SHIFT` to narrow the spread, and draw a ground texture that is
horizontally near-uniform — dither, stripes, scattered noise — so a seam has nothing
structured to break. If seams still read at SHIFT 5, subdivide to 16 bands of 4–5 lines
(8 more adds, 16 more table bytes).

**Register trap, cost an hour in phase 2:** BG4HOFS is **$2113**. `$210F` is BG2HOFS. Setting
`BBAD` to `0x0F` silently drives the wrong layer per-scanline and looks like "HDMA isn't
working". (In Mode 1 the ground is BG1, `$210D`, and `$210F` is the sky's split.)

### Everything on the ground is a sprite

Units, buildings, and terrain decoration are **sprites**, not BG tiles. This is now a choice
rather than a hardware constraint, and the reason is the repeating-layer property above:
buildings sit at unique world positions, so putting them in a tilemap would reintroduce unique
BG content and therefore column refill — plus the ground layer shears per scanline under HDMA
and cannot host anything that must stay rectangular.

### Budgets

- **VRAM: comfortable.** Dropping Mode 7 frees the 32 KB it would have taken at `$0000–$7FFF`.
  The 4bpp sky's tileset runs $1000-$2FFF and the rest are a few KB each; the remainder goes
  to sprite CHR, which is exactly where a sprite-only game needs it.
- **HDMA: 2 of 8 channels** — the ground's bands and the sky's split. Well clear of the
  limit, but each costs CPU time on every scanline its table runs, so a table ends as soon as
  it has nothing left to write. (A BG1 vertical-scroll split for the HUD was planned and is not needed: the layer is
  transparent below the strip.)
- **Palettes.** Sprites are 4bpp (16 colours, 8 palettes, CGRAM 128–255) regardless of BG mode:
  one palette for units, one for structures. BG1 and BG2 share eight 16-colour palettes in
  CGRAM 0–127, and BG3's eight 4-colour ones are the first 32 of those: HUD 0–31, ground
  palette 2, clouds 3, mountains 4 (a sheet each, one palette each); 5–7 free.
- **Lint.** HDMA setup writes the same `BBADx` registers that rule C002 forbids; add the HDMA
  helpers to `exclude_subtrees` in `r65-lint.toml` alongside `boot_load`.

**Forced by this layout:** the HUD/radar strip lives at the **top** of the screen, since the
bottom third is the parallax ground.

## The defining constraint: sprites per scanline

**Every ground unit sits on the same ground line, so they all compete for the same scanlines —
and because the bottom third is sprite-only, so does every building.** This is now the single
hardest technical constraint in the project.

Hardware limits per scanline: **32 sprites, 34 8×8 tiles.** Cost of one scanline crossing each
entity, using the largest hardware sprite sizes that fit:

| Entity | OAM entries | Tiles on a crossing scanline |
|---|---|---|
| Tank / van / launcher (24×16) | 2 | 3 |
| Infantry (8×16) | 1 | 1 |
| Helicopter (32×16) | 2 | 4 |
| Turret (16×16) | 1 | 2 |
| Bunker (32×24) | 2 | 4 |
| Base (64×32) | 4 | 8 |

So a mid-field scanline carrying a bunker (4) + a turret (2) + the helicopter (4) has **24 tiles
left — about 8 vehicles.** Eight 24 px vehicles is 192 px, which nearly fills the 256 px
viewport anyway, so the budget is tight but roughly matches what can physically be on screen.
It will still be exceeded when a convoy bunches at the front line under traffic control.

Four mitigations, designed in from the start:

1. **Cull to the camera window.** Simulate all units; assign OAM slots only to those within the
   visible 256 px. This is the big one — it caps *drawn* entities regardless of army size.
2. **OAM slots are assigned by importance, not by pool index.** The SNES drops the sprites it
   evaluates *last*, and evaluation starts at OAM index 0, so slot order is the drop policy.
   Order: helicopter → munitions in flight → buildings → units nearest the camera centre →
   the rest. This is a change from classickong's static `OAM_ENEMY + i` partitioning, which is
   not usable here: the pool index says nothing about what matters this frame.
3. **OAM priority rotation** (OAMADDR bit 15) so overflow *flickers* frame to frame instead of
   silently vanishing. Standard-era technique, and it degrades gracefully.
4. ~~**2–3 shallow ground lanes.** Stagger unit Y by ~8 px. Sprites are 16 px tall so adjacent
   lanes still share ~8 scanlines — this buys perhaps a third, not a half. Worth having, but it
   is not a substitute for 1–3.~~ *Removed after phase 9:* three 4 px lanes bought little and let
   opposing columns in different lanes walk through each other. Everything stands on one line;
   convoy spacing caps a window at eight vehicles (16 sprites / 24 tiles), inside the limits.

**Halved inventory limits** (roster table above) exist for this reason and should not be raised
without re-running the arithmetic.

## Scrolling — simplified by the graphics architecture

**No R65 project scrolls.** Across the entire corpus — including all 8,471 lines of
classickong.r65 — there are exactly two scroll-register writes, both fixed offsets set once at
boot (`pacman/src/game.r65:655-656`). This is still new code, but the all-repeating-layer
architecture makes it much less new than originally planned.

**Column refill is unnecessary.** It exists to stream unique BG content past a camera. Here
there is no unique BG content — every layer is a repeating pattern and everything
mission-specific is a sprite. Scrolling reduces to:

- **Clouds and hills:** both on BG2; a two-entry HDMA table feeds `BG2HOFS` the clouds'
  `camera_x >> 5` at line 0 and the mountains' `>> 3` at line 104, then ends - the register
  holds it - and the hardware wraps the 512 px (64×32-tile) map.
- **Ground band:** rebuild the 8-entry HDMA band table (shift-and-add, no multiplies) and let
  the channel feed `BG1HOFS` per scanline.
- **HUD:** BG3, fixed; nothing scrolls it.

That removes the `VMAIN = 0x81` column-DMA machinery, the `#[lowram]` column buffer, and the
on-demand column synthesis from the project entirely.

**Keep the kungfu camera logic, drop its renderer.** `/home/nathan/kungfu/game_display.h`
`camera_update` (deadzone follow with catch-up speed) and `game.c:201-302` (12.4 camera consts)
are still the model. `background_set_update` / `background_column_update` / `background_preload`
are not needed unless a mission requires unique BG art.

**Mission terrain is a placement list**, not a tilemap — a compact sorted `[type, x]` array
(AA's own level format, ~1–1.6 KB per level) that the sprite renderer walks with a cursor as the
camera advances. A full 8192 px tilemap would have been 25.6 KB per mission, 256 KB for ten.

## Position representation

An 8192 px world does not fit 12.4 fixed point in a `u16` (even 4096×16 overflows). Store
position as **two SoA arrays: `x_px: u16` (0..8191) and `x_sub: u8`**, with velocity as `i16` in
8.8. Add the low byte with carry into the pixel word. The pixel value is then directly usable
for rendering and comparisons with no shifting.

**Decided in phase 3: use the stdlib Q types where they fit.** Velocity is `Q10` (signed 10.6,
±511, 1/64) — signed is the requirement, and a 5 px/frame cap leaves 320 steps of resolution.
Vertical position is a plain `u16` holding 8.8 screen pixels; 0..224 fits its integer byte.
Horizontal position keeps the `x_px`/`x_sub` split above, because **no 16-bit fixed type can hold
an 8192 px world**: `Q8` caps at 255.996 and `Q10` at ±511.

Integration crosses scales: a `Q10` velocity is 1/64 px, a position fraction is 1/256, so the
per-frame delta is `v.0 << 2`. The `mul`/`div` methods (`far fn`, ~70 cy JSL) are never called —
integration is only `+`, `-` and compare, which newtypes inherit from the payload.

**`>>` is a logical shift even on signed types** (`docs/operators.md:438`; arithmetic shift is not
implemented). Adding a negative delta therefore needs an explicit sign branch whenever the value
is wider than one 16-bit word — `Q10::to_int` documents the same trap at `stdlib/Q10.r65:83`. A
single `u16` is exempt: two's-complement wrap makes `y + (d as u16)` correct for either sign.

## Entity model

Struct-of-arrays, following `classickong.r65/src/enemy.r65:39-92`. One pool for ground units,
one for munitions. Parallel `#[ram]` arrays: `type`, `x_px`, `x_sub`, `y`, `hp`, `state`,
`timer`, `owner`. Rotating free cursor (`enemy_add`:296 / `enemy_remove`:391). Dispatch by
if/else-if chain on the type tag; behavior bodies are `far fn(i, spr)`.

classickong uses **zero traits, zero `impl`, zero `dyn`** across 8,471 lines — confirmed by
grep. Match that. Alternate expensive checks by frame parity (collision one frame, AI retarget
the next), as classickong does for player-vs-hammer collision.

## Sound — snesgss

*Decided: snesgss, most likely. The music/SFX channel split and per-mission vs one battle
track are still open.*

`/home/nathan/R65/snesgss/` is Shiru's SNES Game Sound System: SPC700 driver
(`snes/spc700.asm`), 65816-side API (`snes/sneslib.h`), and a tracker (`snesgss.exe`, runs under
wine) with a CLI export mode:

```
snesgss.exe song.gsm -e <export-path>
```

**The R65 binding already exists and ships in a real game.** `/home/nathan/classickong.r65/src/sound.r65`
(349 lines) implements the whole 65816 side against the same `SCMD_*` protocol:

| Function | Purpose |
|---|---|
| `spc_setup()` | Upload driver + sample bank, initialize |
| `spc_load_data(adr, src, size)` | Block upload over APUIO |
| `spc_command(command, param)` | Handshake command send |
| `spc_load_music(data, size)` | Swap in a music module |
| `music_play(mus)` / `music_stop()` / `music_start()` | Playback control |
| `sfx_play(chn, sfx, pan)` | Fire a sound effect on a channel |
| `spc_volume(v)` / `spc_stereo(s)` | Global mixer |

Commands: `SCMD_STEREO/VOLUME/MUSIC_STOP/MUSIC_PLAY/SFX_PLAY/RELOAD` (0x0000–0x5000).

Asset shape, from `classickong.r65/src/data.r65:149-199` — driver + samples in a dedicated bank,
songs as small `include_bytes!` blobs with a matching size const:

```rust
static spc700_data: [u8; 32579] = include_bytes!("../assets/sound/spc700.bin");
static sounds_data:  [u8; 1281] = include_bytes!("../assets/sound/sounds.bin");
static music_title_data: [u8; 535] = include_bytes!("../assets/sound/music_title.bin");
const SPC700_SIZE: u16 = 32579;
```

Lift `sound.r65` essentially verbatim; replace the `SFX_*` constant block with this game's
effects (rotor loop, gun, bomb release, explosion, unit ordered, order denied, funds credit,
radar jamming, parachute, splat, van warning).

**Note:** none of the remake's audio is original-game audio — the 1991 SFX could not be
re-licensed, so it's ~130 freesound.org clips under mixed licenses (some CC BY-NC), plus two
music tracks, one of which is a Kenny Loggins composition. Audio is authored in snesgss
regardless; the remake is not an audio source.

## Art pipeline

**The toolchain is BMP-only, not PNG.** `r65x bmp2chr` (`r65/tools/bmp2chr.py`, CLI at
`r65/cli.py:144`) reads indexed Windows BMP only (`r65/tools/bitmap.py`, `class BitmapIndex`).

```bash
r65x bmp2chr in.bmp -o out.chr -b4 -p -t   # 4bpp + .pal + dedupe/tilemap
```

`-t` de-duplicates 8×8 tiles including flipped variants — right for the battlefield strip.
Budget a PNG→indexed-BMP step in the drawing workflow.

**No existing project has an asset Makefile target** — conversion is manual everywhere. Add a
real one; it's a genuine improvement over every project in the repo.

Start with `pacman/tools/gen_assets.py`-style programmer art (Python draws shapes, emits literal
arrays) for phases 2–7, then migrate to `include_bytes!` + `#[bank(N)]` for real art.

VRAM/CGRAM delivery: `dma_copy_vram` / `dma_copy_cgram` / `dma_copy_oam`
(`sneslib.r65:1717+`) or the cheaper `*_const!` macros (`:1652-1688`). Copy the boot sequence
from `pacman/src/game.r65:641` (`fn boot_load`). Big transfers inside force-blank.

## Reuse map

| Need | Source |
|---|---|
| Sound | `classickong.r65/src/sound.r65` — verbatim, swap the SFX table |
| OAM / sprites | `src/lib/sneslib.r65:1046-1245` (`OamEntry`, `OamBuffer`) — already in the template, in sync with stdlib |
| Input | `astroids/src/input.r65` (~35 lines) — copy, add `wait_autojoy!()` from classickong |
| RNG | `stdlib/rand.r65` — copy into `src/lib/` |
| Per-frame VRAM updates | `pacman/src/game.r65:98` (`queue_vram`, `QLEN`/`QADDR`/`QDATA`) |
| Entity pool | `classickong.r65/src/enemy.r65:39-92`, `:296`, `:391` |
| Game state machine | `pacman/src/game.r65:24-30`, `fn update`:900 |
| Test harness | `pacman/play.sh` + `tools/mkmovie.py` |
| Makefile | `classickong.r65/Makefile` — all three fixes |
| Bank/asset conventions | `classickong.r65/src/data.r65` |

## Bank layout (initial — expect to shuffle)

| Bank | Contents |
|---|---|
| 0 | Core loop, entity update, collision |
| 1 | Sprite CHR + palettes |
| 2 | BG tiles + terrain placement lists |
| 3 | snesgss driver + sample bank (32 KB, needs its own bank) |
| 4 | Mission tables, convoy strings, AI parameter rows |
| 5 | Front-end: title, briefing, after-action |
| 6 | Music/SFX modules |
| 7 | Game code overflow |

classickong's own comments record this as a reactive process ("moved to bank 4 to avoid bank 2
overflow"). **Plan for 512 KB** *(decided)* — the snesgss driver alone is 32 KB and ten
missions of art and data will not fit 256 KB. Nothing to set: the compiler sizes the ROM from
the highest `#[bank(n)]` in use (256 KB minimum), so it becomes 512 KB the day bank 8 is
declared.

## Landmines (documented, will bite immediately)

1. **No initializers on `#[ram]`/`#[lowram]` mutable statics** — open `__init_start` MVN/DBR bug
   hangs the ROM. Declare bare, initialize in a `boot_load()`.
2. **No `continue` inside entity loops** — compiler region-spill bug (`enemy.r65:1029`). Use
   `if`/`else`.
3. **Use `set_full!`, never `set!`,** for anything that can leave the screen — `set!` writes only
   an 8-bit X and leaves a stale high bit, rendering objects 256 px off, *"invisible while still
   lethal"* (`enemy.r65:396`). In a scroller that means **everywhere**.
4. **`*` accepts only power-of-two constants.** `mul8(i,3)` is ~57 cycles vs ~16 for `(i<<1)+i`.
   Pad tables to power-of-two strides.
5. **Stock Makefile has three defects**: depends only on `src/main.r65` and misses every
   `include!`d file; doesn't `cd src &&` before the assembler (breaks `include_bytes!` paths);
   uses a hand-written single-object linkfile instead of the generated `build/main.link` (breaks
   multi-bank). Fix all three first.
6. **Lint config** — add force-blank helpers (`boot_load`, `load_level`) and HDMA setup fns to
   `exclude_subtrees` in `r65-lint.toml` or expect C001/C002 false positives.
7. **Vendored stdlib** — every project copies stdlib into `src/lib/` and they have all drifted
   (kungfu.r65 by 167 lines). Ours is currently **in sync**; decide whether to keep it that way
   before copying code from an older project.

---

# Part 3 — Implementation phases

Each phase ends in a ROM verifiable on Mesen before the next begins.

1. ~~**Harness first.**~~ **DONE.** Makefile fixes, `snapshot_point()`, `play.sh`,
   `tools/mkmovie.py`, `tools/pngstat.py`, `tests/run.sh`, lint target, `rand.r65`, `input.r65`.
   *Verified: `make verify` is green.*
2. ~~**Scrolling battlefield.**~~ **DONE.** Mode 0 four-layer setup with hardware wrap, the
   8-band HDMA ground parallax, and a window camera. Placeholder instrumented art.
   *Verified: `tests/run.sh` cases `cam_*` assert camera_x at five input lengths; `parallax`
   cross-correlates two frames and asserts 8 equal-height bands with a constant non-zero step.*
3. ~~**Helicopter.**~~ **DONE.** 32x16 OBJ sprite over three tilt frames, 8.8 position with
   Q10 velocity, camera follows the airframe centre, `oam_flush` DMAs the shadow buffer each
   vblank. `src/heli.r65`, OBJ setup in `src/video.r65`.
   *Verified: `tests/run.sh` cases `heli_rest`/`heli_right` assert position, `heli_back` proves
   the borrow path in the negative-delta branch, `heli_wall`/`heli_ceil`/`heli_floor` cover all
   four clamps, and `heli_tilt_*` read the frame back out of the OAM shadow. The `cam_*` figures
   were recalibrated - the camera now follows a 5 px/frame airframe, not the 4 px/frame stand-in.*
4. ~~**Weapons and munitions.**~~ **DONE.** 16-slot munition pool (SoA, rotating free cursor,
   power-of-two mask), gunfire and bombs, the plan's 64/10 loadout, facing via OAM hflip with
   the two airframe cells swapped, ground collision against `GROUND_Y`. `src/muni.r65`, weapons
   in `src/heli.r65`. Smart missiles deferred to phase 10's slice (d) - they need targets.
   *Verified: `tests/run.sh` cases `ammo_*` assert the loadout, the 6-frame gun rate, the
   edge-triggered bomb, that firing past empty stops at zero rather than wrapping, and facing;
   `muni_*` walk a bomb from release to ground contact and a round to the end of its range.*
   *Note: gunfire needed a range (`BULLET_LIFE`) that the plan did not specify - without one a
   round flies to the world edge, holding a pool slot for hundreds of frames, and sustained fire
   starves the pool.*
5. ~~**Landing pad and rearm.**~~ **DONE.** Two decks (48x8, three 16x16 cells) at the plan's
   layout positions, "land only while descending", fuel drain at one unit per 64 frames, dead
   stick with gravity at zero, and reload countdowns on the deck. `src/pad.r65`, fuel and rearm
   in `src/heli.r65`.
   *Verified: `pad_land`/`pad_short`/`pad_over` bracket the deck to the pixel, `pad_slide`
   proves an airframe arriving at floor level without descending is refused, `pad_rearm` walks
   fuel and both ammo counts back up, and `fuel_dry` drains the tank over ~6600 frames and
   confirms the airframe sinks to the floor without reading as landed.*
   *Note: the plan says "reload modulus timers"; these are countdowns, since 20 and 10 are not
   powers of two and a real modulus would mean a mod8 call per frame.*

**Art pipeline (changed during phase 5, finished in phase 10).** All graphics are indexed BMP
under `assets/src` - the only art in git - converted by `r65x bmp2chr` from the Makefile;
`tools/gen_assets.py` is gone and `src/assets.r65` is generated by make from whatever the
converter produced. The file name says what a bitmap produces: a `%.tilemap.bmp` is
de-duplicated into a tileset and the map naming its tiles back, a plain `%.bmp` gets the tileset
alone, and there is one multi-target pattern rule for each - make picks between them by which
source exists. Bit depth and bg4's priority-bit patch are target-specific variables, and the ROM
depends on the result, so an edited bitmap rebuilds everything downstream of it. The converted files and the bindings
are build products: ignored by git, removed by `make clean`. **Backgrounds are stored folded**: a
64x32 SNES tilemap is two 32x32 screens one after the other, but bmp2chr walks a bitmap
row-major at its full width, so bg2/3/4 are authored 32 tiles wide and 64 tall with the
right-hand screen *below* the left. Each layer now carries its own de-duplicated tileset (4-5
tiles each) at its own CHR base, and its own 4-colour block of CGRAM.
6. ~~**Ground units.**~~ **DONE.** `src/unit.r65`: pool, base spawn, march, traffic control,
   tank fire and the damage asymmetry table. OAM slots now come from a shared importance-ordered
   allocator in `video.r65` (`oam_begin`/`oam_take`/`oam_end`) instead of static bases, drawn
   airframe -> munitions -> buildings -> units from the camera centre outward, with OAM priority
   rotation enabled.
   *Verified: `tools/oamstat.py` reads a `--dump oam` and reports peak sprites and tiles per
   scanline; at a bunched line it measured 7 sprites / 14 tiles against limits of 32 / 34.
   Traffic-control spacing is what keeps this safe - units queue at width + gap = 32 px, so a
   256 px window holds at most 8 vehicles = 16 entries, plus the airframe and a deck.*

   **The CPU budget, not the sprite budget, was the real constraint.** The plan's mitigations all
   address sprites; nothing addressed frame time. Measured with `frames_nmi`/`frames_loop` (the
   V-counter is unusable - latching it needs a discarded read of $2137 and the compiler
   eliminates unused hardware reads):
   - 32-unit pool, full field: **0.45 ticks/frame**, i.e. 2.2x over budget.
   - Traffic control is O(n^2); re-evaluating a slice of 4 units per frame instead of all of them
     took it to 0.70. A unit's flag is then ~3 frames stale, about 1.5 px at 0.5 px/frame.
   - Sustained gunfire cost another 23% until the collision test was hoisted: every ground unit
     stands in one narrow scanline band, so a round above it is rejected once per munition
     rather than once per unit. 0.77 -> 0.98.
   - **The pool is 16, not 32.** That is the size that holds 1.00 ticks/frame to a full field.
     Raising it means finding the cycles first.

   *`fastrom` once hung this ROM at boot (execution reached the $80-$BF mirror and never the
   game loop). On since 2026-10-11: no surviving source, with the compiler of its day
   or today's, reproduces the hang, and the stress run went from 0.81 to 0.96 ticks a vblank.*
7. ~~**Economy and ordering.**~~ **DONE.** `src/order.r65` and `src/hud.r65`. Funds accumulate
   `heli_x_px >> 4` per frame against a 40000 threshold - one u16, not the 24-bit add the plan
   assumed, with nothing lost; the threshold is the pace knob (mid-field ~3 s a fund, far end
   ~1.5 s, home pad ~21 s). Start 32, cap 99. The ring is the roster order (van, launcher, tank,
   infantry, engineer, helicopter); L/R walk it, **X** buys, cost off at once, a refusal changes
   nothing. Eight-deep order queue, one man out every 10 frames, held at the gate rather than
   dropped when the pool is full. Caps are the halved limits, counted as field + queue; infantry
   and engineers share the 16. A helicopter order is +1 to `heli_lives` (starts 4) for phase 9.
   Engineer is a new `UnitType` on the infantry's stats and art until phase 12. The enemy base
   keeps the placeholder rotation until phase 10.
   *HUD: BG1 row 0 from a 32-word shadow, DMA'd on change. Glyphs are stamped by
   `tools/hud_glyphs.py` onto map row 28 - below the visible 224 lines - and read back out of
   `BG1_MAP` at runtime, so bmp2chr's de-dup'd tile IDs never reach code.*
   *Verified: six new suite cases on the ROM's own state (purse, selection, what left the
   base, the van cap refusing a seventh, the helicopter life, income after a push east).*

   **Measured: a tank line is the heaviest legitimate load.** Eight player tanks against the
   enemy column run at 0.984 ticks/frame (59 dropped in 3665) because each shell in the ground
   band is tested against the whole pool every frame; fifteen infantry against the same column
   hold 1.00. Accepted and pinned by `unit_budget`; the shell/unit test is where the next cycles
   are if it ever matters.
8. ~~**Structures.**~~ **DONE.** `src/struct.r65`: a 16-slot `#[soa]` pool filled from a sorted
   `#[soa]` ROM level table (bank, base, turret, bunker, turret, bunker, turret, super bunker,
   turret, bunker, turret, bunker, turret, base, bank), drawn third in the OAM order as 16x16
   cell grids standing on the ground line. Ownership is an OBJ palette (green / red-brown / grey)
   built at boot from the sheet's one palette; enemy units wear it too. Rules landed: turrets
   sweep 340 px, loft rounds at the helicopter along the line to it, take 1 from gunfire and 16
   from a shell (hp 62 = the plan's 31 doubled), self-repair, fall to nobody at zero and are
   claimed and restored by an engineer standing at them; bunkers (hp 69) are taken by an
   infantryman of another side who is spent doing so, and moor a balloon (3 gunfire hits, regrows
   in ~16 s) on an 8 px chain that kills any helicopter on contact; the super bunker's hp is the
   men inside (0-5), its gun is anti-air and hostile-neutral when empty - and, since the
   design pass after phase 9, fires along the ground at opposing units when manned, sparing
   anything inside its box - a shell kills a man; the
   base fires homing missiles (10 of the airframe's 20 hp) inside 320 px every 45 frames; the
   bank's gun covers 200 px until two shells silence it, and an enemy infantryman at the player's
   bank halves the purse. Helicopter health (20, gunfire 1) is new: at zero a life goes and the
   airframe returns to the start. Verified by seven suite cases, two of them long waits (a man
   walks the field at a quarter pixel a frame).
   *Deferred to later phases: the player's base and bank against enemy helicopters and the
   enemy purse (10), the van at the base (9), rubble art for a dead bunker and a detached chain
   (12). Missile art is the shell's.*

   **The CPU frame is now the binding constraint.** The structures cost ~1.6k of a ~10k
   instruction frame at full load; the stress movie holds 0.968 (pinned). Measured with a
   Mesen-GDB `trace` from the snapshot attributed to functions through the `.sym`. Cut on the way:
   `oam_end` to a high-water mark, the tank sweep to every 16 frames, `unit_fire` called only for
   tanks, `unit_draw` classifying once into near/far lists, precomputed structure geometry, sorted
   early exits. Next cycles: `unit_advance`'s call overhead (the inliner declines it) and the
   traffic scan. A bunched column of eight vehicles already puts 32 tiles on a scanline against 34.
9. ~~**Win conditions.**~~ **DONE.** `src/game.r65`. A van of either side inside the other's
   base destroys it (`struct_base_van`, every 32 frames) and ends the match; the player's
   fourth helicopter lost ends it the other way (`heli_lost`; the enemy has none until phase
   10). `game_state` gates the simulation while the draw keeps running, so the field freezes
   where it stands under a VICTORY / DEFEAT line on BG1 row 10 - capitals stamped on a second
   hidden glyph row and read back from the tilemap like the digits. Start resets by re-running
   every subsystem's init. *Verified: the loss and the reset by suite (five passes into the
   enemy base's missiles); the van end by planting one at the enemy base with the debugger.*
9b. ~~**The airlift.**~~ **DONE.** `src/para.r65`: boarding within 5 px of a landed
   airframe's middle, X drops paratroopers from an 8-slot pool with its own y, one chute in ten
   fails, a landed man is an infantryman again; men aboard count against the cap. With it the
   order controls moved to the overlay scheme - hold L, Left/Right, A - freeing X, and the
   overlay itself is a BG1 dialog under the strip: icon, name and cost per line, a cursor on the
   highlighted one. The canopy is tile 72 on the sheet. *Verified: `airlift_board` (five men aboard off the pad) and
   `airlift_drop` (five drops, the fixed RNG's two failures, three men back on the field).*
9c. ~~**HUD rows and radar.**~~ **DONE.** `src/hud.r65` rows 0-1 as decided (purse, lives,
   health and fuel bars of six glyph cells; rounds, bombs, men aboard - missiles when they
   exist); `src/radar.r65` row 2, a 256x8 bitmap in 32 tiles the game owns past the art's,
   redrawn every 16th frame from a base image of building ticks: vehicle dots by side (blue
   ours, red theirs, in the row's own sub-palette; men are not shown), the airframe, and noise
   when an enemy van is within RADAR_JAM px; the camera window is a sprite over the row, so it
   moves every frame.
   *Verified: `radar_boot`/`radar_flown` byte for byte, the gauges by their white on screen.*
10. **CPU opponent.** Convoy table, AI flag table, helicopter priority state machine.
    *Decided at the start of the phase (2026-09-20):*
    - **Slices, in order:** (a) the enemy purse and the convoy table, replacing the placeholder
      rotation; (b) the enemy airframe - a second helicopter with its own state, the player's
      weapons against it, the player's turrets, base and bank firing at it, its use of the
      enemy pad, enemy lives as the second way to win; (c) the priority state machine that
      flies it; (d) smart missiles for both airframes, the AI's `useMissile` gating its own.
    - **AI capability rows, one per mission:** `convoy_level`, `fund_min`, `fund_max`,
      `clip_speed`, `regen_time` and the flags `build_truck`, `build_engineers`, `kill_copter`,
      `kill_tank`, `kill_van`, `kill_men`, `use_missile`. The rest of AA's table (napalm,
      flame thrower, scatter bomb, stealth, suicide, kill_end, kill_missile, dumb missiles,
      jamming) is out: weapons the roster does not have, or already covered (van jamming).
      Phase 11's `mission_stats` names the row per mission (`cpu_row`), plus a
      test row of its own that allows trucks and engineers but hunts nothing.
    - **The purse.** The enemy earns as the player does, from its airframe's distance into the
      player's half against the same threshold: `(WORLD_W - x) >> 4` a frame. Until slice (b)
      the airframe is a stand-in parked mid-field, so the CPU earns a fund every ~2.6 s.
    - **Spending.** `fund_min` is a reserve: the CPU buys only what leaves that much in the
      purse. Every `CPU_TICK` frames it lists the convoys at or below its `convoy_level` it
      can afford above the reserve, and takes one at random; above `fund_max` it takes the
      dearest instead, so a purse never sits idle. A letter is an order at the ring's price
      and men count (`I` is five men, `E` two), `M` becomes `I` without `build_truck` and `E`
      becomes `I` without `build_engineers`. The convoy drains through the CPU's own queue at
      the player's gate rules - one unit per `ORDER_GAP` frames, held while the gate is busy -
      and a unit at its side's cap when its turn comes is dropped, not refunded.
    - The CPU rolls its own xorshift (`cpu_rand`), not `rand()`, so its choices never move
      the parachute sequence the airlift cases are pinned on.
    - The state machine's priorities and thresholds are settled in slice (c); the plan's order
      stands: seek pad (fuel < 30 or ammo < 6) > attack the player's airframe > bomb tanks >
      attack bunkers > patrol, with vote counters against flip-flopping.

    *Slice (a) DONE.* `src/cpu.r65`: the ten capability rows, the 25 convoys as one `Order`
    run per convoy with an index of offset, tier and price, the purse, the decision every 64
    frames, the queue and its emitter. *Verified:* `cpu_purse` pins the first buy and the
    income; `poolstat.py` shows the fixed sequence IMEV, M, TI.

    **One march speed, collision at the front** *(decided during slice (a))*. The CPU's first
    convoy at the working level is infantry-led, and under the old rules - men at a quarter
    pixel a frame, everything halting for anything ahead - its whole army crawled behind five
    men: 590 px in 2400 frames, a tank 22,000 frames from the player's bunker. Now every unit
    moves a pixel on each odd frame, nothing overtakes, and each side's column is a list in
    march order (`ahead`/`behind` planes, `unit_head`/`unit_tail`): a follower asks one
    question of the unit ahead, only the leads scan the pool for the other side, and the
    base's gate is the spacing test at the insertion point. The stress movie went from 0.822
    to 0.896 ticks a frame, the pixel-on-odd-frames step being most of it (the sub-pixel add
    per unit was 9% of the frame). Twelve suite cases were re-derived against the CPU column
    with `tools/poolstat.py` and `tools/timeline.sh`; `march_order` pins the packing.

    *Slice (b) DONE.* `src/foe.r65`: the enemy airframe on its own statics with the player's
    physics, loadout, fuel, pad and loss rules; two states for now - the pad under 30 fuel,
    otherwise a patrol 96 px ahead of the column's lead at the row's clip speed; lost to a
    bomb, 20 points of gunfire, two missiles, a balloon or contact with the other airframe
    (both go); regen after the row's `regen_time`; four lives, the last the player's win.
    Every gun that shot the player's airframe now shoots the other side's through
    `air_target` - turrets, super bunker, bases, launchers - and missiles home on the airframe
    of the side that did not fire them; the CPU's purse reads the real position; the enemy
    bank's purse is robbed like the player's. *Verified:* `foe_patrol`, `foe_pad`, `foe_gun`,
    `foe_contact`, `foe_turret` (the player's turret takes the first airframe around frame
    14000 and the next one rises). The purse reading the real airframe moved the CPU's
    purchase timing, so the column-dependent cases were re-derived once more.
    *Slice (c) DONE.* The pilot, adapted from the remake's `Helicopter-AI.js` (read in
    full; the original is a per-frame force accumulator over seek/arrive/avoid vectors and
    votes, not a state machine). Kept: the priority order (refit, dodge, hunt, bomb, wander),
    its numbers (fuel 25 → ours 10 + the trip home, ammo 6, hp 5, view 512, gun 320, dodge
    192, edge 128, mode roll every 30 s at 7/8 attack, chase-on-hit coin toss, one bomb per
    target and three per tank), the wander toward the player's end with a vertical weave, the
    x4 weave under turret fire, bombing turrets and bunkers on the way, and gunfire at the
    player's airframe only when level, in reach and faced. Changed for the SNES: decisions
    every 8 frames set one spot for `foe_steer` instead of summed forces; the balloon and
    chain whiskers are a height clamp near balloons; the wander turns at the player's base
    zone rather than the world's edge, since the base's missiles would take a life every
    pass. Dropped: clouds (none here), paratroopers and the bank raid (both added since, foe.r65),
    kamikaze, missile decoys - and the
    purchasing rule in `cpu.r65` was corrected to the original's on the way (no reserve;
    a random affordable convoy after each pause). Found on the way: a bomb's blast never
    reached a building (`unit_collide` spent it first, and the ground line was excluded).
    Settled while tuning: a bombing run on a turret is a pass, not a hover (the turret's
    own stream shoots down what falls through it), begun only with 16 hp (a pass costs ten);
    climbing rounds do not intercept bombs; the decks repair (the refit rule assumes it);
    the wander turns 900 px from the player's end, short of the base's missiles; vertical
    evasion gets four times the thrust, or a charging player collides with it every time;
    `scatter_bomb` (the original's, on from mission 8) gates bombing, so the first rows'
    pilot only wanders and refits - which is what the suite runs against, with R held at
    boot as the stand-in for a mission select (the eighth row) for the cases that need the
    hunt and the bombs. Also: **only one missile truck per side fires at a time**.
    *Slice (d) DONE.* Smart missiles, the plan's Y weapon: two per load, one per 128 frames
    on the deck, locked at launch on the other side's airframe within 640 px or failing that
    the nearest of its vehicles, and an outright kill for either - buildings keep their own
    rules and are passed by. A press with nothing to lock on to is refused rather than spend
    one. The pilot fires its own under `use_missile` while hunting or once down to 8 points
    (the original's retaliation), one every four seconds. *Verified:* `missile_hold`,
    `missile_unit`, `missile_air`, `missile_foe`. **Phase 10 is complete.**
    *Later removed:* the smart missile is out of the game for both airframes - Y does
    nothing, the HUD's `M` counter is gone, and the four cases above gave way to `y_inert`.
    *Open:* the original's CPU helicopter has unlimited lives; ours has four - on the
    first row it survives a match, on the eighth it spends them on the player's turret.
    *Found on the way:* a compiler bug - vreg-move coalescing tested interference against
    liveness left stale by an earlier coalesce in the same sweep, so `let clip = g; let mut
    want = 0; ... want = clip` folded `want` into `clip` and its `= 0` overwrote the clip
    speed (the airframe never moved). Fixed in `slot_allocator.py` with a regression test;
    the same defect was the long-open "let-copy of a mutable local aliases its source".
    And the sprite budget: eight bunched tanks and a bunker on one line were 36 tiles against
    the PPU's 34 with vehicles drawn as two 16x16 cells; the second cell's live half is now
    two 8x8 sprites, three tiles a line as the design table always budgeted (28 on that line).
11. **Campaign.** Mission table, briefing and after-action screens, a typed continue code.
    *Decided at the start of the phase (2026-09-29):*
    - **Slices, in order:** (a) the mission table - one ROM row per mission driving every knob
      that is a constant today, and the layout derived from it; (b) the screens - title,
      briefing, after-action - on a BG1 text page with the field hidden; (c) the continue
      code, encoded after each mission and typed in from the title; (d) the campaign loop
      that strings them together and the equipment-to-funds conversion between missions.
    - **One row per mission** (`mission_stats`, ten of them): the CPU capability row it uses
      (phase 10's `cpu_stats` index, retiring `CPU_LEVEL`/`CPU_LEVEL_HELD` and the R-at-boot
      hack), the turret tier (fire rate and range), the economy threshold, the player's
      starting funds and lives, and the layout parameters below. `mission_set(n)` writes them
      into the constants' new homes; `game_reset` keeps the mission, as `cpu_level` does now.
    - **The battlefield is derived, not transcribed.** The tier decides how many turrets and
      bunkers stand between the bases, how they are spaced, and how many start owned rather
      than neutral; the two banks, two bases and the super bunker are fixed. A layout is
      then ~6 bytes a mission rather than the ~1.5 KB of AA's placement lists, and the
      generator is the one place the difficulty curve lives. The named battlefields (Cake
      Walk ... Midnight Oasis) stay names on the briefing screen until phase 12.
    - **No SRAM.** Progress is the design's continue code: the mission index and the carried
      funds, encoded as letters from the glyph row, shown after each mission and typed in
      from the title. It is testable from a movie, which a save file is not.
    - *Open until slice (b):* how the text page hides the field (blanking BG2-4 and OBJ, or
      a second BG1 map DMA'd over the strip), and whether the briefing borrows the order
      dialog's box or gets its own.
    *Slice (a) DONE.* `src/mission.r65`: `mission_stats`, one row per mission, holding the
    opponent's `cpu_row`, the turret rate and range, the income threshold, the starting purse
    and lives, and the layout's counts; `mission_set` writes them into the live variables the
    constants became (`turret_rate`, `turret_range`, `econ_thresh`, `start_funds`,
    `start_lives`) and lays the field out. `mission_layout` derives it as planned - banks and
    bases fixed, the super bunker dead centre, turrets and bunkers alternating through the
    middle either side of it, `owned` of them starting on a side - and `LAYOUT_MIDDLE_MAX`
    clamps the derived ones to what is left of the 16-slot pool: the last two missions' 13
    middle buildings plus the 5 fixed ones overflowed it, and `mission_place` had dropped the
    enemy base and bank in silence. All ten layouts were dumped and read back.
    *The test rows are now three missions, not a hack* (rows 10-12, unreachable by playing).
    They carry the pre-campaign hand-made field and its tuning, frozen, so that a ground case
    does not move when the curve is tuned. Reaching them cost the in-loop `R`-at-boot hook,
    which called `game_reset` three frames in and moved every timing after it: `boot_load`
    now reads the pad by hand (`pad_read_manual` - the auto-read wants a frame and an NMI that
    have not happened yet) and `mkmovie.py` holds the button *inside* the boot prefix it
    already emits, so the choice costs no frames at all.
    *Found on the way:* the opponent's convoy pick rides on the pilot's coin tosses - both
    draw `cpu_rand`, so how many times the pilot has reached for it before the first purchase
    decides what the purse can reach, and the whole army is re-dealt by any change to
    `foe.r65`. Hence `cpu_forced`: a test row names the convoy to buy (the tier gate does
    not apply to a forced pick; the purse still does), and the third test row pairs that
    with a logistics `cpu_stats` row - trucks and engineers allowed, nothing hunted - so a
    case can fly the length of the field to meet a vehicle. Seven cases were re-derived
    against the frozen rows (`unit_kinds`, `tank_crush`, `launcher_fire`, `missile_unit`,
    `missile_air`, `missile_foe`, `foe_hunt`); the suite is green at 93.
    *Slice (b) DONE.* `src/screen.r65`: the title, the briefing and the after-action page, all
    one mechanism - BG1 written as a full 32x28 page of text with `TM` naming BG1 alone.
    *Both questions above are answered by that:* the field is hidden by not being drawn (BG2-4
    and OBJ keep their contents and their registers, so coming back is a BG1 map DMA and a
    `hud_init`, not a reload), and the briefing gets its own layout rather than the order
    dialog's box - it borrows only the border tiles, since a full page and an 18-column dialog
    want nothing else from each other. A page is composed into one lowram shadow and DMA'd in
    force blank at the transition, so it costs nothing per frame; `GAME_SCREEN` stops both the
    tick and the draw. The briefing reads `mission_stats` rather than repeating it - the
    mission's number and name, its turrets and bunkers, the purse and the lives it starts you
    with - and the names widened to sixteen capitals each so they can be spelled out.
    *The front end is the campaign's*: a test mission boots straight into its battle, and
    `@x` is a fourth power-on hold for the campaign's first mission with the front end skipped,
    which is the world the suite's oldest (unprefixed) cases were written against. New cases:
    `screen_title`, `screen_brief`, `screen_battle`, `screen_after` (four crash landings spend
    the four lives, which ends the match and brings the page up). Green at 98.
    *Slice (c) DONE.* The continue code, four letters over the title. Eleven bits of payload -
    four of mission, seven of purse - and five of check, scrambled with a salt and cut into
    nibbles, each a letter A..P: 1000 of the 65536 spellings mean anything, so a mistyped code
    is rejected rather than quietly starting the wrong mission, and the line under the field
    says live what the code reads as (the mission it opens, or NEW GAME) so Start never does
    anything the page did not say. Start applies it by writing `start_funds` after
    `mission_set`, which is the whole of "carrying" funds until slice (d) decides what is
    carried. The after-action page spells the code for the next run - the next mission if the
    match was won, this one again if it was not - and leaves it typed into the field, so
    continuing is one press. A held direction repeats after a pause, since four letters is
    otherwise sixty presses; typing redraws only the five rows the field occupies, DMA'd in
    vblank, rather than re-blitting the page in force blank on every keypress. New cases:
    `code_type`, `code_continue` (NKCH is mission 5 carrying 32), `code_bad` (one letter out
    starts a new campaign), and `screen_after` now pins the code it spells. Green at 101.
    *Slice (d) DONE.* The loop closes: the after-action page settles the mission
    (`campaign_settle`) and Start goes on to the next briefing with what it settled, or back to
    the same mission after a defeat, or to the end page once the tenth is taken. The conversion
    is the revision recorded above - purchase price for a ground unit, the original's values
    for a held building, nothing for an airframe - and the page reports it in three lines,
    purse, salvage and carried, so the number in the code is one that was shown. *Verified with
    the debugger*, the winning side being unscriptable: `set` game_state to GAME_WON at a
    snapshot break and step the movie's Start presses - mission 1 won with 32 in hand salvages
    20 and carries 52 into mission 2's briefing, and mission 10 won reaches the end page. New
    case `campaign_retry` drives the losing side end to end. Green at 102.
    **Phase 11 is complete.**
12. **Art and audio.** Replace programmer art with real pixel art; author music and SFX in
    snesgss and wire the export into the Makefile.

## Verification

- **Per phase:** a scripted `.mmo` movie through `play.sh`, plus `--check-mem` assertions on
  known RAM addresses (`textadv`'s `verify` target is the model).
- **Sprite budget:** dump OAM at peak load and count active sprites per scanline band.
- **Performance:** measure scanlines per frame via the V-counter — **not** Mesen's "Cycles:"
  counter, which is blind to memory-speed effects.
- **Regression:** keep one movie per completed phase; re-run all after each new phase.

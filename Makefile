# rotor_raiders - Makefile for SNES development with WLA-DX

# Project configuration
PROJECT   = ROTOR_RAIDERS
MAIN_SRC  = src/main.r65
BUILD_DIR = build
ROM_FILE  = $(BUILD_DIR)/$(PROJECT).smc

# All R65 sources (recursive). main.r65 pulls the rest in via include!, so
# every .r65 file must be a prerequisite or `make` misses edits to include!d
# files. Pure GNU Make recursive wildcard (no `find`) so this also works
# under mingw/MSYS make.
rwildcard = $(foreach d,$(wildcard $(1:=/*)),$(call rwildcard,$d,$2)$(filter $(subst *,%,$2),$d))
R65_SRCS  = $(call rwildcard,src,*.r65)

# Everything the ROM embeds with include_bytes!. The art is generated from
# the bitmaps under assets/src (see the assets section below); the sound
# and level blobs are authored elsewhere and are listed as they are found.
# A bitmap named %.tilemap.bmp is de-duplicated into a tilemap as well as
# a tileset; a plain %.bmp is a sheet addressed by tile number and gets no
# map. The name is the whole declaration - drop a bitmap into assets/src
# and it is converted, bound and embedded with no list to keep in step.
ART_MAP_BMP = $(wildcard assets/src/*.tilemap.bmp)
ART_RAW_BMP = $(filter-out %.tilemap.bmp,$(wildcard assets/src/*.bmp))
ART_MAPPED  = $(patsubst assets/src/%.tilemap.bmp,%,$(ART_MAP_BMP))
ART_RAW     = $(patsubst assets/src/%.bmp,%,$(ART_RAW_BMP))
ART         = $(ART_MAPPED) $(ART_RAW)
ART_CHR  = $(addprefix assets/gfx/,$(addsuffix .chr,$(ART)))
ART_PAL  = $(ART_CHR:.chr=.pal)
ART_MAP  = $(addprefix assets/gfx/,$(addsuffix .tilemap,$(ART_MAPPED)))
ART_OUT  = $(ART_CHR) $(ART_PAL) $(ART_MAP)
BLOBS    = $(wildcard assets/sound/*.bin assets/levels/*.bin)
# The sound driver, cut at 32K: a LoROM bank holds 32K and include_bytes!
# takes a whole file, so src/sound.r65 embeds the two halves in banks of
# their own. The first half is the 2-byte size header and 32766 bytes of
# code, the second the rest - hindstrike's sounds.asm cuts it the same way.
SOUND_SPLIT = $(BUILD_DIR)/sound/spc700_1.bin $(BUILD_DIR)/sound/spc700_2.bin

# Tools
R65C     = python -m r65.compiler.main
WLA      = wla-65816
WLA_LINK = wlalink
R65X     = r65x

# Flags
WLA_FLAGS   = -o
R65C_FLAGS  = -v --cfg snes --dbg -I src

all: $(ROM_FILE)

# Compile R65 source to WLA-DX assembly
# src/assets.r65 is generated and so is not in $(R65_SRCS) on a fresh
# checkout; naming it here is what pulls the whole bitmap -> chr -> bindings
# chain into an ordinary `make`.
$(BUILD_DIR)/main.asm: $(R65_SRCS) src/assets.r65 $(ART_OUT) $(BLOBS) $(SOUND_SPLIT)
	@mkdir -p $(BUILD_DIR)
	$(R65C) $(MAIN_SRC) -o $@ $(R65C_FLAGS)

$(BUILD_DIR)/sound/spc700_1.bin: assets/sound/spc700.bin
	@mkdir -p $(dir $@)
	head -c 32768 $< > $@

$(BUILD_DIR)/sound/spc700_2.bin: assets/sound/spc700.bin
	@mkdir -p $(dir $@)
	tail -c +32769 $< > $@

# Assemble. Run from src/ so relative .INCBIN paths from include_bytes! resolve.
$(BUILD_DIR)/main.o: $(BUILD_DIR)/main.asm
	cd src && $(WLA) $(WLA_FLAGS) ../build/main.o ../build/main.asm

# Link using the compiler-generated linkfile (handles multi-bank layouts)
# A bank that is over full is not an error to wlalink: it writes the code
# over whatever is there - the ROM header and vectors at the top of bank 0
# - says "Overwrite at", and exits 0. The ROM then crashes on its first
# frame. So that line fails the build.
$(ROM_FILE): $(BUILD_DIR)/main.o
	@echo "[LINK] $@"
	$(WLA_LINK) -v -S $(BUILD_DIR)/main.link $@ > $(BUILD_DIR)/link.log 2>&1 || { cat $(BUILD_DIR)/link.log; exit 1; }
	@cat $(BUILD_DIR)/link.log
	@if grep -q "Overwrite at" $(BUILD_DIR)/link.log; then \
		echo "error: a bank overflowed and was linked over other code (link.log: 'Overwrite at')"; \
		rm -f $@; exit 1; fi

# ---------------------------------------------------------------- assets ----
# All art is indexed BMP under assets/src, converted by `r65x bmp2chr`.
# A bitmap named %.tilemap.bmp gets a de-duplicated tileset and the map
# that names its tiles back; a plain %.bmp gets the tileset alone.
# Editing a bitmap is all it takes: every .chr, .pal and .tilemap under
# assets/gfx, the bindings in src/assets.r65 and the ROM rebuild from it.
# Those outputs are build products - they are not in git, and `make clean`
# removes them.
#
#   -b2 / -b4  2bpp (the HUD on BG3) or 4bpp (BG1, BG2, sprites) planar output
#   -p         also emit the .pal
#   -t         de-duplicate tiles and emit a .tilemap
#   -f         write the whole bitmap; without it bmp2chr stops at the size
#              of any existing destination file, silently truncating a
#              sheet that has grown
#
# BACKGROUNDS ARE FOLDED ON THE WAY IN. A 64x32 SNES tilemap is two 32x32
# screens held one after the other, but bmp2chr walks a bitmap row-major at
# its full width. So a 512x256 sheet (ground, sky, mountains - drawn as they
# appear on screen) is folded by tools/fold.py into build/fold/, its
# right-hand 256 px moved below the left, and bmp2chr reads that: its
# row-major output is then byte-identical to what the PPU expects. hud is a
# single 32x32 screen and fold.py passes it through as it is.
#
# Two rule sets, told apart by the source's name. Both are multi-target
# pattern rules - make's way of saying "one run of this command produces
# all of these", so a parallel build starts each conversion once rather
# than once per output.
#
# Which rule make picks is settled by which bitmap exists: for hud.chr the
# plain rule wants assets/src/hud.bmp, which is not there, so the tilemap
# rule takes it; for obj.chr it is the other way round.
#
# Bit depth is the other axis and is a target-specific variable, since it
# has nothing to do with whether a sheet carries a map. It has to be set
# on every output of a sheet, not just the .chr: make looks the variable
# up on whichever file it was asked for, and the .tilemap is often the one
# the bindings want first.
# (a comment after a value would become part of it, so they go above)
# 2bpp unless a sheet says otherwise, and nothing to do afterwards.
BMP2CHR_DEPTH = -b2
BMP2CHR_POST  = true

# The sprite sheets are 4bpp: the shared one, the airframe's own, the
# explosions' (fx, after the airframe's in the second name block) and the
# alert avatar's (after the explosions'). So are Mode 1's BG1 and BG2 -
# the ground, and the sky's two sheets (clouds and mountains); the HUD on
# BG3 is 2bpp.
assets/gfx/obj.chr assets/gfx/obj.pal: BMP2CHR_DEPTH = -b4
assets/gfx/heli.chr assets/gfx/heli.pal: BMP2CHR_DEPTH = -b4
assets/gfx/fx.chr assets/gfx/fx.pal: BMP2CHR_DEPTH = -b4
assets/gfx/avatar.chr assets/gfx/avatar.pal: BMP2CHR_DEPTH = -b4
assets/gfx/sky.chr assets/gfx/sky.pal assets/gfx/sky.tilemap: BMP2CHR_DEPTH = -b4
assets/gfx/mountains.chr assets/gfx/mountains.pal assets/gfx/mountains.tilemap: BMP2CHR_DEPTH = -b4
assets/gfx/ground.chr assets/gfx/ground.pal assets/gfx/ground.tilemap: BMP2CHR_DEPTH = -b4
# The power-on BubbleZap logo (src/intro.r65) is Mode 7: 8bpp, a byte a pixel.
assets/gfx/bubblezap.chr assets/gfx/bubblezap.pal assets/gfx/bubblezap.tilemap: BMP2CHR_DEPTH = -m7
# The title page (src/screen.r65) is Mode 3: BG1 a 256-colour picture,
# 8bpp, 64 bytes a tile. A screen of them is up to 56K, more than a LoROM
# bank, so its tiles are cut at 32K into title_1.chr and title_2.chr, banks
# 7 and 8, as the sound driver is; the bindings below name the halves.
assets/gfx/title.chr assets/gfx/title.pal assets/gfx/title.tilemap: BMP2CHR_DEPTH = -b8
TITLE_SPLIT = assets/gfx/title_1.chr assets/gfx/title_2.chr
assets/gfx/title_1.chr: assets/gfx/title.chr
	head -c 32768 $< > $@
assets/gfx/title_2.chr: assets/gfx/title.chr
	tail -c +32769 $< > $@
	@[ -s $@ ] || { echo "title.chr is under 32K: its second half is empty (Makefile TITLE_SPLIT)" >&2; rm -f $@; exit 1; }

# Tilemap attributes bmp2chr has no flag for, set afterwards by
# tools/tilemap_attr.py. The numbers must match where video.r65 uploads
# each .pal (CGRAM_GROUND, CGRAM_SKY, CGRAM_MOUNTAINS, in 16-colour
# palettes).
# - The 4bpp sheets are drawn from palette 0 and moved up: BG1 and BG2 share
#   CGRAM 0-127, and its first two palettes are BG3's - the HUD's.
# - The ground carries the priority bit, so the airframe rising out of it
#   (heli.r65, OBJ priority 2) draws behind the dirt but in front of the
#   mountains on BG2.
# - The HUD carries it too, so with BGMODE's BG3 bit its rows draw over the
#   dirt and the sky. The radar row is the exception, written at runtime
#   without it, so the camera bracket sprite shows over it.
# - BG1 and BG2 share one tile area, $0000-$3FFF (both name bases $0000,
#   video.r65): 1024 4bpp tiles, the most a layer can address. The three
#   sheets go up in it one after the other - the ground, the clouds (sky),
#   the mountains - so each map names its tiles that many on from the
#   sheets before it (--tile-offset, from their .chr sizes - hence the
#   extra prerequisites), and any of them may grow into what the others
#   leave. Together they must fit in 1023: past $3FFF they overwrite the
#   sprites' tiles at $4000, silently, so the build stops instead - and the
#   last tile is the HUD's top strip (video.r65's TOP_TILE), drawn at boot.
assets/gfx/sky.tilemap: assets/gfx/ground.chr
assets/gfx/sky.chr assets/gfx/sky.pal assets/gfx/sky.tilemap: \
	BMP2CHR_POST = python3 tools/tilemap_attr.py assets/gfx/sky.tilemap --pal 3 \
	    --tile-offset $$(( $$(stat -c%s assets/gfx/ground.chr) / 32 ))
assets/gfx/mountains.tilemap: assets/gfx/ground.chr assets/gfx/sky.chr
assets/gfx/mountains.chr assets/gfx/mountains.pal assets/gfx/mountains.tilemap: \
	BMP2CHR_POST = python3 tools/tilemap_attr.py assets/gfx/mountains.tilemap --pal 4 \
	    --tile-offset $$(( ( $$(stat -c%s assets/gfx/ground.chr) + $$(stat -c%s assets/gfx/sky.chr) ) / 32 )) && \
	  { bg=$$(( $$(stat -c%s assets/gfx/ground.chr) + $$(stat -c%s assets/gfx/sky.chr) + $$(stat -c%s assets/gfx/mountains.chr) )); \
	    [ $$bg -le 32736 ] || \
	    { echo "ground.chr + sky.chr + mountains.chr are $$bg bytes: over the 1023 tiles BG1/BG2's VRAM $$0000-$$3FFF holds beside the top strip's" >&2; \
	      rm -f assets/gfx/mountains.chr; exit 1; }; }
assets/gfx/ground.chr assets/gfx/ground.pal assets/gfx/ground.tilemap: \
	BMP2CHR_POST = python3 tools/tilemap_attr.py assets/gfx/ground.tilemap --pal 2 --priority
assets/gfx/hud.chr assets/gfx/hud.pal assets/gfx/hud.tilemap: \
	BMP2CHR_POST = python3 tools/tilemap_attr.py assets/gfx/hud.tilemap --priority
# - The status rows' glyphs (status, tools/status_art.py) are BG3 tiles
#   too, drawn in sub-palettes 5-7 - an 8-bit bitmap of CGRAM indices, so
#   bmp2chr names each tile's palette itself. They go up past the order
#   menu's icons: the front end's font ends at tile 160 (hud.r65
#   ICON_TILE0), so their map names them 160 + the icons' tile count on
#   (hence the extra prerequisite), and the lot must fit BG3's 256 tiles.
assets/gfx/status.tilemap: assets/gfx/icons.chr
assets/gfx/status.chr assets/gfx/status.pal assets/gfx/status.tilemap: \
	BMP2CHR_POST = off=$$(( 160 + $$(stat -c%s assets/gfx/icons.chr) / 16 )); \
	  python3 tools/tilemap_attr.py assets/gfx/status.tilemap --priority --tile-offset $$off && \
	  { n=$$(( off + $$(stat -c%s assets/gfx/status.chr) / 16 )); [ $$n -le 256 ] || \
	    { echo "icons.chr + status.chr end at BG3 tile $$n: past the 256 that BG3 VRAM 0x7000-0x77FF holds" >&2; \
	      rm -f assets/gfx/status.chr; exit 1; }; }

# A sheet that carries a tilemap: tiles de-duplicated (-t), and the map
# names them back in the bitmap's order. The depths and the tilemap
# attributes are set in this file, so editing it reconverts the art.
assets/gfx/%.chr assets/gfx/%.pal assets/gfx/%.tilemap: assets/src/%.tilemap.bmp Makefile tools/tilemap_attr.py tools/fold.py
	@mkdir -p assets/gfx $(BUILD_DIR)/fold
	@python3 tools/fold.py $< $(BUILD_DIR)/fold/$*.bmp
	$(R65X) bmp2chr $(BUILD_DIR)/fold/$*.bmp -o assets/gfx/$*.chr $(BMP2CHR_DEPTH) -p -t -f
	@$(BMP2CHR_POST)

# And a sheet without one: every tile kept, addressed by its number.
assets/gfx/%.chr assets/gfx/%.pal: assets/src/%.bmp Makefile
	@mkdir -p assets/gfx
	$(R65X) bmp2chr $< -o assets/gfx/$*.chr $(BMP2CHR_DEPTH) -p -f
	@$(BMP2CHR_POST)

# Bindings are generated from whatever r65x actually produced. Tile counts
# move when art is edited - dedup decides them - so a hand-written size in
# include_bytes! would silently desync from the file on disk.
# The backgrounds (the %.tilemap.bmp sheets) go in bank 1 and the sprite
# sheets in bank 3: together they outgrow one 32K bank. The clouds have
# bank 4, with the intro's Mode 7 logo (7K of 8bpp tiles, too much for what
# bank 1 has left), and the ground bank 9 to itself: every 8x8 of its strip
# drawn differently is 384 tiles, 16K with its map, which bank 1 cannot
# hold beside the mountains. The title's picture is two halves cut at 32K, bank 7
# and bank 8, its map and palette with the second (TITLE_SPLIT, above).
# Every upload takes a far pointer, so which bank a sheet lands in is
# invisible to the code.
src/assets.r65: $(ART_OUT) $(TITLE_SPLIT) Makefile
	@echo "[GEN] $@"
	@{ \
	  echo '// GENERATED by make - DO NOT EDIT, and do not commit.'; \
	  echo '// Art source is assets/src/*.bmp, converted by r65x bmp2chr.'; \
	  echo ''; \
	  for n in $(ART); do \
	    case " $(ART_MAPPED) " in \
	      *" $$n "*) b=1;; \
	      *) b=3;; \
	    esac; \
	    [ "$$n" = sky ] && b=4; \
	    [ "$$n" = ground ] && b=9; \
	    [ "$$n" = bubblezap ] && b=4; \
	    [ "$$n" = title ] && b=8; \
	    u=$$(echo $$n | tr a-z A-Z); \
	    [ "$$n" = title ] && { \
	      echo ''; echo '#[bank(7)]'; echo ''; \
	      printf 'static TITLE_CHR_1: [u8; %s] = include_bytes!("../assets/gfx/title_1.chr");\n' \
	        $$(stat -c%s assets/gfx/title_1.chr); bank=7; }; \
	    [ "$$b" = "$$bank" ] || { echo ''; echo "#[bank($$b)]"; echo ''; bank=$$b; }; \
	    [ "$$n" = title ] && \
	      printf 'static TITLE_CHR_2: [u8; %s] = include_bytes!("../assets/gfx/title_2.chr");\n' \
	        $$(stat -c%s assets/gfx/title_2.chr); \
	    for k in chr tilemap pal; do \
	      [ "$$n.$$k" = title.chr ] && continue; \
	      [ -f assets/gfx/$$n.$$k ] || continue; \
	      case $$k in chr) x=CHR;; tilemap) x=MAP;; pal) x=PAL;; esac; \
	      printf 'static %s_%s: [u8; %s] = include_bytes!("../assets/gfx/%s.%s");\n' \
	        $$u $$x $$(stat -c%s assets/gfx/$$n.$$k) $$n $$k; \
	    done; \
	  done; \
	  echo ''; \
	  for n in $(ART); do \
	    u=$$(echo $$n | tr a-z A-Z); \
	    for k in chr tilemap pal; do \
	      [ -f assets/gfx/$$n.$$k ] || continue; \
	      [ "$$n.$$k" = title.chr ] && { \
	        printf 'const TITLE_CHR_1_SIZE: u16 = %s;\nconst TITLE_CHR_2_SIZE: u16 = %s;\n' \
	          $$(stat -c%s assets/gfx/title_1.chr) $$(stat -c%s assets/gfx/title_2.chr); \
	        continue; }; \
	      case $$k in chr) x=CHR;; tilemap) x=MAP;; pal) x=PAL;; esac; \
	      printf 'const %s_%s_SIZE: u16 = %s;\n' \
	        $$u $$x $$(stat -c%s assets/gfx/$$n.$$k); \
	    done; \
	  done; \
	} > $@

# `make assets` is now only a name for the art half of an ordinary build:
# the ROM depends on it, so nothing has to be run by hand.
assets: src/assets.r65

# ------------------------------------------------------------------ test ----
# The compiler writes a .link next to -o, so lint needs a real output path.
lint:
	@mkdir -p $(BUILD_DIR)
	$(R65C) $(MAIN_SRC) -o $(BUILD_DIR)/lint.asm --cfg snes --lint -I src

# The ROM test suite (tests/, pytest on mesen_gdb.rom_driver).
verify: $(ROM_FILE)
	python3 -m pytest tests -n auto -q

# Single ad-hoc run: make play OUT=build/shot.png ACTIONS=start,wait60,shot
OUT     ?= $(BUILD_DIR)/play.png
ACTIONS ?= shot
play: $(ROM_FILE)
	@./play.sh $(OUT) $(ACTIONS)

# ----------------------------------------------------------------- misc ----
clean:
	@echo "[CLEAN] Removing build artifacts..."
	rm -rf $(BUILD_DIR)
	rm -f $(ART_OUT) src/assets.r65
	rm -f *.o *.asm *.smc *.sym *.map linkfile.txt

run: $(ROM_FILE)
	@if command -v Mesen >/dev/null 2>&1; then Mesen $(ROM_FILE); \
	elif command -v higan >/dev/null 2>&1; then higan $(ROM_FILE); \
	elif command -v bsnes >/dev/null 2>&1; then bsnes $(ROM_FILE); \
	else echo "No compatible emulator found."; fi

debug: clean
	$(MAKE) all R65C_FLAGS="-v --cfg snes --dbg -I src"

syntax: $(BUILD_DIR)/main.asm

help:
	@echo "Available targets:"
	@echo "  all      - Build ROM (default)"
	@echo "  assets   - Convert assets/src/*.bmp to SNES CHR + palettes (an ordinary build does this)"
	@echo "  lint     - Run the R65 linter (r65-lint.toml)"
	@echo "  verify   - Build and run the scripted-input regression suite"
	@echo "  play     - One scripted run: make play OUT=x.png ACTIONS=start,wait60,shot"
	@echo "  run      - Launch ROM in an emulator"
	@echo "  syntax   - Compile only, no ROM"
	@echo "  clean    - Remove build artifacts"

.PHONY: all assets lint verify play clean run debug syntax help

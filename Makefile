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
$(BUILD_DIR)/main.asm: $(R65_SRCS) src/assets.r65 $(ART_OUT) $(BLOBS)
	@mkdir -p $(BUILD_DIR)
	$(R65C) $(MAIN_SRC) -o $@ $(R65C_FLAGS)

# Assemble. Run from src/ so relative .INCBIN paths from include_bytes! resolve.
$(BUILD_DIR)/main.o: $(BUILD_DIR)/main.asm
	cd src && $(WLA) $(WLA_FLAGS) ../build/main.o ../build/main.asm

# Link using the compiler-generated linkfile (handles multi-bank layouts)
$(ROM_FILE): $(BUILD_DIR)/main.o
	@echo "[LINK] $@"
	$(WLA_LINK) -v -S $(BUILD_DIR)/main.link $@

# ---------------------------------------------------------------- assets ----
# All art is indexed BMP under assets/src, converted by `r65x bmp2chr`.
# A bitmap named %.tilemap.bmp gets a de-duplicated tileset and the map
# that names its tiles back; a plain %.bmp gets the tileset alone.
# Editing a bitmap is all it takes: every .chr, .pal and .tilemap under
# assets/gfx, the bindings in src/assets.r65 and the ROM rebuild from it.
# Those outputs are build products - they are not in git, and `make clean`
# removes them.
#
#   -b2 / -b4  2bpp (Mode 0 backgrounds) or 4bpp (sprites) planar output
#   -p         also emit the .pal
#   -t         de-duplicate tiles and emit a .tilemap
#   -f         write the whole bitmap; without it bmp2chr stops at the size
#              of any existing destination file, silently truncating a
#              sheet that has grown
#
# BACKGROUNDS ARE STORED FOLDED. A 64x32 SNES tilemap is two 32x32 screens
# held one after the other, but bmp2chr walks a bitmap row-major at its full
# width. So each 64-tile-wide layer is authored 32 tiles wide and 64 tall -
# right-hand screen *below* the left, not beside it - and the row-major
# output is then byte-identical to what the PPU expects. Editing bg2/3/4
# means remembering that the bottom half continues off the right edge of the
# top half. bg1 is a single 32x32 screen and needs no fold.
#
# Two rule sets, told apart by the source's name. Both are multi-target
# pattern rules - make's way of saying "one run of this command produces
# all of these", so a parallel build starts each conversion once rather
# than once per output.
#
# Which rule make picks is settled by which bitmap exists: for bg1.chr the
# plain rule wants assets/src/bg1.bmp, which is not there, so the tilemap
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

# The sprite sheets are 4bpp: the shared one, and the airframe's own.
assets/gfx/obj.chr assets/gfx/obj.pal: BMP2CHR_DEPTH = -b4
assets/gfx/heli.chr assets/gfx/heli.pal: BMP2CHR_DEPTH = -b4

# The ground band's tilemap carries the per-tile priority bit (bit 13). In
# Mode 0 a priority-0 sprite still draws over a low-priority BG3/BG4, so
# without it the airframe rising out of the ground (heli.r65) would sit on
# top of the dirt instead of under it. Transparent pixels are unaffected.
# bmp2chr has no flag for it, so the bit is set on the tilemap afterwards.
assets/gfx/bg4.chr assets/gfx/bg4.pal assets/gfx/bg4.tilemap: \
	BMP2CHR_POST = python3 -c "p='assets/gfx/bg4.tilemap'; d=bytearray(open(p,'rb').read()); d[1::2]=bytes(b|0x20 for b in d[1::2]); open(p,'wb').write(d)"

# A sheet that carries a tilemap: tiles de-duplicated (-t), and the map
# names them back in the bitmap's order.
assets/gfx/%.chr assets/gfx/%.pal assets/gfx/%.tilemap: assets/src/%.tilemap.bmp
	@mkdir -p assets/gfx
	$(R65X) bmp2chr $< -o assets/gfx/$*.chr $(BMP2CHR_DEPTH) -p -t -f
	@$(BMP2CHR_POST)

# And a sheet without one: every tile kept, addressed by its number.
assets/gfx/%.chr assets/gfx/%.pal: assets/src/%.bmp
	@mkdir -p assets/gfx
	$(R65X) bmp2chr $< -o assets/gfx/$*.chr $(BMP2CHR_DEPTH) -p -f
	@$(BMP2CHR_POST)

# Bindings are generated from whatever r65x actually produced. Tile counts
# move when art is edited - dedup decides them - so a hand-written size in
# include_bytes! would silently desync from the file on disk.
src/assets.r65: $(ART_OUT)
	@echo "[GEN] $@"
	@{ \
	  echo '// GENERATED by make - DO NOT EDIT, and do not commit.'; \
	  echo '// Art source is assets/src/*.bmp, converted by r65x bmp2chr.'; \
	  echo ''; \
	  echo '#[bank(1)]'; \
	  echo ''; \
	  for n in $(ART); do \
	    u=$$(echo $$n | tr a-z A-Z); \
	    for k in chr tilemap pal; do \
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

# Scripted-input regression suite. Each movie drives the ROM to a
# snapshot_point breakpoint and screenshots; see tests/run.sh.
verify: $(ROM_FILE)
	@./tests/run.sh

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

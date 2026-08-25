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

# Binary assets pulled in via include_bytes!
ASSETS = $(wildcard assets/gfx/*.chr assets/gfx/*.pal assets/sound/*.bin assets/levels/*.bin)

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
$(BUILD_DIR)/main.asm: $(R65_SRCS) $(ASSETS)
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
# Convert indexed BMP source art to SNES 4bpp CHR + palette.
# -b4 = 4bpp planar, -p = also emit .pal, -t = dedupe tiles (incl. flips)
# and emit a .tilemap. Background strips want -t; sprite sheets do not.
assets/gfx/%.chr: assets/src/%.bmp
	@mkdir -p assets/gfx
	$(R65X) bmp2chr $< -o $@ -b4 -p

assets/gfx/%.bg.chr: assets/src/%.bg.bmp
	@mkdir -p assets/gfx
	$(R65X) bmp2chr $< -o $@ -b4 -p -t

assets: $(patsubst assets/src/%.bmp,assets/gfx/%.chr,$(wildcard assets/src/*.bmp))
	@echo "[ASSETS] up to date"

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
	@echo "  assets   - Convert assets/src/*.bmp to SNES CHR + palettes"
	@echo "  lint     - Run the R65 linter (r65-lint.toml)"
	@echo "  verify   - Build and run the scripted-input regression suite"
	@echo "  play     - One scripted run: make play OUT=x.png ACTIONS=start,wait60,shot"
	@echo "  run      - Launch ROM in an emulator"
	@echo "  syntax   - Compile only, no ROM"
	@echo "  clean    - Remove build artifacts"

.PHONY: all assets lint verify play clean run debug syntax help

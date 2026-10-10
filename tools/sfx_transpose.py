#!/usr/bin/env python3
"""
Transpose sound effects in the SNES GSS export and its project, together.

    sfx_transpose.py SEMITONES SFX...      e.g.  sfx_transpose.py -5 16 17 18 19

One-off authoring helper, run by hand: the GSS tool is a Windows GUI with no
command-line export, so a change of pitch is made in both places it lives -

- assets/sound/spc700.bin, what the ROM uploads: each effect is a compiled
  stream, and every note in it (a byte 150 + semitone + 12 x octave) is
  moved by SEMITONES;
- assets/sound/hindstrike.gsm, the project it was exported from: the same
  notes in the effect's song rows, so a re-export from GSS keeps the change.

SFX are the effect numbers of sounds.asm / src/sound.r65 (SFX_HELI_1 is 16).

The stream format is snesgss/src/UnitMain.cpp's ChannelCompile: 254 n sets
the instrument, 247 n the volume, 245 is a key-off, 253 lo hi a reference
into shared data (compression), 255 the end; a byte under 150 is a delay.
An effect with a reference is refused rather than half transposed.

The driver's header (sound RAM $020A) points at the effect table: a count,
then a 16-bit address per effect; spc700.bin is a 2-byte size and then
sound RAM from $0200, so address A is file offset 2 + A - $0200.
"""
import re
import sys

BIN = 'assets/sound/spc700.bin'
GSM = 'assets/sound/hindstrike.gsm'
NOTE0 = 150                   # C-0 in a compiled stream
NAMES = ['C-', 'C#', 'D-', 'D#', 'E-', 'F-', 'F#', 'G-', 'G#', 'A-', 'A#', 'B-']


def off(adr):
    return 2 + adr - 0x200


def note_bytes(d, start):
    """File offsets of every note byte in the effect stream at *start*."""
    channels = d[start]
    out = []
    for c in range(channels):
        p = off(d[start + 1 + 2 * c] | (d[start + 2 + 2 * c] << 8))
        while True:
            b = d[p]
            if b == 255:
                break
            if b in (254, 247):
                p += 2
            elif b == 253:
                raise SystemExit("sfx_transpose.py: the effect uses a compressed "
                                 "reference (253); transpose it in GSS instead")
            elif b == 245 or b < NOTE0:
                p += 1
            else:
                out.append(p)
                p += 1
    return out


def name(n):
    """A compiled note byte as GSS writes it: B-4, F#4."""
    v = n - NOTE0
    return f"{NAMES[v % 12]}{v // 12}"


def effect_songs(gsm):
    """The project's song number of each effect, in effect-number order."""
    songs = []
    for m in re.finditer(r'^Song(\d+)Effect=1\r?$', gsm, re.M):
        songs.append(int(m.group(1)))
    return songs


def main():
    shift = int(sys.argv[1])
    sfx = [int(a) for a in sys.argv[2:]]
    d = bytearray(open(BIN, 'rb').read())
    gsm = open(GSM, encoding='latin-1', newline='').read()   # keep its CRLFs
    table = off(d[12] | (d[13] << 8))
    songs = [s for s in effect_songs(gsm)
             if re.search(rf'^\[Song{s}\]\r?\n\d{{4}}', gsm, re.M)]   # GSS skips empty ones
    for e in sfx:
        start = off(d[table + 1 + 2 * e] | (d[table + 2 + 2 * e] << 8))
        changed = []
        for p in note_bytes(d, start):
            new = d[p] + shift
            if not NOTE0 <= new < 245:
                raise SystemExit(f"sfx_transpose.py: effect {e}: {name(d[p])} moved "
                                 f"{shift} is out of range")
            changed.append((name(d[p]), name(new)))
            d[p] = new
        # The same notes in the song's rows: a note field is name + 2-digit instrument.
        sec = re.search(rf'^\[Song{songs[e]}\]\r?\n(.*?)(?=^\[|\Z)', gsm, re.M | re.S)
        body = sec.group(1)
        for old, new in changed:
            body = re.sub(re.escape(old) + r'(?=\d\d)', new, body, count=1)
        gsm = gsm[:sec.start(1)] + body + gsm[sec.end(1):]
        print(f"effect {e} (song {songs[e]}): " + ", ".join(f"{a} -> {b}" for a, b in changed))
    open(BIN, 'wb').write(d)
    open(GSM, 'w', encoding='latin-1', newline='').write(gsm)


if __name__ == '__main__':
    main()

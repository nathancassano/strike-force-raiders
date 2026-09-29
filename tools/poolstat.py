#!/usr/bin/env python3
"""poolstat.py WRAM.bin [build/main.asm] - what the field looks like at a snapshot.

Reads a `--dump wram` taken at snapshot_point and prints the ground-unit
pool (slot, kind, owner, x, hp, block), the munitions in flight, the CPU's
purse and queue, and the airframe, resolving every address from the
compiler's .DEFINE lines so nothing here goes stale when the layout moves.

    ./play.sh build/x.png wait600,shot --dump wram build/x.wram
    tools/poolstat.py build/x.wram
    tools/poolstat.py --brief build/tl/*.wram     # one line per dump
"""
import re
import sys

KINDS = {0: "free", 1: "tank", 2: "van", 3: "launcher", 4: "infantry", 5: "engineer"}
ORDERS = {0: "V", 1: "M", 2: "T", 3: "I", 4: "E", 5: "-"}
MUNI = {0: "free", 1: "bullet", 2: "bomb", 3: "shell", 4: "blast", 5: "missile", 6: "smart"}
STRUCT = {0: "turret", 1: "bunker", 2: "super", 3: "base", 4: "bank"}
FOE = {0: "wander", 1: "pad", 2: "dodge", 3: "hunt", 4: "bomb", 5: "struct"}
OWNER = "PEN"


def defines(asm):
    d = {}
    for line in open(asm):
        m = re.match(r"\.DEFINE\s+(\S+)\s+\$([0-9A-Fa-f]+)", line)
        if m:
            d[m.group(1)] = int(m.group(2), 16)
    return d


def main():
    args = sys.argv[1:]
    brief = "--brief" in args
    args = [a for a in args if a != "--brief"]
    asm = "build/main.asm"
    if len(args) > 1 and args[-1].endswith(".asm"):
        asm = args.pop()
    d = defines(asm)
    for path in args:
        report(path, d, brief)


def report(path, d, brief):
    wram = open(path, "rb").read()

    def u8(name, i=0):
        return wram[d[name] + i]

    def u16(name, i=0):
        a = d[name] + 2 * i
        return wram[a] | (wram[a + 1] << 8)

    if brief:
        us = []
        for i in range(32):
            k = u8("units__kind__tag", i)
            if k:
                us.append(f"{'PE'[u8('units__owner', i) & 1]}{KINDS.get(k, '?')[:3]}{i}"
                          f"@{u16('units__x_px', i)}/{u8('units__hp', i)}"
                          f"{'*' if u8('units__block', i) else ''}")
        ms = sum(1 for i in range(16) if u8("muni_kind", i))
        ss = []
        for i in range(u16("struct_count")):
            ss.append(f"{STRUCT.get(u8('structs__kind', i), '?')[:3]}{i}@{u16('structs__x', i)}"
                      f"{OWNER[u8('structs__owner', i)]}{u8('structs__hp', i)}"
                      f"{'m' + str(u8('structs__men', i)) if u8("structs__kind", i) == 2 else ''}")
        foe = ""
        if "foe_x_px" in d:
            foe = (f" foe@{u16('foe_x_px')},{u16('foe_y') >> 8} hp{u8('foe_hp')} "
                   f"f{u8('foe_fuel')} g{u8('foe_gun')} b{u8('foe_bombs')} "
                   f"m{u8('foe_missiles')} L{u8('foe_lives')} "
                   f"{FOE.get(u8('foe_state'), '?')}")
        print(f"{path}: f{u16('frames_loop')} heli@{u16('heli_x_px')} hp{u8('heli_hp')} "
              f"L{u8('heli_lives')} ${u8('funds')} cpu${u8('cpu_funds')} muni{ms}{foe}")
        print("   " + " ".join(us))
        print("   " + " ".join(ss))
        return
    m = f" mission={u8('mission')}" if "mission" in d else ""
    print(f"frame {u16('frames_loop')} (nmi {u16('frames_nmi')}){m}")
    print(f"heli x={u16('heli_x_px')} y={u16('heli_y') >> 8} hp={u8('heli_hp')} "
          f"gun={u8('heli_gun')} bombs={u8('heli_bombs')} missiles={u8('heli_missiles')} "
          f"lives={u8('heli_lives')} funds={u8('funds')}")
    if "cpu_funds" in d:
        q = [ORDERS.get(u8("cpu_q", i), "?") for i in range(u8("cpu_head"), u8("cpu_tail"))]
        print(f"cpu  funds={u8('cpu_funds')} acc={u16('cpu_acc')} "
              f"queue={''.join(q) or '-'} letter={ORDERS.get(u8('cpu_kind'))}x{u8('cpu_men')} "
              f"gap={u8('cpu_gap')} t={u8('cpu_t')}")

    if "foe_x_px" in d:
        extra = ""
        if "foe_tx" in d:
            extra = (f" -> {u16('foe_tx')},{u16('foe_ty') >> 8} attack={u8('foe_attack')} "
                     f"hunt={u8('foe_hunt')} tgt={u8('foe_tgt')} bombed={u8('foe_bombed')}x{u8('foe_bombed_n')}")
        print(f"foe  x={u16('foe_x_px')} y={u16('foe_y') >> 8} vx={u16('foe_vx')} hp={u8('foe_hp')} "
              f"fuel={u8('foe_fuel')} gun={u8('foe_gun')} bombs={u8('foe_bombs')} "
              f"missiles={u8('foe_missiles')}/{u8('foe_missile_cd')} "
              f"lives={u8('foe_lives')} state={FOE.get(u8('foe_state'), '?')} landed={u8('foe_landed')} "
              f"dead={u8('foe_dead')} rising={u8('foe_rising')}{extra}")
    heads = [u8("unit_head", 0), u8("unit_head", 1)]
    tails = [u8("unit_tail", 0), u8("unit_tail", 1)]
    print(f"units: lead P={heads[0]} E={heads[1]}  rear P={tails[0]} E={tails[1]}")
    for i in range(32):
        k = u8("units__kind__tag", i)
        if k == 0:
            continue
        side = "P" if u8("units__owner", i) == 0 else "E"
        def link(name):
            v = u8(name, i)
            return "-" if v == 0xFF else str(v)
        print(f"  {i:2d} {side} {KINDS.get(k, k):9s} x={u16('units__x_px', i):5d} "
              f"hp={u8('units__hp', i):3d} block={u8('units__block', i)} "
              f"ahead={link('units__ahead'):>2s} behind={link('units__behind'):>2s} "
              f"data={u8('units__kind__data', i)}")
    print("munitions:")
    for i in range(16):
        k = u8("muni_kind", i)
        if k == 0:
            continue
        side = "P" if u8("muni_owner", i) == 0 else "E"
        tgt = ""
        if k == 6 and "muni_tgt" in d:
            v = u8("muni_tgt", i)
            tgt = f" -> {'air' if v == 0xFF else 'unit ' + str(v)}"
        print(f"  {i:2d} {side} {MUNI.get(k, k):8s}{tgt} x={u16('muni_x_px', i):5d} "
              f"y={u16('muni_y', i) >> 8:3d} life={u8('muni_life', i)}")


if __name__ == "__main__":
    main()

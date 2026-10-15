"""Phases 9-10: win and loss, the CPU's purse, the enemy airframe and pilot."""

from PIL import Image, ImageStat

from shared import boot, five_passes, read_snapshot

GAME_PLAYING, GAME_LOST, GAME_PAUSED = 0, 2, 4
FREE = 0                                    # an empty unit slot's kind


# ---- Phase 9 - win and loss ---------------------------------------------------
#
# Two ends only: a van at the other side's base, or no helicopters left. The
# van cannot be scripted from the pad in useful time - it was checked by
# planting one at the enemy base with the debugger - so these cover the other
# end and the way back. Both start from `five_passes` (shared.py): five
# pushes into the enemy base's missiles, which lose all four airframes.

def test_game_lost(state):
    """The match ends in defeat and the last airframe is not replaced."""
    snes = state(five_passes)
    v = read_snapshot(snes)
    assert v.game_state == GAME_LOST
    assert v.airframes__lives.u8[0] == 0


def test_game_reset(state):
    """Start begins a fresh match: playing, four lives, the airframe at the
    start, the camera at the west edge.
    """
    snes = state(five_passes)
    snes.start().wait(10)
    v = read_snapshot(snes)
    assert v.game_state == GAME_PLAYING
    assert v.airframes__lives.u8[0] == 4
    assert v.airframes__x_px.u16[0] == 64
    assert v.camera_x == 0


# ---- pause --------------------------------------------------------------------
#
# Start in battle pauses it: no tick runs, the screen fades down to brightness
# 7 of 15, a step every two frames, and PAUSED goes up on the battle-over line.
# Start again fades it back up, still paused, and carries on from the tick it
# stopped at - frames_loop, the clock every stagger and roll is keyed off, is
# put back - so a battle with a pause in it is the same battle.

def test_start_pauses_the_battle(snes):
    """Nothing moves: not the airframe under a held stick, not the enemy's
    first man, not the enemy airframe."""
    boot(snes, "MISSION_TEST_QUIET").wait(300).start()
    v = read_snapshot(snes)
    assert v.game_state == GAME_PAUSED
    man, foe = v.units__x_px.u16[0], v.airframes__x_px.u16[1]
    snes.right(60)
    v = read_snapshot(snes)
    assert v.airframes__x_px.u16[0] == 64
    assert v.units__x_px.u16[0] == man
    assert v.airframes__x_px.u16[1] == foe


def test_start_acts_on_release(snes):
    """Held, Start does nothing - the battle runs on under it; it is its
    release that pauses (input.r65 triggers Start as it comes up)."""
    boot(snes, "MISSION_TEST_QUIET").wait(300)
    snes.press("start", frames=30)
    assert snes.var.game_state == GAME_PLAYING
    snes.wait(3)
    v = read_snapshot(snes)
    assert v.game_state == GAME_PAUSED


def test_a_pause_reads_paused(snes):
    """The six letters, centred on the 32-wide line, are the HUD letter
    row's tiles (map row 29 of HUD_MAP, one a capital from A)."""
    boot(snes, "MISSION_TEST_QUIET").wait(300).start()
    v = read_snapshot(snes)
    hud_map = snes.raw("HUD_MAP_data").u16
    for k, c in enumerate("PAUSED"):
        assert v.hud_msg.u16[13 + k] == hud_map[29 * 32 + ord(c) - ord("A")]


def test_a_pause_dims_the_screen(snes, tmp_path):
    boot(snes, "MISSION_TEST_QUIET").wait(300)
    before = mean_light(snes.screenshot(tmp_path / "before.png"))
    snes.start().wait(30)
    paused = mean_light(snes.screenshot(tmp_path / "paused.png"))
    snes.start().wait(30)
    after = mean_light(snes.screenshot(tmp_path / "after.png"))
    assert paused < before / 2
    assert after > before * 0.9                     # full again; the field has moved on


def test_a_pause_fades_down_and_back_up(snes):
    """A step every two frames: down from 15 to 7 from Start's release
    (the tap's three frames up are the first steps' frames), and back up
    on the next - the battle still paused until it is at 15."""
    boot(snes, "MISSION_TEST_QUIET").wait(300).start()
    down = []
    for _ in range(16):
        down.append(snes.var.game_bright)
        snes.wait(1)
    assert down == [14, 14, 13, 13, 12, 12, 11, 11, 10, 10, 9, 9, 8, 8, 7, 7]
    snes.start()
    up = []
    for _ in range(16):
        up.append((snes.var.game_bright, snes.var.game_state))
        snes.wait(1)
    assert [b for b, _ in up] == [9, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14, 15, 15, 15, 15]
    assert [st for _, st in up] == [GAME_PAUSED] * 14 + [GAME_PLAYING] * 2


def test_a_pause_does_not_re_deal_the_battle(snes):
    """Flown 40 frames right and paused for two seconds, the battle at loop
    tick 614 is the unpaused one's, boot(...).wait(200).right(40).wait(360):
    the first man, the CPU's purse and seed, both airframes. (Neither the
    pausing frame nor the fade back up runs a tick.)"""
    boot(snes, "MISSION_TEST_QUIET").wait(200).right(40).wait(60)
    snes.start().wait(120).start().wait(311)
    v = read_snapshot(snes)
    assert v.frames_loop == 614
    assert v.units__x_px.u16[0] == 7405
    assert v.cpu_funds == 30
    assert v.cpu_seed == 23835
    assert v.airframes__x_px.u16[0] == 314
    assert v.airframes__x_px.u16[1] == 5073


def mean_light(png):
    """Mean luminance of a screenshot, 0-255."""
    return ImageStat.Stat(Image.open(png).convert("L")).mean[0]


# ---- Phase 10 - the CPU's purse and convoys -----------------------------------

def test_cpu_purse(snes):
    """The enemy earns as the player does, from its airframe's distance into
    the player's half.

    It buys a random convoy it can afford once the last has left the gate and
    the row's pause has run. On the quiet row the first buy at frame 64 is I -
    five men for 5 - so by loop frame 315 the purse reads 29 with no income
    yet, the queue is drained, and the fifth man is waiting on the gate. The
    sequence from a cold boot is fixed by the seed and the airframe's flight,
    so any change to the tables, the pause or the pilot moves every
    column-dependent case.
    """
    boot(snes, "MISSION_TEST_QUIET").wait(300)
    v = read_snapshot(snes)
    assert v.cpu_funds == 29
    assert v.cpu_q.u8[0] == 3
    assert v.cpu_head == 1
    assert v.cpu_tail == 1
    assert v.cpu_men == 1


# ---- Phase 10 - the enemy airframe and its pilot ------------------------------
#
# The player's physics and loadout on its own state, and a pilot adapted from
# Armor Alley's: refit, dodge, hunt, bomb, wander, in that order. On the quiet
# row (MISSION_TEST_QUIET) it only wanders and refits; the hunter row
# (MISSION_TEST_HUNTER) hunts the player's airframe and bombs.

def test_the_hot_pilot_hunts_the_player(snes):
    """Flown out to ~3100 and left hovering: the enemy, hunting, arrives at a
    standoff, level, and fires until the player's airframe is lost, then goes
    on to its next target with all four lives.
    """
    boot(snes, "MISSION_TEST_HUNTER").wait(20).right(600).wait(900)
    v = read_snapshot(snes)
    assert v.airframes__lives.u8[0] == 3
    assert v.airframes__lives.u8[1] == 4


def test_the_pilot_steps_out_of_a_hover(snes):
    """Avoidance on both airframes' closing speed: the player hovers in the
    wander's path at x 989 and the pilot steps out of its plane on every pass.

    Counting only the player's speed, it flew into the hover and both were
    lost by frame 1500.
    """
    boot(snes, "MISSION_TEST_QUIET").right(175).wait(1500)
    v = read_snapshot(snes)
    assert v.airframes__lives.u8[0] == 4
    assert v.airframes__lives.u8[1] == 4


def test_the_hot_pilot_bombs_a_tank(snes):
    """A bought tank marching east is found by the pilot on its way in and
    bombed from a hover over it: by frame 3000 the slot is free.
    """
    boot(snes, "MISSION_TEST_HUNTER").press("l", "a", frames=3).wait(3000)
    v = read_snapshot(snes)
    assert v.units__kind__tag.u8[0] == FREE
    assert v.airframes__lives.u8[0] == 4


def test_the_enemy_drops_paratroopers_into_the_super_bunker(snes):
    """On a campaign mission the enemy airframe carries five men
    (foe.r65's Pilot::maybe_drop): from frame ~890 it flies to the super
    bunker at x 4076 (the FOE_PARA mode), hovers over it and drops all of
    them - the super bunker gets the whole load - and they take it, two
    men inside, by 1400, long before its ground column (still past x 7000)
    could. The test missions leave this out, so the cases above keep their
    battles.
    """
    boot(snes, "MISSION_CAKE_WALK").wait(1400)
    v = read_snapshot(snes)
    assert v.pilot__men.u8[0] == 0
    assert v.structs__kind.u8[4] == 2         # the super bunker
    assert v.structs__owner.u8[4] == 1        # the enemy's
    assert v.structs__men.u8[4] == 2


def test_the_enemy_raids_the_bank(snes):
    """Blind Spot is a CPU_ROB_BANK mission (cpu.r65): with the player's
    purse over its fund_min and the pilot's 1-in-4 steal window open (both
    planted), the pilot raids - from ~x 6350, where 99 of purse pays for the
    distance, through the base's missiles at hover height, under the
    balloons - and over the bank (~frame 1820) puts its men out. Two land in
    the doorway and rob it as they touch down (struct_bank_rob_at): 99 ->
    49 -> 24. The third lands short of the door and goes onto the field -
    the raid's drop takes no room, but his own is there once the robbers
    are gone - and walks in: 24 -> 12. (He used to stand where he landed,
    the enemy's units at their cap.) The raider is shot down on its way out.
    """
    boot(snes, "MISSION_BLIND_SPOT")
    snes.write("funds", 99, 1)
    snes.write("pilot__steal", 1, 1)
    snes.wait(2100)
    v = read_snapshot(snes)
    assert v.funds == 12


def test_a_purse_under_fund_max_is_not_raided(snes):
    """Cake Walk carries no CPU_ROB_BANK and its fund_max is 99, which the
    purse cannot pass: with the same plant the pilot never crosses
    FOE_WEST and the purse is untouched.
    """
    boot(snes, "MISSION_CAKE_WALK")
    snes.write("funds", 99, 1)
    snes.write("pilot__steal", 1, 1)
    west = 9999
    for _ in range(20):
        snes.wait(100)
        west = min(west, snes.raw("airframes__x_px").u16[1])
    v = read_snapshot(snes)
    assert v.funds == 99
    assert west >= 900

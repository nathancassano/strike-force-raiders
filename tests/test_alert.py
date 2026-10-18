"""The alert queue and the avatar (alert.r65): an event pushes a code, the
portrait slides in at the bottom right and the code's two lines type out
in the box beside it, one alert at a time.

The box is BG3 map rows 23-26 (`alert_map`, 32 words a row): the lines are
the shadow's rows 1 and 2, from column 11. The quiet opponent buys its
first convoy within a second of the boot, so its ENEMY CONVOY alert is up
first; a case that wants the box to itself starts after it has gone.
"""

from shared import boot, five_passes, read_snapshot

ALERT_IDLE, ALERT_IN, ALERT_TYPING, ALERT_HELD, ALERT_OUT = 0, 1, 2, 3, 4
TEXT_COL = 11                   # the box's first letter column
AFTER_CONVOY = 400              # frames from the boot: the convoy's alert is over


def code(first, second):
    """An alert code: two indexes into alert_lines."""
    return (first << 8) | second


FUNDS = code(19, 20)            # NOT ENOUGH / FUNDS
FUEL_LOW = code(15, 0)          # FUEL LOW
CONVOY = code(23, 24)           # ENEMY CONVOY / ON THE WAY
ENEMY_LOST_BUNKER = code(5, 7)  # ENEMY LOST A / BUNKER
LAST_HELI = code(18, 0)         # LAST HELICOPTER


def letters(snes, text):
    """The HUD's tile words for *text*: capitals from map row 29, a space
    the box's navy (HUD_BLANK)."""
    hud_map = snes.raw("HUD_MAP_data").u16
    return [0x2000 if c == " " else hud_map[29 * 32 + ord(c) - ord("A")] for c in text]


def line(v, row, n):
    """*n* words of the box's text line *row* (1 or 2)."""
    return [v.alert_map.u16[row * 32 + TEXT_COL + k] for k in range(n)]


def short_of_funds(snes):
    """A purchase the purse cannot cover, once the convoy's alert is gone."""
    boot(snes, "MISSION_TEST_QUIET").wait(AFTER_CONVOY)
    snes.write("funds", 0, 1)
    return snes.press("l", "a", frames=3)


def test_the_opponents_convoy_is_announced(snes):
    boot(snes, "MISSION_TEST_QUIET").wait(100)
    v = read_snapshot(snes)
    assert v.alert_cur == CONVOY


def test_only_the_first_convoy_is_announced(snes):
    """ENEMY CONVOY ON THE WAY opens the battle and is not repeated: over a
    minute the quiet opponent buys convoy after convoy, and the alert is up
    for one stretch only."""
    boot(snes, "MISSION_TEST_QUIET")
    showing = []
    for _ in range(360):
        snes.wait(10)
        showing.append(snes.var.alert_cur == CONVOY)
    stretches = sum(1 for a, b in zip([False] + showing, showing) if b and not a)
    assert stretches == 1


def test_an_order_short_of_funds_types_out(snes):
    short_of_funds(snes).wait(60)
    v = read_snapshot(snes)
    assert v.alert_cur == FUNDS
    assert v.alert_state == ALERT_HELD
    assert line(v, 1, 10) == letters(snes, "NOT ENOUGH")
    assert line(v, 2, 5) == letters(snes, "FUNDS")


def test_the_letters_come_two_frames_apart(snes):
    """After the slide, a letter every second frame. (From the first letter:
    the frame the slide ends can be read mid-tick, and whether it shows the
    count at 0 depends on where the loop is when the emulator's frame ends.)
    Read at the frame's end the phase shows too: R65's constant index offset
    folding moved it to 1, 1, 2, 3, 3, 3 (a frame one way and three the
    other), and saving a loop's index register once across a run of calls
    back to 1, 1, 2, 2, 3, 3."""
    short_of_funds(snes)
    seen = []
    for _ in range(30):
        snes.wait(1)
        if snes.var.alert_state == ALERT_TYPING:
            seen.append(snes.var.alert_k)
    first = seen.index(1)
    assert seen[first:first + 6] == [1, 1, 2, 2, 3, 3]


def test_the_portrait_slides_in_from_the_right(snes):
    """Four pixels a tick, read at each frame's end: since R65 folded constant
    index offsets one tick lands a frame early and one a frame late."""
    short_of_funds(snes)
    xs = []
    for _ in range(12):
        snes.wait(1)
        xs.append(snes.var.alert_x)
    slide = [x for x in xs if x > 224]          # under way while the press is held
    assert slide == [248, 244, 236, 232, 232]
    assert xs[len(slide):] == [224] * (len(xs) - len(slide))


def test_the_portrait_is_four_sprites_at_the_bottom_right(snes):
    """Its first sprite is the avatar sheet's first tile (192 in the second
    name block, after the airframe's 96 and the explosions' 96), on OBJ
    palette 6 at priority 3."""
    short_of_funds(snes).wait(40)
    v = read_snapshot(snes)
    oam = v.oam.u8
    slots = [i for i in range(128) if oam[i * 4 + 2] in (192, 196) and oam[i * 4 + 3] == 0x3D]
    assert len(slots) == 1
    i = slots[0]
    assert (oam[i * 4], oam[i * 4 + 1]) == (224, 184)
    assert [oam[(i + k) * 4 + 2] - oam[i * 4 + 2] for k in range(4)] == [0, 2, 32, 34]


def test_alerts_wait_their_turn(snes):
    """FUEL LOW pushed under NOT ENOUGH FUNDS types out after it, in the same
    box: the portrait stays up between them."""
    short_of_funds(snes).wait(20)
    snes.write("airframes__fuel", 26, 1)
    for _ in range(80):
        snes.wait(1)
        if snes.var.alert_qn:
            break
    assert snes.var.alert_cur == FUNDS
    for _ in range(200):
        snes.wait(1)
        if snes.var.alert_cur != FUNDS:
            break
    v = read_snapshot(snes)
    assert v.alert_cur == FUEL_LOW
    assert v.alert_x == 224


def test_the_same_alert_is_not_queued_twice(snes):
    short_of_funds(snes).wait(3)
    snes.press("l", "a", frames=3).wait(3).press("l", "a", frames=3)
    v = read_snapshot(snes)
    assert v.alert_cur == FUNDS
    assert v.alert_qn == 0


def test_a_pause_freezes_the_alert(snes):
    short_of_funds(snes).wait(14).start()
    before = read_snapshot(snes)
    k, x = before.alert_k, before.alert_x
    snes.wait(60)
    v = read_snapshot(snes)
    assert v.game_state == 4
    assert (v.alert_k, v.alert_x) == (k, x)


def test_the_alert_goes_and_the_box_with_it(snes):
    """Typed, held two seconds, slid out: the rows back to the art's
    transparent tile, which is what the map has under them."""
    short_of_funds(snes).wait(300)
    v = read_snapshot(snes)
    assert v.alert_state == ALERT_IDLE
    assert v.alert_up == 0
    clear = snes.raw("HUD_MAP_data").u16[23 * 32]
    assert [v.alert_map.u16[i] for i in range(128)] == [clear] * 128


def test_a_bunker_brought_down_is_announced(snes):
    """The enemy's bunker at 6144 (structs[11]) rammed: it goes to nobody."""
    boot(snes, "MISSION_TEST_QUIET").wait(AFTER_CONVOY)
    snes.write("airframes__x_px", 6144, 2)
    snes.write("airframes__y", 150 * 256, 2)
    snes.wait(20)
    v = read_snapshot(snes)
    assert v.structs__owner.u8[11] == 2
    assert v.alert_cur == ENEMY_LOST_BUNKER


def test_a_reset_clears_the_alert(state):
    """An alert up when the match is lost stays up, frozen; Start restarts
    the match with the box and the queue gone. (The lost match has none up
    of its own by then, so one is planted, held, with another queued.)"""
    snes = state(five_passes)
    snes.write("alert_state", ALERT_HELD, 1)
    snes.write("alert_cur", FUNDS, 2)
    snes.write("alert_q", FUEL_LOW, 2)
    snes.write("alert_qh", 0, 1)
    snes.write("alert_qn", 1, 1)
    snes.write("alert_busy", 1, 1)
    snes.write("alert_up", 1, 1)
    snes.write("alert_x", 224, 2)
    snes.wait(30)
    held = read_snapshot(snes)
    assert (held.alert_state, held.alert_qn) == (ALERT_HELD, 1)   # the battle's over: frozen
    snes.start().wait(10)
    v = read_snapshot(snes)
    assert (v.alert_state, v.alert_qn, v.alert_up) == (ALERT_IDLE, 0, 0)
    clear = snes.raw("HUD_MAP_data").u16[23 * 32]
    assert [v.alert_map.u16[i] for i in range(128)] == [clear] * 128

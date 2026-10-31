"""Phase 11: the campaign - the derived field, the front end, the continue code.

These boot with nothing held, which is the campaign's first mission.
"""

from shared import boot, campaign_lost, campaign_overrun, read_snapshot, screen_colour, title_shot

GAME_PLAYING, GAME_SCREEN = 0, 3
SCREEN_NONE, SCREEN_TITLE, SCREEN_BRIEF, SCREEN_AFTER = 0, 1, 2, 3
BUNKER = 1


def test_mission_first(snes):
    """Cake Walk: row 0 asks for two turrets, one bunker and nothing pre-owned.

    So the derived field is eight buildings west to east - bank, base, turret,
    bunker, the super bunker dead centre, turret, base, bank. The pool must
    come out sorted: the draw cull and the munition test both stop at the
    first building east of what they ask about.
    """
    boot(snes).wait(300)
    v = read_snapshot(snes)
    assert v.mission == 0
    assert v.level_count == 8
    assert v.structs__x.u16[2] == 1536
    assert v.structs__kind.u8[3] == BUNKER
    assert v.structs__x.u16[4] == 4076
    assert v.structs__x.u16[7] == 8064


# The front end: a campaign boot opens on the title page, Start goes to the
# briefing and Start again into the battle. A page is GAME_SCREEN with
# screen_kind saying which, and the field behind it is untouched.

def test_power_on_plays_the_intro_then_the_title(snes):
    """A real power-on - no test flags - plays the BubbleZap intro
    (intro.r65) straight away, the sound driver uploading meanwhile: its
    640 frames, plus the upload of the logo, before the title page goes up.
    """
    snes.until("intro_show", max_frames=400)
    start = snes.frame
    assert start < 30                     # no black screen for the upload first
    snes.until("screen_show", max_frames=800)
    assert 640 <= snes.frame - start < 680


def test_start_skips_the_intro(snes):
    """Start, once the intro has faded in, skips to its fade-out. The sound
    driver uploads while the logo is up (sound.r65's spc_upload_step), so
    what is left of it - most of it, a second in - goes up after, before
    the title: 222 frames from the intro's start, against its 640.
    """
    snes.until("intro_show", max_frames=400)
    start = snes.frame
    snes.wait(60).press("start", frames=4)
    snes.until("screen_show", max_frames=400)
    assert snes.frame - start < 240


def test_the_pad_works_after_the_intro(snes):
    """A real power-on, intro and all, then Start on the title. boot_load
    turned NMI and the auto joypad read on with two read-modify-writes of
    NMITIMEN, which is write-only: after the intro the reads came back 0
    and the second write left the auto read off, so the title saw no
    button. Every other case skips the intro, which is why none caught it.
    """
    snes.until("screen_show", max_frames=900).wait(30)
    snes.start().wait(30)
    v = read_snapshot(snes)
    assert v.game_state == GAME_SCREEN
    assert v.screen_kind == SCREEN_BRIEF


def test_a_campaign_opens_on_the_title(snes):
    boot(snes).wait(30)
    v = read_snapshot(snes)
    assert v.game_state == GAME_SCREEN
    assert v.screen_kind == SCREEN_TITLE


def test_start_goes_to_the_briefing(snes):
    boot(snes).start().wait(30)
    v = read_snapshot(snes)
    assert v.game_state == GAME_SCREEN
    assert v.screen_kind == SCREEN_BRIEF


# Tunes, sound.r65's MUS_* (music_now is the one playing, MUS_NONE 0xFF).
MUS_TITLE, MUS_ORDERS, MUS_NONE = 0, 1, 0xFF


def test_the_briefing_has_its_own_tune(snes):
    """The title plays its theme, the briefing swaps it for its orders, and
    the battle is silent of music."""
    boot(snes).wait(20)
    assert read_snapshot(snes).music_now == MUS_TITLE
    snes.start().wait(30)
    v = read_snapshot(snes)
    assert v.screen_kind == SCREEN_BRIEF
    assert v.music_now == MUS_ORDERS
    snes.start().wait(30)
    assert read_snapshot(snes).music_now == MUS_NONE


def test_start_again_goes_into_the_battle(snes):
    """The battle is the ordinary one: the page gone, the strip back, the
    airframe flying (it has moved east of its start).
    """
    boot(snes).start().wait(10).start().wait(60).right(60)
    v = read_snapshot(snes)
    assert v.game_state == GAME_PLAYING
    assert v.screen_kind == SCREEN_NONE
    assert v.airframes__x_px.u16[0] == 321


def test_the_field_comes_back_after_the_title(snes, tmp_path):
    """The title is Mode 3 and loads its picture over the field's VRAM and
    CGRAM; leaving it puts them back (video_restore), so the battle after
    the briefing is drawn as ever - the sky most of the frame, as on a
    mission booted straight into its battle."""
    boot(snes).start().wait(10).start().wait(60)
    read_snapshot(snes)
    assert screen_colour(snes, tmp_path, (57, 156, 239)) >= 40, "the sky dominates the frame"


def test_title_text_drawn(snes, tmp_path):
    """The title's text is on screen: the menu rows differ from the picture
    where the console font's glyphs are drawn over it (in its entries 34 and
    35, whatever colours the picture gives them)."""
    boot(snes).wait(30)
    read_snapshot(snes)
    _, menu = title_shot(snes, tmp_path)
    assert menu > 300, "the title text is drawn"


# The continue code. The title opens on a menu - NEW GAME, then ENTER CODE -
# and ENTER CODE brings up the code field, where the d-pad types four letters:
# Right moves the cursor, Up and Down run a letter through A..P (a tap steps
# once). Down from A wraps to P, which is letter 15. NKCH is mission 5
# carrying 32: eleven bits of payload and five of check, scrambled and cut
# into four nibbles. Start takes what the page says, so the row's starting
# funds give way to the code's. One letter out (NKCG) is not a near miss: the
# check digits reject it, and Start does nothing with it.
TITLE_MENU, TITLE_CODE = 0, 1


def enter_code(s):
    """From the title's menu to its code field: Down to ENTER CODE, Start."""
    return s.down().start().wait(10)

def type_code(s, code):
    """Type *code* over the title: each letter is Up taps from A, then Right."""
    for i, letter in enumerate(code):
        for _ in range(ord(letter) - ord("A")):
            s.up()
        if i < len(code) - 1:
            s.right()
    return s


def code_text(v):
    """The four letters typed into the code field."""
    return "".join(chr(ord("A") + v.code_letters.u8[i]) for i in range(4))


def test_the_title_opens_on_its_menu(snes):
    """NEW GAME picked; Down picks ENTER CODE, and Start on it brings up
    the code field rather than a briefing."""
    boot(snes).wait(20)
    v = read_snapshot(snes)
    assert v.title_mode == TITLE_MENU
    assert v.title_sel == 0
    enter_code(snes)
    v = read_snapshot(snes)
    assert v.title_mode == TITLE_CODE
    assert v.screen_kind == SCREEN_TITLE


def test_down_from_a_wraps_to_p(snes):
    enter_code(boot(snes).wait(20)).down().right().wait(10)
    v = read_snapshot(snes)
    assert v.code_letters.u8[0] == 15
    assert v.code_cursor == 1


def test_a_continue_code_resumes_its_mission(snes):
    type_code(enter_code(boot(snes).wait(20)), "NKCH").start().wait(20)
    v = read_snapshot(snes)
    assert v.mission == 4
    assert v.start_funds == 32
    assert v.screen_kind == SCREEN_BRIEF


# The briefing, read out of the page shadow (screen_page, 32 words a row). Its
# road (screen_map) is ten stops on row 7 from column 2, three apart: a taken
# stop '#' in the status rows' gold (sub-palette 5), this mission's '@' with a
# '^' under it, the rest 'O', in the font's own (2). The text starts at row 11,
# column 3. A glyph is font tile 96 on, from ASCII 32.
BRIEF_MAP_ROW, BRIEF_MAP_COL, BRIEF_TEXT_ROW, BRIEF_TEXT_COL = 7, 2, 11, 3


def page_glyph(v, row, col):
    """The character at page (row, col) and its BG3 sub-palette."""
    w = v.screen_page.u16[row * 32 + col]
    return chr((w & 0x3FF) - 96 + 32), (w >> 10) & 7


def page_text(v, row, col, n):
    return "".join(page_glyph(v, row, col + k)[0] for k in range(n))


def road(v):
    return "".join(page_glyph(v, BRIEF_MAP_ROW, BRIEF_MAP_COL + 3 * k)[0] for k in range(10))


def test_the_briefing_marks_the_first_stop(snes):
    """A new campaign's briefing: the road with nothing taken, the marker on
    the first stop, and the mission's text under it."""
    boot(snes).start().wait(30)
    v = read_snapshot(snes)
    assert road(v) == "@OOOOOOOOO"
    assert page_glyph(v, BRIEF_MAP_ROW + 1, BRIEF_MAP_COL)[0] == "^"
    assert page_text(v, BRIEF_MAP_ROW - 1, 28, 2) == "10"
    assert page_text(v, BRIEF_TEXT_ROW, BRIEF_TEXT_COL, 26) == "A QUIET STRETCH OF DESERT."
    assert page_text(v, BRIEF_TEXT_ROW + 4, BRIEF_TEXT_COL, 24) == "DRIVE A VAN INTO THEIRS."


def test_the_briefing_road_is_taken_up_to_a_codes_mission(snes):
    """NKCH opens mission 5: the four stops before it are taken, in gold, and
    the road on from it is not."""
    type_code(enter_code(boot(snes).wait(20)), "NKCH").start().wait(20)
    v = read_snapshot(snes)
    assert road(v) == "####@OOOOO"
    assert [page_glyph(v, BRIEF_MAP_ROW, BRIEF_MAP_COL + 3 * k)[1] for k in range(5)] == [5, 5, 5, 5, 2]
    assert page_text(v, BRIEF_MAP_ROW, BRIEF_MAP_COL + 9, 6) == "#==@--"
    assert page_glyph(v, BRIEF_MAP_ROW + 1, BRIEF_MAP_COL + 12)[0] == "^"


def test_a_bad_code_is_refused(snes):
    """Start on a code that names nothing stays on the title, and B goes
    back to the menu."""
    type_code(enter_code(boot(snes).wait(20)), "NKCG").start().wait(20)
    v = read_snapshot(snes)
    assert v.screen_kind == SCREEN_TITLE
    assert v.title_mode == TITLE_CODE
    snes.b().wait(10)
    v = read_snapshot(snes)
    assert v.title_mode == TITLE_MENU


def test_screen_after(state):
    """A match lost with an airframe still up ends on the frozen field, and
    Start there brings up the after-action page.

    It spells the code for the next run - JKDG, this mission again with the
    purse the row deals, since the match was lost - and leaves it typed into
    the title's field. Salvage reads 20: the player's base, all the field it
    still holds.
    """
    snes = state(campaign_overrun)
    v = read_snapshot(snes)
    assert v.game_state == GAME_SCREEN
    assert v.screen_kind == SCREEN_AFTER
    assert v.airframes__lives.u8[0] == 1
    assert v.after_salvage == 20
    assert v.after_carry == 32
    assert code_text(v) == "JKDG"


# The debrief's table (screen_after): headings on row 6, then UNITS DESTROYED,
# CHOPPERS DOWNED and BUILDINGS TAKEN on rows 8-10, the player's figure ending
# on column 21 and the enemy's on 28; PURSE, SALVAGE and CARRIED on 12-14 in
# the player's column.
DEBRIEF_ROW, DEBRIEF_YOU, DEBRIEF_ENEMY = 8, 21, 28


def test_the_debrief_tallies_the_lost_match(state):
    """Three crash landings are three airframes the enemy downed, and nothing
    the player destroyed or took; the page reads the tally (game.r65) as the
    match left it."""
    snes = state(campaign_overrun)
    v = read_snapshot(snes)
    helis = snes.raw("tally_helis").u8           # two bytes: `v.` would read one number
    assert helis[0] == 3
    assert helis[1] == 0
    assert page_text(v, 6, DEBRIEF_YOU - 2, 3) == "YOU"
    assert page_text(v, 6, DEBRIEF_ENEMY - 4, 5) == "ENEMY"
    assert page_text(v, DEBRIEF_ROW, 3, 15) == "UNITS DESTROYED"
    assert page_text(v, DEBRIEF_ROW + 1, 3, 15) == "CHOPPERS DOWNED"
    assert page_glyph(v, DEBRIEF_ROW + 1, DEBRIEF_YOU)[0] == "0"
    assert page_glyph(v, DEBRIEF_ROW + 1, DEBRIEF_ENEMY)[0] == "3"
    assert page_text(v, DEBRIEF_ROW + 5, 3, 7) == "SALVAGE"
    assert page_text(v, DEBRIEF_ROW + 5, DEBRIEF_YOU - 1, 2) == "20"


GAME_WON, SCREEN_END = 1, 4


def test_the_last_victory_is_a_dead_end(snes):
    """Midnight Oasis won (game_state planted - a win cannot be scripted in
    useful time): Start brings up the debrief, and Start again the end page,
    the road with every stop taken and THE END. Nothing leaves it - not
    Start, not any other button."""
    boot(snes, "MISSION_MIDNIGHT_OASIS").wait(10)
    snes.write("game_state", GAME_WON, 1)
    snes.wait(2).start().wait(20)
    assert read_snapshot(snes).screen_kind == SCREEN_AFTER
    snes.start().wait(20)
    v = read_snapshot(snes)
    assert v.game_state == GAME_SCREEN
    assert v.screen_kind == SCREEN_END
    assert road(v) == "##########"
    assert page_text(v, 22, 12, 7) == "THE END"
    snes.start().wait(20).a(1).b(1).x(1).y(1).wait(10).start().wait(30)
    v = read_snapshot(snes)
    assert v.game_state == GAME_SCREEN
    assert v.screen_kind == SCREEN_END


SCREEN_OVER = 5


def test_the_last_airframe_goes_straight_to_game_over(state):
    """Four crash landings: the last airframe's loss plays out as any
    other's, the camera panning home as the screen fades, and then game over
    comes up with no debrief - spelling the debrief's code itself (JKDG,
    this mission with the purse its row deals). The tally still counts the
    four."""
    snes = state(campaign_lost)
    v = read_snapshot(snes)
    assert v.game_state == GAME_SCREEN
    assert v.screen_kind == SCREEN_OVER
    assert v.airframes__lives.u8[0] == 0
    assert snes.raw("tally_helis").u8[0] == 4
    assert page_text(v, 8, 11, 9) == "GAME OVER"
    assert code_text(v) == "JKDG"


def test_a_lost_mission_is_game_over(state):
    """Start on a lost mission's debrief brings up game over, and Start there
    goes back to the title - the debrief's code (JKDG, this mission with the
    purse its row deals) still typed into its field, so ENTER CODE and Start
    fight it again: mission unchanged, 32 to start with.
    """
    snes = state(campaign_overrun)
    snes.start().wait(20)
    v = read_snapshot(snes)
    assert v.screen_kind == SCREEN_OVER
    assert page_text(v, 8, 11, 9) == "GAME OVER"
    snes.start().wait(30)
    v = read_snapshot(snes)
    assert v.screen_kind == SCREEN_TITLE
    assert code_text(v) == "JKDG"
    enter_code(snes).start().wait(20)
    v = read_snapshot(snes)
    assert v.screen_kind == SCREEN_BRIEF
    assert v.mission == 0
    assert v.start_funds == 32

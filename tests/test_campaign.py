"""Phase 11: the campaign - the derived field, the front end, the continue code.

These boot with nothing held, which is the campaign's first mission.
"""

from shared import boot, campaign_lost, read_snapshot, screen_colour

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


def test_start_again_goes_into_the_battle(snes):
    """The battle is the ordinary one: the page gone, the strip back, the
    airframe flying (it has moved east of its start).
    """
    boot(snes).start().wait(10).start().wait(60).right(60)
    v = read_snapshot(snes)
    assert v.game_state == GAME_PLAYING
    assert v.screen_kind == SCREEN_NONE
    assert v.airframes__x_px.u16[0] == 321


def test_title_text_drawn(snes, tmp_path):
    """The title's text is on screen: the console font's white body colour."""
    boot(snes).wait(30)
    read_snapshot(snes)
    assert screen_colour(snes, tmp_path, (255, 255, 255)) > 0.3, "the title text is drawn"


# The continue code. The d-pad types four letters over the title: Right moves
# the cursor, Up and Down run a letter through A..P (a tap steps once). Down
# from A wraps to P, which is letter 15. NKCH is mission 5 carrying 32: eleven
# bits of payload and five of check, scrambled and cut into four nibbles.
# Start takes what the page says, so the row's starting funds give way to the
# code's. One letter out (NKCG) is not a near miss: the check digits reject it
# and Start begins a new campaign.

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


def test_down_from_a_wraps_to_p(snes):
    boot(snes).wait(20).down().right().wait(10)
    v = read_snapshot(snes)
    assert v.code_letters.u8[0] == 15
    assert v.code_cursor == 1


def test_a_continue_code_resumes_its_mission(snes):
    type_code(boot(snes).wait(20), "NKCH").start().wait(20)
    v = read_snapshot(snes)
    assert v.mission == 4
    assert v.start_funds == 32
    assert v.screen_kind == SCREEN_BRIEF


def test_a_bad_code_starts_a_new_campaign(snes):
    type_code(boot(snes).wait(20), "NKCG").start().wait(20)
    v = read_snapshot(snes)
    assert v.mission == 0
    assert v.screen_kind == SCREEN_BRIEF


def test_screen_after(state):
    """The way out: four crash landings spend the four lives, which ends the
    match, and Start on the frozen field brings up the after-action page.

    It spells the code for the next run - JKDG, this mission again with the
    purse the row deals, since the match was lost - and leaves it typed into
    the title's field. Salvage reads 20: the player's base, all the field it
    still holds.
    """
    snes = state(campaign_lost)
    v = read_snapshot(snes)
    assert v.game_state == GAME_SCREEN
    assert v.screen_kind == SCREEN_AFTER
    assert v.airframes__lives.u8[0] == 0
    assert v.after_salvage == 20
    assert v.after_carry == 32
    assert code_text(v) == "JKDG"


def test_campaign_retry(state):
    """Start on the after-action page goes on to the next mission's briefing
    carrying what it settled - or back to the same mission after a defeat,
    which is this: mission unchanged, the purse the row deals.

    (The winning side cannot be scripted in useful time; it was driven through
    the debugger by setting game_state to GAME_WON at a snapshot break.)
    """
    snes = state(campaign_lost)
    snes.start().wait(20)
    v = read_snapshot(snes)
    assert v.mission == 0
    assert v.screen_kind == SCREEN_BRIEF
    assert v.start_funds == 32

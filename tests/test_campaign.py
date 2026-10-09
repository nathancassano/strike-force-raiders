"""Phase 11: the campaign - the derived field, the front end, the continue code.

These boot with nothing held, which is the campaign's first mission.
"""

import pytest

from harness import boot, expect, screen_colour, shot

case = pytest.param
GAME_PLAYING, GAME_SCREEN = 0, 3
SCREEN_NONE, SCREEN_TITLE, SCREEN_BRIEF, SCREEN_AFTER = 0, 1, 2, 3
BUNKER = 1


def test_mission_first(snes):
    # Cake Walk: row 0 asks for two turrets, one bunker and nothing
    # pre-owned, so the derived field is eight buildings west to east - bank,
    # base, turret, bunker, the super bunker dead centre, turret, base, bank.
    # The pool must come out sorted: the draw cull and the munition test both
    # stop at the first building east of what they ask about.
    boot(snes).wait(300)
    shot(snes)
    expect(snes, {"v.mission": 0x00, "v.level_count": 0x08,
                  "v.structs__x.u16[2]": 0x0600, "v.structs__kind.u8[3]": BUNKER,
                  "v.structs__x.u16[4]": 0x0FEC, "v.structs__x.u16[7]": 0x1F80})


# The front end: a campaign boot opens on the title page, Start goes to the
# briefing and Start again into the battle. A page is GAME_SCREEN with
# screen_kind saying which, and the field behind it is untouched.
@pytest.mark.parametrize("script, checks", [
    case(lambda s: boot(s).wait(30), {"v.game_state": GAME_SCREEN, "v.screen_kind": SCREEN_TITLE}, id="screen_title"),
    case(lambda s: boot(s).start().wait(30), {"v.game_state": GAME_SCREEN, "v.screen_kind": SCREEN_BRIEF},
         id="screen_brief"),
    # ... and the battle is the ordinary one: the page gone, the strip back,
    # the airframe flying (it has moved east of its start).
    case(lambda s: boot(s).start().wait(10).start().wait(60).right(60),
         {"v.game_state": GAME_PLAYING, "v.screen_kind": SCREEN_NONE, "v.heli_x_px": 0x0141},
         id="screen_battle"),
])
def test_screens(snes, script, checks):
    script(snes)
    shot(snes)
    expect(snes, checks)


def test_title_text_drawn(snes, tmp_path):
    # The title's text is on screen: the console font's white body colour.
    boot(snes).wait(30)
    shot(snes)
    assert screen_colour(snes, tmp_path, (255, 255, 255)) > 0.3


# The continue code. The d-pad types four letters over the title: Right moves
# the cursor, Up and Down run a letter through A..P (a tap steps once). Down
# from A wraps to P, which is letter 15. NKCH is mission 5 carrying 32: eleven
# bits of payload and five of check, scrambled and cut into four nibbles.
# Start takes what the page says, so the row's starting funds give way to the
# code's. One letter out (NKCG) is not a near miss: the check digits reject it
# and Start begins a new campaign.
def type_code(s, *letters):
    """Type a code over the title: each letter is Up taps from A, then Right."""
    for i, n in enumerate(letters):
        for _ in range(n):
            s.up()
        if i < len(letters) - 1:
            s.right()
    return s


NKCH = (13, 10, 2, 7)          # N K C H
NKCG = (13, 10, 2, 6)          # N K C G


@pytest.mark.parametrize("script, checks", [
    case(lambda s: boot(s).wait(20).down().right().wait(10), {"s.raw('code_letters').u8[0]": 0x0F, "v.code_cursor": 0x01},
         id="code_type"),
    case(lambda s: type_code(boot(s).wait(20), *NKCH).start().wait(20),
         {"v.mission": 0x04, "v.start_funds": 0x20, "v.screen_kind": SCREEN_BRIEF}, id="code_continue"),
    case(lambda s: type_code(boot(s).wait(20), *NKCG).start().wait(20),
         {"v.mission": 0x00, "v.screen_kind": SCREEN_BRIEF},
         id="code_bad"),
])
def test_code(snes, script, checks):
    script(snes)
    shot(snes)
    expect(snes, checks)


def test_screen_after(state):
    # The way out: four crash landings spend the four lives, which ends the
    # match, and Start on the frozen field brings up the after-action page. It
    # spells the code for the next run - JKDG, this mission again with the
    # purse the row deals, since the match was lost - and leaves it typed into
    # the title's field. Salvage reads 20: the player's base, all the field
    # it still holds.
    snes = state("campaign_lost")
    shot(snes)
    code = snes.raw("code_letters")
    expect(snes, {"v.game_state": GAME_SCREEN, "v.screen_kind": SCREEN_AFTER, "v.heli_lives": 0x00,
                  "v.after_salvage": 0x14, "v.after_carry": 0x20})
    assert [code.u8[i] for i in range(4)] == [0x09, 0x0A, 0x03, 0x06]      # J K D G


def test_campaign_retry(state):
    # Start on the after-action page goes on to the next mission's briefing
    # carrying what it settled - or back to the same mission after a defeat,
    # which is this: mission unchanged, the purse the row deals. (The winning
    # side cannot be scripted in useful time; it was driven through the
    # debugger by setting game_state to GAME_WON at a snapshot break.)
    snes = state("campaign_lost")
    snes.start().wait(20)
    shot(snes)
    expect(snes, {"v.mission": 0x00, "v.screen_kind": SCREEN_BRIEF, "v.start_funds": 0x20})

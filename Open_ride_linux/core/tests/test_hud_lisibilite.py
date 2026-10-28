"""Lisibilité du HUD et débordements des panneaux (lot X22) : contraste et hauteur sur des images fabriquées."""

import importlib.util
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"
spec = importlib.util.spec_from_file_location("hud_lisibilite", TESTS / "hud_lisibilite.py")
hl = importlib.util.module_from_spec(spec)
sys.modules["hud_lisibilite"] = hl
spec.loader.exec_module(hl)

BLACK, WHITE = (0, 0, 0), (255, 255, 255)
GREY, LIGHT_GREY = (128, 128, 128), (200, 200, 200)


class Img:
    """Fond uni et « texte » : trois barres verticales de `glyph_h` lignes dans le rectangle (x, y, w, h)."""

    def __init__(self, width, height, bg, fg, rect, glyph_h):
        self.width, self.height, self.bg, self.fg = width, height, bg, fg
        x, y, w, h = rect
        top = y + (h - glyph_h) // 2
        self.bars = [(x + 4 + 10 * i, top, x + 10 + 10 * i, top + glyph_h) for i in range(3)]

    def pixel(self, x, y):
        return self.fg if any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1 in self.bars) else self.bg


def info(**widgets):
    return {"widgets": {k: {"visible": True, "text": t, "rect": r} for k, (t, r) in widgets.items()}}


def test_contrast_ratios_of_the_wcag():
    assert hl.contrast_ratio(WHITE, BLACK) == pytest.approx(21.0)
    assert hl.contrast_ratio(BLACK, BLACK) == pytest.approx(1.0)
    assert hl.contrast_ratio(GREY, LIGHT_GREY) < hl.LABEL_CONTRAST


def test_white_on_black_passes_grey_on_light_grey_fails():
    rect = [100, 50, 60, 40]
    good = hl.measure_text(Img(1280, 720, BLACK, WHITE, rect, 30), rect)
    assert good["contrast"] == pytest.approx(21.0) and good["height_px"] == 30
    checks = dict((n, ok) for n, ok, _ in hl.readability_checks(
        Img(1280, 720, LIGHT_GREY, GREY, rect, 30), info(power=("250", rect), power_caption=("PUISSANCE (W)", rect))))
    assert checks == {"hauteur des chiffres power": True, "contraste power": False, "contraste power_caption": False}


def test_digit_height_is_scaled_to_1080_lines():
    rect = [100, 50, 60, 40]
    # 20 lignes sur 720 : 30 px pour 1080 lignes, lisible ; 18 lignes : 27 px, trop petit.
    ok = hl.readability_checks(Img(1280, 720, BLACK, WHITE, rect, 20), info(speed=("28.8", rect)))
    small = hl.readability_checks(Img(1280, 720, BLACK, WHITE, rect, 18), info(speed=("28.8", rect)))
    assert ok[0][:2] == ("hauteur des chiffres speed", True) and "30 px" in ok[0][2]
    assert small[0][:2] == ("hauteur des chiffres speed", False) and "27 px" in small[0][2]


def test_no_value_and_hidden_widgets_are_skipped():
    rect = [100, 50, 60, 40]
    img = Img(1280, 720, BLACK, WHITE, rect, 30)
    data = info(power=("--", rect), hr=("140", rect))
    data["widgets"]["hr"]["visible"] = False
    assert hl.readability_checks(img, data) == []


def test_panels_inside_the_screen_without_overlap():
    base = info(panel_right=("", [960, 20, 300, 320]), segment_panel=("", [960, 350, 300, 100]),
                bonus_panel=("", [960, 460, 300, 72]), bots_panel=("", [960, 542, 300, 50]),
                profile=("", [40, 600, 1200, 120]))
    assert [ok for _, ok, _ in hl.panel_checks(base, 1280, 720)] == [True, True]
    # Encart des bots volontairement trop grand : il déborde de l'écran et recouvre le profil.
    base["widgets"]["bots_panel"]["rect"] = [960, 542, 300, 400]
    (_, inside, out_msg), (_, apart, pairs) = hl.panel_checks(base, 1280, 720)
    assert not inside and "bots_panel" in out_msg
    assert not apart and pairs == "bots_panel/profile"

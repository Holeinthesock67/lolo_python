"""Guidage des essais : bips du compte à rebours, journal, écran, matériel de chaque essai."""

import io
import json
import wave

from openride_core.tools import guide as gd


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make(tmp_path, screen=False):
    clock = Clock()
    g = gd.Guide("Essai", tmp_path / "guide.jsonl", sound=False, screen=screen, out=io.StringIO(), clock=clock)
    return g, clock


def test_countdown_beeps_once_each_then_end(tmp_path):
    g, clock = make(tmp_path)
    g.step("pente 4 %", 10, "garde 85 rpm", index=2, total=7)
    for t in (5.0, 7.2, 7.5, 8.1, 9.0, 9.5, 10.0, 11.0):
        clock.now = t
        g.tick()
    assert g.sound.played == ["debut", "compte", "compte", "compte", "fin"]
    g.step("court", 2)          # trop court pour un compte 3, 2, 1 : seulement début et fin
    clock.now += 3.0
    g.tick()
    assert g.sound.played[-2:] == ["debut", "fin"]


def test_journal_lines_and_plain_output(tmp_path):
    g, clock = make(tmp_path)
    g.step("Appuie sur +", 30, index=1, total=6)
    clock.now = 1.5
    g.measure("plus", "PLUS_SHORT reçu", ok=True)
    g.alert("Boîtier gauche muet")
    g.finish(True, "tout passe")
    g.close()
    rows = [json.loads(line) for line in (tmp_path / "guide.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["type"] for r in rows] == ["etape", "releve", "alerte", "fin_etape", "verdict"]
    assert rows[1]["t_s"] == 1.5 and rows[1]["ok"] is True and rows[3]["duree_s"] == 1.5
    text = g.out.getvalue()
    assert ">>> [1/6] Appuie sur + (30)" in text and "OK  plus : PLUS_SHORT reçu" in text
    assert "!!! Boîtier gauche muet" in text and "=== tout passe" in text
    assert g.sound.played == ["debut", "alerte", "reussite"]


def test_screen_shows_big_countdown_live_values_and_banner(tmp_path):
    g, clock = make(tmp_path, screen=True)
    g.step("pente 4 %", 75, "garde 85 rpm", index=2, total=7)
    clock.now = 10.0
    g.tick({"puissance": "206 W", "cadence": "84 rpm"})
    g.alert("Cadence 70 rpm", beep=False)
    screen = "\n".join(g.render())
    assert "Étape 2/7" in screen and "PENTE 4 %" in screen and "Cadence 70 rpm" in screen
    assert "206 W" in screen
    assert gd.big_text("1:05")[0] in screen          # 65 s restantes, en grands chiffres
    assert g.out.getvalue().count("\033[2J") >= 2    # écran redessiné
    assert gd.clock_text(65) == "1:05" and gd.clock_text(9.2) == "10" and gd.clock_text(-3) == "0"


def test_prepare_lists_materials_and_waits(tmp_path):
    g, _clock = make(tmp_path)
    asked = []
    g.prepare("click_recette", wait=True, auto_s=0, ask=asked.append)
    assert asked and "piles chargées" in g.out.getvalue()


def test_materials_cover_each_trial_and_wav_is_valid(tmp_path):
    text = gd.materials_text()
    for key, trial in gd.TRIALS.items():
        assert trial.title in text and all(c in text for c in trial.commands), key
    assert gd.main(["materiel", "inconnu"]) == 2
    path = tmp_path / "bip.wav"
    path.write_bytes(gd.wav_bytes(gd.BEEPS["fin"]))
    with wave.open(str(path)) as w:
        assert w.getframerate() == gd.RATE and abs(w.getnframes() / gd.RATE - 0.30) < 0.01

"""Appui long du Click V2 perdu dans une rafale (constat R14 du 8 novembre).

Bouton maintenu, le Click V2 envoie une suite d'appuis et de relâchements toutes les 0,2 à 0,3 s
(20 PLUS_SHORT en 4,5 s au journal) au lieu d'un seul appui : `PressClassifier(repeat_gap_s=…)`
regroupe la rafale en un seul appui long, sans perdre les vrais appuis courts répétés.
"""

from __future__ import annotations

from openride_core import zwift_click
from openride_core.ble_sim import keypad_message
from openride_core.input_providers import ClickPair, ZwiftClickProvider
from openride_core.zwift_click import ClickButtons, InputEvent, PressClassifier

GAP = zwift_click.REPEAT_GAP_S


def burst(c: PressClassifier, button: str, start: float, count: int, period: float = 0.225,
          down: float = 0.05) -> list[InputEvent]:
    """`count` appuis de `down` s toutes les `period` s, comme le Click maintenu ; événements rendus."""
    out: list[InputEvent] = []
    for i in range(count):
        t = start + i * period
        out += [e for e, _ in c.update_timed(button, True, t)]
        out += [e for e, _ in c.update_timed(button, False, t + down)]
        out += c.poll(t + down + 0.01)
    return out


def test_r14_burst_of_twenty_is_one_long_press():
    """Le journal R14 : 20 appuis en 4,5 s = un seul PLUS_LONG, publié après la fin de la rafale."""
    c = PressClassifier(repeat_gap_s=GAP)
    assert burst(c, "PLUS", 0.0, 20) == []           # rien tant que la rafale dure
    end = 19 * 0.225 + 0.05
    assert c.poll(end + GAP / 2) == []
    assert c.poll(end + GAP + 0.01) == [InputEvent.PLUS_LONG]
    assert c.poll(end + 5.0) == []                   # une seule fois


def test_bursts_of_each_long_button_and_r14_spacings():
    """+, −, A et Z ; écarts irréguliers du journal (0,21 à 0,30 s) ; maintiens de 1 à 3 s."""
    for button in ("PLUS", "MINUS", "A", "Z"):
        for hold in (1.0, 2.0, 3.0):
            c = PressClassifier(repeat_gap_s=GAP)
            t, evs = 0.0, []
            spacings = (0.21, 0.30, 0.24, 0.27)
            i = 0
            while True:   # le dernier relâchement de la rafale tombe au vrai relâchement du bouton
                last = t + spacings[i % len(spacings)] >= hold
                evs += [e for e, _ in c.update_timed(button, True, t)]
                evs += [e for e, _ in c.update_timed(button, False, hold if last else t + 0.05)]
                if last:
                    break
                t += spacings[i % len(spacings)]
                i += 1
                evs += c.poll(t - 0.01)
            t = hold
            evs += c.poll(t + GAP + 0.5)
            assert evs == [InputEvent[f"{button}_LONG"]], (button, hold, evs)


def test_real_short_taps_are_not_lost():
    """Appuis courts répétés : chacun garde son événement, regroupés ou non."""
    c = PressClassifier(repeat_gap_s=GAP)
    # Trois tapes rapides (une rafale de 0,6 s, sous le seuil long) : trois PLUS_SHORT.
    assert burst(c, "PLUS", 0.0, 3, period=0.25, down=0.08) == []
    assert c.poll(0.58 + GAP + 0.01) == [InputEvent.PLUS_SHORT] * 3
    # Tapes espacées de plus que l'écart : une par une, chacune après l'écart.
    evs = []
    for k in range(4):
        t = 5.0 + k * 0.6
        c.update("PLUS", True, t)
        c.update("PLUS", False, t + 0.1)
        evs += c.poll(t + 0.1 + GAP + 0.01)
    assert evs == [InputEvent.PLUS_SHORT] * 4


def test_single_press_keeps_the_old_thresholds():
    """Un seul appui (sans rafale) : seuils SRS §4.2 inchangés, publiés après l'écart de rafale."""
    c = PressClassifier(repeat_gap_s=GAP)
    c.update("MINUS", True, 0.0)
    assert c.update("MINUS", False, 1.2) is None
    assert c.poll(1.2 + GAP + 0.01) == [InputEvent.MINUS_LONG]
    c.update("PLUS", True, 5.0)
    c.update("PLUS", False, 5.7)
    assert c.poll(5.7 + GAP + 0.01) == [InputEvent.PLUS_UNCLEAR]
    c.update("A", True, 8.0)
    c.update("A", False, 8.7)
    assert c.poll(8.7 + GAP + 0.01) == []            # zone morte de A : rien


def test_next_notification_after_the_gap_also_ends_the_burst():
    """Sans `poll`, la notification suivante (bouton relâché) finit la rafale, à l'heure du relâchement."""
    c = PressClassifier(repeat_gap_s=GAP)
    c.feed(ClickButtons(True, False), 0.0)
    c.feed(ClickButtons(False, False), 0.1)
    assert c.feed_timed(ClickButtons(False, False), 0.1 + GAP + 0.05) == [(InputEvent.PLUS_SHORT, 0.1)]
    # Nouvel appui après l'écart : l'ancien finit, le nouveau commence.
    c.feed(ClickButtons(True, False), 2.0)
    c.feed(ClickButtons(False, False), 2.1)
    assert c.feed(ClickButtons(True, False), 3.0) == [InputEvent.PLUS_SHORT]


def test_arrows_are_not_delayed_y_is_grouped_like_long_buttons():
    """Les flèches n'ont pas d'appui long : pas de délai. Y en a un depuis la révision 1.11 (demi-tour) : sa
    rafale est regroupée comme celles de +, −, A et Z, et une rafale de 0,9 s ou plus donne Y_LONG."""
    c = PressClassifier(repeat_gap_s=GAP)
    c.feed(ClickButtons(False, False, up_pressed=True), 0.2)
    assert c.feed(ClickButtons(False, False), 0.25) == [InputEvent.UP_SHORT]
    c.feed(ClickButtons(False, False, y_pressed=True), 1.0)
    assert c.feed(ClickButtons(False, False), 1.1) == []
    assert c.poll(1.1 + GAP + 0.05) == [InputEvent.Y_SHORT]
    t = 3.0
    for _ in range(5):   # Y maintenu en rafale : appuis et relâchements toutes les 0,25 s
        c.feed(ClickButtons(False, False, y_pressed=True), t)
        c.feed(ClickButtons(False, False), t + 0.2)
        t += 0.25
    assert c.poll(t + GAP) == [InputEvent.Y_LONG]


def test_gap_zero_is_the_previous_behaviour():
    """`click_repeat_gap_s = 0` : événement dès le relâchement, la rafale reste une suite de courts."""
    c = PressClassifier(repeat_gap_s=0.0)
    evs = []
    for i in range(5):
        c.update("PLUS", True, i * 0.225)
        ev = c.update("PLUS", False, i * 0.225 + 0.05)
        evs.append(ev)
    assert evs == [InputEvent.PLUS_SHORT] * 5
    assert c.poll(10.0) == []


def test_provider_publishes_one_long_and_the_pair_drops_the_relay():
    """Fournisseur réel : la rafale relayée par les deux boîtiers donne un seul PLUS_LONG au jeu."""
    clock = [0.0]
    pair = ClickPair()
    right = ZwiftClickProvider(pair=pair, clock=lambda: clock[0], repeat_gap_s=GAP)
    left = ZwiftClickProvider(pair=pair, clock=lambda: clock[0], optional=True, repeat_gap_s=GAP)
    down, up = keypad_message(True, False), keypad_message(False, False)
    for i in range(8):
        t = i * 0.225
        for prov, lag in ((right, 0.0), (left, 0.02)):   # relais du gauche : 5 à 40 ms plus tard
            clock[0] = t + lag
            prov._on_async(None, bytearray(down))
            clock[0] = t + 0.05 + lag
            prov._on_async(None, bytearray(up))
    assert right.events.empty() and left.events.empty()
    # Tours de boucle (0,2 s) qui ne tombent pas en même temps pour les deux boîtiers.
    clock[0] = 7 * 0.225 + 0.05 + GAP + 0.03
    right._emit(right._classifier.poll_timed(clock[0]), clock[0])
    clock[0] += 0.19
    left._emit(left._classifier.poll_timed(clock[0]), clock[0])
    got = [q.get_nowait() for q in (right.events, left.events) for _ in range(q.qsize())]
    assert got == [InputEvent.PLUS_LONG]


def test_config_key_and_session_pass_the_gap():
    from openride_core.config import from_dict
    from openride_core.session import build_inputs

    cfg = from_dict({"drivers": {"input": "click", "click_repeat_gap_s": 0.2}})
    provs = [p for p in build_inputs(cfg) if isinstance(p, ZwiftClickProvider)]
    assert provs and all(p._classifier.repeat_gap_s == 0.2 for p in provs)
    assert from_dict({}).drivers.click_repeat_gap_s == 0.0   # essai du 8 novembre : pas de regroupement par défaut


def test_click_recette_long_press_mode_in_simulation(tmp_path):
    """`click_recette --appuis-longs` : seulement les 13 maintiens guidés, sans surveillance, et trames.csv."""
    from openride_core.tools import click_recette

    assert [s.key for s in click_recette.LONG_STEPS] == ["plus_long", "minus_long", "a_long", "z_long",
                                                         "plus_rapides"]
    out = tmp_path / "al"
    assert click_recette.main(["--appuis-longs", "--sim", "--sans-attente", "--muet", "--out", str(out)]) == 0
    report = (out / "resume.txt").read_text(encoding="utf-8")
    assert "5 étape(s) OK sur 5" in report and "Appuie brièvement" not in report
    lines = (out / "trames.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "t_s;boitier;trame;evenement"
    assert sum(line.endswith(";PLUS_LONG") for line in lines) >= 1

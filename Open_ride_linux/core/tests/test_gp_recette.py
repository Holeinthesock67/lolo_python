"""Bilan de la recette du Grand Prix des objets (lot GP11) : couverture des objets, pente envoyée, formats."""

import json

import pytest

from openride_core.grandprix.items import ITEM_IDS
from openride_core.tools import gp_recette as gr
from test_grandprix_session import ME, env  # noqa: F401  (fixture de la vraie séance du lot GP2)

T0 = 1_800_000_000.0


def journal(tmp_path, name, *, laps=None, items=ITEM_IDS, events=(), grades=None, winds=None, fin=True):
    """Journal synthétique : `gp_start`, échantillons à 1 Hz, lignes `gp` (`(dt, event, rider, item, extra)`)."""
    lines = [{"kind": "header", "version": 1},
             {"kind": "gp_start", "ts": T0, "opponents": 2, "length_m": 5000.0 if laps is None else 6000.0,
              "laps": laps, "chaos": "normal", "box_every_m": 1500, "items": list(items), "boxes": []}]
    grades = grades if grades is not None else [1.0] * 120
    for i, g in enumerate(grades):
        rec = {"kind": "record", "ts": T0 + i, "t": float(i), "grade_sent": g}
        if winds is not None:
            rec["wind_grade_pct"] = winds[i]
        lines.append(rec)
    for dt, event, rider, item, *extra in events:
        lines.append({"kind": "gp", "t": dt, "event": event, "rider": rider, "item": item, "ts": T0 + dt,
                      **(extra[0] if extra else {})})
    if fin:
        lines.append({"kind": "gp_summary", "ts": T0 + 120, "place": 2, "of": 3, "dodged": 1})
    path = tmp_path / name
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    return path


def full_events():
    """Chaque objet utilisé par le cycliste, et chaque objet qui peut toucher subi au moins une fois."""
    ev, t = [], 1.0
    for item in ITEM_IDS:
        ev.append((t, "use", "me", item))
        t += 1.0
    for item in ("bottle", "bottle_x3", "musette", "musette_x3", "homing", "storm", "star", "bell", "headwind"):
        ev.append((t, "hit", "me", item, {"by": "b1", "loss_s": 3.0}))
        t += 1.0
    ev.append((t, "use", "b1", "stealth"))
    ev.append((t, "steal", "b1", "gel", {"target": "me"}))   # le vol compte pour le Furtif, pas pour l'objet volé
    return ev


def test_couverture_complete_et_deux_formats(tmp_path):
    a = journal(tmp_path, "a.jsonl", laps=3, events=full_events())
    b = journal(tmp_path, "b.jsonl")
    courses = gr.lire(a) + gr.lire(b)
    bil = gr.bilan(courses)
    assert bil["ok"], gr.texte(bil)
    lignes = {o["item"]: o for o in bil["objets"]}
    assert lignes["stealth"]["subi"] == 1 and lignes["gel"]["subi"] == 0
    assert not lignes["gel"]["a_subir"] and not lignes["team_car"]["a_subir"]
    assert lignes["stealth"]["a_subir"] and lignes["bell"]["a_subir"]
    assert gr.main([str(a), str(b)]) == 0


def test_manques_signales(tmp_path, capsys):
    a = journal(tmp_path, "a.jsonl", items=("gel", "bottle"), events=[(5.0, "use", "me", "gel")])
    assert gr.main([str(a)]) == 1
    out = capsys.readouterr().out
    assert "Reste à faire : une course sur circuit." in out
    assert "Reste à utiliser : Bidon glissant." in out
    assert "Reste à subir : Bidon glissant." in out
    assert "Non joués" in out and "Super-forme" in out


def test_objet_bot_ne_compte_pas_pour_le_cycliste(tmp_path):
    a = journal(tmp_path, "a.jsonl", items=("musette",), events=[(5.0, "use", "b1", "musette"),
                                                                 (6.0, "hit", "b2", "musette")])
    lignes = {l.item: l for l in gr.couverture(gr.lire(a))}
    assert lignes["musette"].utilise == 0 and lignes["musette"].subi == 0 and not lignes["musette"].ok


def test_pente_lisse_autour_d_un_coup(tmp_path):
    grades = [1.0 + 0.2 * (i % 5) for i in range(120)]      # route vallonnée : pas de 0,2 à 0,8 point
    a = journal(tmp_path, "a.jsonl", events=[(60.0, "hit", "me", "bottle")], grades=grades, winds=[0.5] * 120)
    (k,) = gr.coups(gr.lire(a)[0])
    assert k.ok and k.pas_pente <= k.seuil_pente


def test_a_coup_de_pente_detecte(tmp_path):
    grades = [1.0] * 120
    grades[62] = 3.0                                      # saut de 2 points juste après le coup
    a = journal(tmp_path, "a.jsonl", events=[(60.0, "hit", "me", "bottle")], grades=grades)
    (k,) = gr.coups(gr.lire(a)[0])
    assert not k.ok and k.pas_pente == pytest.approx(2.0)
    assert "À-COUP ?" in gr.texte(gr.bilan(gr.lire(a)))


def test_a_coup_du_supplement_detecte(tmp_path):
    winds = [0.0] * 120
    winds[61] = 1.0                                       # supplément de vent et d'abri : + 1 point en 1 s
    a = journal(tmp_path, "a.jsonl", events=[(60.0, "hit", "me", "storm")], winds=winds)
    (k,) = gr.coups(gr.lire(a)[0])
    assert not k.ok and k.pas_supplement == pytest.approx(1.0)


def test_dossier_dernieres_courses(tmp_path, capsys):
    d = tmp_path / "journaux"
    d.mkdir()
    journal(d, "a.jsonl", laps=2, events=full_events())
    (d / "classique.jsonl").write_text(json.dumps({"kind": "header", "version": 1}) + "\n", encoding="utf-8")
    assert [p.name for p in gr.journaux_gp(d)] == ["a.jsonl"]
    assert gr.main(["--dossier", str(d), "--dernieres", "5", "--json"]) == 1   # pas de course en ligne
    bil = json.loads(capsys.readouterr().out)
    assert bil["formats"] == {"circuit": True, "en_ligne": False}


def test_aucune_course(tmp_path):
    p = tmp_path / "vide.jsonl"
    p.write_text(json.dumps({"kind": "header", "version": 1}) + "\n", encoding="utf-8")
    assert gr.main([str(p)]) == 2



def test_vraie_seance_circuit_lue_par_le_bilan(env):
    """Course de 3 tours à 4 bots jouée par la vraie séance : le bilan lit le journal écrit par le core."""
    make, run, frame, tmp_path = env
    s, sent, errors = make(6820)
    s._on_command("start", {"mode": "grandprix"}, 2)
    me = s.grandprix.racers[ME]
    me.held, me.charges = "musette_x3", 3

    def press(sess):
        frame(sess)
        if sess.state.gp and sess.state.gp["held"]:
            sess._grandprix_press("Z_SHORT")

    run(s, 1200, press)
    assert s.state.session_state == "FINISHED" and not errors
    (course,) = gr.lire(next((tmp_path / "journal").glob("*.jsonl")))
    assert course.circuit and course.fin is not None and course.echantillons
    assert course.format() == "circuit, 3 tour(s)"
    bil = gr.bilan([course])
    lignes = {o["item"]: o for o in bil["objets"]}
    assert lignes["musette_x3"]["utilise"] == 3
    assert bil["courses"][0]["pente_ok"]                  # aucun objet ne touche la pente envoyée (plan GP §7)
    assert bil["formats"] == {"circuit": True, "en_ligne": False} and not bil["ok"]

"""Lot EP2 : essais physiques guidés par le journal du jeu (fiches, déclencheurs, déroulé)."""

import json

import pytest

from openride_core import seance_file, track
from openride_core.tools import essai_physique as EP


def fiche(**over):
    data = {"id": "x", "but": "tester", "questions": ["note ?"],
            "commandes": [{"cmd": "select_route", "args": {"route_id": "col"}}, {"cmd": "start"}],
            "etapes": [{"quand": {"kind": "event", "event": "start"}, "dire": "Roule à {cible} watts."},
                       {"quand": {"kind": "gp", "event": "box", "rider": "me"}, "dire": "Objet.",
                        "attendu": {"kind": "gp", "event": "use", "rider": "me"}, "delai_s": 20,
                        "rappel": "Z !"},
                       {"quand": {"kind": "record", "distance>=": 500}, "dire": "500 m."}]}
    data.update(over)
    return EP.lire_fiche(data)


def rec(t, d=0.0, **kw):
    return {"kind": "record", "t": t, "distance": d, **kw}


def test_bundled_fiches_are_valid_and_launchable():
    toutes = EP.fiches()
    assert {"gp-voies", "velodrome-elimination", "rogue-depart"} <= set(toutes)
    for f in toutes.values():
        assert f.but and f.duree_max_s <= 600 and 1 <= len(f.questions) <= 3
        seance_file.check([{"cmd": n, "args": a} for n, a in f.commandes])
        for name, args in f.commandes:   # épreuves de piste valides pour le core
            if args.get("mode") == "track":
                track.check(args["track"]["event"], {k: v for k, v in args["track"].items() if k != "event"})
    assert toutes["rogue-depart"].route_id is None and toutes["gp-voies"].route_id == "demo-circuit"


@pytest.mark.parametrize("over, why", [
    ({"but": " "}, "'but' vide"),
    ({"duree_max_s": 900}, "duree_max_s"),
    ({"etapes": []}, "aucune étape"),
    ({"questions": []}, "questions"),
    ({"etapes": [{"quand": {}, "dire": "x"}]}, "table non vide"),
    ({"etapes": [{"quand": {"t>=": "dix"}, "dire": "x"}]}, "compare un nombre"),
    ({"commandes": [{"cmd": "select_route"}]}, "finit par 'start'"),
])
def test_bad_fiches_are_refused(over, why):
    with pytest.raises(EP.FicheError, match=why):
        fiche(**over)


def test_predicates():
    assert EP.correspond({"kind": "rogue", "phase!=": "WARMUP"}, {"kind": "rogue", "phase": "ROOM"})
    assert not EP.correspond({"kind": "rogue", "phase!=": "WARMUP"}, {"kind": "rogue", "phase": "WARMUP"})
    assert EP.correspond({"distance>=": 500}, {"distance": 500.0})
    assert not EP.correspond({"distance>=": 500}, {"distance": "500"})
    assert not EP.correspond({"rider": "me"}, {"kind": "gp"})


def test_watts_are_direct_and_rounded():
    assert EP.watts("Roule à {cible} W, puis {cible:120} W.", 103) == "Roule à 105 W, puis 125 W."


def test_steps_follow_the_game_not_the_clock():
    d = EP.Deroule(fiche(), 100)
    assert d.lire({"kind": "header", "route_id": "col"}) == []
    assert d.lire(rec(0.0)) == []                         # rien avant le vrai départ
    assert [a.texte for a in d.lire({"kind": "event", "event": "start"})] == ["Roule à 100 watts."]
    assert d.lire(rec(60.0, 400.0)) == []                 # l'étape 2 attend une boîte, la distance ne compte pas
    assert [a.sorte for a in d.lire({"kind": "gp", "event": "box", "rider": "me", "t": 3.0})] == ["consigne"]
    assert [a.texte for a in d.lire(rec(85.0, 600.0))] == ["Z !"]   # 20 s sans Z : un seul rappel
    assert [a.sorte for a in d.lire({"kind": "gp", "event": "use", "rider": "me"})] == ["vu"]
    assert [a.texte for a in d.lire(rec(86.0, 610.0))] == ["500 m."]
    assert d.vus == 1 and not d.fini


def test_reminder_once_then_next_step():
    d = EP.Deroule(fiche(), 100)
    d.lire({"kind": "event", "event": "start"})
    d.lire({"kind": "gp", "event": "box", "rider": "me"})
    assert [a.sorte for a in d.lire(rec(21.0))] == ["rappel"]
    assert [a.sorte for a in d.lire(rec(42.0, 900.0))] == ["consigne"]   # pas de 2e rappel : étape suivante
    assert d.vus == 0


def test_missing_trigger_is_skipped_after_attente_max():
    d = EP.Deroule(fiche(), 100)
    d.lire({"kind": "event", "event": "start"})
    assert [a.sorte for a in d.lire(rec(EP.ATTENTE_MAX_S + 1))] == ["saute"]
    assert d.sautes == 1 and d.i == 2


def test_wrong_terrain_stops():
    d = EP.Deroule(fiche(), 100)
    acts = d.lire({"kind": "header", "route_id": "alpe"})
    assert acts[0].sorte == "terrain" and d.fini


def test_ends_after_ten_minutes_of_riding_time():
    d = EP.Deroule(fiche(), 100)
    assert d.lire(rec(599.0)) == [] or not d.fini
    assert [a.sorte for a in d.lire(rec(600.0))][-1] == "fin" and d.fini


def test_game_time_of_mode_lines_is_not_session_time():
    d = EP.Deroule(fiche(), 100)
    d.lire({"kind": "track", "event": "lap", "t": 900.0})
    assert not d.fini and d.t == 0.0


def test_average_of_real_sessions_only(tmp_path):
    def write(name, source, power, n=150):
        lines = [{"kind": "header", "source": source}] + [rec(i, power=power) for i in range(n)]
        (tmp_path / name).write_text("\n".join(json.dumps(x) for x in lines))
    write("a.jsonl", "live", 100.0)
    write("b.jsonl", "simulated", 300.0)
    write("c.jsonl", "live", 110.0)
    write("court.jsonl", "live", 500.0, n=30)
    assert EP.moyenne_reelle(tmp_path.glob("*.jsonl")) == pytest.approx(105.0)
    assert EP.moyenne_reelle([]) is None


def test_cli_lists_and_shows(capsys):
    assert EP.main(["liste"]) == 0 and "gp-voies" in capsys.readouterr().out
    assert EP.main(["voir", "gp-voies"]) == 0 and "demo-circuit" in capsys.readouterr().out
    assert EP.main(["voir", "absent"]) == 2

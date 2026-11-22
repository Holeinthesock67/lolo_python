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
    assert d.lire(rec(0.0, 600.0)) == []                  # rien avant le vrai départ
    assert [a.texte for a in d.lire({"kind": "event", "event": "start"})] == ["Roule à 100 watts."]
    assert d.lire(rec(60.0, 400.0)) == []
    assert [a.sorte for a in d.lire({"kind": "gp", "event": "box", "rider": "me", "t": 3.0})] == ["consigne"]
    # 20 s sans Z : un seul rappel ; la distance de 500 m part au même instant, dans l'ordre du jeu
    assert [a.texte for a in d.lire(rec(85.0, 600.0))] == ["Z !", "500 m."]
    assert [a.sorte for a in d.lire({"kind": "gp", "event": "use", "rider": "me"})] == ["vu"]
    assert d.vus == 1 and d.sautes == 0 and not d.fini


def test_steps_fire_in_game_order_not_fiche_order():
    d = EP.Deroule(fiche(), 100)
    d.lire({"kind": "event", "event": "start"})
    assert [a.texte for a in d.lire(rec(30.0, 520.0))] == ["500 m."]   # avant toute boîte
    assert [a.texte for a in d.lire({"kind": "gp", "event": "box", "rider": "me"})] == ["Objet."]


def test_reminder_once_then_silence():
    d = EP.Deroule(fiche(), 100)
    d.lire({"kind": "event", "event": "start"})
    d.lire({"kind": "gp", "event": "box", "rider": "me"})
    assert [a.sorte for a in d.lire(rec(21.0))] == ["rappel"]
    assert d.lire(rec(42.0)) == []                      # pas de 2e rappel
    assert d.vus == 0


def test_missing_trigger_stays_silent():
    d = EP.Deroule(fiche(), 100)
    d.lire({"kind": "event", "event": "start"})
    assert d.lire(rec(EP.ATTENTE_MAX_S + 1)) == []      # rien d'annoncé en roulant
    assert d.sautes == 2 and d.i == 1


def test_time_step_waits_after_a_consigne():
    f = fiche(etapes=[{"quand": {"kind": "event", "event": "start"}, "dire": "Go."},
                      {"quand": {"kind": "record", "t>=": 1}, "dire": "Temps."}])
    d = EP.Deroule(f, 100)
    d.lire(rec(0.0))
    d.lire({"kind": "event", "event": "start"})
    assert d.lire(rec(2.0)) == []                        # 8 s de calme après « Go. »
    assert [a.texte for a in d.lire(rec(9.0))] == ["Temps."]


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


# --- cohérence consigne / bots (essai du 21 novembre : consigne 125 W, bots à 140 W) ---------------------

def _fiche_gp(**extra):
    data = {"id": "x", "but": "essai", "questions": ["note ?"],
            "commandes": [{"cmd": "select_route", "args": {"route_id": "demo-circuit"}},
                          {"cmd": "start", "args": {"mode": "grandprix"}}],
            "etapes": [{"quand": {"kind": "event", "event": "start"}, "dire": "{cible} watts"}],
            "config": {"depart": {"echauffement_min": 0}}}
    config = {**data["config"], **extra.pop("config", {})}
    data.update(extra, config=config)
    return data


def test_bots_sans_reglage_sur_la_consigne_refuses():
    with pytest.raises(EP.FicheError, match="bots_cible_pct"):
        EP.lire_fiche(_fiche_gp())


def test_niveau_fixe_des_bots_refuse():
    with pytest.raises(EP.FicheError, match="level_pct fixe"):
        EP.lire_fiche(_fiche_gp(bots_cible_pct=100, config={"bots": {"level_pct": 80}}))


def test_consigne_du_depart_loin_des_bots_refusee():
    with pytest.raises(EP.FicheError, match="consigne du départ"):
        EP.lire_fiche(_fiche_gp(bots_cible_pct=130))


def test_niveau_des_bots_calcule_sur_la_consigne():
    f = EP.lire_fiche(_fiche_gp(bots_cible_pct=100, bots_duree_s=1200, config={"bots": {"objective": "tempo"}}))
    from openride_core.bot_effort import curve_pct
    niveau = EP.niveau_bots(f, 125.0, 250.0)
    effort_w = 250.0 * 0.80 * curve_pct(1200) / 100.0 * niveau / 100.0
    assert abs(effort_w - 125.0) < 2.0


def test_niveau_des_bots_borne():
    f = EP.lire_fiche(_fiche_gp(bots_cible_pct=100))
    assert EP.niveau_bots(f, 400.0, 100.0) == 150 and EP.niveau_bots(f, 20.0, 400.0) == 50


def test_objectif_du_velodrome_suit_l_epreuve():
    data = _fiche_gp(bots_cible_pct=100)
    data["commandes"][1]["args"] = {"mode": "track", "track": {"event": "elimination", "opponents": 7}}
    assert EP.lire_fiche(data).objectif_bots == "tempo"


def test_run_rogue_sans_parcours_pas_de_mauvais_terrain():
    f = EP.fiches()["rogue-depart"]
    d = EP.Deroule(f, 120.0)
    assert d.lire({"kind": "header", "route_id": "rogue", "version": 1}) == [] and not d.fini


def test_fiches_livrees_coherentes():
    for f in EP.fiches().values():
        assert EP.incoherences(f) == [], f.id


# --- synchronisation avec le jeu (essai du 21/11 : « fin de l'échauffement » jamais venue) --------------

def test_phase_lines_of_the_run_reach_the_journal():
    from openride_core.rogue.mode import journal_line
    line = journal_line("rogue phase=ROOM step=2 t=361.0", 5.0, 361.0)
    assert line["event"] == "phase" and line["phase"] == "ROOM" and line["step"] == 2
    assert journal_line("rogue phase=BOSS step=9 t=900.0", 5.0, 900.0)["event"] == "boss_phase"


def _source(rel):
    from pathlib import Path
    import openride_core
    return (Path(openride_core.__file__).parent / rel).read_text(encoding="utf-8")


def test_known_events_are_written_by_the_game():
    import re
    gp = set(re.findall(r'self\._log\("(\w+)"', _source("grandprix/mode.py")))
    from pathlib import Path
    import openride_core
    track = set()
    for f in (Path(openride_core.__file__).parent / "track").glob("*.py"):
        track |= set(re.findall(r'_emit\("(\w+)"', f.read_text(encoding="utf-8")))
    assert EP.EVENEMENTS["gp"] <= gp | {"finish"}
    assert EP.EVENEMENTS["track"] <= track
    rogue = _source("rogue/mode.py")
    for ev in EP.EVENEMENTS["rogue"]:
        assert f'"{ev}"' in rogue, ev


def test_unknown_trigger_is_refused():
    data = {"id": "x", "but": "essai", "questions": ["note ?"],
            "commandes": [{"cmd": "start_run", "args": {"objective": "endurance", "duration_min": 30}},
                          {"cmd": "start", "args": {}}],
            "etapes": [{"quand": {"kind": "rogue", "event": "warmup_end"}, "dire": "Go."}]}
    with pytest.raises(EP.FicheError, match="n'écrit pas"):
        EP.lire_fiche(data)


def test_replay_of_a_journal_gives_each_consigne_at_its_game_time(tmp_path):
    lignes = [{"kind": "header", "version": 1, "route_id": "demo-circuit", "source": "live"},
              {"kind": "record", "t": 0.0, "distance": 0.0, "ts": 100.0},
              {"kind": "event", "event": "start", "ts": 101.0}]
    lignes += [{"kind": "record", "t": float(t), "distance": 7.0 * t, "ts": 101.0 + t} for t in range(1, 60)]
    lignes.insert(30, {"kind": "gp", "event": "box", "rider": "me", "t": 26.0, "ts": 128.0})
    lignes += [{"kind": "gp", "event": "use", "rider": "me", "t": 61.0, "ts": 162.0}]
    j = tmp_path / "seance.jsonl"
    j.write_text("\n".join(json.dumps(x) for x in lignes) + "\n", encoding="utf-8")
    out = EP.rejouer(EP.fiches()["gp-voies"], j, 120.0)
    assert out[0].startswith("t=    0 s  [consigne] C'est parti. 120 watts")
    assert any("Objet. Z" in x and x.startswith("t=   27") for x in out)
    assert any("Flèche gauche" in x and x.startswith("t=   36") for x in out)   # 250 m à t=36 s
    assert any("[vu]" in x for x in out)
    assert any(x.startswith("jamais venue : Objet. Colle") for x in out)


def test_consigne_carries_the_game_instant():
    d = EP.Deroule(fiche(), 100)
    a = d.lire({"kind": "event", "event": "start", "ts": 123.5})[0]
    assert a.ts_jeu == 123.5


def test_elimination_has_no_bell_in_the_journal():
    assert "bell" not in EP.evenements_piste("elimination")
    assert {"start", "out", "finish"} <= EP.evenements_piste("elimination")
    assert "bell" in EP.evenements_piste("scratch")
    data = {"id": "x", "but": "essai", "questions": ["note ?"], "bots_cible_pct": 100,
            "commandes": [{"cmd": "select_route", "args": {"route_id": "velodrome-250"}},
                          {"cmd": "start", "args": {"mode": "track", "track": {"event": "elimination",
                                                                                "opponents": 7}}}],
            "etapes": [{"quand": {"kind": "event", "event": "start"}, "dire": "{cible} watts"},
                       {"quand": {"kind": "track", "event": "bell"}, "dire": "Cloche."}]}
    with pytest.raises(EP.FicheError, match="elimination n'écrit pas"):
        EP.lire_fiche(data)


def test_rogue_trial_has_a_short_warmup_without_touching_the_game_table(tmp_path, monkeypatch):
    import tomllib
    from openride_core.rogue import balance as B
    f = EP.fiches()["rogue-depart"]
    assert f.rogue_balance["calendars"]["30"][0] <= 1.0          # échauffement d'une minute à l'essai
    table = tmp_path / "rb.toml"
    table.write_text(EP._toml(f.rogue_balance) + "\n", encoding="utf-8")
    assert tomllib.loads(table.read_text(encoding="utf-8")) == f.rogue_balance
    monkeypatch.delenv(B.ESSAI_ENV, raising=False)
    assert B.run_balance() is B.DEFAULT_BALANCE                  # le jeu garde ses 6 min
    monkeypatch.setenv(B.ESSAI_ENV, str(table))
    bal = B.run_balance()
    assert bal.calendars[30][0] == 1.0 and bal.warmup_relic_s == 30.0
    from openride_core.rogue.scenario import compose_run
    steps = compose_run("endurance", 30, 1, balance=bal).steps
    assert steps[0].kind == "warmup" and steps[0].nominal_s == 60.0 and steps[1].kind == "room"


def test_bad_rogue_balance_is_refused():
    data = {"id": "x", "but": "essai", "questions": ["note ?"], "rogue_balance": {"inconnu": 1},
            "commandes": [{"cmd": "start_run", "args": {"objective": "endurance", "duration_min": 30}},
                          {"cmd": "start", "args": {}}],
            "etapes": [{"quand": {"kind": "event", "event": "start"}, "dire": "Go."}]}
    with pytest.raises(EP.FicheError, match="rogue_balance"):
        EP.lire_fiche(data)


def test_open_world_trial_checks_it_rides_the_open_world():
    f = EP.fiches()["mer-biarritz"]
    assert f.monde_ouvert and f.commandes[0][0] == "start_open_world"
    assert EP.Deroule(f, 100).lire({"kind": "header", "route_id": "ow:ow-20261122-0900"}) == []
    d = EP.Deroule(f, 100)
    assert d.lire({"kind": "header", "route_id": "demo"})[0].sorte == "terrain" and d.fini
    assert seance_file.check([{"cmd": n, "args": a} for n, a in f.commandes])


def test_race_trials_have_no_race_warmup():
    for fid in ("gp-voies", "velodrome-elimination"):
        v = [x for sec, k, x in EP.fiches()[fid].config if (sec, k) == ("depart", "echauffement_min")]
        assert v and 0 <= v[0] <= EP.ECHAUFFEMENT_ESSAI_MAX_MIN
    data = _fiche_gp(bots_cible_pct=100)
    del data["config"]["depart"]
    with pytest.raises(EP.FicheError, match="echauffement_min"):
        EP.lire_fiche(data)


def test_bot_power_and_overrides_of_the_shelter_trial(tmp_path):
    f = EP.fiches()["abri-bonus"]
    start = dict(f.commandes)["start"]
    assert EP.en_watts(start, 123.0) == {"bots": [{"kind": "constant", "power_w": 125}]}
    assert f.surcharges == {"powerups.toml": {"obtain": {"arch_every_m": 500}}}
    from openride_core.powerups import load_table
    p = tmp_path / "powerups.toml"
    p.write_text(EP._toml({"feather": {"factor": 0.9}, **f.surcharges["powerups.toml"]}) + "\n", encoding="utf-8")
    assert load_table(p).arch_every_m == 500


def test_only_known_files_can_be_overridden():
    data = _fiche_gp(bots_cible_pct=100, surcharges={"config.toml": {"x": {"y": 1}}})
    with pytest.raises(EP.FicheError, match="surcharge"):
        EP.lire_fiche(data)


def test_launch_writes_the_overrides_then_puts_everything_back(tmp_path, monkeypatch):
    import subprocess
    from openride_core import config as config_mod
    monkeypatch.setattr(config_mod, "OPENRIDE_HOME", tmp_path)
    monkeypatch.setattr(config_mod, "DEFAULT_CONFIG_PATH", tmp_path / "config.toml")
    (tmp_path / "powerups.toml").write_text("[feather]\nfactor = 0.9\n", encoding="utf-8")
    seen = {}

    class Fin:
        pid = 0

        def __init__(self, cmd, **kw):
            seen["powerups"] = (tmp_path / "powerups.toml").read_text(encoding="utf-8")
            seen["config"] = "".join(q.read_text(encoding="utf-8") for q in tmp_path.rglob("*.toml")
                                     if q.name in ("config.toml", "profil.toml"))
            seen["seance"] = json.loads(Path(cmd[cmd.index("--seance") + 1]).read_text(encoding="utf-8"))

        def poll(self):
            return 0

    from pathlib import Path
    monkeypatch.setattr(subprocess, "Popen", Fin)
    assert EP.lancer(EP.fiches()["abri-bonus"], "principal", True, 120.0, muet=True) == 1
    assert "arch_every_m = 500" in seen["powerups"] and "factor = 0.9" in seen["powerups"]
    assert 'mode = "tactiques"' in seen["config"]
    assert seen["seance"]["commandes"][1]["args"]["bots"][0]["power_w"] == 120
    assert (tmp_path / "powerups.toml").read_text(encoding="utf-8") == "[feather]\nfactor = 0.9\n"
    assert not [q for q in tmp_path.rglob("*.toml") if q.name in ("config.toml", "profil.toml")]


def test_guided_trials_run_in_high_unless_the_fiche_says_otherwise():
    assert ("render", "quality", "high") in EP.reglages_essai(fiche())
    basse = fiche(config={"render": {"quality": "low"}})
    assert [v for s, k, v in EP.reglages_essai(basse) if (s, k) == ("render", "quality")] == ["low"]
    from openride_core import config
    assert EP.QUALITE_ESSAI in config.CHOICES[("render", "quality")]

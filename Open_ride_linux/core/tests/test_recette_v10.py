"""Recette guidée V10 (tools/recette_v10.py) : parcours, consignes, sauvegardes, essais PC et bilan."""

from __future__ import annotations

import json

import pytest

from openride_core import config
from openride_core.equipment import apply_equipment, load_catalogue
from openride_core.garage import ProgressionService
from openride_core.journal import JournalWriter, Record
from openride_core.physics import PhysicsParams
from openride_core.profile import DEFAULT_EQUIPPED, Profile, load_profile, save_profile
from openride_core.progression import load_table
from openride_core.route import load_world
from openride_core.tools import recette_v10 as rv
from openride_core.tools.seance_guidee import cues_json

AERO = {"frame": "frame_tt", "wheels": "wheels_disc"}


BASE = {"frame": DEFAULT_EQUIPPED["frame"], "wheels": DEFAULT_EQUIPPED["wheels"]}


def _service(tmp_path, profile_path):
    return ProgressionService(config.Config(), tmp_path / "journal", None, profile_path, table_path=None)


def _write_block(path, route_id, loadout, speed, power=200.0, minutes=10, grade_sent=0.0):
    with JournalWriter(path, route_id=route_id, source="live", progression={"loadout": loadout}) as w:
        w.event("start", 1_760_000_000.0)
        for i in range(1, minutes * 60 + 1):
            w.record(Record(ts=1_760_000_000.0 + i, t=float(i), distance=speed * i, speed=speed, power=power,
                            cadence=90.0, grade=0.0, gear=12, grade_sent=grade_sent))
        w.event("stop", 1_760_000_000.0 + minutes * 60 + 1)
    return path


def test_routes_and_cues(tmp_path):
    written = rv.write_all(tmp_path / "routes", tmp_path / "Essais", terrain=False)
    assert len(written) == 4
    for name, cues in rv.SESSIONS:
        world = load_world(tmp_path / "routes" / f"{name}.world")
        assert world.route.length_m == rv.ROUTE_LENGTH_M
        sprints = [s for s in world.segments if s.type == "sprint"]
        assert [s.s_start for s in sprints] == list(rv.SPRINTS_M)
        data = json.loads((tmp_path / "Essais" / f"{name}.consignes.json").read_text(encoding="utf-8"))
        assert len(data["cues"]) == len(cues)


def test_cues_leave_time_to_react():
    """Au moins 20 s d'affichage, une consigne à la fois, préavis d'une minute avant chaque geste à préparer."""
    for _, cues in rv.SESSIONS:
        times = [c[0] for c in cues]
        assert times == sorted(times) and times[0] == 0 and times[-1] < rv.BLOCK_S
        for (at, _, shown, _), nxt in zip(cues, times[1:] + [rv.BLOCK_S]):
            assert shown >= 20 and at + shown <= nxt
        for cue in cues_json(cues)["cues"]:
            if "warn_s" in cue:
                assert cue["warn_s"] >= 60 and cue["at_s"] - cue["warn_s"] >= 0


def test_backup_keeps_the_first_copy(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text("a", encoding="utf-8")
    assert len(rv.backup([f, tmp_path / "absent.json"], tmp_path / "bk")) == 1
    f.write_text("b", encoding="utf-8")
    assert rv.backup([f], tmp_path / "bk") == []
    assert (tmp_path / "bk" / "config.toml").read_text(encoding="utf-8") == "a"


def test_set_bike_then_restore_returns_to_no_profile(tmp_path):
    profile_path, essais = tmp_path / "profile.json", tmp_path / "Essais"
    rv.set_bike(profile_path, AERO, essais / rv.RECETTE)
    assert {k: load_profile(profile_path).equipped[k] for k in AERO} == AERO
    rv.write_all(tmp_path / "routes", essais, terrain=False)
    lines = rv.restore(profile_path, tmp_path / "routes", essais)
    assert not profile_path.exists() and len(lines) == 5
    assert rv.restore(profile_path, tmp_path / "routes", essais) == []


def test_profile_reset_check_restores_the_profile(tmp_path):
    profile_path = tmp_path / "profile.json"
    p = Profile()
    p.equipped.update(AERO)
    save_profile(p, profile_path)
    before = profile_path.read_bytes()
    ok, lines = rv.check_profile_reset(
        lambda: _service(tmp_path, profile_path), profile_path, tmp_path / "bk")
    assert ok and "Profil remis" in lines[0]
    assert profile_path.read_bytes() == before


def test_verdict_reads_both_blocks(tmp_path):
    jdir = tmp_path / "journal"
    _write_block(jdir / "a.jsonl", "recette-v10-depart", BASE, 9.0)
    _write_block(jdir / "b.jsonl", "recette-v10-equipe", AERO, 9.3)
    blocks = rv.last_blocks(jdir)
    assert set(blocks) == {"recette-v10-depart", "recette-v10-equipe"}
    plain = PhysicsParams.from_config(config.Config())
    equipped = apply_equipment(plain, AERO, load_catalogue(load_table(None)))
    ok, lines = rv.verdict(blocks, plain, equipped)
    assert ok, lines
    assert any("temps gagné" in line for line in lines) and any("braquet 12" in line for line in lines)

    _write_block(jdir / "c.jsonl", "recette-v10-equipe", BASE, 9.0)
    ok, lines = rv.verdict(rv.last_blocks(jdir), plain, plain)
    assert not ok and any("même cadre" in line for line in lines)


def test_verdict_names_a_missing_block(tmp_path):
    ok, lines = rv.verdict({}, None, None)
    assert not ok and "recette-v10-depart" in lines[0]


def test_materiel_prints_the_plan(capsys):
    assert rv.main(["materiel"]) == 0
    out = capsys.readouterr().out
    assert "python -m openride_core.tools.recette_v10\n" in out and "sprint" in out


class FakeOpenRide:
    """Lanceur simulé : écrit d'un coup le journal d'un bloc de 10 min avec le vélo du profil, puis attend SIGTERM."""

    def __init__(self, tmp_path, ride_s=600):
        self.tmp, self.ride_s, self.cmds, self.signals = tmp_path, ride_s, [], []

    def __call__(self, cmd):
        self.cmds.append(cmd)
        route = cmd[cmd.index("--route") + 1]
        equipped = load_profile(self.tmp / "profile.json").equipped
        loadout = {k: equipped[k] for k in ("frame", "wheels")}
        _write_block(self.tmp / "journal" / f"{route}.jsonl", route, loadout,
                     9.3 if loadout == AERO else 9.0, minutes=self.ride_s // 60)
        self.done = False
        return self

    def poll(self):
        return 0 if self.done else None

    def send_signal(self, sig):
        self.signals.append(sig)
        self.done = True

    def kill(self):
        self.done = True


def _ride(fake):
    clock = iter(range(0, 10**6, 1))
    return rv.Ride(spawn=fake, clock=lambda: float(next(clock)), sleep=lambda s: None)


def _dirs(tmp_path):
    return ["--routes-dir", str(tmp_path / "routes"), "--essais-dir", str(tmp_path / "Essais"),
            "--journal-dir", str(tmp_path / "journal"), "--profile", str(tmp_path / "profile.json"),
            "--config", str(tmp_path / "absent.toml"), "--sans-terrain"]


@pytest.mark.recette_sans_velo
def test_one_command_runs_both_blocks_and_restores(tmp_path):
    """Une seule commande : essais PC, bloc 1 vélo de départ, bloc 2 aéro, verdict, profil et parcours restaurés."""
    p = Profile()
    p.equipped.update({"helmet": "helmet_route"})
    save_profile(p, tmp_path / "profile.json")
    before = (tmp_path / "profile.json").read_bytes()
    fake = FakeOpenRide(tmp_path)
    assert rv.main(_dirs(tmp_path), ride=_ride(fake)) == 0
    assert [c[c.index("--route") + 1] for c in fake.cmds] == ["recette-v10-depart", "recette-v10-equipe"]
    assert all("--autostart" in c and "--no-compile" in c for c in fake.cmds)
    assert len(fake.signals) == 2   # OpenRide fermé par l'outil à 10 min, deux fois
    assert (tmp_path / "profile.json").read_bytes() == before
    assert not (tmp_path / "routes" / "recette-v10-depart.world").exists()
    assert not (tmp_path / "Essais" / "recette-v10-equipe.consignes.json").exists()


@pytest.mark.recette_sans_velo
def test_block_cut_short_stops_and_restores(tmp_path):
    fake = FakeOpenRide(tmp_path, ride_s=120)
    fake.poll = lambda: 0   # OpenRide fermé avant les 10 min
    assert rv.main(_dirs(tmp_path), ride=_ride(fake)) == 1
    assert len(fake.cmds) == 1 and not (tmp_path / "profile.json").exists()


def test_restaurer_without_a_run_does_nothing(tmp_path, capsys):
    assert rv.main(["restaurer", *_dirs(tmp_path)[:-1]]) == 0
    assert "Rien à restaurer" in capsys.readouterr().out


def test_recette_rides_on_the_trial_profile(tmp_path, monkeypatch):
    """Lot MJ9 : OpenRide lancé sur le profil d'essai ; par défaut, profil et journaux du profil d'essai."""
    from openride_core import config as config_mod
    from openride_core import profiles

    assert rv.launch_command("recette-v10-depart", None)[-5:-2] == ["--profil", "_essai", "--autostart"]
    monkeypatch.setattr(config_mod, "OPENRIDE_HOME", tmp_path / "OpenRide")
    seen = {}
    monkeypatch.setattr(rv, "_main", lambda args, ctx, ride: seen.update(
        profile=args.profile, journal=args.journal_dir, ctx=ctx.id, active=profiles.current().id) or 0)
    assert rv.main(["pc"]) == 0
    assert seen["ctx"] == seen["active"] == "_essai"
    assert profiles.current().id is None   # contexte rendu après la recette

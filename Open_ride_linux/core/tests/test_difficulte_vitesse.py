"""La difficulté (%) ne règle que la résistance ressentie : pente envoyée au trainer, jamais la vitesse.

La vitesse virtuelle ne dépend que de la puissance mesurée, de la pente réelle de la route et de la
masse : deux séances identiques à 0 % et 100 % de difficulté roulent à la même vitesse, au même
endroit, avec les mêmes bots, en SIM comme en ERG, et enregistrent la même vitesse dans le journal.
"""

import asyncio

from openride_core import fit_export
from openride_core.bots import ConstantPowerBot
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.journal import read_journal
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession


ERG_ZWO = """<workout_file><name>ERG</name><workout>
<SteadyState Duration="600" Power="0.70"/></workout></workout_file>"""


def _session(tmp_path, monkeypatch, pct, port, workout=None):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    workouts = tmp_path / "Workouts"
    workouts.mkdir(parents=True, exist_ok=True)
    (workouts / "erg.zwo").write_text(ERG_ZWO, encoding="utf-8")
    cfg = Config()
    cfg.trainer.difficulty_pct = pct
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    s = CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                    routes_root=tmp_path / "routes", workouts_dir=workouts, config_path=tmp_path / "config.toml",
                    bots=[ConstantPowerBot(180.0, bot_id="b1"), ConstantPowerBot(240.0, bot_id="b2")])
    s.server.send_raw = lambda m: None
    s._on_command("select_route", {"route_id": "demo"}, 1)
    if workout:
        s._on_command("select_workout", {"workout_id": workout}, 2)
    s._on_command("start", {}, 3)
    return s


def _ride(sessions, seconds):
    for i in range(int(seconds / 0.02)):
        for s in sessions:
            s.driver._power_w = 150.0 + 100.0 * ((i // 500) % 2)   # paliers 150 / 250 W
            s._step(0.02, 10.0 + i * 0.02)


def _speeds(s):
    return [r["speed"] for r in read_journal(s._rec.path) if r.get("kind") == "record"]


def test_difficulty_changes_sent_grade_but_not_speed_bots_or_journal(tmp_path, monkeypatch):
    async def scenario():
        easy = _session(tmp_path / "0", monkeypatch, 0.0, 6310)
        hard = _session(tmp_path / "100", monkeypatch, 100.0, 6312)
        _ride((easy, hard), 120.0)
        assert hard.physics.s > 300.0
        assert easy.state.grade_sent == 0.0 and hard.state.grade_sent != 0.0   # ressenti différent
        assert easy.state.v == hard.state.v and easy.physics.s == hard.physics.s
        assert easy.state.grade == hard.state.grade                            # pente réelle identique
        assert [b.s for b in easy.bots] == [b.s for b in hard.bots]
        assert easy._draft == hard._draft
        assert _speeds(easy) and _speeds(easy) == _speeds(hard)
        hard._on_command("set_difficulty", {"pct": 25}, 9)                      # changement en cours de route
        _ride((easy, hard), 30.0)
        assert easy.state.v == hard.state.v and easy.physics.s == hard.physics.s
    asyncio.run(scenario())


def test_difficulty_has_no_effect_in_erg(tmp_path, monkeypatch):
    async def scenario():
        easy = _session(tmp_path / "0", monkeypatch, 0.0, 6320, workout="erg")
        hard = _session(tmp_path / "100", monkeypatch, 100.0, 6322, workout="erg")
        _ride((easy, hard), 60.0)
        assert easy.state.mode == hard.state.mode == "ERG"
        assert easy.driver.target_power_w == hard.driver.target_power_w
        assert easy.state.v == hard.state.v and easy.physics.s == hard.physics.s
    asyncio.run(scenario())

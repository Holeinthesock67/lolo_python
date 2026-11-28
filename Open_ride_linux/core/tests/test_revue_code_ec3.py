"""Revue de code vague 3, lot EC3 (Cyber-Rogue), partie core.

- E10-01 : après une relance du core (run reprise d'un instantané), `rogue_resync` rend la salle en cours, l'offre
  ouverte et les salles des portes du couloir ; avant, il ne rendait que les messages envoyés par le processus
  courant, donc rien, et la salle se roulait sans ruban ni repères.
- E10-08 : après le bilan d'une séance, le core envoie `progression` (pièces et vies à jour) ; avant, l'écran de
  départ du Cyber-Rogue gardait les vies et le solde d'avant la run jusqu'au lancement suivant.
"""

from __future__ import annotations

import asyncio

from openride_core.config import Config
from openride_core.physics import RiderPhysics
from openride_core.rogue.mode import RogueMode, parse_start_run

from test_progression_session import make, of, ride


def _mode() -> tuple[RogueMode, RiderPhysics]:
    cfg = Config()
    mode = RogueMode(cfg, parse_start_run({"objective": "threshold", "duration_min": 30, "seed": 5}, cfg))
    return mode, RiderPhysics(mode.rider.params)


def _until(mode, body, cond, t, power=230.0, limit_s=2400.0):
    """Roule jusqu'à `cond(mode)` ; rend (instant, dernière ligne d'instantané vue)."""
    dt, snap = 0.02, None
    while not cond(mode):
        _, lines = mode.step(dt, power, 90.0, body, False, t)
        snap = next((ln for ln in lines if ln.get("kind") == "rogue_snapshot"), snap)
        t += dt
        assert t < limit_s, "phase jamais atteinte"
    return t, snap


def _restarted(snap: dict) -> RogueMode:
    """Core relancé : un `RogueMode` neuf, repris de l'instantané (comme `resume.py`)."""
    fresh, _ = _mode()
    fresh.restore(snap)
    return fresh


def test_resync_after_a_core_restart_rebuilds_the_current_room():
    mode, body = _mode()
    t, snap = _until(mode, body, lambda m: m.in_fight and m.engine.phase == "ROOM", 0.0)
    t, snap2 = _until(mode, body, lambda m: m.engine.t_phase > 1.0, t)
    snap = snap2 or snap
    assert snap is not None and snap["kind"] == "rogue_snapshot"
    fresh = _restarted(snap)
    assert fresh.sent == []                                   # rien d'envoyé par le processus relancé
    msgs = fresh.resync()
    rooms = [m for m in msgs if m["type"] == "room"]
    assert rooms and {m["room_id"] for m in rooms} == {mode.engine.room_id}
    assert sorted(m["part"] for m in rooms) == list(range(1, rooms[0]["parts"] + 1))
    assert rooms == mode.engine.room.to_messages(mode.engine.room_id)   # la même salle que celle envoyée


def test_resync_after_a_core_restart_rebuilds_the_corridor_offer_and_doors():
    mode, body = _mode()
    _, snap = _until(mode, body, lambda m: m.engine.phase == "CORRIDOR" and m.engine.stage == "card", 0.0)
    fresh = _restarted(snap)
    assert fresh.engine.phase == "CORRIDOR"
    msgs = fresh.resync()
    loot = [m for m in msgs if m["type"] == "loot"]
    assert len(loot) == 1 and msgs[-1] is loot[0] and loot[0]["cards"]
    doors = {d["room_id"] for d in loot[0]["doors"]}
    if fresh.engine.door_ids:                                 # couloir à portes : leurs salles pour les aperçus
        assert doors <= {m["room_id"] for m in msgs if m["type"] == "room"}


def test_resync_keeps_only_the_current_offer_after_a_reroll():
    mode, body = _mode()
    t, _ = _until(mode, body, lambda m: m.engine.phase == "CORRIDOR" and m.engine.stage == "card", 0.0)
    mode.engine.gold = 500.0
    mode.press("Z_SHORT")                                    # relance des cartes : nouvelle offre, même couloir
    mode.step(0.02, 230.0, 90.0, body, False, t)
    sent_loots = [m for m in mode.sent if m["type"] == "loot"]
    assert len(sent_loots) >= 2
    loots = [m for m in mode.resync() if m["type"] == "loot"]
    assert loots == [mode.engine._loot_message()]


def test_resync_in_the_warmup_relic_offer_and_without_offer():
    mode, body = _mode()
    _until(mode, body, lambda m: m.engine.phase == "WARMUP" and m.engine.stage == "card", 0.0)
    assert [m["type"] for m in mode.resync()][-1] == "loot"
    mode2, body2 = _mode()
    mode2.step(0.02, 150.0, 90.0, body2, False, 0.0)
    assert mode2.resync() == []                               # échauffement sans offre : rien à renvoyer


def test_progression_follows_the_session_summary(tmp_path, monkeypatch):
    async def scenario():
        monkeypatch.setattr("openride_core.session.XP_RESULT_PERIOD_S", 0.01)
        s, frames = make(tmp_path, monkeypatch, min_session_s=30)
        ride(s, 40)
        s._on_command("end_session", {"save": True}, 3)
        await asyncio.sleep(0.3)
        progs = of(frames, "progression")                      # validé par le schéma
        results = of(frames, "xp_result")
        assert len(progs) == 1 and progs[0]["request_cmd_id"] == 0
        assert progs[0]["coins"] == results[0]["coins_total"]
        assert frames.index(progs[0]) > frames.index(results[0])  # après le bilan, une seule fois
        assert progs[0]["lives"] == s.progress_svc.profile.lives_left
    asyncio.run(scenario())


def test_progression_follows_the_summary_out_of_the_event_loop(tmp_path, monkeypatch):
    s, frames = make(tmp_path, monkeypatch, min_session_s=30)
    ride(s, 40)
    s._on_command("end_session", {"save": True}, 3)
    assert [f["type"] for f in frames if f["type"] in ("xp_result", "progression")] == ["xp_result", "progression"]

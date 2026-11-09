"""Tests du contrat IPC de la collection de cartes (série BC, lot BC2, issue #751).

Vérifie :
1. Schémas et messages valides selon Draft202012Validator.
2. Taille du message sous 60 000 octets avec 42 cartes gagnées et 10 éditions de saison.
3. Séparation stricte entre profil d'essai et profil de joueur.
4. Commande collection_seen : mise à jour de collection_vue.json et refus (bad_args) des clés inconnues.
5. Objet facultatif summary.collection à la fin de séance (présent si nouvelle carte, absent sinon).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
import pytest

# Prise en charge de l'environnement Windows pour les tests
if sys.platform == "win32" and "fcntl" not in sys.modules:
    fake_fcntl = types.ModuleType("fcntl")
    fake_fcntl.LOCK_EX = 2
    fake_fcntl.LOCK_NB = 4
    fake_fcntl.LOCK_UN = 8
    fake_fcntl.flock = lambda *a, **k: None
    sys.modules["fcntl"] = fake_fcntl
    os.environ["OPENRIDE_TESTS_VERROU"] = "1"

from openride_core import profiles, recorder
from openride_core.collection import (
    Card,
    Collection,
    Earned,
    card_line,
    load_catalogue,
    load_seen,
    seen_path,
)
from openride_core.config import Config
from openride_core.ipc_lists import (
    build_collection_message,
    compute_summary_collection,
    record_collection_seen,
)
from openride_core.ipc_server import LIST_MESSAGE_TYPES, MAX_LIST_DATAGRAM_SIZE
from openride_core.journal import JournalWriter, Record
from openride_core.progression import Table, load_table
from openride_core.session import CoreSession

# Sur Windows, malloc_trim n'existe pas dans libc
recorder.release_heap = lambda: None

IPC_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"


def load_schema(name: str) -> dict[str, Any]:
    return json.loads((IPC_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def assert_valid(msg: dict[str, Any], schema_name: str | None = None) -> None:
    target = schema_name or msg["type"]
    schema = load_schema(target)
    validator = jsonschema.Draft202012Validator(schema)
    errors = [f"{e.json_path}: {e.message}" for e in validator.iter_errors(msg)]
    assert not errors, f"Validation {target} échouée :\n" + "\n".join(errors)


def write_test_journal(path: Path, start: float, minutes: float = 30.0, km: float = 20.0,
                       source: str = "live", profile_id: str | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(minutes * 60)
    with JournalWriter(path, route_id="demo", source=source,
                       profile={"profile_id": profile_id} if profile_id else None) as w:
        w.event("start", start)
        w.record(Record(ts=start + 1, t=1.0, distance=10.0, alt=100.0, power=200.0))
        w.record(Record(ts=start + n, t=float(n), distance=km * 1000.0, alt=100.0, power=200.0))
        w.event("stop", start + n + 1)
    return path


class MockIpcServer:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.errors: list[tuple[str, str]] = []
        self.hello_config: dict[str, Any] = {}

    def send_raw(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)

    def send_error(self, code: str, message: str) -> None:
        self.errors.append((code, message))

    def send_state(self, state: Any) -> None:
        pass


# ==============================================================================================
# 1. Schémas et contrat
# ==============================================================================================

def test_collection_in_list_message_types():
    """`collection` est bien répertorié parmi les types autorisés jusqu'à 60 000 octets."""
    assert "collection" in LIST_MESSAGE_TYPES


def test_collection_message_schema_valid():
    """Vérifie la validité structurelle du schéma collection.schema.json."""
    schema = load_schema("collection")
    jsonschema.Draft202012Validator.check_schema(schema)


def test_cmd_schema_contains_collection_commands():
    """cmd.schema.json contient `list_collection` et `collection_seen`."""
    cmd_schema = load_schema("cmd")
    enum_names = cmd_schema["properties"]["name"]["enum"]
    assert "list_collection" in enum_names
    assert "collection_seen" in enum_names


def test_state_schema_contains_optional_collection_summary():
    """state.schema.json permet `summary.collection` avec `{card, others}`."""
    state_schema = load_schema("state")
    summary_props = state_schema["properties"]["summary"]["properties"]
    assert "collection" in summary_props
    col_schema = summary_props["collection"]
    assert col_schema["required"] == ["card", "others"]


# ==============================================================================================
# 2. Critère d'acceptation : taille maximale sous 60 000 octets (42 cartes + 10 saisons)
# ==============================================================================================

def test_worst_case_collection_message_size_and_schema():
    """42 cartes gagnées + 10 éditions de saison (52 au total) tiennent largement sous 60 000 octets."""
    catalogue = load_catalogue()
    assert len(catalogue) == 42

    cards_list = [
        {
            "id": c.id,
            "title": c.title,
            "text": c.text,
            "family": c.family,
            "rarity": c.rarity,
            "visual": c.visual,
        }
        for c in catalogue
    ]

    earned_list = []
    # 42 cartes standard
    for i, c in enumerate(catalogue):
        earned_list.append({
            "id": c.id,
            "key": c.id if c.kind != "saison" else f"{c.id}:2026",
            "edition": None if c.kind != "saison" else 2026,
            "title": c.title,
            "text": c.text,
            "family": c.family,
            "rarity": c.rarity,
            "visual": c.visual,
            "journal": f"2026-03-{i+1:02d}_10-00-00.jsonl",
            "date": f"2026-03-{i+1:02d}",
        })

    # 10 éditions de saison supplémentaires (éditions 2016 à 2025)
    saison_card = next(c for c in catalogue if c.kind == "saison")
    for yr in range(2016, 2026):
        earned_list.append({
            "id": saison_card.id,
            "key": f"{saison_card.id}:{yr}",
            "edition": yr,
            "title": saison_card.title,
            "text": saison_card.text,
            "family": saison_card.family,
            "rarity": saison_card.rarity,
            "visual": saison_card.visual,
            "journal": f"{yr}-10-31_18-00-00.jsonl",
            "date": f"{yr}-10-31",
        })

    assert len(earned_list) == 52

    msg = {
        "type": "collection",
        "v": 1,
        "request_cmd_id": 99,
        "cards_count": len(catalogue),
        "first_time": False,
        "cards": cards_list,
        "earned": earned_list,
        "remaining": [{"id": "carte_future", "value": 1500.5, "target": 5000.0}],
        "new": [e["key"] for e in earned_list[:5]],
    }

    assert_valid(msg)

    payload = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    assert len(payload) <= MAX_LIST_DATAGRAM_SIZE
    assert len(payload) < 25000, f"Taille mesurée {len(payload)} octets (loin sous la limite)"


# ==============================================================================================
# 3. Critère d'acceptation : profil d'essai et profil de joueur séparés
# ==============================================================================================

def test_profile_isolation_trial_vs_player(tmp_path):
    """Une séance simulée compte dans le profil d'essai mais pas dans le profil de joueur.

    Chaque profil a ses propres fichiers, son propre dossier et son propre collection_vue.json.
    """
    home = tmp_path / "OpenRide"
    profiles_root = home / "Profils"

    # 1. Profil joueur
    player_ctx = profiles.ProfileContext.for_id("joueur-1", base=profiles_root)
    assert player_ctx.type == "joueur"
    assert player_ctx.counted_sources == ("live",)
    player_ctx.journal_dir.mkdir(parents=True, exist_ok=True)

    # 2. Profil d'essai
    trial_ctx = profiles.ProfileContext.for_id(profiles.TRIAL_ID, base=profiles_root)
    assert trial_ctx.type == "essai"
    assert "simulated" in trial_ctx.counted_sources
    trial_ctx.journal_dir.mkdir(parents=True, exist_ok=True)

    # Séance simulée de 105 km dans le profil joueur
    sim_journal_player = player_ctx.journal_dir / "sim_p.jsonl"
    write_test_journal(sim_journal_player, 1772880000.0, minutes=120.0, km=105.0,
                       source="simulated", profile_id=player_ctx.id)

    # Même séance simulée dans le profil d'essai
    sim_journal_trial = trial_ctx.journal_dir / "sim_t.jsonl"
    write_test_journal(sim_journal_trial, 1772880000.0, minutes=120.0, km=105.0,
                       source="simulated", profile_id=trial_ctx.id)

    # Calcul message collection pour joueur : aucune séance comptée
    msg_player = build_collection_message(1, player_ctx)
    assert_valid(msg_player)
    assert len(msg_player["earned"]) == 0, "Le joueur n'a rien gagné avec une séance simulée"

    # Calcul message collection pour essai : séances simulées comptabilisées
    msg_trial = build_collection_message(2, trial_ctx)
    assert_valid(msg_trial)
    earned_trial_ids = {e["id"] for e in msg_trial["earned"]}
    assert "premiere_seance" in earned_trial_ids
    assert "km_100" in earned_trial_ids

    # Isolation des fichiers collection_vue.json
    record_collection_seen(player_ctx, ["premiere_seance"])
    assert load_seen(seen_path(player_ctx.root)) == {"premiere_seance"}
    assert load_seen(seen_path(trial_ctx.root)) is None, "Le profil d'essai n'est pas touché par le joueur"


# ==============================================================================================
# 4. Critère d'acceptation : collection_seen et refus des clés inconnues (bad_args)
# ==============================================================================================

def test_collection_seen_valid_and_unknown_keys(tmp_path):
    """`collection_seen` met à jour collection_vue.json et refuse les clés invalides."""
    ctx = profiles.ProfileContext.for_id("joueur-seen", base=tmp_path / "Profils")
    ctx.root.mkdir(parents=True, exist_ok=True)

    # Clé valide standard
    seen1 = record_collection_seen(ctx, ["premiere_seance"])
    assert "premiere_seance" in seen1
    assert load_seen(seen_path(ctx.root)) == {"premiere_seance"}

    # Clé valide de saison (avec millésime)
    seen2 = record_collection_seen(ctx, ["halloween:2026"])
    assert {"premiere_seance", "halloween:2026"}.issubset(seen2)
    assert load_seen(seen_path(ctx.root)) == {"premiere_seance", "halloween:2026"}

    # Refus : clé de carte inconnue
    with pytest.raises(ValueError, match="Clé de collection inconnue"):
        record_collection_seen(ctx, ["carte_inexistante_xyz"])

    # Refus : carte standard avec millésime (non-saison)
    with pytest.raises(ValueError, match="Clé de collection inconnue"):
        record_collection_seen(ctx, ["premiere_seance:2026"])

    # Refus : carte de saison sans millésime
    with pytest.raises(ValueError, match="Clé de collection inconnue"):
        record_collection_seen(ctx, ["halloween"])

    # Refus : millésime non numérique
    with pytest.raises(ValueError, match="Clé de collection inconnue"):
        record_collection_seen(ctx, ["halloween:annee_prochaine"])

    # Refus : pas une liste
    with pytest.raises(ValueError, match="attend une liste"):
        record_collection_seen(ctx, "premiere_seance")  # type: ignore


# ==============================================================================================
# 5. Commandes dans CoreSession et gestion d'erreurs IPC
# ==============================================================================================

def test_session_collection_commands(tmp_path, monkeypatch):
    """Test IPC : réception de list_collection et collection_seen dans CoreSession."""
    home = tmp_path / "OpenRide"
    profiles_root = home / "Profils"
    ctx = profiles.ProfileContext.for_id("testeur", base=profiles_root)
    ctx.root.mkdir(parents=True, exist_ok=True)
    ctx.journal_dir.mkdir(parents=True, exist_ok=True)

    # Création d'une séance dans le journal
    write_test_journal(ctx.journal_dir / "s1.jsonl", 1772880000.0, minutes=30.0, km=15.0, profile_id=ctx.id)

    cfg = Config()
    s = CoreSession(cfg)
    s.profile_ctx = ctx
    s.journal_dir = ctx.journal_dir
    mock_server = MockIpcServer()
    s.server = mock_server

    # 1. list_collection
    asyncio.run(s._send_collection(cmd_id=10))
    assert len(mock_server.sent) == 1
    resp = mock_server.sent[0]
    assert resp["type"] == "collection"
    assert resp["request_cmd_id"] == 10
    assert resp["cards_count"] == 42
    assert resp["first_time"] is True
    assert {e["id"] for e in resp["earned"]} == {"premiere_seance"}
    assert resp["new"] == ["premiere_seance"]
    assert_valid(resp)

    # 2. collection_seen avec clé valide
    s._handle_collection_seen({"keys": ["premiere_seance"]}, cmd_id=11)
    assert load_seen(seen_path(ctx.root)) == {"premiere_seance"}
    assert len(mock_server.errors) == 0

    # Nouvelle interrogation : first_time est faux et new est vide
    mock_server.sent.clear()
    asyncio.run(s._send_collection(cmd_id=12))
    resp2 = mock_server.sent[0]
    assert resp2["first_time"] is False
    assert resp2["new"] == []

    # 3. collection_seen avec clé inconnue -> bad_args
    s._handle_collection_seen({"keys": ["inconnue_bidon"]}, cmd_id=13)
    assert len(mock_server.errors) == 1
    code, msg = mock_server.errors[0]
    assert code == "bad_args"
    assert "Clé de collection inconnue" in msg

    # 4. collection_seen sans objet keys -> bad_args
    mock_server.errors.clear()
    s._handle_collection_seen({}, cmd_id=14)
    assert len(mock_server.errors) == 1
    assert mock_server.errors[0][0] == "bad_args"


# ==============================================================================================
# 6. summary.collection au bilan de fin de séance
# ==============================================================================================

def test_summary_collection_present_when_new_card(tmp_path):
    """summary.collection ({card, others}) est présent quand une nouvelle carte est gagnée."""
    home = tmp_path / "OpenRide"
    ctx = profiles.ProfileContext.for_id("cycliste", base=home / "Profils")
    ctx.root.mkdir(parents=True, exist_ok=True)
    ctx.journal_dir.mkdir(parents=True, exist_ok=True)

    # Aucune séance : calcul du bilan renvoie None
    res0 = compute_summary_collection(ctx)
    assert res0 is None

    # Première séance terminée
    write_test_journal(ctx.journal_dir / "s1.jsonl", 1772880000.0, minutes=30.0, km=15.0, profile_id=ctx.id)

    # Calcul du bilan : annonce de la nouvelle carte "premiere_seance"
    res1 = compute_summary_collection(ctx)
    assert res1 is not None
    assert res1["card"]["id"] == "premiere_seance"
    assert res1["others"] == 0

    # Intégration dans state.summary et validation contre state.schema.json
    state_msg = {
        "type": "state",
        "v": 0.0,
        "seq": 1,
        "t": 1800.0,
        "session_state": "FINISHED",
        "trainer_status": "MOCK",
        "input_status": "KEYBOARD",
        "s": 15000.0,
        "cadence": 85.0,
        "power": 180.0,
        "power_3s": 180.0,
        "hr": 140,
        "lat": 48.8566,
        "lon": 2.3522,
        "alt": 35.0,
        "grade": 0.0,
        "grade_sent": 0.0,
        "route_id": "demo",
        "route_length_m": 20000.0,
        "mode": "SIM",
        "erg": None,
        "pause_reason": None,
        "gear": 1,
        "gears_total": 24,
        "last_cmd_id": 1,
        "summary": {
            "duration_s": 1800.0,
            "distance_m": 15000.0,
            "avg_power_w": 180.0,
            "fit_path": None,
            "collection": res1,
        },
    }
    assert_valid(state_msg, "state")

    # Une fois la carte vue, summary.collection ne doit plus apparaître
    record_collection_seen(ctx, ["premiere_seance"])
    res2 = compute_summary_collection(ctx)
    assert res2 is None


def test_session_finish_attaches_summary_collection(tmp_path, monkeypatch):
    """Lors d'une fin de séance (_finish), summary.collection est attaché si une nouvelle carte est gagnée."""
    home = tmp_path / "OpenRide"
    ctx = profiles.ProfileContext.for_id("cycliste-fin", base=home / "Profils")
    ctx.root.mkdir(parents=True, exist_ok=True)
    ctx.journal_dir.mkdir(parents=True, exist_ok=True)

    cfg = Config()
    s = CoreSession(cfg)
    s.profile_ctx = ctx
    s.journal_dir = ctx.journal_dir
    mock_server = MockIpcServer()
    s.server = mock_server

    journal_path = write_test_journal(ctx.journal_dir / "s1.jsonl", 1772880000.0, minutes=30.0, km=15.0, profile_id=ctx.id)

    class DummyRecorder:
        path = journal_path
        workout_id = None
        records = []
        events = []
        def finish(self, save=True, ts=None):
            class S:
                timer_s = 1800.0
                distance_m = 15000.0
                avg_power = 180.0
            return None, S(), None

    s._rec = DummyRecorder()
    s._finish(save=True)
    assert s.state.summary is not None
    assert "collection" in s.state.summary
    assert s.state.summary["collection"]["card"]["id"] == "premiere_seance"
    assert s.state.summary["collection"]["others"] == 0

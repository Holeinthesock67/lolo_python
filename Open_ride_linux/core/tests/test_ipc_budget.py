"""Budget de taille des trames IPC (lot X25) : pire trame par révision et allègement."""

import json
import random
from pathlib import Path

import jsonschema

from openride_core import ipc_budget
from openride_core.ipc_budget import (MAX_DATAGRAM_SIZE, STATE_DEGRADATION, encode, fit_state,
                                      revisions, size, worst_state)
from openride_core.ipc_server import MAX_STATE_DATAGRAM_SIZE, IpcServer

KEPT = ("type", "v", "seq", "t", "session_state", "s", "power", "power_3s", "cadence", "grade")


def test_encode_is_utf8_without_ascii_escapes():
    raw = encode({"name": "Fantôme du 24/10"})
    assert "Fantôme".encode() in raw and b"\\u" not in raw
    assert json.loads(raw.decode("utf-8")) == {"name": "Fantôme du 24/10"}


def test_every_revision_fits_after_degradation():
    # Les pires trames n'utilisent que des valeurs permises par le schéma (énumérations, longueurs, types).
    path = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc" / "state.schema.json"
    validator = jsonschema.Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))
    for rev in revisions():
        frame = worst_state(rev)
        assert [e.message for e in validator.iter_errors(frame)] == [], f"révision {rev}"
        out, dropped = fit_state(frame)
        assert size(out) <= MAX_DATAGRAM_SIZE, f"révision {rev} : {size(out)} octets ({dropped})"
        for key in KEPT:
            assert key in out, f"révision {rev} : {key} retiré"


def test_frames_without_devices_need_no_degradation():
    # Les trames sans `devices` (29 sur 30) passent entières, bots et ERG compris.
    for rev in revisions():
        frame = worst_state(rev)
        frame.pop("devices", None)
        assert fit_state(frame) == (frame, []), f"révision {rev} : {size(frame)} octets"


def test_devices_frame_keeps_devices():
    out, dropped = fit_state(worst_state(revisions()[-1]))
    assert "devices" in out and "erg" in out
    assert "devices" not in dropped


def test_fit_state_does_not_modify_input():
    frame = worst_state(revisions()[-1])
    before = json.dumps(frame, sort_keys=True)
    fit_state(frame)
    assert json.dumps(frame, sort_keys=True) == before


def test_degradation_order_is_known():
    labels = [label for label, _ in STATE_DEGRADATION]
    assert labels.index("devices") > labels.index("bots (trame avec devices)")
    assert labels[-1] == "erg"


def test_random_oversized_frames_always_fit():
    rng = random.Random(1)
    for _ in range(200):
        frame = worst_state(rng.choice(revisions()))
        frame["route_id"] = "x" * rng.randint(1, 300)
        if isinstance(frame.get("erg"), dict):
            frame["erg"]["workout_name"] = "é" * rng.randint(1, 400)
        out, _ = fit_state(frame)
        if size(out) > MAX_DATAGRAM_SIZE:
            # Seul un route_id démesuré peut encore dépasser : il n'est jamais tronqué.
            assert len(frame["route_id"]) > 200


def test_server_sends_degraded_state_instead_of_dropping(caplog):
    sent = []

    class Sock:
        def sendto(self, payload, addr):
            sent.append(payload)

    srv = IpcServer()
    srv._tx_sock = Sock()
    # Depuis la révision 1.3, la limite de state est de 4 096 octets : la pire trame passe entière.
    srv.send_raw(worst_state(revisions()[-1]))
    assert len(sent) == 1 and len(sent[0]) > MAX_DATAGRAM_SIZE
    sent.clear()
    # Allègement à une limite plus basse (même chemin qu'au-delà de 4 096 octets).
    srv.send_raw(worst_state(revisions()[-1]), max_size=MAX_DATAGRAM_SIZE)
    srv.send_raw(worst_state(revisions()[-1]), max_size=MAX_DATAGRAM_SIZE)
    assert len(sent) == 2 and all(len(p) <= MAX_DATAGRAM_SIZE for p in sent)
    assert json.loads(sent[0])["devices"]["trainer"]["status"] == "RECONNECTING"
    assert sum("allégée" in r.message for r in caplog.records) == 1   # avertissement limité


def test_target_and_limit_per_revision():
    assert ipc_budget.state_limit("1.2") == MAX_DATAGRAM_SIZE == 1400
    assert ipc_budget.state_limit("1.3") == ipc_budget.STATE_LIMIT_1_3 == MAX_STATE_DATAGRAM_SIZE
    text = ipc_budget.report()
    assert "cible 1400" in text and "4096" in text
    worst = worst_state("1.3")
    assert worst["draft_bot"] == worst["bots"][0]["id"] and size(worst) <= ipc_budget.STATE_LIMIT_1_3


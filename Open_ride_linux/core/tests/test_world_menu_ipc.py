"""Menu du monde ouvert côté core (lot W11) : recherche, carte, régions, épinglage, taille des données embarquées."""

import asyncio
import json
import sys
from pathlib import Path

import jsonschema
import pytest

from openride_core import fit_export
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.ipc_lists import MAX_DATAGRAM_BYTES, build_world_messages
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession
from openride_core.world_menu import USER_AGENT, WorldMenu, fold, place_kind

HERE = Path(__file__).resolve().parent
STUB = HERE / "data" / "stub_menu_query.py"
ROOT = HERE.parents[1]
IPC_DIR = ROOT / "docs" / "contracts" / "ipc"


def validator(name):
    return jsonschema.Draft202012Validator(json.loads((IPC_DIR / f"{name}.schema.json").read_text(encoding="utf-8")))


class Net:
    """Réseau simulé : horloge, attente et réponses de Nominatim."""

    def __init__(self):
        self.t = 100.0
        self.urls = []
        self.times = []

    def clock(self):
        return self.t

    def sleep(self, s):
        self.t += s

    def fetch(self, url, headers, timeout):
        self.urls.append((url, headers))
        self.times.append(self.t)
        return json.dumps([{"display_name": "Ventoux, Vaucluse, France", "type": "peak", "lat": "44.17", "lon": "5.27"}]).encode()


def menu(net=None, network=True):
    net = net or Net()
    return WorldMenu(network, None, query_cmd=[sys.executable, str(STUB)], fetch=net.fetch, clock=net.clock,
                     sleep=net.sleep), net


def test_place_kinds_follow_the_contract():
    assert [place_kind(k) for k in ("mountain_pass", "peak", "village", "bar", None)] == ["pass", "peak", "village", "other", "other"]


def test_fold():
    assert fold("Évian-les-Bains") == "evian les bains"


def test_embedded_list_finds_ventoux_first():
    wm, _ = menu(network=False)
    items = wm.embedded("ventoux")
    assert items[0]["name"] == "Mont Ventoux" and items[0]["kind"] == "peak"
    assert abs(items[0]["lat"] - 44.174) < 0.01 and items[0]["source"] == "embedded" and not items[0]["cached"]
    assert wm.embedded("") == [] and wm.embedded("zzzzzz") == []
    assert any(i["name"] == "Paris" for i in wm.embedded("paris"))


def test_search_merges_sources_and_validates_contract():
    wm, net = menu()
    (msg,) = wm.search(5, "ventoux")
    validator("places").validate(msg)
    assert msg["request_cmd_id"] == 5 and msg["parts"] == 1
    sources = [i["source"] for i in msg["items"]]
    assert sources[0] == "embedded" and "nominatim" in sources
    (msg,) = wm.search(6, "bonette")
    assert [i["source"] for i in msg["items"]][0] == "base"


def test_offline_never_asks_nominatim():
    wm, net = menu(network=False)
    for text in ("ventoux", "paris", "inconnu"):
        wm.search(1, text)
    assert net.urls == [] and wm.nominatim_requests == 0


def test_nominatim_at_most_one_request_per_second_with_project_user_agent():
    wm, net = menu()
    for text in ("a1", "b2", "c3", "d4"):
        wm.search(1, text)
    assert len(net.times) == 4
    assert all(b - a >= 1.0 - 1e-9 for a, b in zip(net.times, net.times[1:]))
    assert net.urls[0][1]["User-Agent"] == USER_AGENT and "OpenRide" in USER_AGENT
    assert "nominatim.openstreetmap.org" in net.urls[0][0]


def test_empty_query_asks_nothing():
    wm, net = menu()
    (msg,) = wm.search(1, "   ")
    assert msg["items"] == [] and net.urls == []
    (msg,) = wm.search(1, None)
    assert msg["items"] == []


def test_failing_sources_give_an_empty_list_not_an_error():
    wm = WorldMenu(True, None, query_cmd=["/nonexistent/binary"], fetch=lambda *a: (_ for _ in ()).throw(OSError("hors ligne")))
    (msg,) = wm.search(1, "ventoux")
    assert [i["source"] for i in msg["items"]] == ["embedded"]


def test_world_map_in_parts_with_header_fields():
    wm, _ = menu(network=False)
    msgs = wm.world_map(9, {"lat": 44.17, "lon": 5.27, "radius_m": 8000})
    for m in msgs:
        validator("world_map").validate(m)
    assert msgs[0]["lat"] == 44.17 and msgs[0]["radius_m"] == 8000.0 and len(msgs[0]["roads"]) == 400
    (bad,) = wm.world_map(9, {"lat": "x"})
    assert bad["roads"] == []
    (huge,) = wm.world_map(9, {"lat": 44.0, "lon": 5.0, "radius_m": 1e9})
    assert huge["radius_m"] == 20000.0


def test_world_messages_split_under_60000_bytes():
    roads = [{"c": "t", "xz": [k, 0, k + 100, 5, k + 250, -20, k + 400, 11]} for k in range(4000)]
    msgs = build_world_messages("world_map", 3, "roads", roads, extra={"lat": 44.0, "lon": 5.0, "radius_m": 8000.0})
    assert len(msgs) >= 2
    for i, m in enumerate(msgs, 1):
        assert len(json.dumps(m, separators=(",", ":")).encode()) <= MAX_DATAGRAM_BYTES
        assert m["part"] == i and m["parts"] == len(msgs) and m["lat"] == 44.0
        validator("world_map").validate(m)
    assert sum(len(m["roads"]) for m in msgs) == 4000


def test_regions_and_pin():
    wm, _ = menu(network=False)
    (msg,) = wm.regions(2)
    validator("world_regions").validate(msg)
    assert msg["items"][0]["id"] == "provence" and msg["items"][0]["pinned"] is False and msg["cache_max_bytes"] == 100
    (msg,) = wm.regions(3, {"region_id": "provence", "pinned": True})
    validator("world_regions").validate(msg)
    assert msg["items"][0]["pinned"] is True
    (msg,) = wm.regions(4, {"region_id": "provence", "pinned": "oui"})    # argument invalide : simple liste
    assert msg["items"][0]["pinned"] is False


def test_embedded_files_stay_under_3_mb():
    files = [ROOT / "engine" / "assets" / "globe" / "globe.jpg", ROOT / "engine" / "assets" / "globe" / "coast.json",
             Path(__file__).resolve().parents[1] / "src" / "openride_core" / "data" / "places.json"]
    sizes = {f.name: f.stat().st_size for f in files}
    assert sum(sizes.values()) < 3_000_000, sizes
    assert sizes["globe.jpg"] <= 1_000_000 and sizes["coast.json"] <= 500_000 and sizes["places.json"] <= 1_000_000
    assert (ROOT / "engine" / "assets" / "globe" / "LICENCES.md").is_file()
    places = json.loads(files[2].read_text(encoding="utf-8"))["places"]
    assert len(places) > 1000 and all(len(p) == 6 for p in places)


def test_session_answers_menu_commands(tmp_path, monkeypatch):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = 7030, 7031
    s = CoreSession(cfg, driver=MockDriver(base_power_w=200.0, ramp_amplitude_w=0.0), inputs=[NullProvider()],
                    journal_dir=tmp_path / "journal", routes_root=tmp_path / "routes")
    sent = []
    s.server.send_raw = lambda msg, max_size=None: sent.append(msg)
    s.worldmenu, _ = menu(network=False)

    async def run():
        s._on_command("world_search", {"query": "ventoux"}, 11)
        s._on_command("world_regions", {}, 12)
        s._on_command("world_pin", {"region_id": "provence", "pinned": True}, 13)
        s._on_command("world_map", {"lat": 44.17, "lon": 5.27, "radius_m": 5000}, 14)
        for _ in range(200):
            await asyncio.sleep(0.02)
            if len(sent) >= 4:
                break

    asyncio.run(run())
    by_id = {m["request_cmd_id"]: m for m in sent}
    assert by_id[11]["type"] == "places" and by_id[11]["items"][0]["name"] == "Mont Ventoux"
    assert by_id[12]["type"] == "world_regions" and by_id[13]["items"][0]["pinned"] is True
    assert by_id[14]["type"] == "world_map" and by_id[14]["roads"]

"""Cadence réelle des trames `state` dans la boucle du core (contrat IPC §3 : 30 Hz).

Trouvé par l'essai de bout en bout (lot J8) : avec des pas de physique de 20 ms, l'échéance
« maintenant + 1/30 s » ne tombait qu'un pas sur deux, soit 25 trames par seconde.
"""

import asyncio
import socket

from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_state_frames_are_sent_at_30_hz(tmp_path) -> None:
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = _free_port(), _free_port()
    s = CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()],
                    journal_dir=tmp_path / "journal", routes_root=tmp_path / "routes")
    frames: list[dict] = []
    s.server.send_raw = lambda msg: frames.append(msg)   # type: ignore[method-assign]

    async def scenario() -> None:
        task = asyncio.create_task(s.run())
        await asyncio.sleep(0.5)                 # démarrage
        start = len(frames)
        await asyncio.sleep(2.0)
        count = sum(1 for f in frames[start:] if f["type"] == "state")
        s.stop_event.set()
        await task
        rate = count / 2.0
        assert 28.0 <= rate <= 31.0, f"{rate:.1f} trames state par seconde"

    asyncio.run(scenario())

"""Séance simulée sans matériel : MockDriver, clavier du terminal, démarrage immédiat.

Raccourci historique, équivalent à `openride-core run --trainer mock --input keyboard --autostart`.
Toute la logique est dans `openride_core.session.CoreSession`.

    python -m openride_core.tools.run_mock_session
"""

from __future__ import annotations

import asyncio
import logging

from .. import config as config_mod
from ..session import CoreSession


def main() -> None:
    logging.basicConfig(level=logging.INFO, force=True,
                        format="%(asctime)s %(levelname)-7s %(name)s %(message)s")
    cfg = config_mod.load()
    cfg.drivers.trainer, cfg.drivers.input = "mock", "keyboard"
    asyncio.run(CoreSession(cfg).run(autostart=True))


if __name__ == "__main__":
    main()

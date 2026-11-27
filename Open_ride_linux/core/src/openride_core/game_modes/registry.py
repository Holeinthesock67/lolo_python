"""Table des modes de jeu (série IM) : un adaptateur par mode, dans l'ordre fixe d'appel.

L'ordre (classique, WTF, survivant, Grand Prix, piste, Cyber-Rogue) est celui des lignes de `session.py` avant la
série : mêmes calculs, même décoration de la liste `bots` de la trame, même ordre des lignes du journal. Ne pas le
changer sans relancer `scripts/modes_identique.py`.
"""

from __future__ import annotations

from .base import GameMode
from .classic import ClassicMode
from .grandprix import GrandPrixGameMode
from .rogue import RogueGameMode
from .survivor import SurvivorMode
from .track import TrackMode
from .wtf import WtfGameMode

MODES: tuple[GameMode, ...] = (ClassicMode(), WtfGameMode(), SurvivorMode(), GrandPrixGameMode(), TrackMode(),
                               RogueGameMode())
BY_ID: dict[str, GameMode] = {m.id: m for m in MODES}

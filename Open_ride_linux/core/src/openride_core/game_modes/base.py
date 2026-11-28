"""Interface `GameMode` et contexte `ModeContext` des adaptateurs de mode (série IM, lot IM1).

Un adaptateur ne garde aucun état : l'objet du mode (`ClassicRace`, `WtfMode`…) reste un attribut de la séance
(`session.race`, `session.wtf`…), que les tests et les outils lisent toujours. L'adaptateur le lit par
`ModeContext.mode_object`.
"""

from __future__ import annotations

from typing import Any


class ModeContext:
    """Vue étroite de la séance pour les adaptateurs : temps, physique, bots, trame et les quelques aides de la
    séance dont un mode a besoin. Pas d'accès au trainer ni à l'IPC bas niveau. Chaque lot de la série n'y ajoute
    que ce que ses points d'appel lisent."""

    __slots__ = ("_s",)

    def __init__(self, session: Any) -> None:
        self._s = session

    @property
    def state(self) -> Any:
        """Trame `state` en cours de remplissage (`IpcState`)."""
        return self._s.state

    @property
    def running(self) -> bool:
        """Séance en cours (`RUNNING` ou `PAUSED`) : hors de là, un mode vide son champ de la trame."""
        return self._s.state.session_state in ("RUNNING", "PAUSED")

    @property
    def t_session(self) -> float:
        return self._s._t_session

    @property
    def physics(self) -> Any:
        return self._s.physics

    @property
    def bots(self) -> list[Any]:
        return self._s.bots

    @property
    def survivor_out(self) -> dict[str, float]:
        """Bots éliminés du Dernier survivant (ils se rangent) : lu par la trame, l'abri et la boucle des bots."""
        return self._s._survivor_out

    def survivor_catch_w(self, rid: str) -> int | None:
        """Puissance pour revenir sur le coureur `rid` à la prochaine arche (reste dans la séance : abri, vent)."""
        return self._s._survivor_catch_w(rid)

    def mode_object(self, attr: str) -> Any:
        """Objet du mode porté par la séance (`race`, `wtf`, `survivor`, `grandprix`, `track_event`, `rogue`)."""
        return getattr(self._s, attr)


class GameMode:
    """Adaptateur d'un mode de jeu. Chaque point d'appel a un défaut qui ne fait rien ; un adaptateur ne redéfinit
    que ceux dont son mode se sert (règle du cadrage : un point d'appel n'existe que si deux modes s'en servent)."""

    id: str = ""        # identifiant du mode (table des modes)
    attr: str = ""      # attribut de la séance qui porte l'objet du mode

    def obj(self, ctx: ModeContext) -> Any:
        return ctx.mode_object(self.attr)

    def fill_frame(self, ctx: ModeContext) -> None:
        """Remplit le champ du mode dans `ctx.state` et décore la liste `bots` de la trame ; vide son champ hors
        séance. Appelé à chaque trame (30 Hz), mode actif ou non, dans l'ordre fixe de la table des modes."""

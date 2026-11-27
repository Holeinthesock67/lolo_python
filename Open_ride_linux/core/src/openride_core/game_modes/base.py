"""Interface `GameMode` et contexte `ModeContext` des adaptateurs de mode (série IM, lots IM1 et IM2).

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

    def take_mode_object(self, attr: str) -> Any:
        """Fin de séance (lot IM2) : retire l'objet du mode de la séance et le rend."""
        obj = getattr(self._s, attr)
        setattr(self._s, attr, None)
        return obj

    # --- fin de séance (lot IM2) ---

    @property
    def recording(self) -> bool:
        """Séance enregistrée : le journal de jeu reçoit les lignes des modes."""
        return bool(self._s._rec)

    def game(self, line: dict) -> None:
        """Ligne du journal de jeu (appeler seulement si `recording`)."""
        self._s._rec.game(line)

    def reset_physics(self) -> None:
        """Paramètres physiques de base de la séance remis (fin du Mode WTF)."""
        self._s.physics.p = self._s._base_params

    def end_survivor_bots(self) -> None:
        """Bots remis hors du Dernier survivant (éliminations et consignes de survie oubliées)."""
        self._s._end_survivor_bots()

    def end_grandprix(self, gp: Any) -> None:
        """Fin du Grand Prix : voie du cycliste reprise, coups et boîtes encore en attente au journal."""
        self._s._lane = self._s._rider_lane()
        if self._s._rec:
            self._s._flush_grandprix_journal(gp)

    def end_track_choice(self) -> None:
        """Épreuve de piste oubliée : choix du `start`, consignes et comportements de course des bots."""
        s = self._s
        s._track_choice = None
        s._track_plan = s._race_field = None

    def track_record(self, ev: Any, save: bool) -> int | None:
        """Record de la piste (table par épreuve) quand la séance est gardée ; rend sa place, None sinon."""
        return self._s._track_record(ev, save)


class GameMode:
    """Adaptateur d'un mode de jeu. Chaque point d'appel a un défaut qui ne fait rien ; un adaptateur ne redéfinit
    que ceux dont son mode se sert (règle du cadrage : un point d'appel n'existe que si deux modes s'en servent)."""

    id: str = ""        # identifiant du mode (table des modes)
    attr: str = ""      # attribut de la séance qui porte l'objet du mode
    summary_key: str = ""   # section du bilan (`state.summary`) du mode
    elo_modes: tuple[str, ...] = ()   # modes de `start` dont la cote Elo et la ligue lisent `ranking`

    def obj(self, ctx: ModeContext) -> Any:
        return ctx.mode_object(self.attr)

    def fill_frame(self, ctx: ModeContext) -> None:
        """Remplit le champ du mode dans `ctx.state` et décore la liste `bots` de la trame ; vide son champ hors
        séance. Appelé à chaque trame (30 Hz), mode actif ou non, dans l'ordre fixe de la table des modes."""

    # --- fin de séance (lot IM2) : trois temps, chacun dans l'ordre fixe de la table ---

    def end(self, ctx: ModeContext, obj: Any) -> None:
        """Premier temps, juste après le retrait de l'objet du mode (`obj` peut être None : mode pas joué) : champ
        de la trame vidé, bots remis en état."""

    def finish(self, ctx: ModeContext, obj: Any, save: bool) -> Any:
        """Deuxième temps (`obj` jamais None) : dernières lignes et bilan du mode au journal ; rend ce que
        `summary` reprend (place du record de la piste), None sinon."""
        return None

    def summary(self, obj: Any, result: Any) -> dict | None:
        """Troisième temps, séance enregistrée seulement (`obj` jamais None) : section `summary_key` du bilan."""
        return None

    def ranking(self, obj: Any) -> list[list[str]] | None:
        """Classement final en groupes d'égalité (identifiants des coureurs, cycliste compris), pour la cote Elo et
        la ligue ; None si la course n'est pas allée à son terme pour le cycliste."""
        return None

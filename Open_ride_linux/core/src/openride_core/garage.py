"""Progression branchée dans la séance (lot V11) : profil, équipement, Garage et bilan d'expérience.

Assemble les modules purs de la série V (`progression.py`, `equipment.py`, `coins.py`,
`profile.py`) pour la session du core. Rien n'est stocké ici : le niveau, l'expérience, les défis
et les pièces gagnées se recalculent depuis les journaux (avec un cache, `progression.FactsCache`),
le profil ne garde que le choix de l'équipement, les achats, les vies et l'avatar.

Les erreurs de refus portent les codes du contrat (révision 1.4) : `item_locked`,
`not_enough_coins`, `avatar_invalid`, plus `bad_args` et `recording_failed` (profil non écrit ;
l'énumération des codes du contrat est fermée).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

from . import coins as coins_mod
from . import equipment as equipment_mod
from .config import Config
from .equipment import Catalogue, CatalogueError
from .physics import PhysicsParams
from .workout import WorkoutError, load_workout, workout_path
from . import profiles
from .profile import (Profile, ProfileError, ProfileTooNew, SLOTS, check_avatar,
                      equip, load_profile, save_profile, set_avatar)
from .tools import estimate_cp
from .progression import (FactsCache, Progress, ProgressionError, Table,
                          WorkoutDurations, load_table, recompute)

log = logging.getLogger(__name__)

_FROM_PROFILE: Any = object()   # surcharge des tables du profil en cours (série MJ)
CACHE_NAME = ".progression.json"   # cache des séances lues, dans le dossier des journaux
MAX_UNLOCKED = 8
MAX_CHALLENGES = 4
ITEMS_PER_PART = 150   # éléments du catalogue par partie du message `garage`


def workout_duration_finder(directory: Path):
    """Durée d'un entraînement d'après son identifiant (None s'il est introuvable)."""
    cache: dict[str, float | None] = {}

    def find(workout_id: str) -> float | None:
        if workout_id not in cache:
            try:
                cache[workout_id] = load_workout(workout_path(directory, workout_id)).duration_s
            except (WorkoutError, OSError):
                cache[workout_id] = None
        return cache[workout_id]
    return find


def estimate_w_prime(journal_dir: Path, ftp_w: float, cache_path: Path | None = None) -> float | None:
    """W' estimé depuis les séances passées (FIT et journaux du dossier des activités), `None` si
    l'historique ne suffit pas ou ne se lit pas (lot R16 : `hello_ack.config.rogue.w_prime_estimate_j`).
    `cache_path` nul : cache des meilleures puissances du profil de joueur en cours (série MJ)."""
    directory = journal_dir.parent if journal_dir.name == ".journal" else journal_dir
    try:
        return estimate_cp.estimate_w_prime(directory, ftp_w, cache_path=cache_path)
    except Exception:
        log.exception("Estimation de W' impossible (%s)", directory)
        return None


class GarageError(Exception):
    """Commande refusée ; `code` est un code d'erreur du contrat."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ProgressionService:
    """État de la progression pour la session : tables, catalogue, profil et progression."""

    def __init__(self, cfg: Config, journal_dir: Path, workouts: WorkoutDurations = None,
                 profile_path: Path | None = None, table_path: Path | None = _FROM_PROFILE,
                 cache_path: Path | None = None) -> None:
        """`profile_path` et `table_path` : défaut, ceux du profil de joueur en cours (lot MJ1) ;
        `table_path=None` : tables livrées seules."""
        ctx = profiles.current()
        self.cfg = cfg
        self.journal_dir = journal_dir
        self.workouts = workouts
        self.profile_path = profile_path if profile_path is not None else ctx.profile_path
        self.table_path = ctx.table_path if table_path is _FROM_PROFILE else table_path
        self.counted = ctx.counted_sources   # séances qui rapportent (profil d'essai : simulées aussi, MJ2)
        self.owns = ctx.owns
        self.cache_path = cache_path if cache_path is not None else journal_dir / CACHE_NAME
        self.enabled = False
        self.table: Table | None = None
        self.catalogue: Catalogue | None = None
        self.ct: coins_mod.CoinTable | None = None
        self.profile = Profile()
        self.progress: Progress | None = None
        if cfg.progression.enabled:
            self.load()

    # --- chargement ------------------------------------------------------------------------

    def load(self) -> None:
        """Tables, catalogue, profil et progression ; en cas de défaut, la progression se coupe."""
        try:
            self.table = load_table(self.table_path)
            self.catalogue = equipment_mod.load_catalogue(self.table)
            self.ct = coins_mod.coin_table(self.table, self.cfg.rider.ftp_w)
        except (ProgressionError, CatalogueError, coins_mod.CoinsError) as exc:
            log.warning("Progression coupée : %s", exc)
            self.enabled = False
            return
        self.profile = load_profile(self.profile_path, known_items=set(self.catalogue.items))
        self.enabled = True
        self.progress = self._recompute()

    def _recompute(self) -> Progress:
        cache = FactsCache(self.cache_path)
        return recompute(self.journal_dir, self.table, self.workouts, cache, self.counted, self.owns)

    def refresh(self) -> Progress | None:
        """Recalcule la progression (après une séance) ; renvoie l'ancienne."""
        old = self.progress
        if self.enabled:
            self.progress = self._recompute()
        return old

    # --- physique et journal ---------------------------------------------------------------

    def physics_params(self, base: PhysicsParams) -> PhysicsParams:
        """Paramètres de la séance avec le cadre et les roues choisis (identiques si coupé)."""
        if not self.enabled:
            return base
        return equipment_mod.apply_equipment(base, self.profile.equipped, self.catalogue)

    def journal_header(self, equipped: bool = True) -> dict[str, Any] | None:
        """`loadout` et `ftp_w` pour l'en-tête du journal ; `None` si la progression est coupée.

        `equipped=False` (run Cyber-Rogue, lot V5) : l'équipement ne s'applique pas, `loadout` vaut None.
        """
        if not self.enabled:
            return None
        if not equipped:
            return {"ftp_w": self.cfg.rider.ftp_w, "loadout": None}
        mass, cda = equipment_mod.physical_deltas(self.profile.equipped, self.catalogue)
        return {"ftp_w": self.cfg.rider.ftp_w,
                "loadout": {"frame": self.profile.equipped.get("frame"),
                            "wheels": self.profile.equipped.get("wheels"),
                            "mass_delta_kg": round(mass, 3), "cda_delta_pct": round(cda, 3)}}

    # --- messages --------------------------------------------------------------------------

    def balance(self) -> int:
        return coins_mod.balance(self.progress, self.profile, self.ct)

    def progression_dict(self) -> dict[str, Any] | None:
        """Champs de `hello_ack.config.progression` et du message `progression` ; `None` si coupée."""
        if not self.enabled or self.progress is None:
            return None
        lv = self.progress.level
        avatar = dict(self.profile.avatar)
        avatar["standing_grade_pct"] = self.cfg.avatar.standing_grade_pct   # `[avatar]` de config.toml (lot V6)
        avatar["standing_power_pct"] = self.cfg.avatar.standing_power_pct
        return {"level": lv.level, "xp": self.progress.total_xp, "xp_level_start": lv.xp_level_start,
                "xp_next_level": lv.xp_next_level, "coins": self.balance(),
                "equipped": dict(self.profile.equipped), "avatar": avatar,
                "lives": max(self.profile.lives_left, 0)}

    def garage_items(self) -> list[dict[str, Any]]:
        """Éléments du message `garage`, par emplacement puis par niveau."""
        challenges = {c.reward: c.name for c in self.table.challenges}
        items = []
        for slot in SLOTS:
            for it in self.catalogue.by_slot(slot):
                items.append({
                    "id": it.id, "slot": it.slot, "name": it.name,
                    "state": coins_mod.item_state(it, self.progress, self.profile, self.catalogue),
                    "level_required": it.level, "price": it.price,
                    "challenge": challenges.get(it.id),
                    "mass_delta_kg": it.mass_delta_kg, "cda_delta_pct": it.cda_delta_pct,
                    "terrain": it.terrain, "look": it.look or it.id})
        return items

    def garage_messages(self, request_cmd_id: int) -> list[dict[str, Any]]:
        items = self.garage_items()
        chunks = [items[i:i + ITEMS_PER_PART] for i in range(0, len(items), ITEMS_PER_PART)] or [[]]
        return [{"type": "garage", "v": 1, "request_cmd_id": request_cmd_id, "part": n, "parts": len(chunks),
                 "items": chunk} for n, chunk in enumerate(chunks, 1)]

    def progression_message(self, request_cmd_id: int) -> dict[str, Any]:
        return {"type": "progression", "v": 1, "request_cmd_id": request_cmd_id, **self.progression_dict()}

    # --- commandes du Garage ---------------------------------------------------------------

    def _save(self) -> None:
        try:
            save_profile(self.profile, self.profile_path)
        except (ProfileTooNew, OSError, ProfileError) as exc:
            raise GarageError("recording_failed", f"profil non enregistré : {exc}") from exc

    def _mutate(self, change: Any) -> None:
        """Applique `change(profile)` sur une copie, écrit, puis adopte : rien ne change si l'écriture échoue."""
        before = Profile.__new__(Profile)
        before.__dict__.update({k: _copy(v) for k, v in self.profile.__dict__.items()})
        try:
            change(self.profile)
            self._save()
        except Exception:
            self.profile = before
            raise

    # --- Cyber-Rogue (lot R9) ----------------------------------------------------------------

    def rogue_progress(self) -> tuple:
        """(table des châssis, statistiques des runs, vies en réserve) ; `(None, None, 0)` si coupée.

        Une table de châssis invalide laisse le seul châssis standard (avertissement au journal).
        """
        from .rogue import progress as rogue_progress

        if not self.enabled or self.progress is None or self.table is None:
            return None, None, 0
        try:
            chassis = rogue_progress.load_chassis(self.table)
        except rogue_progress.ChassisError as exc:
            log.warning("Châssis du Cyber-Rogue ignorés : %s", exc)
            return None, None, 0
        return chassis, rogue_progress.rogue_stats(self.progress), max(self.profile.lives_left, 0)

    def use_lives(self, count: int) -> None:
        """Retire du profil les vies utilisées pendant une run (défaites rattrapées, lot R9)."""
        if not self.enabled or count <= 0:
            return

        def change(p: Profile) -> None:
            for _ in range(count):
                coins_mod.use_life(p)
        try:
            self._mutate(change)
        except (coins_mod.CoinsError, GarageError) as exc:
            log.warning("Vies du Cyber-Rogue non retirées du profil : %s", exc)

    def equip(self, slot: Any, item_id: Any) -> None:
        if not isinstance(slot, str) or not isinstance(item_id, str):
            raise GarageError("bad_args", "equip attend `slot` et `item_id` (textes)")
        if slot not in SLOTS:
            raise GarageError("bad_args", f"emplacement inconnu : {slot!r}")
        item = self.catalogue.items.get(item_id)
        if item is None:
            raise GarageError("item_locked", f"pièce inconnue : {item_id!r}")
        if item.slot != slot:
            raise GarageError("bad_args", f"« {item.name} » ne va pas à l'emplacement {slot}")
        owned = coins_mod.owned_items(self.progress, self.profile, self.catalogue)
        if item_id not in owned:
            raise GarageError("item_locked", f"« {item.name} » n'est pas possédée")
        self._mutate(lambda p: equip(p, slot, item_id, owned))

    def buy(self, item_id: Any) -> None:
        if not isinstance(item_id, str):
            raise GarageError("bad_args", "buy attend `item_id` (texte)")
        try:
            self._mutate(lambda p: coins_mod.buy(item_id, self.progress, p, self.catalogue, self.ct))
        except coins_mod.CoinsError as exc:
            code = "item_locked" if exc.code in ("item_unknown", "already_owned", "item_locked") else exc.code
            raise GarageError(code, str(exc)) from exc

    def set_avatar(self, avatar: Any) -> None:
        try:
            checked = check_avatar({k: v for k, v in avatar.items()
                                    if k not in ("standing_grade_pct", "standing_power_pct")}
                                   if isinstance(avatar, dict) else avatar)
        except ProfileError as exc:
            raise GarageError("avatar_invalid", str(exc)) from exc
        self._mutate(lambda p: set_avatar(p, checked))

    # --- bilan de fin de séance ------------------------------------------------------------

    def xp_result(self, journal: str, old: Progress | None, records: Iterable[dict] | None = None,
                  base: PhysicsParams | None = None) -> dict[str, Any]:
        """Message `xp_result` de la séance `journal` ; `old` : progression d'avant la séance."""
        new = self.progress
        result = next((r for r in new.sessions if r.facts.journal == journal), None)
        eligible = result is not None and result.gains is not None
        old_level = old.level.level if old else new.level.level
        gains = result.gains.as_list() if eligible else []
        unlocked = self._newly_buyable(old) if eligible else []
        done_before = {c.id for c in old.challenges} if old else set()
        challenges = [{"id": c.id, "name": c.name, "reward_item": c.reward}
                      for c in new.challenges if c.id not in done_before] if eligible else []
        gain_s = None
        if records is not None and base is not None:
            gain_s = equipment_mod.equipment_time_gain(records, self.physics_params(base), base)
        by_session = coins_mod.coins_by_session(new, self.ct)
        return {
            "type": "xp_result", "v": 1, "eligible": eligible,
            "reason": None if eligible else (result.reason if result else "too_short"),
            "gains": gains, "total": result.gains.total if eligible else 0,
            "level_before": old_level, "level_after": new.level.level,
            "xp_total": new.total_xp, "xp_next_level": new.level.xp_next_level,
            "coins_gained": by_session.get(journal, 0) if eligible else 0,
            "coins_total": self.balance(),
            "unlocked": unlocked[:MAX_UNLOCKED], "challenges": challenges[:MAX_CHALLENGES],
            "equipment_gain_s": round(gain_s, 1) if gain_s is not None else None,
            "more": len(unlocked) > MAX_UNLOCKED or len(challenges) > MAX_CHALLENGES,
        }

    def _newly_buyable(self, old: Progress | None) -> list[str]:
        """Pièces à vendre dont le niveau vient d'être atteint."""
        if old is None:
            return []
        lo, hi = old.level.level, self.progress.level.level
        return [it.id for slot in SLOTS for it in self.catalogue.by_slot(slot)
                if it.buyable and not it.default and lo < it.level <= hi]


def _copy(value: Any) -> Any:
    import copy
    return copy.deepcopy(value)

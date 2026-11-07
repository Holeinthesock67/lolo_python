"""Valeurs d'équilibrage de la Course tactique (série CT, lot CT0), réunies dans un seul objet.

Sur le modèle de `rogue/balance.py` (lot R7) : `DEFAULT_BALANCE` est la table de référence, `balance.toml`
(embarqué) la reprend à l'identique (un test le vérifie), et `load_balance()` accepte une surcharge
`~/OpenRide/tactical_balance.toml` qui ne garde que les lignes changées. Une clé inconnue ou une valeur hors
bornes est refusée avec un message qui nomme la clé.

Les lots CT2 à CT8 reprennent leurs valeurs ici ; tant qu'ils ne sont pas faits, le simulateur `tactical_sim`
appelle les bouchons de `tactical/bouchons.py`, réglés par ces mêmes valeurs.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path

from ..rogue.balance import BalanceError, _check_range_deep, _like


@dataclass(frozen=True)
class TacticalBalance:
    # Course simulée (CT0)
    dt_s: float = 0.5                   # pas de la simulation (comme le calibrage des bots du lot T13)
    rider_ftp_w: float = 250.0          # cycliste virtuel : FTP = CP
    rider_w_prime_j: float = 20000.0    # cycliste virtuel : W′
    rider_mass_kg: float = 75.0         # cycliste virtuel : masse sans le vélo
    bike_mass_kg: float = 8.0           # vélo de tout le monde (bots compris, comme en séance)
    bots_level_pct: float = 95.0        # bots calibrés seuls sur le circuit au temps du cycliste seul à ce % de FTP
    form_spread_pct: float = 3.0        # jour avec, jour sans : CP de chacun tirée à ± 3 % (Y10 : 0,97 à 1,03)
    # Surchauffe (CT2, décision du 29 octobre : 70 % de la CP pendant 8 s)
    burnout_cap_pct: float = 70.0       # puissance prise en compte pendant le Burnout, en % de la CP
    burnout_s: float = 8.0              # durée du Burnout
    burnout_tolerance_s: float = 0.5    # réserve à 0 pendant 0,5 s avant le Burnout (retard de la puissance mesurée)
    # Catapulte (CT4)
    sling_full_s: float = 15.0          # charge pleine en 15 s roue dans la roue (abri 0,40)
    sling_decay_pct_s: float = 10.0     # charge perdue par seconde sans abri (passé devant)
    sling_gain_pct: float = 35.0        # puissance prise en compte majorée de 35 % à charge pleine...
    sling_boost_s: float = 3.0          # ... pendant 3 s, sans vider la réserve (impulsion gratuite)
    sling_min_pct: float = 30.0         # charge minimale pour lancer la catapulte
    sling_cooldown_s: float = 60.0      # au plus une catapulte par minute
    # Pacte de relais et capacités (CT6, effets du catalogue 4.0)
    relay_min_s: float = 15.0           # un relais en tête compte à partir de 15 s
    credits_full_kj: float = 25.0       # travail aérodynamique donné aux suiveurs pour remplir la jauge
    breakaway_cost_pct: float = 25.0    # « Échappée » (`breakaway`) : pas d'abri pour les suiveurs...
    breakaway_s: float = 20.0           # ... et pas de réponse des bots pendant 20 s
    shield_cost_pct: float = 50.0       # « Bouclier d'inertie » : pas de Burnout...
    shield_s: float = 10.0              # ... pendant 10 s
    aero_cost_pct: float = 100.0        # « Casque aéro » (`aero`) : CdA × 0,75...
    aero_s: float = 20.0                # ... pendant 20 s
    aero_cda_mult: float = 0.75         # CdA multiplié par 0,75 pendant le Casque aéro
    # Cerveau des bots (CT3, sur les règles de Y10)
    bot_follow_cp_pct: float = 125.0    # un bot qui suit une accélération roule au plus à 1,25 × CP...
    bot_follow_reserve_pct: float = 40.0   # ... s'il lui reste plus de 40 % de réserve...
    bot_follow_stop_pct: float = 20.0   # ... et il lâche sous 20 %
    bot_error_pct: float = 15.0         # erreur de jugement (difficulté 50 %) : il suit quand même et peut exploser
    bot_relay_reserve_pct: float = 30.0   # pas de relais sous 30 % de réserve
    bot_relay_min_s: float = 30.0       # relais de 30 s (réserve à 30 %)...
    bot_relay_max_s: float = 60.0       # ... à 60 s (réserve pleine)
    bot_chase_cp_pct: float = 105.0     # en tête d'un groupe, poursuite à 1,05 × CP d'un coureur parti devant...
    bot_chase_look_m: float = 400.0     # ... à moins de 400 m
    baroudeur_cp_pct: float = 105.0     # baroudeur : échappée à 1,05 × CP...
    baroudeur_until_pct: float = 60.0   # ... lancée dans les 60 premiers % de la course...
    baroudeur_stop_pct: float = 35.0    # ... tenue jusqu'à 35 % de réserve...
    baroudeur_restart_pct: float = 80.0   # ... et relancée quand la réserve est remontée à 80 %
    pull_off_pct: float = 85.0          # fin de relais : puissance à 85 % pendant qu'on se fait doubler...
    pull_off_max_s: float = 15.0        # ... au plus 15 s
    bot_climb_attack_cp_pct: float = 120.0   # attaque du grimpeur en montée : 1,2 × CP (T12 : 1,1 en séance)...
    bot_climb_attack_reserve_pct: float = 40.0   # ... tant qu'il lui reste plus de 40 % de réserve
    bot_sprint_cp_pct: float = 200.0    # sprint final des bots sans pic : 2 × CP
    bot_sprint_m: float = 250.0         # sprint lancé à 250 m de l'arrivée (le sprinteur garde son pic à 200 m)
    bot_attack_cp_pct: float = 120.0    # attaque d'un rouleur dans le final : 1,2 × CP...
    bot_attack_from_m: float = 2500.0   # ... entre 2,5 km...
    bot_attack_to_m: float = 800.0      # ... et 800 m de l'arrivée...
    bot_attack_stop_pct: float = 15.0   # ... tenue jusqu'à 15 % de réserve
    # Cycliste virtuel (stratégies du simulateur)
    rider_relay_s: float = 45.0         # « rouleur » : relais de 45 s
    rider_attack_cp_pct: float = 130.0  # « attaquant » : contre à 1,3 × CP...
    rider_attack_trigger_pct: float = 10.0   # ... quand un bot de son groupe passe sous 10 % de réserve
    rider_attack_min_pct: float = 50.0  # ... s'il lui reste plus de 50 %
    rider_cut_pct: float = 3.0          # il coupe son effort à 3 % de réserve (évite le Burnout)
    rider_solo_cp_pct: float = 100.0    # « échappée » : seul devant à la CP
    rider_sprint_cp_pct: float = 200.0  # sprint du cycliste : 2 × CP...
    rider_sprint_m: float = 250.0       # ... dans les 250 derniers mètres
    rider_finale_m: float = 1500.0      # capacités achetées dans les 1 500 derniers mètres


DEFAULT_BALANCE = TacticalBalance()

EMBEDDED_PATH = Path(__file__).with_name("balance.toml")
OVERRIDE_PATH = Path.home() / "OpenRide" / "tactical_balance.toml"
VALUE_RANGE = (0.0, 100000.0)


def apply_overrides(base: TacticalBalance, data: dict) -> TacticalBalance:
    """Rend `base` modifié par `data` (contenu d'un fichier TOML). Lève `BalanceError` sinon."""
    names = {f.name for f in fields(TacticalBalance)}
    changes: dict = {}
    for k, v in data.items():
        if k not in names:
            raise BalanceError(f"{k} : clé inconnue")
        val = _like(k, v, getattr(base, k))
        _check_range_deep(k, val, *VALUE_RANGE)
        changes[k] = val
    if changes.get("dt_s", base.dt_s) <= 0:
        raise BalanceError("dt_s : le pas doit être positif")
    return replace(base, **changes)


def _read(path: Path) -> dict:
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise BalanceError(f"{path} : TOML invalide ({exc})") from None


def load_balance(override: Path | None = None, *, required: bool = False) -> TacticalBalance:
    """Table embarquée, puis surcharge `~/OpenRide/tactical_balance.toml` si elle existe (ou `override`)."""
    bal = apply_overrides(TacticalBalance(), _read(EMBEDDED_PATH))
    path = OVERRIDE_PATH if override is None else override
    if required and not path.is_file():
        raise BalanceError(f"{path} : fichier introuvable")
    if path.is_file():
        try:
            bal = apply_overrides(bal, _read(path))
        except BalanceError as exc:
            raise BalanceError(f"{path} : {exc}") from None
    return bal


def balance_hash(bal: TacticalBalance) -> str:
    """Empreinte courte (8 caractères) de la table, notée dans le rapport."""
    raw = json.dumps({f.name: getattr(bal, f.name) for f in fields(bal)}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:8]

# Lot R2 – Modèle W'bal et postures de cadence avec hystérésis

## 1. Objectif

Deux modules purs du core pour le mode Cyber-Rogue : la réserve anaérobie W'bal, calculée seconde par seconde à partir de la puissance, et la posture de combat déduite de la cadence (Roc, Fluide, Véloce). Ils ne touchent ni au trainer ni à l'IPC : la session (R8) les appelle à chaque pas.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/2.0/GDD_CYBER_ROGUE.md` §1.2 et §2.3 (avec ses corrections), `docs/2.0/PLAN_SERIE_R.md` §2 (Q5).
2. Code : `core/src/openride_core/physics.py` (style des modules purs), `core/src/openride_core/config.py` (sections, bornes `_BOUNDS`).

## 3. Prérequis

Aucun.

## 4. Travail demandé

### 4.1 W'bal (`rogue/wbal.py`)

- Modèle différentiel de Skiba (2015), pas de calcul de 1 Hz à 50 Hz (le résultat ne dépend pas du pas à 1 % près) :
  - si P > CP : dW'bal/dt = −(P − CP) ;
  - sinon : dW'bal/dt = (W' − W'bal) × (CP − P) / W' ;
  - W'bal reste entre 0 et W'.
- Bonus de jeu, assumé comme tel (pas de la physiologie) : en posture Fluide **et** cadence de 80 à 95 rpm, la recharge est multipliée par `fluid_regen_mult` (1,2).
- Paramètres : `cp_w` (défaut : FTP), `w_prime_j` (défaut 20 000, décision Q5).
- Configuration : section `[rogue]` de `config.toml`, `w_prime_j` (bornes 5 000 à 60 000) et `cp_w` (0 = FTP ; bornes 0 à 1 000).
- Fonction `wbal_step(state, power_w, cadence_rpm, dt) -> state` sans effet de bord ; état `{w_bal_j, depleted_s}` (`depleted_s` : temps passé à 0).

### 4.2 Postures (`rogue/posture.py`)

Seuils corrigés le 26 octobre (le GDD laissait des trous entre 70 et 80 et entre 95 et 100 rpm) :

| Posture | Entrée | Sortie |
| --- | --- | --- |
| `ROC` | cadence < 70 rpm | cadence ≥ 73 rpm |
| `FLUIDE` | tout le reste (70 à 100 rpm) | — |
| `VELOCE` | cadence > 100 rpm | cadence ≤ 97 rpm |
| `ARRET` | cadence < 20 rpm ou puissance < 10 W | cadence ≥ 30 rpm et puissance ≥ 10 W |

- Une nouvelle posture n'est adoptée qu'après 1,5 s continues dans sa plage (`posture_hold_s`), sauf `ARRET`, immédiat.
- Cadence lissée sur 2 s avant le test.
- La « meilleure régénération » du GDD (80 à 95 rpm) est le bonus de W'bal du §4.1, pas une posture distincte.
- Le GDD demandait moins de 75 rpm pour la charge du Grimpeur : corrigé, la charge demande la posture `ROC` (moins de 70 rpm).

### 4.3 Valeurs dans un objet commun

Toutes les constantes du lot sont des champs d'une dataclass `RogueBalance` dans `rogue/balance.py` (créée ici, complétée par R4 à R6, chargée depuis un fichier de données par R7).

## 5. Fichiers concernés

- **Créés :** `core/src/openride_core/rogue/__init__.py`, `rogue/wbal.py`, `rogue/posture.py`, `rogue/balance.py`, `core/tests/test_rogue_wbal_posture.py`.
- **Modifiés :** `core/src/openride_core/config.py` (section `[rogue]`, deux champs et leurs bornes), `docs/SRS_v1.1.md` §11 (exemple `config.toml`), `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Section `[rogue]` de la configuration (SRS §11), deux champs.

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe.
2. Effort de 3 min à CP + 100 W avec W' = 20 kJ : W'bal = 2 kJ à ± 1 % à la fin.
3. Récupération à 50 % de CP après épuisement : W'bal remonte à 63 % de W' en `W' / (CP × 0,5)` secondes à ± 2 %.
4. Même séance calculée à 1 Hz et à 50 Hz : écart de W'bal inférieur à 1 % de W'.
5. Cadence qui oscille entre 69 et 72 rpm : la posture ne change pas plus d'une fois ; montée de 65 à 105 rpm en 10 s : `ROC`, `FLUIDE`, `VELOCE` dans cet ordre.
6. Arrêt de pédalage : `ARRET` immédiat ; reprise : `FLUIDE` après 1,5 s.

## 8. Hors périmètre

- Estimation de CP et W' depuis l'historique (lot R16).
- Effets des postures sur le combat (lot R5).

## 9. Livraison (27 octobre 2026)

- Paquet `rogue` du core (`rogue/wbal.py`, `rogue/posture.py`, `rogue/balance.py`) et section `[rogue]` de `config.toml` (`w_prime_j`, `cp_w`), sans changement de `session.py` ni du contrat ; branchement par R8. Tests : `core/tests/test_rogue_wbal_posture.py`.
- La recharge est intégrée de façon exacte sur le pas (exponentielle), donc indépendante du pas de calcul.
- `wbal_step` prend `cp_w` et `w_prime_j` en paramètres nommés (R8 y met la FTP quand `cp_w` vaut 0) et un argument facultatif `posture` : donné, le bonus de recharge exige `FLUIDE` ; sinon seule la cadence compte.
- À la reprise après `ARRET`, la cadence lissée repart de la cadence mesurée, sinon la posture retomberait en `ROC` par effet du lissage.

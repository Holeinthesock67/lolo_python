# Lot BT1 – Effort des bots selon la durée de la course et l'objectif

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Bots réglés sur la courbe de puissance : FTP × courbe(durée de la course) × objectif × niveau, pour tous les modes à bots, vélodrome par épreuve | Python, GDScript | T13 (#900 : échelle unique) | Moyenne | **Livré le 16 novembre** (PR #909) |

## 1. Objectif

Essai du Grand Prix du 15 novembre : « bots beaucoup trop forts », même à 50 %. Consigne du propriétaire : la base reste la FTP, mais un humain a une courbe de puissance ; il faut adapter le % de FTP à la longueur de la séance et à l'objectif de l'entraînement. Réflexion et décisions : note `ETUDE_NIVEAU_BOTS_COURBE_PUISSANCE.md` (dossier du projet, `plans/`).

Décisions du 15 novembre : objectif par défaut **Tempo** ; parts de la courbe **55, 65, 80, 92 et 100 %** ; au vélodrome, l'objectif suit l'épreuve ; ailleurs, **un seul réglage commun** gardé d'une séance à l'autre.

## 2. La règle

Puissance cible des bots = FTP × courbe(durée de la course) × objectif × niveau des bots (`bot_effort.py`, module pur).

| Durée à fond | 1 min | 5 min | 10 min | 20 min | 1 h | 2 h | 3 h |
|---|---|---|---|---|---|---|---|
| % de la FTP | 160 | 120 | 110 | 105 | 100 | 88 | 80 |

Interpolation sur le logarithme de la durée, bornée aux extrémités. Objectifs (`bots.objective`) : `recovery` 55 %, `endurance` 65 %, `tempo` 80 % (défaut), `threshold` 92 %, `max` 100 %. « Niveau des bots » reste un réglage fin (100 % : plateau juste pour l'objectif).

- **Durée de la course :** temps du cycliste de référence (sans vent, `RouteProfile.ref_time`) à la puissance cible, recalculé trois fois. Grand Prix : tours × tour, ou la distance en ligne ; Dernier survivant, session libre, WTF : un passage du parcours.
- **Vélodrome :** `TRACK_EFFORT`, par épreuve : À fond pour les contre-la-montre (poursuite, kilo, 500 m, 200 m lancé, heure, vitesse et poursuite par équipes, keirin) ; Tempo pour la séance libre (1 h) et les courses en groupe (scratch, points, tempo, élimination, omnium, américaine) sur leurs tours.
- **Calibrage :** `bots.calibrate_bots(..., effort=)` calibre l'échelle du rouleur (#900) pour finir dans le temps du cycliste de référence à cette cible ; chaque bot garde `effort_target` (% de la FTP, durée). Ligne du journal du core : « Effort des bots (tempo) : 86 % de la FTP (216 W) sur ≈ 13 min ».

## 3. Livraison

**Fusionné le 16 novembre 2026 (PR #909).** Les points « Reste » ci-dessous décrivent l'état d'avant la fusion.

- Core : `bot_effort.py` ; `bots.effort_target`, `calibrate_bots(effort=)` ; `Session._bot_effort` (mode de la séance) ; réglage `bots.objective` (`config.py`, choix, clé du profil ; `settings.py` « Objectif des bots ») ; banc `bots_race --objectif` (le cycliste roule à l'effort d'un bot de son niveau).
- Engine : ligne « Objectif des bots » sur les écrans Prêt du Dernier survivant et du Grand Prix, et dans les réglages (`settings_view_model.gd` : « tempo (80 %) »…).
- Tests : `core/tests/test_bot_effort.py` ; `test_survivor_menu.gd`, `test_grandprix_menu.gd`, scénarios `grand_prix` et `dernier_survivant` repris.
- Contrat : aucun champ nouveau (le réglage passe par `list_settings`).

## 4. Reste

- Banc `bots_race` sur le PC, low, medium et high, en Tempo et en À fond.
- Essai du propriétaire : 10 min de Grand Prix en Tempo, puis 10 min en Endurance.
- Plus tard : puissance cible et durée affichées en watts sur l'écran Prêt (« Bots : ≈ 225 W pendant ≈ 9 min ») : demande une réponse du core avant le départ ; course conseillée (CO9) dont l'objectif suit le besoin du jour ; vraie courbe du cycliste (`estimate_cp`).

# Lots GP-niv et BOT-elo – Effort des bots en watts et cote Elo

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Effort des bots en watts sur l'écran Prêt et au bilan, objectif de la course conseillée (GP-niv) ; cote Elo du cycliste et des bots qui règle le peloton (BOT-elo) | Python, GDScript | BT1 (#909), T13 (#900) | Moyenne | **Livré le 21 novembre** (PR #941) |

## 1. Objectif

- **GP-niv** (fil « Créer des parcours propres au Grand Prix », 15 novembre) : la suite de BT1 laissée « pour plus tard » : la cible des bots en watts sur l'écran Prêt (règle du 14 novembre : des watts, pas des %), la puissance des bots au bilan face à la tienne, l'objectif de la course conseillée qui suit le besoin du jour.
- **BOT-elo** (demande du propriétaire du 16 novembre, lancée le 20 novembre) : une cote pour le cycliste et une par bot, mise à jour après chaque course, qui règle le niveau des adversaires. Choix du 20 novembre : **une cote commune à tous les modes, active par défaut** (réglage pour la couper).

Étude : `ETUDE_ELO_BOTS_2026-11-20.md` (dossier du projet, `plans/`).

## 2. La règle

- **Cote du cycliste** : départ 1 500, bornée de 1 000 à 2 100. **Écart propre de chaque bot** : la cote d'un bot est celle du cycliste plus son écart (± 100 points au plus, recentrés sur 0 après chaque course). Un bot garde son identité par sa place dans le plateau composé par le core : profil et rang (`climber#2` = « Grimpeur 2 »).
- **Courses qui comptent** : Grand Prix (cycliste arrivé), Dernier survivant (cycliste éliminé ou vainqueur ; les bots encore en course passent devant lui), épreuves de piste en groupe finies (scratch, points, tempo, élimination, keirin, omnium). Une séance non gardée ou arrêtée avant la fin ne compte pas. Les bots à puissance fixe et le fantôme ne sont jamais dans un plateau composé. Un mode à classement ajouté plus tard (course classique contre bots) s'ajoute à `bot_elo.MODES` et à `CoreSession._elo_order`.
- **Mise à jour** : Elo à plusieurs (chaque paire : 1 devant, 0 derrière, ½ à égalité, somme divisée par le nombre d'adversaires) ; K = 40 pour le cycliste sur ses 10 premières courses, puis 24 ; K = 8 pour les bots.
- **Effet** : niveau d'un bot = niveau du plateau × (1 + (cote du bot − 1 500) / 4 000), soit **+2,5 % de puissance par 100 points**, borné au réglage `bots.level_pct`. Le peloton suit la cote du cycliste : il se renforce quand tu gagnes, s'affaiblit quand tu perds.
- **Équilibre** (test `test_convergence_simulee_juste_part`) : un cycliste 10 % plus fort que sa FTP ne le dit voit sa cote monter vers 1 900, puis sa place moyenne revient au milieu du peloton ; les écarts des bots restent bornés.

## 3. Livraison

- Core : `bot_elo.py` (module pur hors `elo.json` du profil, à côté de `records.json`) ; `CoreSession._elo_levels` (plateaux du Dernier survivant, du Grand Prix et du vélodrome), `_elo_finish` (cotes, ligne `elo` du journal, `summary.elo`) ; `bots_preview` (`_send_bots_preview`) ; `summary.bots_effort` (cible moyenne et puissance moyenne réelle des bots, `ConstantPowerBot.avg_power_w`) ; `start.objective` ; `coach.route.objective` (`bot_effort.NEED_OBJECTIVE`) ; réglage `bots.elo` (`config.py`, clé du profil ; `settings.py` « Niveau automatique (Elo) ») ; `TrackEvent.full_ranking`.
- Engine : ligne grisée « Bots : ≈ 225 W, ≈ 9 min » (à droite : « cote 1540 ») sous « Lancer » sur les écrans Prêt du Dernier survivant, du Grand Prix et du vélodrome (`menu_flow.wanted_bots_preview`, `on_bots_preview`, `menu_model.bots_info`), redemandée quand la course change ; lignes « Bots » et « Cote » du bilan (`summary_view_model.bots_lines`) ; objectif de la course conseillée dans `start`.
- Contrat : révision 1.22 (`bots_preview`, `start.objective`, `coach.route.objective`, `summary.elo`, `summary.bots_effort`).
- Banc des campagnes : `python -m openride_core.tools.elo_campagne` (3 forces × 30 Grand Prix simulés, vraie séance, `elo.json` temporaire). Au cloud le 21/11 : force 0,92 → 1 352, force 1 → 1 486, force 1,08 → 1 654 ; place moyenne du dernier tiers 3,4, 2,7 et 2,7 sur 5 ; cote stable (écart type 7 à 9 points) ; écarts des bots sous 100.
- Tests : `core/tests/test_bot_elo.py`, `test_elo_campagne.py` ; `test_survivor_session.py` (cote après une victoire, plateau suivant plus fort, cote coupée, `bots_preview`, `start.objective`), `test_grandprix_session.py`, `test_track_session.py` ; engine `test_grandprix_menu.gd`, `test_summary_view_model.gd`.

## 4. Reste

- Bancs PC low, medium et high des écrans Prêt (ligne « Bots ») et du bilan (lignes « Bots » et « Cote »), captures à valider par le propriétaire.
- Banc PC : `elo_campagne` (logique, sans GPU), pour juger la cote : un essai vélo de 10 min ne fait qu'une ou deux courses (remarque du propriétaire du 21/11).
- Essai vélo : seulement le ressenti d'une course serrée (bots ni trop forts ni trop faibles), pas la cote.
- Plus tard : vraie courbe de puissance du cycliste (`estimate_cp`) à la place de la courbe type.

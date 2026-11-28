# Lot RT1 – Retours et consignes communs à tous les modes

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Chaque moment se voit, s'entend et se lit, de la même façon dans tous les modes : bandeau du moment, résultat, zone de consigne unique, fin de course explicite | GDScript | EL1, DS6, VD9, GP8 | Moyenne | **Livré le 24 novembre** (PR #959) |

## 1. Objectif

Essai vélo du 21 novembre (vélodrome, élimination gagnée sans aucun signal, « le jeu a continué comme s'il y avait des
éliminations en attente ») : « c'est le problème général de manque de retour, de lisibilité et de compréhension du
jeu », puis « on est censé deviner quoi faire, les choses ne sont pas assez explicites ». Audit des modes et règle
commune : dossier du projet `plans/AUDIT_RETOURS_JEU_2026-11-21.md` ; maquettes validées le 21 novembre
(`captures/rt1-maquettes/`).

## 2. Spécification

| # | Règle |
| --- | --- |
| 1 | Cinq familles de moments, les mêmes partout : DÉPART, BIEN, ATTENTION, REFUSÉ, RÉSULTAT. Chaque moment donne ensemble un mot en tête (« ▶ DÉPART », « + BIEN », « ! ATTENTION », « × REFUSÉ », « ★ RÉSULTAT »), une couleur fixe de la famille, un titre, une ligne de détail et un son de la famille (`fb_bien`, `fb_attention`, `fb_refus` ; résultat : `jingle_winner`, `jingle_finish`, `jingle_elim`) ; un mode peut donner sa variante de son (`jingle_elim` à l'élimination). Le mot passe avant la couleur. |
| 2 | Une seule zone de consigne en bas au centre, la même pour tous les modes : « À FAIRE », l'action à faire maintenant en gros, puis « Objectif : … · Pourquoi : … », et les boutons utiles à droite. Le bandeau du moment s'affiche juste au-dessus (4 s), le résultat au milieu de l'écran (6 s). |
| 3 | Moment de fin unique (choix du propriétaire, 21 novembre) : dès que l'issue est connue, résultat « VICTOIRE ! », « ARRIVÉE · 3e sur 8 », « ÉLIMINÉ · 5e sur 8 » ou « ENTRAÎNEMENT TERMINÉ », puis la consigne devient « COURSE FINIE · 1er sur 8 / Roule au calme autant que tu veux / Y puis A maintenu = bilan » jusqu'à la fin de la séance. |
| 4 | Un seul modèle d'affichage (`feedback_model.gd`, vue `feedback_view.gd`) ; chaque mode ne fait que rendre ses moments et sa consigne (`moments`, `consigne`, `goal` de son modèle) : plus de bandeau du milieu ni du bas propre au Dernier survivant ou à la piste. |
| 5 | Branchés dans ce lot : Dernier survivant (adversaire éliminé, cycliste dernier, éliminé, victoire ; « Passe X avant l'arche »), toutes les épreuves de piste (adversaire sorti, dernier, éliminé, résultat de l'épreuve ; consigne par épreuve : élimination, scratch, points, tempo, keirin, américaine, poursuites, contre-la-montre, heure), Grand Prix (consigne : passer dans une boîte « + BONUS », lancer l'objet), fin d'un entraînement ERG (remplace l'invite du bandeau du haut), départ (« ▶ DÉPART » et l'objectif du mode). |
| 6 | Le Click perdu ne s'affiche pas (choix du propriétaire, 21 novembre : journal technique seulement). La séance libre n'a pas de consigne. |

## 3. Livraison

- Engine : `feedback_model.gd`, `feedback_view.gd` (nouveaux), `main.gd` (`_update_feedback`, `_mode_consigne`, `_mode_goal`), `survivor/survivor_hud_model.gd` et `survivor_view.gd`, `track/track_hud_model.gd` et `track_view.gd`, `grandprix/gp_hud_model.gd`, `event_sounds_model.gd` (`fb_*`), `hud_view_model.gd` et `banner.gd` (invite de fin d'entraînement retirée).
- Tests : `test_feedback.gd` (nouveau), `test_survivor_hud.gd`, `test_track_hud.gd`, `test_gp_hud.gd`, `test_hud_view_model.gd` ; `visual_check.py` (fin d'entraînement).
- Captures low, medium et high (vraie scène, trames du core réel pour la piste) : dossier du projet `captures/rt1-retours/` (script `capture_rt1.py`).

## 4. Reste (lots suivants de l'audit)

- RT2 : fin commune côté core pour le Grand Prix, la Course et l'arrivée d'un parcours en ligne (aujourd'hui la séance s'arrête et le bilan s'ouvre) ; objectif sur l'écran de départ.
- Pages « Comment ça marche ? » pour chaque mode et chaque épreuve de piste, sur le modèle de l'aide du Grand Prix (#952), une fois #952 et #939 fusionnées.
- RT3 : bots lisibles (attaque, relais), révision IPC 1.27 ; RT4 : refus (Z sans objet ou sans effet) avec leur raison dans tous les modes, Cyber-Rogue (sas, cartes).

## Recette PC
Catégorie : rendu
- Cloud : suites unitaires de l'engine, captures low, medium et high (`captures/rt1-retours/`)
- Fumée (≈ 5 min) : `python3 engine/tests/menu_bench.py --native --scenario elimination --scenario dernier_survivant --qualite low --voies clavier --out {sortie}`
- Matrice, une étape par qualité, ordre low, high, medium (≈ 30 min chacune, ≈ 1 h 30 en tout) :
  `python3 engine/tests/sim_bench.py --native --probe --scenario dernier_survivant --scenario grand_prix --scenario erg_village --quality {qualite} --out {sortie}`
  (Dernier survivant 7 min, Grand Prix 8 min, ERG court 5 min 45 jusqu'à « ENTRAÎNEMENT TERMINÉ » ; budgets GPU 8, 13 et 16 ms ; HUD seulement, aucun changement 3D attendu)
- Essai vélo : moments et consigne lisibles en roulant (vélodrome élimination)
- Versions : pas de révision IPC ; WORLDGEN_VERSION et SCHEMA_VERSION inchangés

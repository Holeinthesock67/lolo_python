# Lot R4 – Firewall : cycliste virtuel à une fraction de la FTP, écart au joueur

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Firewall : cycliste virtuel à une fraction de la FTP, écart au joueur | Python | R3 | Petite | **Livré le 27 octobre** (module pur ; branché par R8), **version 2.0** |

## 1. Objectif

Le Firewall (mur de décompilation) poursuit le joueur sur la piste. C'est un cycliste virtuel qui roule le profil de la salle à la puissance du `firewall_plan` (fraction de la FTP du joueur), avec la même physique que le joueur. Si l'effort du joueur baisse, le mur le rattrape et entame son bouclier et son or.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/2.0/GDD_CYBER_ROGUE.md` §2.1 (point 2), `docs/lots/LOT_R3_generateur_salles.md` (`firewall_plan`).
2. Code : `core/src/openride_core/physics.py`, `core/src/openride_core/bots.py` (bots à puissance constante, même principe).

## 3. Prérequis

R3 livré.

## 4. Travail demandé

- `Firewall(room, rider, balance)` avec `step(dt, player_s, paused) -> FirewallState` ; état `{s, v, gap_m, contact}`.
- Physique : celle du joueur (masse, CdA, Crr de la configuration), pente du profil de la salle **sans** décalage de braquet, puissance = fraction du `firewall_plan` × FTP. Pas de vent ni d'aspiration.
- Départ : le mur part `start_gap_m` derrière le joueur (défaut 150 m) à l'entrée de chaque salle.
- Écart plafonné à `max_gap_m` (défaut 400 m) : au-delà, le mur avance à la vitesse du joueur (pas d'avance infinie à capitaliser).
- Contact (`gap_m` ≤ 0) : le mur ne dépasse pas le joueur, il reste collé ; `contact` vrai. Les dégâts du contact sont appliqués par le combat (R5).
- Pause : le mur s'arrête aussi. Click perdu (`input_status` = `LOST`) : le mur s'arrête jusqu'au retour du Click ou de l'appui sur une touche (risque 4 du plan).
- Couloirs et récupérations : pas de Firewall.
- Constantes dans `RogueBalance`.

## 5. Fichiers concernés

- **Créés :** `core/src/openride_core/rogue/firewall.py`, `core/tests/test_rogue_firewall.py`.
- **Modifiés :** `core/src/openride_core/rogue/balance.py`, `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe.
2. Joueur simulé à la même puissance que le mur : écart constant à ± 5 m sur une salle Diesel de 4 min.
3. Joueur à 10 % sous le mur sur une salle Diesel seuil : contact avant la fin de la salle ; à 10 % au-dessus : écart plafonné à 400 m, jamais plus.
4. Salves du Sprinteur : l'écart baisse pendant chaque salve pour un joueur à puissance constante.
5. Pause et Click perdu : écart inchangé pendant l'arrêt.

## 8. Hors périmètre

- Dégâts et perte d'or au contact (R5), affichage du mur (R10).

## 9. Livraison (27 octobre 2026)

- `rogue/firewall.py` (`Firewall.step(dt, player_s, paused, input_lost)`) et `start_gap_m`, `max_gap_m` dans `RogueBalance`. Tests : `core/tests/test_rogue_firewall.py`.
- **Choix :** le mur lit la pente et la fraction de FTP du plan à la position du joueur (même terrain au même instant) ; à puissance égale l'écart reste donc constant, et les salves du Sprinteur tombent en même temps pour le joueur et le mur. Lu à sa propre position, le mur dérivait de 20 m en 4 min sur une rampe, contre le critère à ± 5 m.
- Au contact, le mur reste collé au joueur à sa vitesse ; au plafond de 400 m, il suit le joueur à distance fixe. Le contact de 10 % sous le mur sur un Diesel seuil demande une salle d'au moins 8 min avec l'écart de départ de 150 m ; à 4 min l'écart tombe à 50 m seulement.

# Lot RT4 – Refus expliqués : pourquoi, et quoi faire

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Chaque refus (départ refusé, appui sans effet, bonus refusé, trainer muet ou perdu) dit en mots simples pourquoi et quoi faire, avec le bandeau commun « × REFUSÉ » | GDScript | RT1, NI1 | Petite | En revue (captures à valider) |

## 1. Objectif

Audit des retours du 21 novembre (dossier du projet `plans/AUDIT_RETOURS_JEU_2026-11-21.md`, §2 colonne « Erreurs,
refus », §4 et §6) : un refus ne disait pas toujours pourquoi, et presque jamais quoi faire. Le Z sans objet du Grand
Prix laissait la case vide, le Z de la piste ou du Dernier survivant ne faisait rien sans le dire, un départ refusé
par le core affichait « Échec : » suivi du texte technique du core sur quelques écrans seulement, et rien du tout pour
un entraînement ou un plan refusés en séance libre. Lancé le 22 novembre à la demande du propriétaire (« On peut lancer
autres lots ? »), avant la fusion de #959 et #960.

## 2. Spécification

| # | Règle |
| --- | --- |
| 1 | Un seul format partout : le mot « × REFUSÉ » en tête, le pourquoi, puis « À faire : … ». Le mot vient avant la couleur (gris de la famille REFUSÉ de RT1, son `fb_refus`). |
| 2 | Départ refusé par le core (`start`, écran Prêt de tous les modes, séance libre comprise) : « × REFUSÉ · Départ impossible : <pourquoi> » puis « À faire : <quoi faire> », en rouge sur la ligne d'état. Le pourquoi et le quoi faire viennent du code d'erreur et du texte du core (`refusal_model.gd`, `LAUNCH_CODES`, `LAUNCH_PATTERNS`) ; un texte inconnu est gardé tel quel, avec un quoi faire générique. |
| 2 bis | Un départ refusé ainsi expliqué n'affiche plus, par-dessus, le bandeau technique « Erreur du core [code] » (il reste au journal). Les erreurs de parcours (`route_*`) et du trainer (`trainer_control_refused`) gardent leur bandeau. |
| 3 | « Lancer » grisé du Dernier survivant et du Grand Prix : même format (« × REFUSÉ · Lancer grisé : … » puis « À faire : … »). |
| 4 | Appui sans effet en séance, bandeau « × REFUSÉ » 4 s au-dessus de la zone de consigne : Grand Prix, Z sans objet (« passe dans une boîte « + BONUS » ») ou pendant le tirage ; piste et Dernier survivant, Z sans effet (« tout se joue aux jambes ») ; séance libre avec bonus, Z sans bonus en réserve ou avec un bonus déjà en cours. Rien pendant un entraînement ERG (Z passe le bloc), au Cyber-Rogue et au mode WTF (refus déjà expliqués par leurs lots), menu affiché, ni après la fin de la course. |
| 5 | Bonus refusé par le core (`powerup.refused`, contrat 1.13) : même bandeau, une fois par refus, avec la raison du core et quoi faire (« Gardé en réserve · garde-le pour la prochaine descente »). La case du bonus garde son affichage. |
| 6 | Trainer perdu pendant la séance : bandeau « ! ATTENTION · Trainer perdu : reconnexion en cours », « Continue de pédaler pour le réveiller · la séance reprend toute seule », une fois par perte. Attente du départ : après 8 s sur l'étape « Trainer », l'écran « START YOUR ENGINES » ajoute « À faire : allume le trainer et pédale pour le réveiller ; sinon Y, puis Appareils » ; après 20 s sur « Décor », « Décor long à charger : patiente encore un peu, ou Y pour annuler ». |
| 7 | Le Click perdu ne s'affiche jamais (choix du propriétaire, 21 novembre : journal technique seulement). La ligne « ÉTAT: … TRAINER … ENTRÉE » est retirée par NI1 (#963), qui garde un avis « Trainer perdu » au bandeau central. |

Sans révision IPC : l'engine reçoit déjà chaque appui relayé par le core (`input_event`), avant que le core le traite ;
la trame connue est celle d'avant l'appui.

## 3. Livraison

- Engine : `refusal_model.gd` (nouveau), `main.gd` (`_explain_press`, moments de `refusals.on_state` dans `_update_feedback`), `menu_flow.gd` (`READY_REFUSALS`, `ready_message`, textes de « Lancer » grisé), `start_wait_model.gd` (`hint`), `start_screen.gd` (ligne d'aide).
- Tests : `test_refusal_model.gd` (nouveau) ; `test_menu_flow.gd`, `test_grandprix_menu.gd`, `test_survivor_menu.gd` (nouveaux textes).
- Captures low, medium et high des écrans concernés seulement : écran Prêt avec un départ refusé, bandeau « × REFUSÉ » en Grand Prix, attente du trainer ; dossier du projet `captures/rt4-refus/`.

## 4. Reste

- Cyber-Rogue : sas entre salles et choix des cartes sans « pourquoi » (audit §6) ; à faire après la fusion de #960 et #965, avec le fil Cyber-Rogue, pour ne pas toucher les mêmes écrans en même temps.
- Grand Prix : un Z refusé parce que trop tôt après le précédent reste muet (le core ne dit pas la raison) ; demanderait un champ IPC.

## Recette PC
Catégorie : rendu
- Cloud : suites unitaires de l'engine, captures low, medium et high (`captures/rt4-refus/`)
- Fumée (≈ 5 min) : `python3 engine/tests/menu_bench.py --native --scenario dernier_survivant --qualite medium --voies clavier --out {sortie}`
- Pas de matrice : menus et HUD seulement, aucun changement 3D attendu (banc medium seul, règle du 21 novembre)
- Versions : pas de révision IPC ; WORLDGEN_VERSION et SCHEMA_VERSION inchangés

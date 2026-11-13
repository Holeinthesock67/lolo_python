# Lot GP4 – Voiture d'équipe et Furtif

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : Voiture d'équipe (remorquage dans l'abri d'un véhicule d'AS6) et Furtif (Échappée de TT4 plus vol d'objet) | Python + GDScript | GP1, AS6, TT4 | Petite | En revue le 12 novembre (version 4.0 ; captures low, medium, high à valider avant fusion) |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Ajouter les deux objets qui reposent sur d'autres séries : la Voiture d'équipe, qui réutilise le véhicule et l'abri du lot AS6, et le Furtif, qui reprend l'Échappée (`breakaway`) de TT4 et ajoute le vol de l'objet du coureur devant.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` §3 ; cahier AS6 ; plan TT (`docs/4.0/PLAN_SERIE_TT.md`, lot TT4).

## 3. Travail demandé

- Voiture d'équipe : 6 s à 1,5 × la vitesse d'équilibre, invincible, tirée seulement à plus de 15 s du premier ; véhicule et ressenti d'abri d'AS6 (supplément négatif seulement, borné).
- Furtif : effet `breakaway` de la table, 10 s, plus vol de l'objet du coureur devant à moins de 50 m.
- Les deux objets entrent dans le catalogue par ce lot : avant lui, ils n'existent pas, et le tirage de GP1 répartit leurs poids sur les autres objets, comme pour un objet désactivé (aucun test spécial dans le code).

## 4. Critères d'acceptation

1. Tests : gain de la voiture d'équipe à ± 10 % du tableau du plan ; vol refusé sans coureur à moins de 50 m.
2. Ressenti : supplément de pente de la voiture toujours négatif ou nul, rampes respectées.

## 5. Livraison (12 novembre 2026)

État de départ : le lot GP1 avait déjà mis les deux objets au catalogue (`items.py` : voiture d'équipe en plancher et plafond à 1,5 × v_éq pendant 6 s, invincible, tirée seulement à plus de 15 s du premier ; Furtif avec la marque `breakaway` de 10 s et le vol à moins de 50 m), et le test de gain du plan couvrait déjà `team_car`. Ce lot branche ce qui dépendait d'AS6 et de TT4, sans nouvelle révision du contrat IPC (révision inchangée) et sans test du nom d'un objet dans le code.

- **Voiture d'équipe, véhicule d'AS6.** Nouveau champ de données `ItemSpec.escort` (sorte de véhicule de `traffic.KINDS`, `car_a` pour la voiture d'équipe, vide pour les autres objets) ; `GrandPrixMode.escorts()` donne les coureurs remorqués tant que dure l'effet. La séance (`_gp_escorts`) pose le véhicule 3 m devant la roue avant du coureur remorqué (`ESCORT_GAP_M`, distance de référence de l'abri d'AS6 ; 2 m au premier passage, porté à 3 m le 13 novembre pour écarter les contacts d'affichage voiture / bot remorqué), à sa vitesse et sur sa ligne, identifiant court `tc<rang>` ; il passe en tête de la liste `vehicles` de `state` (au plus 4 véhicules, schéma et budget inchangés), même sans circulation. L'engine le dessine comme tout véhicule du core (décor vivant).
- **Pas de contact (banc du 13 novembre : 44 contacts voiture / bot).** La voiture se glisse devant son coureur dès que la place est libre (aucun autre coureur sous sa carrosserie), puis y reste jusqu'à la fin de l'effet ; pour le placement AS2, le coureur remorqué et sa voiture forment un seul bloc au gabarit de la voiture (`_update_draft`) : le bloc double les plus lents et les autres l'évitent. Test : tous les bots remorqués sans arrêt pendant 20 s, aucune voiture sous un coureur.
- **Ressenti de l'abri.** La voiture est une source d'abri d'AS6 comme les autres (`traffic.vehicle_draft`, plafond `VEHICLE_ALPHA_CAP` de 0,60, lissage d'une seconde de `draft.smooth`) : le supplément de pente est négatif ou nul, avec les rampes de l'abri, et suit le réglage `[ride] vehicle_draft` (coupé : voiture dessinée, gain de vitesse inchangé, pas d'abri ressenti). La vitesse virtuelle reste celle de l'objet (plancher et plafond), l'abri ne la change pas.
- **Furtif, Échappée de TT4.** `effects.is_unseen` et `GrandPrixMode.unseen(id)` ; la séance réunit l'Échappée du cycliste (TT4) et le Furtif du Grand Prix, cycliste ou bot, dans `_unseen_ids()` : ces coureurs n'abritent personne (`Source.shelters` pour le cycliste, nouvel attribut `shelters` des bots, lu par `draft._group_draft` et `draft.update_bots`) et les bots ne suivent pas leurs attaques (`bot_tactics.update_field(unseen=...)`). La roue suivie et la poussée restent (on ne traverse pas un coureur invisible à l'abri).
- **Vol.** Inchangé depuis GP1 : l'objet du premier coureur devant à moins de 50 m qui en tient un passe dans la réserve vide du Furtif ; sans coureur à moins de 50 m, le Furtif part quand même et rien n'est volé.
- **Engine.** `gp_items.gd` : `UNSEEN` et `unseen(fx)` (objets qui portent la marque `breakaway`) ; avatar du cycliste translucide sous le Furtif comme pendant l'Échappée (`main.gd`, une ligne autour de `_show_power_up_effects`) ; bots sous le Furtif translucides aussi (`bots_view_model.gd` champ `unseen` lu dans `bots[].fx`, `bots_view.gd` appelle `set_breakaway`) ; `avatar_view.set_breakaway` rend l'opacité d'avant (bot fantôme) à la fin.
- **Tests.** `core/tests/test_gp4_voiture_furtif.py` : escorte pendant 6 s seulement et donnée propre à la voiture ; Furtif 10 s et vol à 40 m ; vol refusé à 60 m et sans coureur devant ; bot sous Furtif sans abri donné ; séance : voiture `tc0` de sorte `car_a` dans `vehicles` (schéma `state` et budget de 4 096 octets), abri ressenti borné, rampe d'au plus 0,6 × (1 − e^(−0,02)) par pas, pente envoyée jamais au-dessus de celle sans abri au même pas et plus basse derrière la voiture ; réglage `vehicle_draft` coupé respecté ; `_unseen_ids` et `shelters` des bots ; place de la voiture devant le coureur. Moteur : `engine/tests/test_gp_hud.gd` (`unseen`).
- **Banc.** Scénarios `engine/tests/sim_bench_scenarios/grand_prix_gp4_voiture.json` et `grand_prix_gp4_furtif.json` : course de `grand_prix` où seul l'objet du scénario est joué et tiré dans toutes les tranches (`bench.grandprix`, nouveau : écrit `~/OpenRide/grandprix.toml` comme `bench.powerups`), cycliste à 200 W derrière les bots, Z toutes les 3 s autour de chaque rangée de boîtes, captures 30 et 50 m après chaque rangée ; `python3 engine/tests/sim_bench.py --scenario grand_prix_gp4_voiture --camera follow_far --quality low|medium|high` (vue subjective : ni avatar ni voiture à l'écran ; premier passage du 12 novembre, un seul scénario mixte en vue subjective, n'a montré que la pastille du Furtif).
- **Reste.** Captures en low, medium et high (cycliste sous Furtif, bot sous Furtif, voiture d'équipe devant le cycliste) et mesure GPU au banc `grand_prix` sur le PC, validées par le propriétaire avant la fusion.

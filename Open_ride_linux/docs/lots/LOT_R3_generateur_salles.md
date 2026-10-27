# Lot R3 – Générateur de salles : profils des cinq archétypes et du boss, graine, marqueurs

## 1. Objectif

Produire, à partir d'une graine, le profil de pente et les marqueurs de chaque salle du mode Cyber-Rogue. Une salle devient une route en mémoire (distance, pente), lue par la physique et l'interpolation existantes ; le moteur de jeu (R5, R6) et l'engine (message `room`, T1) lisent les marqueurs.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/2.0/GDD_CYBER_ROGUE.md` §2.4, §2.5 et §2.7, `docs/2.0/PLAN_SERIE_R.md` §2 et §7.
2. `docs/lots/LOT_R0_delai_frein.md` §4.3 (règles tirées de la mesure du frein), `docs/lots/LOT_T1_contrat_1_4.md` §4.3 (forme de `room`).
3. Code : `core/src/openride_core/route.py` (route en mémoire, interpolation), `core/src/openride_core/physics.py` (vitesse d'équilibre à une puissance donnée).

## 3. Prérequis

Aucun pour le code. Les valeurs issues de R0 (durée minimale d'une bosse, chute maximale) sont des paramètres ; leurs défauts sont ceux du §4.3.

## 4. Travail demandé

### 4.1 Interface

- `generate_room(archetype, variant, objective, nominal_s, rider, seed, balance) -> Room`, pur et déterministe (même entrée, même salle, à l'octet près).
- `Room` : `archetype`, `variant`, `length_m`, `nominal_s`, `profile` (pente tous les 10 m), `markers`, `firewall_plan` (puissance du Firewall en fraction de FTP, par tronçon), `target_frac` (cible de puissance par tronçon, pour R4 et R7).
- **Longueur en distance, durée nominale en temps :** chaque tronçon est conçu en secondes, puis converti en mètres avec la vitesse d'équilibre d'un cycliste qui tient la cible du tronçon (`physics.py`, masse et CdA du profil du cycliste). Un cycliste sur la cible finit la salle en `nominal_s` ± 2 %.
- `room_to_route(room) -> Route` : route en mémoire sans GPS, lue par `route.py` comme une route de parcours.

### 4.2 Profils (valeurs de départ)

Pente de l'ennemi, avant le décalage du braquet (Q2). Les fractions de FTP sont celles du Firewall.

| Archétype | Variante endurance | Variante seuil | Variante VO2max |
| --- | --- | --- | --- |
| Diesel | Rampe 2 à 3 %, Firewall 0,68 | Rampe 3 à 4 %, Firewall 0,90 | — |
| Puncheur | — | — | Bosses de 15 s à 9 %, creux de 30 s à −2 % ; Firewall 0,80 en moyenne |
| Grimpeur | Paliers d'une minute 2, 3, 4 % ; Firewall 0,70 | Paliers 4, 7, 10 % ; Firewall 0,88 | Paliers 5, 8, 10 % ; Firewall 0,95 |
| Sprinteur | — | Plat 0 % ; Firewall 0,75, salves à 1,30 pendant 10 s toutes les 45 s | Plat 0 % ; Firewall 0,80, salves à 1,50 pendant 8 s toutes les 40 s |
| Saboteur | Pente de 1 à 3 % (bruit lissé, période 30 à 60 s) ; Firewall 0,68 | Pente de 2 à 5 % ; Firewall 0,88 | — |

- **Règles tirées de R0 :** durée minimale d'une bosse `min_bump_s` (défaut 15 s ; 30 s si R0 l'exige, le creux passe alors à 30 s) ; chute de pente maximale `max_drop_pts` en 10 s (défaut 5 points ; les chutes plus fortes sont étalées).
- Pente bornée à −3 à +10 % avant braquet : avec la vitesse 12 (+6 points), la pente envoyée reste dans la plage du trainer (+16 %).

### 4.3 Marqueurs

| Marqueur | Pose | Paramètre |
| --- | --- | --- |
| `arch` (Perfect Shift) | À chaque rupture de pente d'au moins 3 points, `arch_lead_s` avant (défaut 0,8 s, valeur de R0) | Sens conseillé : `up` ou `down` |
| `strike_target` | Diesel : à la fin de chaque tunnel ; Grimpeur : balises d'armure ; boss phase 1 : verrous | Points d'armure |
| `parry_zone` | Puncheur : zone bleue de 2 s avant chaque bosse ; boss phase 2 : ondes de choc | — |
| `tunnel` | Diesel : tunnels de cadence de 20 s toutes les 40 s | Cadence visée (90) et tolérance (3) |
| `rock` | Grimpeur : rochers à briser, un par palier | Armure (2) |
| `pad` | Sprinteur : pavés de boost de 8 s pendant les salves | Seuil (1,40 FTP) et braquet minimal (10) |
| `purge` | Saboteur : balise de purge 20 s après chaque piratage | — |
| `shockwave` | Boss phase 2 : toutes les 30 s | — |

- Cibles (`strike_target`), zones de parade (`parry_zone`) et balises (`purge`) ne se chevauchent jamais, avec au moins 1 s d'écart à la vitesse nominale : un appui sur Z n'a qu'un sens (plan de boutons commun).

### 4.4 Le boss « la Chimère centrale »

Une salle par phase, durées d'une run de 45 min (R15 les adapte aux autres durées) :
1. Blindage, 3 min : rampe à 5 % (3 % en endurance), 4 verrous `strike_target` ;
2. Furie tactique, 4 min : enchaînement 8 / 0 / 10 % par blocs de 40 s (4 / 0 / 5 % en endurance), ondes de choc ;
3. Exécution, 90 s : 0 %, Firewall à 1,20 FTP (0,85 en endurance).
30 s de transition à 0 % avant chaque phase (soit 10 min au total pour 8 min 30 de combat).

## 5. Fichiers concernés

- **Créés :** `core/src/openride_core/rogue/rooms.py`, `core/tests/test_rogue_rooms.py`.
- **Modifiés :** `core/src/openride_core/rogue/balance.py` (paramètres des profils), `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe.
2. Déterminisme : 100 graines × 5 archétypes × variantes, deux appels identiques donnent le même profil et les mêmes marqueurs.
3. Un cycliste simulé qui tient `target_frac` finit chaque salle en `nominal_s` ± 2 %.
4. Aucune bosse plus courte que `min_bump_s`, aucune chute de plus de `max_drop_pts` en 10 s, pente toujours entre −3 et +10 %.
5. Une arche avant chaque rupture d'au moins 3 points ; aucun marqueur hors de la salle.
6. `room_to_route` donne une route lue par `route.py` (longueur et pentes à 0,1 % près).
7. Un message `room` construit pour la plus longue salle (5 min, Grimpeur VO2max) tient en une partie de 60 000 octets.

## 8. Hors périmètre

- Choix des archétypes et enchaînement des salles (lot R15).
- Règles de combat liées aux marqueurs (lot R5).

## 9. Livraison (27 octobre 2026)

- `rogue/rooms.py` (`generate_room`, `room_to_route`, `Room.to_message`), paramètres des profils dans `RogueBalance.room_profiles` et ses champs de salle (`rogue/balance.py`). Tests : `core/tests/test_rogue_rooms.py` (157 cas, 7 s).
- **Conception en secondes, conversion en mètres** avec la vitesse d'équilibre à la cible de chaque tronçon ; `Room.time_s` donne le temps nominal à chaque point du profil, `firewall_plan` et `target_frac` sont des tronçons `Stretch` en distance (égaux au départ : le joueur tient le rythme du Firewall, R7 pourra les séparer).
- **Choix de lecture du cahier :** `variant` vaut `""` ou `"30_30"` (Puncheur, imposé quand `min_bump_s` dépasse la bosse de 15 s) et `"phase1"` à `"phase3"` pour le boss (archétype `boss`) ; l'objectif choisit la colonne du tableau, et la colonne la plus proche est prise quand l'archétype n'en a pas (Diesel en VO2max donne le seuil, Puncheur en endurance donne le VO2max). Grimpeur : le dernier palier se prolonge si la durée dépasse les paliers prévus. Sprinteur et Puncheur : la graine décale la première salve ou le premier creux ; Diesel : la graine décale la rampe de ±0,2 point ; Saboteur : somme de deux sinusoïdes de période 30 à 60 s.
- Les fractions de FTP du boss (phase 1 : 0,90 et 0,70 en endurance ; phase 2 : 1,00 / 0,70 / 1,05 et 0,80 / 0,60 / 0,85 ; transition : 0,50) ne figuraient pas au cahier : valeurs de départ à valider en R14.
- `param` des marqueurs est un nombre ou un texte (schéma de `room`) : cadence visée des tunnels, armure, seuil de FTP des pavés, délai de piratage des balises de purge, sens `up`/`down` des arches. La tolérance des tunnels (3 rpm) et le braquet minimal des pavés (10) sont dans `RogueBalance`.
- Les chutes de pente sont étalées (au plus `max_drop_pts` en 10 s), les montées restent brusques ; les arches (`arch_lead_s` avant) sont posées au début de chaque rupture de 3 points ou plus.

# OpenRide 2.0 – Sprints, montées chronométrées et bonus (série T)

25 octobre 2026. Demande du propriétaire : ajouter au mode classique, comme dans Zwift, des zones de sprint, des montées chronométrées et des bonus (légèreté, aérodynamique, puissance). Ce plan les découpe en lots. **La série T commence après la 1.0.** Les cahiers des lots seront rédigés au démarrage de la série et ajoutés à `docs/lots/00_INDEX.md`.

## 1. En résumé

Presque tout tient dans le core, sans toucher au pilotage du trainer :

- **Segments :** un segment est un intervalle `[s_début, s_fin]` de la route. Il est détecté automatiquement sur le profil (montées) ou déclaré à la main (sprints), puis rangé dans une nouvelle couche facultative `segments` du `.world`.
- **Chronométrage :** le core chronomètre chaque passage à 50 Hz, avec l'heure de franchissement interpolée. Il compare au record personnel et publie l'écart en direct.
- **Bonus :** ils modifient pendant quelques secondes les paramètres de `core/src/openride_core/physics.py` (masse, CdA, puissance prise en compte) et n'agissent que sur la vitesse virtuelle, comme dans Zwift. Ils s'activent avec le bouton Z du Click, libre en mode classique (Y y met en pause depuis le lot N6).

Ce plan réutilise ce que la série R a déjà prévu : règles du jeu dans le core, boutons Y, Z et A dans le contrat, données d'équilibrage dans un fichier modifiable. Il s'articule aussi avec la série P (décor vivant), qui ajoute le vent physique (P2) et l'aspiration derrière les bots (P3).

## 2. Ce qui se réutilise

| Besoin | Existant | Où |
| --- | --- | --- |
| Position, pente, altitude le long de la route | Lecture du `.world` et interpolation | `core/src/openride_core/route.py` |
| Ajout d'une couche sans recompiler la route | `add-layer` du compilateur, versions par couche | `docs/contracts/world_format_v1.md` §2 et §10 |
| Masse, CdA, rendement, terme d'aspiration | `PhysicsParams`, `alpha_draft` | `core/src/openride_core/physics.py` |
| Bots et fantôme à chronométrer aussi | Lot N9 | `docs/lots/LOT_N9_bots_core.md` |
| Historique des séances | Lecture des séances passées | `core/src/openride_core/tools/history.py` |
| Bouton Z décodé | `KEYPAD_BITS` du boîtier droit | `core/src/openride_core/zwift_click.py` |
| Bandeaux et HUD | Modèle du HUD, bandeau | `engine/scripts/hud_view_model.gd`, `engine/scripts/banner.gd` |

## 3. Choix de conception proposés

### 3.1 Segments

- **Montées (détection automatique) :** au moins 500 m, une pente moyenne d'au moins 3 % et un gain d'au moins 30 m. Les montées voisines séparées par moins de 200 m de replat sont fusionnées. Une catégorie de 4 à HC est calculée à partir du produit longueur × pente.
- **Sprints :** déclarés à la main dans un petit fichier à côté du GPX (début et fin en km), ou proposés automatiquement sur un tronçon de 200 à 500 m entre −1 et +2 %, au plus un tous les 10 km.
- **Parcours de démonstration :** un sprint et une montée, pour tester sans trace réelle.
- **Boucles et aller-retour :** un segment se chronomètre à chaque passage ; sur un aller-retour, il ne compte que dans le sens où il a été défini.

### 3.2 Chronométrage et records

- L'heure d'entrée et de sortie est interpolée entre deux pas de 50 Hz : la précision est d'environ 0,02 s.
- Une pause pendant un segment l'annule ; une pause `trainer_lost` aussi.
- Chaque passage garde : temps, puissance moyenne, W/kg, vitesse moyenne, bonus utilisés.
- Les records personnels par parcours et par segment sont dans `~/OpenRide/`, recalculables depuis le journal des séances.
- En direct : distance jusqu'au prochain segment, chrono, écart au record (« −3,2 s »), puis le résultat à l'arrivée.
- Classement local du passage : toi, tes records passés, les bots et le fantôme (N9).

### 3.3 Bonus

| Bonus | Effet proposé | Durée |
| --- | --- | --- |
| Légèreté | Masse totale × 0,90 | 15 s |
| Aérodynamique | CdA × 0,75 | 15 s |
| Puissance | Puissance prise en compte par la physique × 1,10 | 15 s |

- **Obtention :** un bonus au hasard à la fin de chaque segment, et sous une arche tous les 5 km. Un seul bonus en réserve ; un nouveau remplace l'ancien.
- **Activation :** bouton Z du Click, appui court (touche du clavier en secours). Pas d'activation automatique.
- **Boutons du mode classique :** + et B changent de braquet (appui long : 10 braquets), Y met en pause (lot N6, accord du propriétaire du 25 octobre), Z active le bonus ; A reste libre.
- **Valeurs :** dans un fichier de données modifiable, comme la table d'équilibrage de la série R.
- **Résistance au trainer :** inchangée par les bonus, comme dans Zwift. Seule exception, voulue : le supplément de pente dû au vent et à l'aspiration (série P, `feel = "grade"`) se calcule avec le CdA courant, donc le bonus aéro l'allège aussi, sans deuxième calcul : P2 et P3 calculent ce supplément à chaque pas avec les `PhysicsParams` courants (CdA et masse).
- **Fichiers :** la puissance du FIT et du journal reste la puissance mesurée. La vitesse et la distance restent les valeurs virtuelles, comme aujourd'hui. Les bonus utilisés vont au journal.
- **ERG :** les segments sont chronométrés, les bonus sont désactivés (entraînement structuré).

### 3.4 Contrat

Les ajouts suivent ceux de la série P, qui prend la version 1.2 du contrat IPC (lot P1). La série T, comme la série R, passe donc en **v1.3**, par ajouts compatibles :

- **Format `.world` 1.x :** couche facultative `segments` (`segments.json` : identifiant, nom, type `sprint` ou `climb`, `s_start`, `s_end`, longueur, pente moyenne, gain, catégorie, source `auto` ou `manual`). L'engine la lit lui-même, comme les autres couches.
- **Trame `state` :** champ facultatif `segment` (segment en cours ou prochain, distance, chrono, écart au record) et champ `powerup` (bonus en réserve, bonus actif, temps restant).
- **Message `segment_result` :** temps, record battu ou non, classement du passage.
- **Événements `input` Z et A :** communs aux séries R et T ; le premier des lots de contrat (R1 ou T1) les ajoute. Y arrive avant, avec la pause du lot N6.

## 4. Risques

| # | Risque | Parade |
| --- | --- | --- |
| 1 | Profil bruité : faux départs de montée sur une trace GPS | Détection sur la pente lissée déjà utilisée par la route, seuils en constantes, vecteurs de test |
| 2 | Records faussés par les bonus | Records « avec bonus » et « sans bonus » séparés (question T-Q1) |
| 3 | Bonus puissance perçu comme une triche dans l'historique (NP, TSS) | Bilan calculé sur la puissance mesurée, jamais sur la puissance bonifiée |
| 4 | Conflit de version du contrat avec les séries P et R | Ordre fixé : P1 en v1.2, puis R et T en v1.3 |
| 5 | HUD chargé (vent, abri, ERG, segment, bonus) | Blocs segment et bonus dans le coin supérieur droit, hors de la colonne HUD de gauche ; le lot P16 laisse cette zone libre |

## 5. Lots de la série T

| Lot | Contenu | Dépend de | Type |
| --- | --- | --- | --- |
| T1 | Contrat : couche `segments` du `.world`, champs `segment` et `powerup`, message `segment_result`, événements Z et A (IPC v1.3) | P1 | Interne (décision) |
| T2 | Détection automatique des montées et des sprints (module pur, vecteurs de test) | — | Délégable |
| T3 | Compilateur : couche `segments` par `add-layer`, sprints déclarés à la main, segments du parcours de démonstration | T1, T2 | Délégable |
| T4 | Chronométrage dans le core : franchissements interpolés, pauses, boucles et aller-retour, journal | T1, T2 | Délégable |
| T5 | Records personnels et classement local (historique, bots, fantôme) | T4, N9 | Délégable |
| T6 | Bonus : types, obtention, activation par Z, effets sur `PhysicsParams`, fichier de valeurs, désactivés en ERG | T1 | Délégable |
| T7 | Bonus et série P : supplément vent et aspiration calculé avec le CdA courant, essais combinés | T6, P2, P3 | Délégable |
| T8 | Engine : lignes de départ et d'arrivée en 3D, arches de bonus, panneaux « Sprint » et « Montée » | T1 | Interne (rendu) |
| T9 | Engine : HUD segment (approche, chrono, écart au record, résultat) et HUD bonus (icône, compte à rebours), coin supérieur droit | T1, P16 | Interne |
| T10 | Menu : records par parcours, option bonus | T5, N6 | Interne |
| T11 | Recette sur ton PC et ton vélo : un sprint, une montée réelle, chaque bonus | T3 à T10 | Propriétaire |

Ordre conseillé : T1 après P1, puis T2, T4 et T6 en parallèle ; T3, T5 et T7 ensuite ; enfin l'engine (T8 à T10) et la recette T11. Les numéros T ne se confondent pas avec les constats d'audit, et les lots R non plus (les constats « R3 » et « S2 » du lot M9 sont sans rapport).

## 6. Questions pour le propriétaire

- [ ] **T-Q1 Records :** séparer « avec bonus » et « sans bonus » ? (Recommandé : oui.)
- [ ] **T-Q2 ERG :** bonus désactivés en ERG, segments chronométrés quand même ? (Recommandé : oui.)
- [ ] **T-Q3 Ressenti :** les bonus ne changent pas la résistance du trainer, hors vent et aspiration ? (Recommandé : oui, comme Zwift.)
- [ ] **T-Q4 Valeurs :** légèreté −10 % de masse, aéro −25 % de CdA, puissance +10 %, 15 s chacun, un bonus par segment et tous les 5 km ? (Recommandé : oui, modifiable dans le fichier de données.)
- [ ] **T-Q5 Maillots :** un maillot vert (sprint) et à pois (montée) quand tu détiens le record d'un segment ? (Facultatif.)

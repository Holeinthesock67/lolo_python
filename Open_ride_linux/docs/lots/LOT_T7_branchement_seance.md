# Lot T7 – Core : série T branchée dans la séance (segments, records, bonus, maillots, écarts)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 2.0 série T : branchement dans la séance du core (segments, records, bonus et bouton Z, supplément vent et aspiration avec le CdA courant, maillots, écarts, champs de la révision 1.4, journal, option `[powerups]`) | Python | T1 à T6, T14, T16, P2, P3 (livrés) | Grande | **Livré le 27 octobre** (issue #397) ; `classic.py`, révision 1.4 annoncée par le core |

## 1. Objectif

Brancher dans la séance du core les modules purs déjà livrés de la série T (T2, T4, T5, T6, T14, T16) et remplir les champs du contrat 1.4 (lot T1) qui les concernent. Le plan prévoyait pour T7 « bonus et série P : supplément vent et aspiration calculé avec le CdA courant » ; ce supplément ne se calcule qu'une fois les bonus branchés dans le pas de physique. T7 devient donc **le lot d'intégration de la série T**, comme R8 pour la série R et V11 pour la série V (un seul lot de branchement par série, sans exception). Le supplément vent et aspiration avec le CdA courant en fait partie.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_T.md` §3 et §6 (décisions T-Q1 à T-Q6 et du 27 octobre).
2. Contrat : `docs/contracts/ipc_v1.md` révision 1.4 (champs `segment`, `powerup`, `jerseys`, `bot_ahead`, `bot_behind`, champs des bots, `summary.segments`, message `segment_result`) ; `docs/contracts/world_format_v1.md` §8 bis (couche `segments.json`).
3. Cahiers livrés : `LOT_T2_detection_segments.md`, `LOT_T3_couche_segments.md`, `LOT_T4_chronometrage_segments.md`, `LOT_T5_records_classement.md`, `LOT_T6_bonus.md`, `LOT_T14_points_maillots.md`, `LOT_T16_ecarts_temps_passage.md`.
4. Code : `core/src/openride_core/session.py` (pas `_step`, vent et aspiration des lots P2 et P3), `ipc_server.py`, `route.py` (lecture du `.world`), `journal.py`, `recorder.py`, `resume.py`, `fit_export.py`, `config.py`, `settings.py` ; modules `segments.py`, `segment_timing.py`, `records.py`, `powerups.py`, `jerseys.py`, `gaps.py`, `bots.py`.

## 3. Prérequis

T1 et T3 (livrés le 27 octobre), T2, T4, T5, T6, T14, T16, P2, P3 et la PR #287 (boutons, révision 1.3), tous livrés. T12 n'est pas nécessaire : les bots de N9 (puissance constante) sont chronométrés et marquent des points ; T12 changera seulement leur puissance et ajoutera leurs champs de profil.

## 4. Travail demandé

**Chargement du parcours.** `route.py` lit la couche `segments.json` si le manifeste la déclare (sinon aucun segment, sans message) ; un fichier invalide est ignoré avec un avertissement, la séance reste possible. Les segments vont à un `SegmentTimer` (T4), à un `Standings` (T14) et à l'`ArchSchedule` des bonus (T6).

**À chaque pas de `RUNNING` :**

- chronométrage des segments pour le cycliste et pour chaque bot (même `SegmentTimer` par coureur) ; une pause Y annule les passages en cours du cycliste, une pause subie (trainer perdu…) les suspend (révision du 28 octobre 2026) ;
- bonus : `PowerUps.step(dt)`, arches franchies (`award("arch")`), bonus à la fin de chaque segment (`award("segment")`) ; `params(base)` donne les `PhysicsParams` du pas et `power(mesurée)` la puissance prise en compte ;
- **supplément vent et aspiration avec le CdA courant** (ancien contenu de T7) : le supplément de pente de P2 et P3 (`feel = "grade"`) se calcule avec les `PhysicsParams` du pas, bonus compris ; un bonus aéro l'allège donc, sans deuxième calcul. La pente du parcours envoyée au trainer ne dépend pas des bonus (décision T-Q3) ;
- arrivées sur les lignes de fin envoyées à `Standings.finish` ; écarts en temps de passage par `GapTracker` (T16).

**Bouton Z.** `Z_SHORT` en SIM active le bonus en réserve (plan de boutons de la spécification générale §7.1) ; touche Z du clavier par l'engine, comme le Click. En ERG, les segments sont chronométrés, mais obtention et activation sont refusées et la réserve est gardée pour le retour en SIM (T-Q2).

**Trame `state` (révision 1.4).** `segment` (segment en cours ou prochain : `id`, `kind`, `category`, `d_to_start_m`, `elapsed_s`, `gap_to_pr_s` par `RecordBook.live_gap`) ; `powerup` en SIM (`held`, `active`, `remaining_s` ; correspondance des noms : `lightweight` du module devient `light` dans le contrat, `reserve` devient `held`) ; `jerseys` (`"me"`, `id` d'un bot ou `null`) ; `bot_ahead`, `bot_behind` et, pour chaque bot, `jersey` et `gap_s`. Les champs restent absents sans segment ou sans bot. Mesure de la pire trame par `ipc_budget` inchangée (moins de 4 096 octets).

**Fin d'un passage du cycliste.** `RecordBook.ranking` puis `add` (table avec ou sans bonus, T-Q1), écriture de `~/OpenRide/records.json` hors de la boucle à 50 Hz (fil ou file d'attente), message `segment_result` envoyé 3 fois à une seconde d'intervalle, `points` gagnés par `Standings`. `equipment_gain_s` reste `null` (série V, lot V11).

**Journal et reprise.** Lignes `segment` (passage terminé : segment, tour, temps, bonus) et `jersey` (porteurs à la fin) lues par la série V (lot V5), ligne `powerup` à chaque activation (T5). `resume.py` et `recorder.py` recopient aussi les lignes `powerup`, `segment` et `jersey`. Le FIT garde la puissance mesurée.

**Fin de séance.** `summary.segments` : 10 derniers passages, `more`, porteurs des maillots.

**Options.** `config.toml` : `[powerups] mode = "on"` (à `"off"`, aucun bonus, ni arche ni réserve ; le reste fonctionne), lu par `config.py`, réglable par `set_setting` (clé ajoutée à `settings.py`, utilisée par le menu de T10). Valeurs des bonus : `~/OpenRide/powerups.toml` (T6). Révision annoncée : `CONTRACT_REV` = « 1.4 » (tous les champs de la révision sont facultatifs ; R8 et V11 ajoutent les leurs).

## 5. Fichiers concernés

- **Modifiés :** `session.py`, `route.py`, `ipc_server.py`, `journal.py`, `recorder.py`, `resume.py`, `config.py`, `settings.py`, leurs tests ; `engine/tests/fake_core.py` (trames de démonstration avec segment et bonus) ; `docs/SRS_v1.1.md` §11 (section `[powerups]`), `README.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveau :** `core/tests/test_session_serie_t.py`.
- **Interdits :** les modules purs de la série T sauf correction de bogue, le contrat IPC, l'engine hors `fake_core.py`.

## 6. Modifications de contrat autorisées

Aucune au-delà de T1. Configuration : section `[powerups]` (une clé).

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/` ; chaque trame émise valide les schémas de la révision 1.4.
2. Parcours de démonstration (une montée, un sprint) en séance simulée à 250 W : `state.segment` puis 3 messages `segment_result` identiques à la fin de chaque segment, records écrits dans `records.json` (table « sans bonus »), ligne `segment` au journal.
3. Bonus aéro activé par `Z_SHORT` : vitesse virtuelle plus haute pendant 15 s, pente envoyée au trainer égale à celle d'une séance sans bonus quand le vent est coupé ; avec du vent de face (`feel = "grade"`), supplément de pente plus faible pendant le bonus. Passage rangé dans la table « avec bonus ».
4. En ERG : `powerup` absent, `Z_SHORT` sans effet sur les bonus, segments chronométrés.
5. Pause pendant un segment : pas de `segment_result`, pas de record.
6. Avec 4 bots de N9 : `bot_ahead`, `bot_behind` et `gap_s` présents, maillot à pois au premier arrivé au sommet.
7. `[powerups] mode = "off"` : aucun champ `powerup`, aucune arche ; trames de la 1.0 inchangées sur un parcours sans segment.
8. Reprise après plantage du core : les lignes `powerup`, `segment` et `jersey` sont recopiées.

## 8. Hors périmètre

- Bots à profil et leurs champs `profile`, `cp_w`, `mass_kg`, `wbal_pct` (T12, T13).
- Rendu, HUD et menus (T8, T9, T10, T15), recette (T11).

## 9. Livraison (27 octobre 2026)

- Nouveau module `core/src/openride_core/classic.py` (`ClassicRace`) : un objet par séance réunit `SegmentTimer` (cycliste et bots, le fantôme exclu), `RecordBook`, `PowerUps` et `ArchSchedule`, `Standings` et `GapTracker` ; il donne les `PhysicsParams` et la puissance du pas, les champs de la trame `state`, les messages `segment_result`, les lignes du journal et `summary.segments`. `session.py` ne fait que l'appeler.
- `route.py` lit la couche `segments.json` (`World.segments`) ; une couche invalide est ignorée avec un avertissement. `ipc_server.py` annonce la révision 1.4 et porte `segment`, `powerup`, `jerseys`, `bot_ahead` et `bot_behind`. `journal.py`, `recorder.py` et `resume.py` écrivent et reprennent les lignes `powerup`, `segment` et `jersey`. `config.py` et `settings.py` : section `[powerups]`, clé `mode`.
- Choix faits :
  - option « Bonus » : clé `[powerups] mode = "on"` ou `"off"` plutôt qu'un booléen `enabled`, car les réglages du menu (`settings`, révision 1.3) ne connaissent que les types `int` et `choice` ;
  - le message `settings` doit tenir dans 1 400 octets : le libellé « Poids du cycliste » devient « Poids » (unité kg) pour laisser la place à « Bonus » ;
  - un segment qui commence au départ du parcours (`s_start` = 0, cas de la montée du parcours de démonstration) est chronométré : la position de départ est donnée aux chronomètres avant le premier pas ;
  - `records.json` n'est jamais réécrit s'il était illisible au départ (il est gardé tel quel, avertissement au journal) ; l'écriture passe par un fil quand la boucle asyncio tourne ;
  - après une reprise sur plantage, les segments repartent de la position du journal ; points et maillots repartent à zéro ;
  - les chemins de `records.json` et de `powerups.toml` sont des paramètres de `CoreSession` ; la suite de tests les place dans le dossier temporaire de chaque test (`core/tests/conftest.py`) ;
  - `engine/tests/fake_core.py` reste inchangé : ses trames de démonstration avec segment et bonus viennent avec le HUD qui les lit (T9).
- Tests : `core/tests/test_session_serie_t.py` (critères 2 à 8, 8 tests), révision 1.4 dans `test_contract_ipc.py`.

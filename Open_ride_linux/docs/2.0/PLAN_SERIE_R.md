# OpenRide 2.0 – Plan du mode Cyber-Rogue (série R)

25 octobre 2026. Évaluation du [GDD](GDD_CYBER_ROGUE.md) face à l'architecture d'OpenRide 1.0, décisions du propriétaire et découpage en lots. **La série R commence après la 1.0** (séries N et O) ; seul l'essai R0 peut se glisser dans les essais sur le vélo de la série O. Les cahiers des lots seront rédigés au démarrage de la série et ajoutés à `docs/lots/00_INDEX.md`.

## 1. En résumé

Le mode tient sur le socle actuel : le core pilote déjà le trainer en pente avec des braquets virtuels, connaît la FTP et décode les cinq boutons du boîtier droit du Click. Il faut surtout un moteur de partie dans le core, des ajouts compatibles à l'IPC (v1.3, après la v1.2 de la série P) et une scène Godot séparée. Le risque principal est le temps de réponse du frein, jamais mesuré.

## 2. Décisions du propriétaire (25 octobre 2026)

| # | Question | Décision |
| --- | --- | --- |
| Q1 | Où vivent les règles du jeu ? | Dans le core, en modules purs testés en pytest. L'engine n'affiche que le ruban, le décor, les ennemis et le HUD. Raison : pente envoyée au trainer, journal, FIT et reprise après plantage sont déjà dans le core, qui reste le maître |
| Q2 | Quelle formule de frein ? | Décalage centré : pente envoyée = pente de l'ennemi + (vitesse − 6) × 1 point, bornée à la plage du trainer (−10 à +16 % par défaut). La vitesse 1 retire 5 points, la 12 en ajoute 6. Le mode classique garde sa formule (la multiplicative s'inverse en descente sous −G_base, l'additive du GDD ne peut jamais alléger) |
| Q3 | Rouler trop fort en endurance ? | Surchauffe : au-delà de 75 % de la FTP, l'adrénaline se vide |
| Q4 | Table d'équilibrage ? | Oui : points de vie, dégâts, or, dans un fichier de données modifiable |
| Q5 | W' par défaut ? | 20 kJ ; modifiable dans `config.toml` et dans les menus, et estimé à partir des séances passées |
| Q6 | Durée de la run ? | Durée et objectif (VO2max, seuil, endurance) se choisissent dans le menu ; le jeu compose le scénario de la run à partir de ces deux paramètres |
| Q7 | Que donnent les châssis permanents ? | Des bonus de jeu, pas seulement l'apparence |
| Q8 | Enregistrer dans le dépôt ? | Oui : ce dossier et une issue de suivi « série R » |

**Pause :** en mode classique, Y met en pause (lot N6, accord du 25 octobre). Dans le mode Cyber-Rogue, Y sert à l'attaque ; la pause y passe par un appui long sur A (proposition, à confirmer au lot R1), pour qu'une attaque un peu longue ne coupe jamais un combat.

Conséquence de Q2 : la variation de la pente envoyée est limitée à 2 % par seconde (`grade_rate_pct_per_s`), soit 4,5 s pour passer de 0 à 9 %. Le mode Cyber-Rogue aura sa propre limite, fixée après l'essai R0.

## 3. Ce qui se réutilise

| Besoin du GDD | Existant | Où |
| --- | --- | --- |
| Frein selon pente et braquet | Pente effective bornée, envoyée en SIM FTMS | `core/src/openride_core/gearing.py`, `core/src/openride_core/ftms_driver.py` |
| Cassette de 12 vitesses | `n_gears` configurable de 2 à 40 | `core/src/openride_core/config.py` |
| FTP | `rider.ftp_w`, déjà envoyée à l'engine dans `hello_ack` | `core/src/openride_core/session.py` |
| Watts et cadence en continu | `state` à 30 Hz, physique à 50 Hz | `docs/contracts/ipc_v1.md` |
| Boutons +, A, B, Y, Z | Décodés bit par bit (`KEYPAD_BITS`) ; seuls + et − deviennent des événements | `core/src/openride_core/zwift_click.py` |
| Bouton − inutilisé | Contourne le défaut connu du boîtier gauche | idem |
| Cibles en % de FTP | Contrôleur ERG | `core/src/openride_core/workout.py` |
| Bilan, journal, FIT | NP, IF, TSS, JSONL, FIT | `core/src/openride_core/tools/session_summary.py`, `core/src/openride_core/recorder.py` |
| Historique des séances (pour W') | Cumul et lecture des séances passées | `core/src/openride_core/tools/history.py` |
| Essais sans matériel | Trainer, Click et ceinture simulés, scénarios | `core/src/openride_core/ble_sim.py`, `core/src/openride_core/sim_scenarios.py` |
| Menus au Click, lanceur | Modèle de menu, lanceur unique | `engine/scripts/menu_model.gd`, `core/src/openride_core/launcher.py` |

Ne servent pas : compilateur GPX, terrain, OSM, végétation, thèmes de paysage.

## 4. Ce qu'il faut ajouter

**Core (modules purs) :** modèle W'bal (Skiba, CP ≈ FTP par défaut) ; postures de cadence avec hystérésis ; générateur de salles à graine (profil transformé en route en mémoire, physique et interpolation inchangées) ; Firewall (cycliste virtuel à X % de FTP calculé avec `physics.py`) ; combat (bouclier, adrénaline, dégâts, fenêtres de timing, surchauffe) ; run (machine à états, deck, or, reliques, boss) ; scénariste (objectif × durée vers une suite de salles) ; progression permanente sous `~/OpenRide/` ; événements de jeu dans le journal.

**Contrat IPC v1.3 (ajouts compatibles, après la v1.2 du lot P1) :** événements `input` `Y_SHORT`, `Z_SHORT`, `A_SHORT` (B reste « − » ; communs avec la série T, ajoutés par le premier des lots R1 ou T1) ; champ facultatif `rogue` de `state` (phase, salle, bouclier, adrénaline, W'bal, posture, écart au Firewall, fenêtres actives) ; message `room` (profil et marqueurs, gros datagramme comme `routes`) ; message `loot` (3 cartes) ; commandes `start_run` (objectif, durée, graine) et `abandon_run`.

**Engine (scène séparée de la scène classique) :** ruban 3D construit depuis `room`, shader de couleur par pente, arches et zones ; décor néon (grille, glow, particules) ; ennemis géométriques et boss ; HUD diégétique (hologramme, arcs, FOV, tremblement) ; menu Cyber-Rogue (objectif, durée, W'), couloirs, cartes, fin de run.

## 5. Risques

| # | Risque | Parade |
| --- | --- | --- |
| 1 | Délai du frein inconnu (inertie du volant, notifications de 1 à 8 Hz) face à une fenêtre de 1,5 s et des bosses de 15 s | Mesurer d'abord (R0), puis caler fenêtres, durées et limite de variation de pente |
| 2 | Pente plafonnée à +16 % : un effet comme « +40 % de frein » sur un mur à 10 % serait coupé | Exprimer chaque effet de carte en points de pente, résultat borné et affiché |
| 3 | FTP fausse ou W' inconnu : équité perdue | Proposer `rampe_test.zwo` avant la première run, W' estimé (R16) |
| 4 | Click : déconnexions spontanées, latence BLE | Fenêtres tolérantes, clavier de secours, Firewall en pause si le Click tombe |
| 5 | Efforts > 140 % FTP en fin de séance | Sortie sans pénalité à tout moment, avertissement au départ |
| 6 | Le GDD ne chiffre ni points de vie, ni dégâts, ni or | Table d'équilibrage et run simulée (R7) |
| 7 | « Tron » et « Lightcycle » sont des marques ; dépôt public | Inspiration seulement, aucun de ces noms dans le jeu |
| 8 | Glow et particules sur GTX 1060 | Préréglages de qualité existants (lot L4) |

## 6. Lots de la série R

| Lot | Contenu | Dépend de | Type |
| --- | --- | --- | --- |
| R0 | Mesure du délai du frein : saut de pente, temps jusqu'au couple ressenti et jusqu'à la puissance stable (script fourni) | — | Propriétaire (vélo) |
| R1 | Contrat IPC v1.3 : événements Y, Z, A, champ `rogue`, messages `room` et `loot`, commandes de run | P1 (série P) | Interne (décision) |
| R2 | Modèle W'bal et postures de cadence avec hystérésis | — | Délégable |
| R3 | Générateur de salles : profils des 5 archétypes et du boss, graine, marqueurs | — | Délégable |
| R4 | Firewall : cycliste virtuel à X % de FTP, écart au joueur | R3 | Délégable |
| R5 | Combat : bouclier, adrénaline, dégâts, fenêtres de timing, Perfect Shift, surchauffe | R0, R2, R3 | Délégable |
| R6 | Run : machine à états, couloirs, deck et cartes, or, reliques, boss en 3 phases | R5 | Délégable |
| R7 | Table d'équilibrage en données et run simulée avec cyclistes types | R6 | Délégable |
| R8 | Intégration dans la session du core : formule centrée, boutons Y, Z, A, journal, pause et reprise | R1, R6 | Interne |
| R9 | Progression permanente : châssis à bonus de jeu, statistiques de runs | R6 | Délégable |
| R10 | Engine : scène néon, ruban 3D, shader de pente, arches et zones | R1 | Interne (rendu) |
| R11 | Engine : HUD diégétique, arcs au sol, FOV et tremblement | R1 | Interne (rendu) |
| R12 | Engine : ennemis et boss géométriques, effets d'impact | R10 | Interne (rendu) |
| R13 | Engine : menu Cyber-Rogue (objectif, durée, W'), couloirs, cartes, fin de run | R1, N6 | Interne |
| R14 | Recette sur le PC et le vélo : run complète, 60 images/s, ressenti des boutons | R8, R10 à R13 | Propriétaire |
| R15 | Scénariste de run : échauffement, salles, couloirs et boss composés à partir de l'objectif (VO2max, seuil, endurance) et de la durée | R3, R6 | Délégable |
| R16 | Estimation de CP et W' à partir des séances passées (courbe de puissance de l'historique) | — | Délégable |

Ordre conseillé : R0 et R1 d'abord ; puis R2 à R7, R15 et R16 en parallèle pendant que R10 et R11 avancent ; enfin R8, R9, R12, R13 et la recette R14. Une première salle jouable (Diesel, sans deck) est possible après R0 à R5, R8, R10 et R11.

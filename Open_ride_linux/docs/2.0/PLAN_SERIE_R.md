# OpenRide 2.0 – Plan du mode Cyber-Rogue (série R)

25 octobre 2026. Évaluation du [GDD](GDD_CYBER_ROGUE.md) face à l'architecture d'OpenRide 1.0, décisions du propriétaire et découpage en lots. **La série R commence après la 1.0** (séries N et O) ; seul l'essai R0 peut se glisser dans les essais sur le vélo de la série O. Les cahiers des lots R0 à R16 sont rédigés depuis le 26 octobre (audit de la spécification, voir §7 et §8) et listés dans `docs/lots/00_INDEX.md` ; leurs issues seront ouvertes au démarrage de la série.

## 1. En résumé

Le mode tient sur le socle actuel : le core pilote déjà le trainer en pente avec des braquets virtuels, connaît la FTP et décode les cinq boutons du boîtier droit du Click. Il faut surtout un moteur de partie dans le core, des ajouts compatibles à l'IPC (révision 1.4 ; la 1.2 est prise par Q1, N13 et O4, la 1.3 par la série P) et une scène Godot séparée. Le risque principal est le temps de réponse du frein, jamais mesuré.

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

**Boutons du mode (plan commun à tous les modes, spécification générale, §7.1, validé le 26 octobre ; remplace la répartition notée plus tôt le même jour) :** + et B courts = vitesse ±1, longs = ±3 (le grand pas remplace le Disjoncteur, sans délai de recharge) ; Y = pause et reprise, comme partout ; Z court = action du mode, selon le marqueur sous la roue : attaque sur une cible, parade dans une zone de parade, purge sur une balise du Saboteur ; en couloir, Z court relance le tirage ; Z long = carte ou relique active (au plus une équipée) ; A court = faire défiler cartes et portes quand un choix est affiché, sinon changer de vue de caméra ; A long = valider la carte ou la porte, sinon revenir à la vue par défaut ; flèches gauche et droite du boîtier gauche = précédent et suivant (raccourci, jamais indispensable). Le deck se consulte dans l'écran de pause.

Conséquence de Q2 : la variation de la pente envoyée est limitée (2 % par seconde jusqu'au lot Q4, puis 4 %/s à la montée et 8 %/s à la descente), et l'essai 69 du 25 octobre a montré environ 22 s de retard du trainer sur des marches de 0 à 7 %, surtout au relâchement. Le mode Cyber-Rogue aura sa propre limite, et la durée minimale des bosses en dépend : les deux sont fixées après la mesure R0 (règles dans le cahier de R0, §4.3).

### Corrections du 26 octobre (audit de la spécification)

Le GDD laissait des trous ou des contradictions ; les cahiers suivent ces corrections :

| Sujet | GDD | Correction |
| --- | --- | --- |
| Calendrier de 45 min | 3 ou 4 salles de 3 à 5 min et couloirs de 2 min entre 8 et 30 min : jusqu'à 28 min pour une fenêtre de 22 min | 4 salles de 3,5 min en moyenne et 4 couloirs de 2 min ; boss de 10 min dont 1,5 min de transitions ; calendriers de 30, 60 et 90 min dans R15 |
| Seuils de cadence | Roc < 70, Fluide 80 à 95, Véloce > 100 : rien entre 70 et 80 ni entre 95 et 100 | Fluide de 70 à 100 rpm, hystérésis de 3 rpm et maintien de 1,5 s ; bonus de W'bal entre 80 et 95 rpm (R2) |
| Charge du Grimpeur | Posture Roc « < 75 rpm » | Posture Roc (< 70 rpm), comme ailleurs |
| Couleurs du ruban | Cyan −3 à +1 %, jaune ou orange 2 à 6 %, magenta ≥ 7 % : trous entre 1 et 2 % et entre 6 et 7 % | Bleu < −3 %, cyan jusqu'à 1,5 %, jaune jusqu'à 4 %, orange jusqu'à 6,5 %, magenta au-delà (R10) |
| Overdrive | « +40 % de frein » | +4 points de pente, borné à la plage du trainer (risque 2) |
| Soin | Bouclier régénéré « 2 fois plus vite » | Le bouclier ne se recharge pas en combat : +1 par seconde (R6) |
| Points de vie, dégâts, or, bouclier, adrénaline | Non chiffrés | Valeurs de départ dans R5 et R6, table de données et calibrage dans R7 |
| W' et CP | 20 kJ, estimé « à partir des séances passées » | Modèle de Skiba (R2), CP = FTP par défaut ; estimation par régression travail-temps sur 3 à 20 min, avec seuils de confiance (R16) |
| Composition d'une run | « Le jeu compose le scénario » | Calendriers par durée, réservoirs d'archétypes par objectif, rattrapage d'un joueur en retard (R15) |

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

**Contrat IPC v1.4 (ajouts compatibles, après la 1.3 du lot P1) :** utilise les événements `input` de tous les boutons du Click, ajoutés à la révision 1.3 (spécification générale §6.1 et §7.1) ; liste `modes` dans `hello_ack.config` ; valeur `ROGUE` de `mode` et champ facultatif `rogue` de `state` (phase, salle, bouclier, adrénaline, W'bal, posture, écart au Firewall, fenêtres actives) ; message `room` (profil et marqueurs, gros datagramme comme `routes`) ; message `loot` (3 cartes, 2 portes) ; commandes `start_run` (objectif, durée, graine, W') et `rogue_resync` ; fin de run par `end_session` (détail dans le cahier de T1).

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
| 7 | Noms d'œuvres et de marques existantes ; dépôt public | Inspiration seulement, aucun nom d'œuvre ni de marque dans le jeu ni dans le dépôt |
| 8 | Glow et particules sur GTX 1060 | Préréglages de qualité existants (lot L4) |

## 6. Lancement dans le jeu

```text
Accueil (entrées construites depuis hello_ack.config.modes)
  Rouler · Entraînements · Cyber-Rogue · Réglages · Quitter
     └─► Départ : Objectif (Endurance, Seuil, VO2max) · Durée (30, 45, 60, 90 min) · W' · Châssis · Lancer
            └─► start_run ─► LOADING ─► Prêt (salles prévues, graine) ─► start
                   └─► RUNNING en mode ROGUE : main.gd instancie rogue.tscn à la place du monde classique
                          ├─► Y ou Échap : Pause (Reprendre · Terminer et enregistrer · Abandonner)
                          └─► fin de run ─► bilan (summary.rogue) ─► Accueil
```

- **Côté 1.0 (lanceur et menu principal, lot N15 de la PR #230) :** pas d'entrée « Cyber-Rogue » grisée ; `menu_model.gd` construit déjà l'accueil depuis une table `HOME_MODES` filtrée par `modes` (`set_modes`, appelé à chaque `hello_ack`). L'accueil se construit à partir d'une table locale de modes, filtrée par la liste `modes` que le core annoncera dans `hello_ack.config` (absente en 1.0 : `["ride", "erg"]`). Ainsi la 2.0 n'ajoute qu'une ligne à la table, et l'entrée apparaît seule quand le core sait lancer le mode. Rien à changer au contrat de la 1.0.
- Détail : cahier de T1 (§4.3), R8 (§4.1) et R13 (§4.1).

## 7. Questions ouvertes (à trancher par le propriétaire)

Chaque cahier part de la proposition ; une réponse différente se reporte dans le cahier concerné. **Réponses du propriétaire du 26 octobre (22 h 03) :** toutes les questions sont tranchées (22 h 03 et 22 h 05) ; R-Q2 a un ajout et R-Q6 une autre réponse que la proposition.

| # | Question | Proposition | Lots |
| --- | --- | --- | --- |
| R-Q1 | La difficulté du trainer (50 % par défaut, lot Q1) s'applique-t-elle au mode Cyber-Rogue ? | Non : les salles sont dessinées pour la pente réelle et les braquets donnent déjà le contrôle. **Décidé : non appliquée.** | R8 |
| R-Q2 | Joueur en retard sur le calendrier : que faire ? | Raccourcir les couloirs (jusqu'à 60 s), puis retirer une salle ; jamais le boss ni le retour au calme. **Décidé, avec un ajout du propriétaire :** une salle retirée compte comme un échec, avec un malus de points (−10 or et la salle comptée « manquée » au bilan), une animation et un son qui le signalent. | R15 |
| R-Q3 | Garder une commande `abandon_run` ? | Non : `end_session` suffit, le bilan dit `abandoned`. **Décidé : pas d'`abandon_run`.** | T1, R13 |
| R-Q4 | Durées proposées au menu | 30, 45, 60 et 90 min. **Décidé.** | T1, R15 |
| R-Q5 | Seuils de cadence corrigés (Fluide de 70 à 100 rpm, hystérésis 3 rpm, maintien 1,5 s) | À valider sur le vélo en R14. **Décidé comme réglage de départ, à essayer sur le vélo.** | R2 |
| R-Q6 | Pause par appui long sur A (0,9 s), aucun autre bouton pendant une run | **Décidé autrement :** même pause que les autres modes (Y), puis plan de boutons commun (spécification générale, §7.1) : Z = attaque, parade et purge, A = choisir et valider (§2) | T1, R5, R6, R8, R13 |
| R-Q7 | Qu'est-ce qu'une relique de départ ? | Une carte passive parmi 3 (bouclier +20, or +25 %, fenêtre de Perfect Shift +0,3 s). **Décidé.** | R6 |
| R-Q8 | Une carte de module A remplace-t-elle le Disjoncteur ? | Oui, comme le dit le GDD. **Revu avec le plan de boutons commun :** le Disjoncteur devient l'appui long sur B (−3 vitesses) et la carte active passe sur Z long ; elles ne se remplacent plus. Une seule carte active équipée | R5, R6 |
| R-Q9 | Valeurs de départ de l'équilibrage (R5, R6) et cibles de R7 | À accepter comme point de départ, calibrées par R7 puis R14. **Décidé : à ajuster après les essais.** | R5 à R7 |
| R-Q10 | Châssis : bonus bornés à 10 %, vies à 30 pièces, au plus 3, utilisées automatiquement | Oui. **Décidé.** | R9 |

## 8. Lots de la série R

| Lot | Contenu | Dépend de | Type |
| --- | --- | --- | --- |
| R0 | Mesure du délai du frein : saut de pente, temps jusqu'au couple ressenti et jusqu'à la puissance stable (script R0a délégable, même outil que X5 du plan des outils de test ; essai R0b sur le vélo) | Q3, Q4 | Propriétaire (vélo) |
| T1 | Contrat IPC 1.4 commun aux séries R, T et V (lot de la série T) ; partie R : valeur `rogue` de `modes`, champ `rogue`, messages `room` et `loot`, commandes de run, bilan | P1 (série P) | Interne (décision) |
| R2 | Modèle W'bal et postures de cadence avec hystérésis | — | Délégable |
| R3 | Générateur de salles : profils des 5 archétypes et du boss, graine, marqueurs | — | Délégable |
| R4 | Firewall : cycliste virtuel à X % de FTP, écart au joueur | R3 | Délégable |
| R5 | Combat : bouclier, adrénaline, dégâts, fenêtres de timing, Perfect Shift, surchauffe | R0, R2, R3 | Délégable |
| R6 | Run : machine à états, couloirs, deck et cartes, or, reliques, boss en 3 phases | R5 | Délégable |
| R7 | Table d'équilibrage en données et run simulée avec cyclistes types | R6 | Délégable |
| R8 | Intégration dans la session du core : formule centrée, boutons Z et A, pause Y, journal, pause et reprise | T1, R6, R15 | Interne |
| R9 | Progression permanente : châssis à bonus de jeu, statistiques de runs, vies achetées avec les pièces de la série V (une vie évite la dégradation du butin après une défaite), dans le système de déblocage commun de la série V | R6, V2, V3b | Délégable |
| R10 | Engine : scène néon, ruban 3D, shader de pente, arches et zones | T1 | Interne (rendu) |
| R11 | Engine : HUD diégétique, arcs au sol, FOV et tremblement | T1 | Interne (rendu) |
| R12 | Engine : ennemis et boss géométriques, effets d'impact | R10 | Interne (rendu) |
| R13 | Engine : lancement depuis l'accueil, écran de départ (objectif, durée, W', châssis), couloirs, cartes, pause, fin de run | T1, R8, R10, R11, N6, O4 | Interne |
| R17 | Direction artistique : charte néon (palette, formes, post-traitement), matériaux et shaders partagés, catalogue des objets graphiques (vélo, traînée, portes, cartes, coffres…) et des effets, planche de démonstration ; tout généré par le code (demande du propriétaire du 27 octobre) | T1 | Délégable (shaders) ; charte validée par le propriétaire |
| R14 | Recette sur le PC et le vélo : run complète, 60 images/s, ressenti des boutons | R8, R10 à R13 | Propriétaire |
| R15 | Scénariste de run : échauffement, salles, couloirs et boss composés à partir de l'objectif (VO2max, seuil, endurance) et de la durée | R3, R6 | Délégable |
| R16 | Estimation de CP et W' à partir des séances passées (courbe de puissance de l'historique) | — | Délégable |

Ordre conseillé : R0 et T1 d'abord, puis R17 avant tout rendu (le script de R0 peut être fait avant la 1.0, comme l'outil X5) ; puis R2 à R7, R15 et R16 en parallèle pendant que R10 et R11 avancent ; enfin R8, R9, R12, R13 et la recette R14. Une première salle jouable (Diesel, sans deck) est possible après R0 à R5, R8, R10 et R11.

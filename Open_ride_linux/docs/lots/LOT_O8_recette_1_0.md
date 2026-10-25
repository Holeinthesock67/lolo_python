# Lot O8 – Recette de la version 1.0 et publication

## 1. Objectif

Déclarer la 1.0 quand OpenRide a été installé, utilisé et validé de bout en bout sur le matériel de référence, sans terminal. Ce lot rassemble **en une seule liste** les essais restés ouverts (suivi d'avancement §3, recette E3/E4, critères de la SRS §13) et les étapes de publication. Il est fait par le propriétaire, avec l'aide d'une session qui lit les journaux et corrige ce qui casse.

**Lot interne :** essais sur le vélo, le Click, la ceinture et la GTX 1060.

## 2. À lire

`docs/SUIVI_AVANCEMENT.md` §3, `docs/RECETTE_E3_E4.md`, `docs/SRS_v1.1.md` §13, `docs/GUIDE_UTILISATION.md` (O6), `CHANGELOG.md` (O2).

## 3. Prérequis

Série N fusionnée, O1 à O6 et O9 à O15 fusionnés ; O7 selon le choix du propriétaire. Fin de J4 (issue #50) pour l'installation hors du dépôt.

## 4. Liste de recette

Chaque ligne se coche dans ce cahier (section « Livraison ») avec la date et, si besoin, le numéro de la PR qui a corrigé un défaut. Les lignes **en gras** sont bloquantes pour la 1.0 ; les autres peuvent glisser en 1.0.x.

**Installation (session Ubuntu vierge ou second compte)**
1. **Installation en une commande (N14), icône présente, premier démarrage guidé.**
2. **Mise à jour depuis l'icône : parcours, séances et `~/OpenRide/config.toml` conservés.**

**Matériel**
3. **Appairage depuis le menu : trainer, deux boîtiers du Click (bouton + identifié), ceinture (N12, N13).**
4. **Séance libre de 10 min ou plus en SIM avec braquets perceptibles, puis relecture des mesures `Perf` du journal.**
5. **Un `.zwo` complet en ERG : cibles tenues, biais ± 2 % au Click, bip à T − 3 s (lot F, N7).**
6. **Click : boîtier gauche ou contournement par B du boîtier droit utilisable pendant toute une séance de 30 min (journal K8 sans coupure non reprise).**
7. Ceinture cardio réelle : contact, choix de l'appareil, batterie (M2).
8. Erreur ATT éventuelle suivie de « renvoi 1/2 » et non d'une reconnexion (M1).
9. Biais et coupures dans le bilan (M4) ; cible ERG et écart par bloc (L6).
10. Délai appui → commande au trainer relevé dans le journal.
11. Trainer libéré après la séance : une autre application s'y connecte (déjà validé le 24 octobre, à revérifier depuis l'icône).

**Entraînement (série O, ajouts du 25 octobre)**
12. **Test de FTP par rampe complet sur le HomeTrainer, fin détectée, nouvelle FTP acceptée depuis le menu (O10, O12).**
13. **Une séance du jour d'un plan, roulée puis comptée (O11, O12).**
14. **Courbes de cible, puissance, FC et cadence justes et lisibles pendant une séance ERG (O14).**
15. Un `.erg` exporté de GoldenCheetah roulé en entier (O9) ; un parcours choisi par la bibliothèque avec ses filtres (O15).

**Rendu (GTX 1060, 1 920 × 1 080)**
16. **Recette E3/E4 (`docs/RECETTE_E3_E4.md`) : ciel, brouillard, arbres, bâtiments, eau, sons.**
17. **30 images/s en qualité basse sur un parcours avec village (SRS sprints 3 et 5), relevé `[perf-rendu]`.**
18. **1 h de séance sans plantage ni saccade visible.**
19. Préparation des arbres sous 150 ms (`UNIT=test_tree_renderer`, O1).
20. Menus, écran Appareils, Réglages (si O4), bilan lisibles à 2 m et pilotables au Click.

**Fichiers et parcours**
21. **Un FIT de séance OpenRide importé sans erreur dans Garmin Connect et dans GoldenCheetah.**
22. Pente maximale d'une vraie trace de col à ± 1 point de Garmin Connect (sprint 2).
23. Parcours tiré d'un vrai FIT Garmin, déposé tel quel dans `~/OpenRide/GPX/` (M7, O5), roulé.
24. Historique des séances réelles (`openride-core history --weeks 8`, L7).

**Documentation**
25. **Le guide d'utilisation (O6) suivi du début à la fin sans terminal, hors installation.**

## 5. Publication

1. Tous les tests passent sur le PC cible (`core`, `compiler`, `engine/tests/run_engine_tests.sh`, `run_e2e.sh`, `run_visual_tests.sh`).
2. `scripts/bump-version.sh 1.0.0` (O2), `CHANGELOG.md` complété (défauts corrigés pendant la recette), `docs/SUIVI_AVANCEMENT.md` remis à plat (cases cochées ou reportées en 1.0.x).
3. PR « Version 1.0.0 », fusion, puis étiquette `v1.0.0` sur `main` et release GitHub avec les notes de version (depuis une session cloud, jamais depuis un clone local ancien).
4. Vérification de confidentialité avant l'étiquette : aucune donnée personnelle dans l'arbre de `main` (recherche des noms, coordonnées, adresses Bluetooth réelles, nom du trainer, fichiers d'activité), comme lors de l'audit du 24 octobre.

## 6. Hors périmètre

- Paquet `.deb` ou Flatpak, démarrage automatique (cahier N14 §8).

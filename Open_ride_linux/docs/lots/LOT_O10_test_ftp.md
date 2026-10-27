# Lot O10 – Test de FTP : test par paliers (rampe) et test de 20 minutes, côté core

## 1. Objectif

Pour que l'ERG soit juste, la FTP doit être la vraie. Ce lot ajoute deux tests de FTP qui se roulent comme un entraînement et proposent à la fin une nouvelle FTP, enregistrée dans `~/OpenRide/config.toml` après accord du cycliste :

- **test par paliers (rampe)** : la cible monte par paliers d'une minute jusqu'à ce que le cycliste ne tienne plus ; FTP = 75 % de la meilleure puissance moyenne sur 1 minute ;
- **test de 20 minutes** : échauffement guidé, 20 minutes à fond en mode libre (SIM sur le plat ou ERG désactivé), FTP = 95 % de la puissance moyenne des 20 minutes.

L'écran du menu (choix du test, acceptation de la nouvelle FTP) est le lot O12.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_F_erg_zwo.md`, `docs/lots/LOT_K7_bilan_seance.md` (meilleures puissances), `docs/lots/LOT_O3_reglages_core.md` (écriture de `config.toml`).
2. Code : `core/src/openride_core/workout.py` (`ErgController`), `core/src/openride_core/session.py` (fin de séance, pause), `core/src/openride_core/tools/session_summary.py` (meilleures puissances), `core/src/openride_core/config_edit.py` (écriture ciblée de `config.toml`, lots N12 et O3).

## 3. Prérequis

O3 fusionné (écriture de la FTP). O9 utile (blocs en watts absolus) : sinon, le lot ajoute lui-même le mode absolu au `Block` et O9 le réutilise.

## 4. Travail demandé

- Nouveau module `core/src/openride_core/ftp_test.py` :
  - `ramp_workout(start_w=100, step_w=20, step_s=60, warmup_s=300)` : `Workout` en watts absolus (échauffement puis paliers), paliers générés jusqu'à 700 W au plus ;
  - `twenty_min_workout(ftp_w)` : échauffement de 20 min avec deux efforts courts, récupération, puis 20 min en bloc `freeride` (pas de cible), retour au calme ;
  - **détection de fin de la rampe** : cadence sous 50 tr/min pendant 5 s, ou puissance sous 80 % de la cible pendant 10 s, ou abandon volontaire (le geste de saut de bloc du Click, déjà géré en ERG, vaut abandon pendant le test) ; la séance passe alors au retour au calme (5 min à 100 W) au lieu de s'arrêter net ;
  - `estimate_ftp(records, kind) -> FtpResult` (`ftp_w`, méthode, puissance de référence, durée tenue, palier atteint, avertissements : test trop court, cadence erratique, coupure du trainer pendant l'effort) ; valeurs arrondies à 1 W.
- Séance : `openride-core run --ftp-test ramp|20min` ; le résultat est écrit dans le journal (ligne `ftp_test` à la fin, format décrit dans `journal.py`) et affiché dans `openride-core summary`.
- Acceptation : `openride-core ftp-test --accept [FICHIER]` relit le dernier test (ou le journal donné) et écrit `[rider] ftp_w` via `config_edit` ; sans `--accept`, il affiche l'ancienne et la nouvelle FTP et l'écart.
- Historique des tests : `openride-core ftp-test --history` liste les tests trouvés dans `~/OpenRide/Activities/` (date, méthode, FTP), pour voir la progression.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/ftp_test.py`, `core/tests/test_ftp_test.py`.
- **Modifiés :** `session.py`, `journal.py` (ligne `ftp_test`, champ facultatif ; format v1 toujours lisible), `tools/session_summary.py`, `__main__.py`, `README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** l'engine, le contrat IPC (le résultat passera au menu par O12).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Rampe simulée (cycliste simulé qui tient jusqu'à 340 W puis lâche) : fin détectée en moins de 10 s, retour au calme enclenché, FTP proposée = 75 % de la meilleure minute (à 1 W près).
3. Test de 20 min simulé à 260 W de moyenne : FTP proposée 247 W.
4. Coupure simulée du trainer pendant l'effort : avertissement dans le résultat, aucune écriture automatique.
5. `ftp-test --accept` sur un fichier de configuration temporaire ne change que `ftp_w` (commentaires conservés, `.bak` créé) ; FTP hors bornes de `config.py` refusée.
6. Journaux anciens sans ligne `ftp_test` : `summary` et `history` inchangés.

**Sur le PC cible (le propriétaire) :** une rampe complète sur le HomeTrainer ; vérifier que la fin est détectée vite et que la FTP proposée paraît juste.

## 8. Hors périmètre

- Écran du menu et acceptation au Click (lot O12).
- Estimation de la FTP sans test, à partir de l'historique (modèle CP, version 2.0).

## 9. Livraison

Livré le 27 octobre 2026 (issue #154), thread « Développer les lots O restants ».

- `core/src/openride_core/ftp_test.py` : `ramp_workout`, `twenty_min_workout`, `workout_for`, `planned_workout` et `planned_duration_s` (pour les plans du lot O11 : la rampe attendue s'arrête au palier où la meilleure minute vaut FTP / 0,75), `RampWatch` (fin de la rampe), `estimate_ftp` et `FtpResult`, `run` (commande `ftp-test`).
- Une séance de test est un entraînement d'identifiant `ftp_test:ramp` ou `ftp_test:20min` : `select_workout` l'accepte (aucun changement du contrat IPC), comme `--workout` ; `openride-core run --ftp-test KIND` en est le raccourci et demande `--autostart`. La reprise après plantage (lot N8) reconstruit le test et sa surveillance.
- Rampe : échauffement de 5 min (60 % à 100 % du premier palier), 31 paliers de 100 à 700 W, retour au calme de 5 min à 100 W. Fin : `ErgController.goto` (nouveau, `workout.py`) saute au retour au calme ; pendant les paliers, le saut de bloc (appui long « + ») vaut abandon.
- 20 minutes : échauffement de 20 min (deux efforts d'une minute à 110 %), 5 min de récupération, 20 min `freeride` (SIM), 10 min de retour au calme.
- Avertissements : `too_short` (moins de 4 min de paliers ou de 19 min d'effort), `erratic_cadence` (écart type de la cadence au-dessus de 12 tr/min, les 15 dernières secondes de la rampe exclues), `trainer_dropout` (ligne `device` trainer `down` pendant l'effort), `paused`. Tous sauf `erratic_cadence` font refuser `--accept` sans `--force`.
- Journal : ligne `ftp_test` juste avant `stop` (`journal.py`, `recorder.py`) ; `summary` ajoute la clé `ftp_test` seulement si elle existe ; `history` et `xp` l'ignorent.
- `--accept` passe par `config_edit.update_config` : seule la ligne `ftp_w` change, copie `config.toml.bak`, FTP hors des bornes de `config.py` (50 à 600 W) refusée sans écriture.
- Plans (lot O11) : le TSS d'une journée de test vient de `planned_workout`.
- Tests : `core/tests/test_ftp_test.py` (critères 2 à 6, cycliste simulé qui lâche après 340 W, 20 min à 260 W donnant 247 W, ligne de commande).
- Sur le PC : une rampe complète sur le HomeTrainer, sur une boucle.

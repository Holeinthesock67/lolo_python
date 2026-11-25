# Lot PZ1 – Zone privée au départ dans les FIT et le GPX du monde ouvert

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Vie privée : aucune position à moins de 500 m du départ dans les FIT exportés et le GPX des balades du monde ouvert, réglage « Zone privée au départ » coupé par défaut (audit de cohérence du 22 novembre) | Python, GDScript (une ligne) | X56, W14 | Petite | **En revue** (branche `claude/project-thread-v3ups8`) |

## 1. Objectif

Point de l'audit de cohérence et de qualité du 22 novembre validé par le propriétaire : un fichier FIT partagé (Garmin Connect, GoldenCheetah, envoi à un tiers) ou une balade du monde ouvert enregistrée ne doit pas pouvoir montrer le lieu de départ, souvent le domicile. Option coupée par défaut, réglable dans Réglages, en mots écrits.

## 2. Comportement

- Réglage `[privacy] hide_start` (`on` / `off`, défaut `off`), menu **Réglages › Avancé › Zone privée au départ** (oui / non), au niveau du profil (`config.PROFILE_KEYS`), pris en compte à la séance suivante.
- **FIT** (`fit_export.write_fit`, appelé par `SessionRecorder.finish`, `journal_to_fit` pour `recover` et la fin d'une séance interrompue) : chaque relevé à moins de 500 m (vol d'oiseau, haversine) du premier relevé qui porte une position perd sa latitude et sa longitude, y compris quand une boucle repasse près du départ. Temps, distance, vitesse, puissance, cadence, FC et altitude restent ; totaux des tours et de la séance et résumé du bilan sont calculés sur les relevés complets et ne changent pas.
- **GPX du monde ouvert** (`open_world_save.save_ride`, fin de séance et `openride-core open-world-save`) : le début et la fin de la trace sont coupés tant qu'ils restent dans la zone ; pas de trou au milieu, que le compilateur relierait d'un trait droit. Balade qui ne sort jamais de la zone : rien d'enregistré.
- **`fit-check`** : ligne d'information « positions » (OK) quand une partie seulement des relevés porte une position.
- Module pur `privacy_zone.py` (`RADIUS_M`, `radius_m(cfg)`, `mask_records`, `trim_points`).

## 3. Effets sur les outils

- Coach, historique, CP estimée, courbe de puissance, fantôme (`GhostBot`) et rejeu : aucun, ils lisent la puissance, le temps et la distance.
- Garmin Connect et GoldenCheetah : carte sans les 500 m du départ (positions absentes acceptées, lot X56) ; totaux identiques.
- FIT réimporté comme parcours (compilateur, lot M7, points sans GPS ignorés) : le parcours commence hors de la zone.
- Journal `.jsonl` : inchangé ; il reste sur le PC.
- Pas de nouvelle révision IPC : la liste `settings` existante porte la nouvelle ligne.

## 4. Critères d'acceptation

1. `core/tests/test_privacy_zone.py` passe en cloud, avec des traces fictives seulement (aller-retour en plein Atlantique, 0° N 20° O ; aucun FIT, GPX ni position réels dans le dépôt).
2. Captures du sous-écran Avancé en low, medium et high validées par le propriétaire.
3. Avec l'option coupée, FIT et GPX identiques à ceux d'avant le lot.

## 5. Livraison

- Code : `privacy_zone.py`, `config.py` (`PrivacyConfig`), `settings.py`, `fit_export.py`, `recorder.py`, `session.py`, `open_world_save.py`, `__main__.py`, `tools/fit_check.py`, `engine/scripts/settings_view_model.gd` (libellés oui / non).
- Documentation : guide (Réglages › Avancé), SRS (`[privacy]`), suivi.

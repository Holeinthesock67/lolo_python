# Lot P33 – Vent d'après la météo locale

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série P : vent d'après la météo locale lue au lancement par un processus annexe, repli sans vent hors ligne | Python | P1, P2 | Moyenne | Prêt (version 3.0, reprise de l'exigence 2.0-VNT-1) |

Décision n° 1 du lot P1 (propriétaire, 25 octobre) : en 2.0, vent activé par défaut d'après la météo locale. Jamais fait : relevé le 8 novembre (fil « Expliquer quand le vent est actif »), reporté en 3.0 par la feuille de route. Règles R-NET-1 à R-NET-3 de la spécification générale (§3).

## 1. Objectif

Rouler avec le vent du jour au lieu de régler force et direction à la main.

## 2. À lire

`docs/lots/LOT_P1_contrat_vent_decor.md` (décisions) ; `core/src/openride_core/config.py` (`WindConfig`) ; `core/src/openride_core/wind.py` ; `docs/SPECIFICATION_GENERALE.md` §3 (réseau) et §6.3 (vent).

## 3. Travail demandé

- Nouveau mode `local` de `[wind] mode` : au lancement, le lanceur (jamais le core) lit vitesse, direction et rafales pour le point de départ du parcours, avec un délai court (5 s) et un cache de 3 h ; le core reçoit des valeurs déjà prêtes.
- Source : **Open-Meteo** (sans clé ni compte, décision du propriétaire du 8 novembre, 4 h 47) ; aucune coordonnée précise du domicile dans le dépôt ni dans les journaux (position arrondie à environ 10 km, invariant A8).
- Repli sans vent hors ligne, avec une ligne au journal et un message au menu.
- Défaut : `local` si le propriétaire confirme la décision P1 n° 1, sinon `off` (question posée avant le code).
- Menu : valeur « Météo du jour » du réglage Vent ; HUD inchangé.

## 4. Critères d'acceptation

1. Le core n'attend jamais le réseau (test avec un serveur qui ne répond pas).
2. Hors ligne : séance identique à `off`.
3. `core/tests/test_options_menus.py` vert.

## 5. Fichiers touchés

`core/src/openride_core/launcher.py`, `core/src/openride_core/config.py`, `core/src/openride_core/settings.py`, `core/src/openride_core/wind.py`, tests, `docs/GUIDE_UTILISATION.md`.

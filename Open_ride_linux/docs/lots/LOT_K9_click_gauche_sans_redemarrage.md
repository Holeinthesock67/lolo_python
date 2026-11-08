# Lot K9 – Boîtier gauche du Click sans redémarrage

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Click gauche (4.0) : garder le boîtier gauche déverrouillé sans le redémarrer chaque minute, essai sur le vélo | Python | K8, Q6 | Petite | Prêt (version 4.0) |

Décision du propriétaire du 28 octobre : l'essai du boîtier gauche face à Zwift est reporté en 4.0. Depuis le 30 octobre, le gauche est redémarré par `0x18` quand Zwift le verrouille (essai C, `docs/RECHERCHE_CLICK_GAUCHE.md` §9) : environ 4 s sans boutons à gauche chaque minute. L'essai B (appli Zwift) est abandonné, faute d'abonnement. Cahier rédigé le 8 novembre (aucun lot ne portait la 4.0).

## 1. Objectif

Supprimer le trou d'environ 4 s par minute, en gardant le redémarrage `0x18` comme repli.

## 2. À lire

`docs/RECHERCHE_CLICK_GAUCHE.md` §7 (essai D) à §9 ; `docs/DIAG_CLICK_GAUCHE.md` ; `core/src/openride_core/zwift_click.py` (`parse_status`, redémarrage) ; `docs/SPECIFICATION_GENERALE.md` §7.1 (B double « − », rien d'indispensable sur le seul gauche).

## 3. Travail demandé

- **Essai D :** envoyer la séquence d'activation complète et la réponse `ff 04 00`, puis mesurer si le mode reste à 0 au-delà de la minute (firmware 1.2.0, ne pas mettre à jour).
- Si l'essai tient : nouveau choix `keep` de `[drivers] click_reset_locked` (redémarrage seulement si le maintien échoue) ; sinon, garder `0x18` et documenter le résultat.
- Journal : durée de chaque fenêtre de boutons, appuis perdus.

## 4. Critères d'acceptation

1. Séance de 30 min au Click (en deux blocs de 10 min si le propriétaire préfère) : moins d'un appui perdu par tranche de 10 min sur le gauche.
2. Le boîtier droit ne tombe jamais.

## 5. Fichiers touchés

`core/src/openride_core/zwift_click.py`, `core/src/openride_core/config.py`, `docs/RECHERCHE_CLICK_GAUCHE.md`.

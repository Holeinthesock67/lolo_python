# Lot BC4 – Visuels des cartes par Gemini

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série BC : fiche de commande des 42 visuels pour l'IA d'images Gemini, planche d'essai de 6 cartes, contrôle des fichiers à l'import | Doc + Python | BC0 | Moyenne | Livré le 7 novembre (PR #757) |

Série BC (version 5.0, badges et cartes à collectionner, demande du propriétaire du 7 novembre 2026). Plan de la série : `docs/5.0/PLAN_SERIE_BC.md`.

## 1. Objectif

Demande du propriétaire du 7 novembre : les visuels des cartes et des badges sont créés par l'IA Gemini (« Nano Banana »). Ce lot prépare la commande et contrôle ce qui revient.

## 2. Travail demandé

- `docs/5.0/VISUELS_BC4.md` (écrite le 7 novembre avec le plan), tirée du catalogue : une fiche par `visual` (sujet, rareté, palette de la charte CT9, éléments interdits : texte, chiffres, logos, marques, personnes réelles) et le gabarit commun du plan (§12).
- Format : PNG 512 × 512, fond transparent, sujet dans un cercle de 440 px, 200 Ko au plus.
- Script de contrôle en CI : un fichier par `visual` de `collection.toml`, taille, canal alpha, poids ; liste des manquants (un manquant s'affiche avec un pictogramme neutre).
- Planche d'essai de 6 cartes (une par rareté, une de saison, une d'heure) validée par le propriétaire avant les 36 autres.

## 3. Critères d'acceptation

1. Le script refuse une image de mauvaise taille, sans transparence ou trop lourde (tests négatifs).
2. Planche d'essai, puis planche complète, validées par le propriétaire.
3. Aucune donnée du cycliste dans les consignes envoyées ; licence d'usage notée dans la PR.

## 4. Livraison (7 novembre 2026)

- scripts/controle_visuels.py : contrôle de conformité des images (dimensions 512x512, canal alpha et transparence effective, poids <= 200 Ko, correspondance catalogue collection.toml, mode strict et sortie JSON) et normalisation automatique sans anneau blanc.
- core/tests/test_controle_visuels.py : 9 tests unitaires validant l'ensemble des critères d'acceptation et cas d'erreur.
- engine/assets/collection/ : ensemble complet des 42 visuels livrés et validés (42/42 valides en mode strict).

# Lot W16 – Recette du monde ouvert sur le PC et le vélo

## 1. Objectif

Vérifier sur le matériel réel (PC cible avec GTX 1060, HomeTrainer, Click) qu'une heure de monde ouvert se roule sans accroc, et que le cache tient sa promesse : revenir au même endroit sans rien télécharger.

## 2. À lire

`docs/2.0/PLAN_SERIE_W.md` §3, §4 et §8 ; cahiers W8 à W13 ; `docs/OUTILS_DE_TEST.md` (banc simulé, analyse du journal).

## 3. Prérequis

W9, W10, W11 et W12 livrés (W13 pour l'essai sans extrait régional).

## 4. Déroulé (propriétaire, avec Claude par Remote Control)

1. Préparation : `region-add` d'une région (ou rien, pour l'essai par tuiles vectorielles), `cache-info`.
2. Départ depuis le menu globe, en SIM, mode balade, 60 min ; un changement de branche au Click à au moins trois carrefours, un carrefour laissé au navigateur.
3. Pendant la séance : coupure du Wi-Fi 5 min dans une zone déjà en cache (aucune pause attendue).
4. Fin : enregistrement de la balade (W14).
5. Deuxième séance de 15 min au même départ, réseau coupé : aucun téléchargement (journal du générateur), départ immédiat.
6. Une séance de 15 min en ERG en monde ouvert (W-Q5).

## 5. Critères

1. Au moins 55 images/s en moyenne et temps d'image p99 sous 25 ms, qualité `low` (ligne `[perf-rendu]`).
2. Aucune pause `world_data` ni attente pendant l'heure ; horizon toujours au-dessus de 3 km dans le journal.
3. Gigue de la boucle physique du core sous 5 ms pendant la génération (journal du core).
4. Changement de branche pris en compte à chaque fois, sans à-coup de résistance au-delà de la limitation de variation habituelle.
5. Deuxième séance : zéro octet téléchargé, aucun carré recalculé.
6. Cache sous le plafond configuré à la fin.
7. Aucun fichier de séance ni coordonnée réelle ajouté au dépôt (vérification `git status`).

## 6. Livrable

Un bilan `docs/RECETTE_W16.md` (chiffres, captures facultatives, écarts), sans coordonnées précises du lieu d'essai.

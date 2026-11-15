# Lot EP2 – Guide des essais physiques déclenché par le jeu

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série EP (essais physiques) : `tools/essai_physique.py`, une fiche par essai (but, terrain verrouillé, étapes déclenchées par le journal de séance, questions), consignes en watts, « vu » ou un rappel, arrêt à 10 min de séance | Python | EP1 | Moyenne | Livré le 15 novembre 2026 (PR #905) ; premier essai sur le vélo à faire |

## 1. Objectif

Remarque du propriétaire pendant les essais du 15 novembre 2026 : « le script de test est encore décorrélé de l'action à l'instant t », « verrouiller le parcours », « sur l'Alpe d'Huez impossible de tester changement de voie ». Le guide `guide_seance.py` (hors dépôt) donnait ses consignes à l'horloge et laissait choisir le parcours au menu. Principe validé le 15 novembre : une seule forme de séance, sans exception.

## 2. Spécification

| # | Règle |
| --- | --- |
| EP2-1 | Fiche `core/src/openride_core/data/essais/<id>.toml` : `id` (nom du fichier), `but` (ce que l'essai teste, annoncé avant de pédaler), `commandes` (liste du lot EP1), `[config.<section>]` (réglages imposés, remis à la fin), `duree_max_s` (≤ 600), `questions` (1 à 3), `[[etapes]]`. Le parcours de la fiche est choisi pour offrir les conditions du test. |
| EP2-2 | Étape : `quand` (table qui doit correspondre à une ligne du journal de séance ; clés égales ou avec opérateur en suffixe `>=`, `<=`, `>`, `<`, `!=`), `dire`, `attendu` facultatif (même forme), `delai_s` (30 s), `rappel`, `attente_max_s` (180 s). Les étapes se suivent : une à la fois. |
| EP2-3 | Temps : uniquement le temps de séance `t` des lignes `record` (arrêté en pause), jamais l'horloge ni le temps propre d'un mode. Fin à `duree_max_s` de séance ou à l'événement `stop`. |
| EP2-4 | Attendu vu dans le délai : « Vu, merci. » et son distinct ; sinon un seul rappel, puis étape suivante. Déclencheur absent pendant `attente_max_s` : annoncé, étape sautée. |
| EP2-5 | Terrain : l'en-tête du journal doit porter le parcours de la fiche (`null` pour une run Cyber-Rogue) ; sinon le guide le dit et arrête, l'essai ne compte pas. |
| EP2-6 | Watts directs : `{cible}` et `{cible:PCT}`, arrondis à 5 W ; cible = moyenne en pédalant des 3 dernières séances `live` d'au moins 2 min du profil (lue sur le PC, jamais écrite dans le dépôt), ou `--cible`. |
| EP2-7 | Sorties : voix (spd-say, espeak), sons, terminal et bandeau `~/OpenRide/Essais/consigne_directe.json` (`id`, `texte`, `sorte`, `duree_s`) pour l'engine (EP3). Réponses aux questions ajoutées à `~/OpenRide/Essais/essais.txt`. |

## 3. Fiches livrées

`gp-voies` (Grand Prix sur le Circuit des Prés : voies, objets), `velodrome-elimination` (élimination à 7), `rogue-depart` (Cyber-Rogue : fin d'échauffement, première salle, Z).

## 4. Tests

`core/tests/test_essai_physique.py` : fiches livrées valides (épreuves de piste vérifiées par `track.check`), fiches refusées, prédicats, watts, déroulé nourri de lignes de journal (départ, boîte puis objet, rappel unique, étape sautée, mauvais terrain, fin à 10 min, temps des modes ignoré), moyenne réelle, ligne de commande.

## Livraison

15 novembre 2026 : `tools/essai_physique.py`, 3 fiches, tests. Commande sur le PC : `cd ~/Games/lolo_python/Open_ride_linux/core && .venv/bin/python -m openride_core.tools.essai_physique lancer gp-voies`.

# Lot VD10 – Menu

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : filtre des pistes, écran Prêt du vélodrome et options d'épreuve | GDScript | VD6 | Petite | En PR (version 4.0) |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Plan validé par le propriétaire le 6 novembre (lot VD0).

## 1. Objectif

Rendre le vélodrome accessible depuis les menus, sans ligne de commande.

## 2. À lire

§8 du plan ; `engine/scripts/menu_flow.gd` ; `core/src/openride_core/catalog.py`.

## 3. Travail demandé

- Filtre « Vélodrome » et fiches des pistes dans la liste des parcours.
- Écran Prêt : épreuve, puis options (tours, distance, bots, adversaire de poursuite).
- Banc des menus complété (scénario vélodrome).

## 4. Critères d'acceptation

1. Tout se lance depuis le menu ; banc des menus vert.
2. Guide d'utilisation mis à jour (`test_docs_coherence.py`).

## 5. Fichiers touchés

- `menu_flow.gd`, `catalog.py`, `docs/GUIDE_UTILISATION.md`.

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 6, 12 et 14 ms) et ses captures sont validées par le propriétaire avant la fusion.

## 6. Livraison (7 novembre, demande du propriétaire : « Lance tout »)

- Piste dans les contenus de départ (`contents.py`, `install_velodromes`) : écrite par le core sans compilateur, au premier lancement ou par **Réglages › Contenus › Contenus de départ**, jamais écrasée ; le détail des contenus compte « 1 piste de vélodrome ». Le banc des menus la pose par `"velodrome": true`.
- Liste des parcours : l'étiquette `velodrome` de la fiche (le schéma du manifeste veut des minuscules sans accent) s'affiche « Vélodrome » (`CatalogModel.TAG_LABELS`) dans le filtre « Étiquette : Vélodrome », le détail de la ligne et la fiche, qui donne la longueur, le bois et le relèvement (description du manifeste).
- Réglages des épreuves envoyés par le core : `hello_ack.config.track` = `track.menu_options()` (épreuve → réglage → [défaut, valeurs], 1,4 ko), schéma et contrat 1.7 à jour. Le core ramène un nombre JSON (20.0) à la valeur du registre (20) : sans cela, le départ d'une épreuve lancée du menu arrêtait le core (trouvé par le banc des menus, test ajouté).
- Écran Prêt du vélodrome (`menu_model.gd`, piste choisie en session libre ou ERG) : « Lancer : épreuve », « Épreuve : … » (A long : suivante, séance libre par défaut), une ligne par réglage (« Tours : 40 », A long : valeur suivante, noms de `track/track_names.gd`), « Passer en session ERG » ou « Changer d'entraînement » en séance libre seulement (une autre épreuve en ERG revient en SIM), « Changer de parcours » ; `start` part avec `mode` « track » et `track` = {event, réglages} ; un refus du core s'affiche sur l'écran Prêt. Choix gardés par épreuve jusqu'à la fermeture de l'engine.
- Tests : `engine/tests/unit/test_track_menu.gd`, `core/tests/test_contract_ipc.py` (hello_ack), `test_track_events.py` (nombres JSON), `test_contenus.py` ; scénario `velodrome` du banc des menus (filtre, piste, écran Prêt, course aux points en 20 tours, départ au journal du core, bilan).
- Guide d'utilisation : paragraphe « Vélodrome » de la section 4.

Écarts à la maquette VD8 de l'écran Prêt : l'écran garde la forme des autres écrans Prêt (liste, A long pour changer) au lieu de deux colonnes ; « Sprint tous les 10 tours », « Braquet fixe » et « Fantôme » ne sont pas des réglages du core et n'y sont pas ; les choix ne sont pas écrits dans `config.toml`. Le plan des boutons (§8 : A court pour monter ou redescendre sur la piste) n'est pas encore codé côté core : le placement reste automatique.

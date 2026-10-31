# Lot V7 – Engine : cadres, roues et tenues sur l'avatar, sons des roues, traînées d'air

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Engine : cadres, roues et tenues sur l'avatar, sons des roues, traînées d'air | GDScript | V6 ; P10 pour les sons | Moyenne | **Livré le 27 octobre** (issue #373) ; recette de rendu sur le PC |

## 1. Objectif

Rendre l'équipement visible et audible : chaque cadre et chaque paire de roues a sa forme, chaque tenue ses couleurs et motifs, la position est plus basse sur un vélo aéro, les roues ont leur son (bourdonnement de la lenticulaire, sifflement des jantes hautes) et des traînées d'air apparaissent au-delà de 45 km/h (plan §2.2, « des sensations »).

**Lot interne (rendu) :** recette visuelle et sonore.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_V.md` §2.2 ; `LOT_V3_catalogue_equipement.md` §4.1 (champ `look`) ; `LOT_V6_avatar_engine.md`.
2. Code : `avatar_mesh.gd`, `avatar_view.gd` (V6), `sound_model.gd`, `sound_player.gd` (sons du vélo de P10), `quality_presets.gd`.

## 3. Prérequis

V6 livré ; P10 livré pour les sons (sinon la partie sonore attend, `sound_player.gd` étant partagé par P9, P10, P13, P15 et P21, l'un après l'autre).

## 4. Travail demandé

- **Pièces de rendu par `look` :** cadres (tubes ronds fins pour Grimpeur et Polyvalent, tubes profilés et plus épais pour Aéro et Contre-la-montre, prolongateurs pour Contre-la-montre), roues (rayons pour Standard et Légères, jante haute pour Profilées, disque plein pour Lenticulaire), casques (route, aéro, profilé), tenues (couleur principale et secondaire de l'avatar, motifs : uni, bandes, pois, néon), chaussettes, lunettes. Tout est généré par le code, couleurs par matériau.
- **Position :** buste plus bas et bras rapprochés sur les cadres Aéro et Contre-la-montre (position assise seulement).
- **Sons :** couche « roue » de `sound_model.gd` selon la vitesse et le `look` des roues : bourdonnement grave pour la lenticulaire, sifflement léger pour les jantes hautes, rien de plus pour les roues à rayons ; volume réglé par le volume « vélo » existant.
- **Traînées d'air :** quelques lignes translucides le long de l'avatar au-delà de 45 km/h, coupées par `living(preset)` en qualité basse si le budget n'est pas tenu.
- **Bots :** gardent la version allégée de V6, sans équipement détaillé.

## 5. Fichiers concernés

`avatar_mesh.gd`, `avatar_view.gd`, nouveau `equipment_meshes.gd` et son test, `sound_model.gd` et son test, `sound_player.gd`, `quality_presets.gd`, `fake_core.py`, tests graphiques, `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Toutes les suites passent ; test sans écran : chaque `look` du catalogue livré (V3) a une géométrie, un `look` inconnu retombe sur la pièce par défaut.
2. Captures du faux core : les quatre cadres et les quatre roues se distinguent ; traînées visibles à 50 km/h, absentes à 40.
3. Coût : l'équipement le plus lourd à dessiner n'enlève pas plus de 1 image/s en qualité basse sur le PC cible.

**Sur le PC cible (le propriétaire) :** sons des roues audibles mais pas gênants, position aéro visible.

## 8. Hors périmètre

Choix au menu (V8), effet physique (V3, V11).

## 9. Livraison (27 octobre 2026, issue #373)

- **Engine :** `equipment_meshes.gd` (un `look` par pièce du catalogue : 5 cadres, 4 roues, 3 casques, 6 tenues à motif, 4 chaussettes, 3 lunettes ; pièce par défaut pour un `look` inconnu), `avatar_mesh.gd` (posture selon le cadre : buste plus bas et mains rapprochées sur les cadres aéro et contre-la-montre, prolongateurs), `avatar_view.gd` (`set_equipment`, motifs de tenue en textures générées, traînées d'air au-dessus de 45 km/h). `ipc_client.gd` demande `list_garage` à chaque `hello_ack` (parties réunies, signal `garage_received`) et relaie `progression` ; `main.gd` fait le lien identifiants équipés → `look`.
- **Sons des roues :** couche « roues » de `sound_model.gd` et `sound_player.gd` : ronronnement grave (roue lenticulaire) ou sifflement léger (jantes hautes) de 20 à 50 km/h, silence en pause.
- **Triangles :** niveau 0 sous 6 000 avec l'équipement le plus lourd ; niveau 1 sous 1 500 (jante seule, sans rayons). Les bots (niveau 2) restent sans équipement détaillé.
- **Tests :** `test_avatar_model.gd` (looks, postures, roues, motifs, traînées), `test_sound_model.gd` (roues), test du core qui vérifie que chaque `look` du catalogue figure dans `equipment_meshes.gd`, scènes du banc visuel (4 cadres et 4 roues se distinguent, traînées à 50 km/h et pas à 40).
- **Reste, sur le PC :** recette de rendu (lisibilité des cadres et des roues à l'écran, volume des sons des roues à l'oreille).


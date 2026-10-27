# Lot V7 – Engine : cadres, roues et tenues sur l'avatar, sons des roues, traînées d'air

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

# Lot WTF6 – Engine : Katamari, peloton délirant, horloge, vélo minuscule et caméras

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série WTF : engine, Katamari, peloton délirant, horloge, vélo minuscule, caméras | GDScript | WTF2, WTF4 | Grande | En PR le 31 octobre (version 2.0), captures et banc à faire sur le PC |

Série WTF (mode « What the fuck », demande du propriétaire du 29 octobre 2026). Plan de la série : `docs/2.0/PLAN_SERIE_WTF.md`.

## 1. Objectif

Afficher les règles permanentes et les gags de décor : boule Katamari et objets ramassés (`wtf.kata`), costumes des bots et attaque des mamies (`wtf.skins`, `wtf.attack`), soleil piloté par `wtf.clock_h` et pluie de poissons, cuisine géante du vélo minuscule, caméras pigeon, escargot et roue.

## 2. Critères d'acceptation

1. Tests Godot et `visual_check` passent.
2. Banc simulé en `low`, `medium` **et** `high`, captures montrées au propriétaire avant fusion.

## 3. Livraison (31 octobre, en PR, avec WTF5)

- Même modèle et même nœud que WTF5 (`wtf_scene_model.gd`, `wtf_scene.gd`) : boule Katamari qui grossit et objets à ramasser devant (`wtf.kata.next`), costumes des bots au-dessus d'eux (mamie, tracteur, baignoire, baleine ; la mamie qui attaque s'allume en rouge), soleil réglé par `wtf.clock_h` et pluie de poissons (6, 12 ou 20 selon la qualité), cuisine géante et caméra à hauteur de fourmi du vélo minuscule, vues pigeon, escargot et roue (le cycliste reste visible), chef en tandem et plats de la surprise du chef (voile vert de la gelée, rouge du piment qui brûle).
- Tests : `engine/tests/unit/test_wtf_scene.gd`.
- Retouches après l'essai PC 7cn du 31 octobre : boule Katamari affichée à sa vraie taille (0,45 m de rayon par unité, elle en faisait 1 m), plafonnée à × 3 à l'écran et poussée à droite du cycliste ; vaches de la tornade × 2,5 et à 28 m devant au lieu de 45 ; carte du gag déplacée à gauche (pile carte, Katamari, horloge), hors du centre de l'image ; côté core, livraison d'œufs ramenée à 1 km en 2 min 30 au plus, aucun gag au-delà de 2 min 30 (`EVENT_MAX_S`) et tirage « en sac » (chaque gag actif sort une fois avant qu'un autre ne revienne).
- Reste : captures en `low`, `medium` et `high` et banc sur la GTX 1060 (file du PC).

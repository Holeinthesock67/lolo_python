# Lot P35 – Lumières de nuit, ambiance à l'heure du jeu, nuit courte en journée accélérée

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série P : éclairage du vélo, fenêtres éclairées, luminaires publics et lanternes la nuit ; sons d'ambiance et phares des véhicules à l'heure du jour et de la nuit ; nuit au quart du jour en journée accélérée | GDScript | P19, Y8, P25, JP5 | Moyenne | En revue (PR à venir) : captures et bancs PC à faire |

Demandes du propriétaire du 13 novembre : « Ajoute phare vélo, lumière fenêtre et autres objets lumineux », « Ajoute éclairage vélo, luminaires publics », « Corrige le décalage sons ambiance », « Pour la journée accélérée fais durer la nuit un quart du temps du jour ». Le cahier P19 (§8) laissait l'éclairage public, le phare du vélo et les fenêtres éclairées hors périmètre.

## 1. Règle commune

Une seule règle pour tout ce qui est neuf : **les lampes existent dès que « Jour et nuit » est actif, elles s'allument au coucher du soleil**. Avec « Jour et nuit » coupé (défaut), l'image est celle d'avant ce lot : aucune lampe dessinée, aucune fenêtre allumée, aucun projecteur.

- `night_lights.gd` : `level(daylight)` vaut 0 au-dessus de ON_DEG (4°), 1 sous FULL_DEG (−5°), montée douce entre les deux ; 0 si le jour et la nuit est coupé.
- Deux globaux des shaders (`project.godot`) : `night_glow` (niveau d'allumage) et `night_lamps` (1 quand le jour et la nuit est actif). `main.gd _step_cycle` les pose au plus une fois par seconde, comme le reste du cycle.

## 2. Ce qui s'allume

| Objet | Comment | Coût |
| --- | --- | --- |
| Fenêtres des bâtiments | `building.gdshader` : chaque ouverture vitrée tire si elle est éclairée (40 % des fenêtres, 75 % des vitrines, granges et église plus rarement, shōji en papier éclairé) ; émission chaude × `night_glow` | Aucun nœud ; quelques instructions du shader, sautées de jour |
| Phare et feu arrière des vélos | `avatar_view.gd` : un maillage de deux lampes (un appel de dessin) sur le vélo du joueur et des bots proches (niveaux 0 et 1, pas le fantôme) | 1 appel de dessin par avatar détaillé |
| Éclairage du vélo du joueur | `bike_lights.gd` : vrai projecteur blanc (SpotLight3D, 45 m, sans ombre) vers la route devant, petite lueur rouge derrière ; reste allumé en vue subjective | 2 lumières sans ombre, la nuit seulement (cachées de jour) |
| Luminaires publics | `street_lights.gd` : candélabre tous les 32 m, côtés alternés, là où un bâtiment est à moins de 35 m de la route (villages et villes, rien en rase campagne) ; un MultiMesh par tronçon OSM ; projecteurs sous les plus proches : 0 en low, 4 en medium, 8 en high | 1 appel de dessin par tronçon ; 0, 4 ou 8 lumières sans ombre la nuit |
| Lanternes de pierre (Japon, JP5) | `roadside_props.gd` : foyer qui s'allume | 1 appel de dessin par lanterne |
| Phares des voitures, camions, bateaux | Déjà prévus (P25) mais calés sur le soleil fixe du thème : `living_decor.set_sun_elevation` leur donne le soleil du cycle | Aucun |

## 3. Sons d'ambiance à l'heure de la scène

Les fonds d'ambiance (oiseaux du matin, insectes du soir, grenouilles la nuit, `ambience_model.gd`) lisaient l'heure du PC : en journée accélérée, ils ne suivaient pas l'image. `living_world.solar_hour` (posé par `main.gd`) leur donne l'heure solaire de la scène ; jour et nuit coupé : heure du PC, comme avant.

## 4. Journée accélérée : nuit au quart du jour

Le cycle reste d'une heure de séance, départ à 6 h. La nuit (soleil sous −6°) n'en prend que le cinquième (12 min), le jour crépuscules compris les quatre cinquièmes (48 min) : l'horloge va plus vite la nuit et plus lentement le jour, selon la durée du jour du lieu et de la date (`DaylightModel.accelerated`, `SkyCycle.ACCEL_NIGHT_SHARE` = 0,2). Jour ou nuit polaire : allure constante. Une heure accélérée d'un thème (`sky.time_of_day.mode = "accelerated"`) garde son allure constante (pas de `night_share`).

## 5. Tests et outils

- `tests/unit/test_night_lights.gd` : allumage, globaux, lampes du vélo et de l'avatar, luminaires (seulement près des maisons, côtés alternés, crosse au-dessus de la chaussée, projecteurs par préréglage), éclairage du vélo.
- `tests/unit/test_sky_cycle.gd` : 12 min de nuit et 48 min de jour un 13 novembre à 48,9° N, retour à 6 h du lendemain après une heure, jour polaire.
- `tests/vitrine_nuit.gd` : rue de village à quatre heures (coupé, midi, coucher, nuit), vues de poursuite et subjective, CSV des luminances.

## 6. Reste à faire

- Captures validées par le propriétaire (low, medium, high).
- Banc PC 3 qualités, la nuit, dans un village : `day_night = "accelerated"` ou `"theme"` avec une heure de nuit, comparé à main.
- Le soleil reste calculé au premier point du parcours (P19) ; à reprendre si un long parcours le demande.

## 7. Fichiers touchés

`engine/scripts/night_lights.gd`, `bike_lights.gd`, `street_lights.gd` (nouveaux), `engine/shaders/night_lamp.gdshader` (nouveau), `building.gdshader`, `project.godot`, `main.gd`, `living_world.gd`, `living_decor.gd`, `avatar_view.gd`, `roadside_props.gd`, `daylight_model.gd`, `sky_cycle.gd`, tests et vitrine.

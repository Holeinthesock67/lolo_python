# Lot Y11 – Chaussée réaliste et faux relief de l'herbe (proposé, chiffré)

**Statut : proposition du 27 octobre, à valider par le propriétaire** (questions dans `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §10). Fin de projet, comme toute la série Y : rien n'est codé avant Y2 (Godot 4.7.x), et chaque étape est soumise aux budgets X2, X13 et X16.

## 1. Objectif

Demandes du propriétaire du 27 octobre : « un asphalte plus réaliste » puis « regarde aussi le faux relief graphique pour l'herbe ». Aujourd'hui :

- **Route** : une image de 64 px de couleur unie (ou la texture du thème) avec la ligne médiane peinte dans l'image (`road_builder.make_material`, rugosité fixe 0,9), remplacée par P17 par le shader de marquages de P14 (`road_markings.gdshader`, couleur unie, rugosité 0,9 ou 0,7 sur la peinture). Ni relief, ni reflet, ni variation : la route paraît en plastique mat et se répète tous les 6 m avec une texture de thème.
- **Herbe** : couleur ou texture du thème projetée en triplanaire, légère variation par bruit (`terrain.gdshader`, E2 et E3) ; touffes en `MultiMesh` sur une bande de 2 à 15 m du bord de route (P5, `grass_tufts.gd`, 0 / 4 000 / 12 000 touffes). Le sol est plat à l'œil dès qu'on sort de la bande des touffes.

Le lot donne du relief **sans géométrie** (cartes de normales, rugosité, variation à deux échelles) partout, et réserve les techniques chères (parallaxe, coquilles d'herbe) au préréglage `high`.

## 2. Principe commun à la route et à l'herbe (pas d'exception)

Une seule forme de « couche de surface » pour toutes les surfaces du thème (`road`, `terrain.grass`, `terrain.rock`, `terrain.snow`) :

| Clé (thème, ajout compatible) | Rôle | Sans la clé |
| --- | --- | --- |
| `texture` (existe) | Couleur | Couleur unie `color` |
| `normal` | Carte de normales (convention OpenGL, celle des packs CC0) | Normales **générées par le code** (bruit dans le shader) |
| `roughness` | Rugosité (canal R) | Rugosité générée par le code |
| `height` | Hauteur pour la parallaxe (`high` seulement) | Pas de parallaxe |
| `scale_m` (existe pour le terrain, ajouté à `road`) | Taille d'une répétition | Valeurs actuelles (6 m pour la route) |

- **Sans pack de textures, le rendu est déjà meilleur** : normales et rugosité procédurales dans les shaders (invariant A9 : aucune texture dans le dépôt). Le pack ne fait qu'ajouter de la finesse.
- **Sources des textures** : packs CC0 (ambientCG, Poly Haven : jeux « Asphalt » et « Grass/Ground » avec couleur, normale, rugosité, hauteur), installés hors du dépôt par `theme-install` et déclinés en niveaux 512 / 1 024 / 2 048 px par P20 (`theme-pack`, `provenance.toml`). **Pas de Gemini pour les sols** (décision du 26 octobre, LOT_P20 §4) : Gemini ne sait pas produire une normale et une rugosité cohérentes avec la couleur. Gemini reste possible pour des **décalques** (inscriptions peintes dans les cols, §3 A6), avec la méthode P20 (`gen_decalque_<sujet>_<NN>.png`, provenance, relecture de confidentialité).
- **Un seul shader de route** : `road_markings.gdshader` (P14) devient le shader de la chaussée, marquages compris ; `road_builder.make_material` (image avec ligne peinte) est retiré quand P17 l'a remplacé, pour ne pas garder deux chemins.
- **Réglages** : les techniques par préréglage sont des clés du dictionnaire `PRESETS` de `quality_presets.gd` (comme `ssao`), lues par une seule fonction ; aucune constante cachée dans un shader.

## 3. Chaussée : techniques chiffrées

Coûts : **estimations** pour la GTX 1060 en 1080p, préréglage `medium`, caméra basse qui regarde la route (la chaussée couvre 20 à 35 % de l'écran) ; à confirmer par l'essai de rendu (`docs/ESSAI_RENDU_Y11_Y12.md`). Le temps d'image actuel en `medium` est à relever par cet essai (référence connue : 16,8 ms en moyenne et p99 22 ms en `low`, le 25 octobre).

| # | Technique | Gain visuel | Coût GPU estimé | `low` | `medium` | `high` |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | **Carte de normales + rugosité** (pack ou procédurales) : grain, gravillons, fissures fines qui accrochent la lumière | Fort : fin de l'effet « plastique » | 0,1–0,2 ms | Oui (512 px ou procédural) | Oui (1 024 px) | Oui (2 048 px) |
| A2 | **Détail à deux échelles** : texture fine (0,5–1 m) + variation lente (20–50 m, bruit de valeur dans le shader) de teinte et de rugosité, pour casser la répétition | Fort : plus de motif répété tous les 6 m | < 0,1 ms | Oui | Oui | Oui |
| A3 | **Rugosité variable** : bandes de roulement plus lisses (là où roulent les voitures), rapiéçages plus sombres et plus rugueux, joints, bords usés ; avec un **soleil bas** de face, la route brille sur les bandes lisses | Moyen à fort au soleil rasant | < 0,1 ms | Oui | Oui | Oui |
| A4 | **Bords de chaussée** : transition chaussée → bas-côté (gravillons, terre) par masque dans le shader au lieu d'une coupure nette | Moyen | < 0,05 ms | Oui | Oui | Oui |
| A5 | **Parallaxe** (`heightmap_enabled`, occlusion de parallaxe, 8 à 16 pas, effacée au-delà de 25 m) | Faible à moyen : visible seulement de près et au ras du sol | 0,3–0,8 ms | Non | Non | Oui, si une `height` existe |
| A6 | **Décalques de route** : taches d'huile, plaques d'égout, rustines, inscriptions peintes dans les montées (noms **fictifs**), limités en distance (60 m) et en nombre | Moyen | 0,1–0,3 ms selon le nombre | 0 | 20 | 40 |
| A7 | **Route mouillée** (plus tard, avec la pluie de P8) : `wetness` de `weather_model` assombrit la couleur, abaisse la rugosité, remplit les creux (flaques par masque de hauteur ou de bruit), ronds de gouttes animés dans la normale | Fort sous la pluie | 0,1 ms sans reflet ; **+0,5–1,5 ms avec SSR** | Sans SSR (reflet du ciel seulement) | SSR demi-résolution (4.6) | SSR pleine résolution |

**Reprise d'Y8 :** les « décalques de route » de la troisième priorité d'Y8 passent dans Y11 (A6), pour qu'un seul lot touche la chaussée ; Y8 garde les toits, les façades et l'étalonnage.

## 4. Herbe : faux relief chiffré

| # | Technique | Gain visuel | Coût GPU estimé | `low` | `medium` | `high` |
| --- | --- | --- | --- | --- | --- | --- |
| H1 | **Normale et rugosité de l'herbe** dans `terrain.gdshader` (pack ou procédurales), projetées **par le dessus seulement** (l'herbe est sur les pentes douces ; la roche garde le triplanaire) : une lecture de texture au lieu de trois | Fort : le sol prend du grain et réagit au soleil | 0,15–0,3 ms (le terrain couvre 40 à 60 % de l'écran) | Oui (512 px ou procédural) | Oui | Oui |
| H2 | **Variation de teinte à deux échelles** : grandes plaques (prés fauchés, herbe sèche, zones plus vertes près de l'eau, 30–100 m) + fine variation existante | Fort à distance moyenne | < 0,05 ms | Oui | Oui | Oui |
| H3 | **Vagues de vent sur l'herbe** : bandes claires et sombres qui défilent dans le sens du vent du modèle P4 (même vent que `tree_sway.gdshader` et les touffes), intensité selon la force du vent | Fort : le paysage « vit » | < 0,05 ms | Oui | Oui | Oui |
| H4 | **Touffes raccordées au sol** : la base des touffes prend la teinte du terrain sous elles (même bruit qu'H2), fondu de hauteur à la limite de distance pour qu'elles ne surgissent pas | Moyen : fin de l'effet « collé » | ≈ 0 | — (0 touffe) | Oui | Oui |
| H5 | **Plus de touffes près de la caméra** : budget par préréglage revu (proposition : `low` 1 500 simples, `medium` 8 000, `high` 20 000), bande élargie hors de la route jusqu'à 25 m, alpha scissor (T10) | Moyen à fort | 0,2–0,6 ms en `medium` (taux de remplissage) | 1 500 si l'essai le permet | 8 000 | 20 000 |
| H6 | **Coquilles d'herbe** (« shell texturing ») : le terrain proche (≤ 20 m) redessiné en 6 à 12 couches décalées, découpées en alpha scissor, pour un tapis d'herbe en vrai volume | Fort de près | 1–2,5 ms | Non | Non | Essai seulement ; décision après mesure |
| H7 | **Parallaxe de l'herbe** | Faible : l'herbe n'a pas de relief net, la parallaxe donne un aspect de moquette | 0,3–0,8 ms | Non | Non | **Non retenue** (H6 ou H5 font mieux) |

Le vent des touffes et des vagues d'herbe vient du même calcul (P4 `wind_model`, vent apparent de P5) : un seul jeu d'uniformes partagé, pas de deuxième vent.

## 5. Enveloppe et budgets

- **Enveloppe proposée pour Y11** : au plus **+1,0 ms de GPU en `medium`** (médiane de la sonde X13), **+0,5 ms en `low`**, et le p99 ne doit pas monter de plus de 1 ms. En `low`, le budget de la spécification reste la règle : 55 images/s, p99 sous 25 ms, tout le décor vivant actif.
- **Lien avec Y1** : le brouillard opaque à 4 / 6 / 9 km efface les détails au loin ; les détails A1, A3, H1 et H3 s'effacent vers une couleur moyenne avant 300 m (mipmaps et fondu) pour ne pas scintiller ni coûter là où ils ne se voient pas. La teinte moyenne de la route et de l'herbe est inchangée au loin : le brouillard garde son aspect.
- **Mémoire vidéo** (P20) : jeu complet route + herbe en 1 024 px compressé ≈ 6 Mo (couleur, normale, rugosité) ; en 2 048 px avec hauteur ≈ 30 Mo : négligeable face au budget de 1 Go de `medium`.
- **X2** : nouveau budget de test `road_material_build` (création du matériau, ≤ 5 ms) dans `perf_budgets.json`. **X16** : endurance d'une heure en `medium` à la fin du lot, sans dérive de mémoire vidéo.
- Une technique n'est gardée que si elle tient dans l'enveloppe ; sinon elle descend d'un préréglage.

## 6. Travail demandé (le jour du lot)

1. Mesure de référence (banc simulé, sonde X13, `medium` puis `low`, mondes `village` et `demo`), captures à positions fixes, dont une face au soleil bas.
2. Contrat du thème : clés `normal`, `roughness`, `height` des couches de surface et `road.scale_m` (ajout compatible, `world_format_v1.md` §9 et `theme.schema.json`) ; `theme_render_params.gd` les lit pour toutes les couches de la même façon ; `theme-check` et `theme-pack` (P20) les traitent comme les autres textures.
3. Shader de chaussée : A1 à A4, puis A6 et A7 ; retrait de `road_builder.make_material` et de `road_image` si P17 les a remplacés.
4. Terrain et touffes : H1 à H5 ; H6 en essai mesuré en `high`.
5. Préréglages : clés de §3 et §4 dans `PRESETS` (`road_parallax`, `grass_shells`, `road_decals`, `ssr`), budgets de touffes dans `LIVING` ; tests unitaires.
6. Mesure après, captures, rapport dans `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §8.

## 7. Dépendances

Y2 (Godot 4.7 : SSR refait, occlusion spéculaire), P20 (packs par niveau), P14 et P17 (shader de marquages en place), P5 et P4 (touffes, vent), P8 (pluie, pour A7), Y1. Fichiers partagés : `road_markings.gdshader` (P14, puis Y11), `terrain.gdshader` (E2, E3, P6, puis Y11), `grass_tufts.gd` (P5, puis Y11), `quality_presets.gd`.

## 8. Taille et découpage

Moyenne à grande : **Y11a** chaussée (A1–A4, A6), **Y11b** herbe (H1–H5), **Y11c** route mouillée (A7, quand la pluie est en jeu) et essai des coquilles (H6). Délégable en partie (shaders oui ; recette visuelle et mesures sur le PC du propriétaire).

## 9. Hors périmètre

Géométrie de route nouvelle (dévers, nids-de-poule en relief réel), tessellation (absente de Godot 4), herbe interactive (écrasée par les roues), saisons et jour/nuit (version 2.0, P18 et P19), biomes de la 3.0 (série U, qui reprendra ces couches de surface).

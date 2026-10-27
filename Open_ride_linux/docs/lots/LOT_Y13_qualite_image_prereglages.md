# Lot Y13 – Qualité d'image par préréglage (consommer la marge du GPU)

## 1. Objectif

Demande du propriétaire du 27 octobre (19 h 33) : « augmenter la qualité graphique générale vu la marge ». Sur la GTX 1060 du PC cible, la carte graphique travaille environ 5 ms par image en `medium` sur les 16,7 ms d'une image à 60 Hz : il reste de quoi rendre l'image plus belle sans repasser sous les budgets.

Consigne du propriétaire (19 h 35) : **la résolution reste la résolution maximale de l'écran**. Ni mise à l'échelle 3D, ni suréchantillonnage, ni FSR ou résolution adaptative dans ce lot : la marge sert aux autres leviers.

Le lot procède par étapes, chacune mesurée sur le PC avant et après ; l'étape 1 est un prototype soumis à l'accord du propriétaire avant de généraliser.

## 2. État des lieux chiffré (`main` du 27 octobre, Godot 4.3, Forward+)

Mesures : banc simulé `montee_descente` avec la sonde X13 sur la GTX 1060 (essai Y1 du 27 octobre, fenêtre 1857 × 1011, synchronisation verticale à 60 Hz), médianes après les 20 premières secondes.

| Préréglage | Images/s | Temps GPU par image | Charge GPU | Appels de dessin | Primitives | Arbres |
| --- | --- | --- | --- | --- | --- | --- |
| `low` (village) | 60 | 2,8 ms | 23 % (pointe 66 %) | 430 | 1,0 M | 19 700 |
| `medium` (village) | 60 | 5,0 ms | 35 % (pointe 40 %) | 443 | 1,4 M | 49 700 |
| `medium` (OSM) | 60 | 4,7 ms | 34 % (pointe 37 %) | 444 | 1,4 M | 49 700 |

Essais en fenêtre du 27 octobre (`medium`) : 59 images/s en moyenne, p99 du temps d'image ≈ 21 ms, GPU à 28 % en moyenne et 54 % au plus fort. Le PC du propriétaire tourne bien en `medium` (`[render] quality = "medium"` dans sa configuration, vérifié le 27 octobre).

Réglages d'image avant ce lot :

| Réglage | `low` | `medium` | `high` | Où |
| --- | --- | --- | --- | --- |
| Rendu des tons | Linear (aucun) | Linear | Linear | défaut de l'`Environment` |
| Étalonnage (contraste, saturation) | aucun | aucun | aucun | — |
| Anticrénelage | aucun | MSAA 2× | MSAA 4× | `quality_presets.gd` |
| Filtrage anisotrope | 4× (défaut Godot) | 4× | 4× | `project.godot` |
| Occlusion ambiante (SSAO) | non | qualité « très basse » | qualité « très basse » | `project.godot` |
| Lumière indirecte d'écran (SSIL) | non | non | non | — |
| Glow | non | non | non | — |
| Ombres du soleil | atlas 2048, 4 cascades, filtre par défaut, 150 m | idem, 300 m | idem, 600 m | `project.godot`, `quality_presets.gd` |
| Brouillard opaque | 4 km | 6 km | 9 km (+ volumétrique) | Y1 |
| Densité de végétation, arbres | 0,3, 20 000 | 0,6, 50 000 | 1,0, 100 000 | `quality_presets.gd` |
| Bâtiments visibles jusqu'à | 1,5 km | 2,5 km | 4 km | `quality_presets.gd` |
| LOD automatique (seuil) | 1 px (défaut) | 1 px | 1 px | — |

Constat : aucun rendu des tons ni étalonnage (couleurs plates, ciel délavé), SSAO au plus bas, pas d'anticrénelage en `low`, ombres floues et peu visibles sous les arbres.

## 3. Budgets par préréglage

Mesurés à la résolution native de l'écran, en plein écran ou fenêtre maximale, avec tout le décor vivant.

| Préréglage | Images/s | p99 du temps d'image | Temps GPU médian | Enveloppe de ce lot |
| --- | --- | --- | --- | --- |
| `low` | ≥ 55 (spécification) | < 25 ms | ≤ 4 ms | +0,5 ms au plus |
| `medium` | ≥ 58 | < 25 ms | ≤ 12 ms, Y11 et Y12 compris | +4,5 ms au plus |
| `high` | ≥ 55 | < 25 ms | ≤ 14 ms | +6 ms au plus |

Le plafond de 12 ms en `medium` garde environ 30 % de marge pour les scènes chargées (villages, pluie, foules) et laisse l'enveloppe de +2,5 ms déjà accordée à Y11 et Y12.

## 4. Plan, ordonné par gain visuel par milliseconde

Coûts estimés pour la GTX 1060 en 1080p, à confirmer au banc à chaque étape.

| Étape | Contenu | Gain visuel | Coût GPU estimé (`medium`) | Godot |
| --- | --- | --- | --- | --- |
| **1 (prototype, cette PR)** | Rendu des tons Filmic, exposition, contraste et saturation (tous préréglages) | Fort : couleurs, ciel non délavé | ≈ 0 | 4.3 |
| 1 | Ombres : atlas 4096, filtre doux par préréglage, 4 cascades en `medium` et `high` (2 en `low`) | Fort : ombres nettes sous les arbres et les bâtiments | +0,5 à 1 ms | 4.3 |
| 1 | SSAO « medium » et SSIL « low » en demi-résolution (`medium`), SSAO « high » et SSIL « medium » en pleine résolution (`high`) | Moyen à fort : pieds des arbres, coins des maisons | +1 à 1,5 ms | 4.3 |
| 1 | MSAA 4× en `medium` (2× avant), FXAA en `low` (rien avant) | Moyen : bords des arbres, lignes de route | +0,5 à 1 ms ; `low` +0,2 ms | 4.3 |
| 1 | Filtrage anisotrope 16× (tous) | Moyen : route et sol nets au loin | +0,1 à 0,3 ms | 4.3 |
| 1 | Glow léger sur les zones très claires (`medium`, `high`) | Faible à moyen | +0,3 ms | 4.3 |
| 1 | Seuil des LOD automatiques 2 / 1 / 0,5 px | Faible | ≈ 0 | 4.3 |
| 2 | Densités et distances en `medium` : végétation 0,6 → 0,8, arbres 50 000 → 70 000, ombres 300 → 400 m, bâtiments 2,5 → 3,5 km | Moyen : paysage plus plein | +1 à 2 ms ; risque sur le p99 (construction des tuiles, à mesurer) | 4.3 |
| 3 | Brume volumétrique légère en `medium` (profondeur de l'air dans les vallées) | Moyen | +1 à 2 ms | 4.3 |
| 4 | Après la migration Y2 (4.7) : tonalité AgX, SMAA en `low`, SSR de l'eau (Y12), glow recalé (changé en 4.6) | Moyen | à mesurer | 4.7 |

Les plus gros gains visuels restants ne sont pas des réglages mais du contenu, déjà prévus ailleurs et non dupliqués ici : toits à pans et façades (Y8), forêts jusqu'à l'horizon en imposteurs (Y5), chaussée et herbe (Y11, et le fil « Améliorer l'herbe et les personnages »), lumières et particules (Y12), animaux et véhicules (P22 à P27).

## 5. Étape 1 réalisée (prototype)

- `quality_presets.gd` : nouvelle table `IMAGE` (anticrénelage `msaa` et `fxaa`, `ssao`, `ssil`, `ao_half_size`, `glow`, `shadow_atlas`, `shadow_splits`, `shadow_filter`, `mesh_lod_threshold`) et fonction `image(name)`. Les clés `ssao` et `msaa` quittent `PRESETS` pour cette table : toute la qualité d'image est au même endroit. Les budgets du décor vivant (`LIVING`) ne changent pas.
- `render_quality.gd` : `apply_image()` applique la table ; `LOOK` (rendu des tons et étalonnage communs) et `GLOW` ; `scaling_3d_scale` forcé à 1 (résolution native).
- `project.godot` : filtrage anisotrope 16×.
- Tests : `test_quality_presets.gd` (clés, valeurs connues, qualité croissante de `low` à `high`, toujours un anticrénelage) et `test_render_quality.gd` (application sur le viewport, l'environnement et le soleil).

| Réglage | `low` | `medium` | `high` |
| --- | --- | --- | --- |
| Rendu des tons | Filmic, exposition 1,25, blanc 6, contraste 1,08, saturation 1,18 | idem | idem |
| Anticrénelage | FXAA | MSAA 4× | MSAA 4× |
| SSAO / SSIL | non / non | medium / low, demi-résolution | high / medium, pleine résolution |
| Glow | non | oui | oui |
| Ombres | atlas 2048, 2 cascades, filtre doux bas | atlas 4096, 4 cascades, filtre doux moyen | atlas 4096, 4 cascades, filtre doux haut |
| Seuil LOD | 2 px | 1 px | 0,5 px |

Le rendu des tons a été choisi sur captures parmi Linear, Reinhard, Filmic et ACES : Filmic garde un ciel bleu et des verts francs, ACES délave le ciel, Reinhard aplatit les contrastes.

**Moteur Compatibility** (Xvfb, GPU modestes) : le filtre doux des ombres y tire un bruit différent à chaque image (grain qui scintille, relevé par la vérification « image figée » de `visual_check.py`) ; sans RenderingDevice, les ombres restent dures, comme SSAO et SSIL restent coupés. En `medium` sous Compatibility, le MSAA 4× sur les touffes d'herbe qui ondulent fait dépasser le seuil de cette même vérification (le vent bouge l'image) ; les tests automatiques tournent en `low` et le rendu Forward+ de `medium` passe la vérification.

**Captures avant et après** : rendu Forward+ réel de Godot 4.3 (Vulkan logiciel lavapipe, sans carte graphique) par `visual_check.py --native` sous Xvfb, 537 vérifications sur 537 en `low`, `medium` et `high`. Les captures ne sont pas prises au même instant exact (le rendu logiciel tourne à 1 à 3 images/s) : la position diffère de quelques mètres et les touffes d'herbe, construites progressivement, sont moins nombreuses après. Les mesures de temps se font sur le PC.

## 6. Mesures à faire sur le PC (étape 1)

Deux blocs de moins de 10 minutes, PC au calme, sans séance vélo, fenêtre annoncée avant ouverture :

1. `main` puis la branche, `medium`, monde `village` : `python3 engine/tests/sim_bench.py --native --probe --quality medium --size 1920x1080 --world village` (environ 3 min chacun).
2. La branche en `low` puis en `high`, même commande.

Critères : budgets du §3 ; écart d'images/s et de p99 entre `main` et la branche ; GPU médian et pointe dans `sonde.csv`. Si `medium` dépasse son enveloppe, retirer d'abord le SSIL, puis passer le MSAA à 2×.

## 7. Fichiers concernés

- **Modifiés :** `engine/scripts/quality_presets.gd`, `render_quality.gd`, `engine/project.godot`, `engine/tests/unit/test_quality_presets.gd`, `test_render_quality.gd`, ce cahier, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`, `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md`.
- **Hors lot :** les clés `LIVING` (décor vivant, fils P22 à P27 et herbe), `crowd_renderer.gd`, `grass_tufts.gd`, `fauna_*.gd`, `traffic_*.gd`, les shaders de la route et du terrain (Y11), les menus.

## 8. Liens avec les autres lots de la série Y

- **Y4 (ombres)** garde le côté coût : objets sans ombres, distances. La qualité des ombres (atlas, filtre, cascades) est ici.
- **Y6** : la résolution adaptative et la mise à l'échelle 3D sont écartées par la consigne du 27 octobre (résolution native seulement). L'anticrénelage de `low` (FXAA) est fait ici ; le SMAA attend Y2.
- **Y8** : l'étalonnage passe ici (étape 1) ; Y8 garde les toits et les façades.
- **Y2** : la migration recale la tonalité (AgX) et le glow (changé en 4.6) sur ces réglages.

## 9. Modifications de contrat autorisées

Aucune : ni IPC, ni format `.world`, ni thème, ni configuration (`[render] quality` reste le seul choix du joueur).

# Lot WTF9 : lisibilité du mode WTF et objets reconnaissables

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série WTF : gags lisibles et objets reconnaissables | GDScript | WTF8 étape A | Moyenne | **Livré le 12 novembre** (PR #848) |

Série WTF (2.0). Demande du propriétaire : constat WTF8 étape A du 8 novembre (gags peu compréhensibles faute d'annonce, objets mal définis, boule Katamari non identifiée) et règle du 11 novembre « gameplay lisible, expérience fluide, objets reconnaissables, pas de pavés ou de boule roses ».

## Diagnostic

- **Rose** : pas le matériau de secours de Godot. La scène WTF ne charge aucun shader ni matériau depuis un fichier (tout est `StandardMaterial3D` créé dans le code) ; la boule était peinte `WtfHudModel.PINK` et les objets à ramasser étaient des cubes d'un mètre (seule la vache avait sa forme).
- **Gags non annoncés** : le bandeau donnait le nom et le temps, mais rien sur quoi faire ; plusieurs gags n'avaient pas de carte (vélo minuscule, caméras, chef à l'arrivée).
- **Route qui s'effondre** : les tronçons tombaient sous le sol, donc invisibles ; on ne voyait qu'une bande noire.

## Ce qui change (engine seul, ni `main.gd` ni contrat IPC)

| Fichier | Changement |
| --- | --- |
| `wtf_hud_model.gd` | `banner.do` (consigne de chaque gag, de chaque manche des micro-défis, de chaque phase et plat du chef) ; `LEGENDS` (nom, ce qui se passe, ce que tu fais) et `legend_keys` (gag en premier, puis Katamari, cadence, peloton) ; `kata.next` (prochain objet, distance, ramassé ou « boing », d'après `KATA_NEED`, copie de `KATAMARI` du core). |
| `wtf_view.gd` | Ligne « À toi : … » dans le bandeau ; annonce (bandeau × 1,15 pendant 0,5 s à chaque nouveau gag ou phase) ; légende du premier passage, 7 s, à droite sous la colonne du HUD (au centre elle cachait le gag) ; ligne « Prochain » du Katamari ; invite du chef placée sous le bandeau quelle que soit sa hauteur. `update_view(view, now_s)` : horloge injectable pour les tests. |
| `wtf_scene.gd` | Boule du Katamari couverte de 32 objets collés ; pomme, panneau « danger », voiture, maison, église ; plaque de route arrachée (bitume, bande blanche, gravier, motte de terre, cailloux) ; gouffre avec lèvre déchiquetée, bords de terre et fissures devant le front ; plats sur assiette. Toujours un maillage à couleurs par sommet par objet (un appel de dessin), maillages partagés en cache. |
| `wtf_scene_model.gd` | Objets du Katamari sur la ligne de la boule, pomme à la taille 1 (à 0,3 elle disparaissait derrière le cycliste) ; plaques de l'effondrement basculées au-dessus du sol ; plats × 1,6 (`DISH_SCALE`). |
| `tests/vitrine_wtf.gd` | HUD par-dessus la 3D (`--hud 0` pour le retirer) ; gags ajoutés : effondrement proche, quatre plats, Katamari × 3, les six objets au sol sans la boule (`objets_katamari`). |

## Vérifications

- `test_wtf_hud_model` (59) et `test_wtf_scene` (61) : consigne et légende pour chaque gag, ordre des légendes, durée et reprise à la séance suivante, annonce, chaque objet en un maillage d'au moins deux couleurs sans rose uni.
- Captures `vitrine_wtf.gd` en `low`, `medium`, `high` à valider par le propriétaire avant fusion.
- Banc GPU low/medium/high sur le PC (budgets 8, 13, 16 ms) : les objets restent des primitives fusionnées, coût attendu négligeable ; à mesurer par la file PC (`sim_bench.py`).
- Puis WTF8 étape B sur le vélo (5 min, plan des essais du 14 novembre).

## Retouches du 15 novembre (séance WTF sur le vélo)

Constats du propriétaire : « où sont les œufs à l'écran ? » (le gag des œufs était joué, jingle et cinq casses au journal, mais rien n'était posé en 3D : seule la carte du HUD le montrait) et « la boule tourne dans le faux sens » (rotation `t × 4` liée à l'horloge, de signe opposé au roulement vers l'avant, et sans rapport avec la vitesse).

| Fichier | Changement |
| --- | --- |
| `wtf_scene_model.gd` | Champs `roll_r` et `rider` de chaque objet. Boule du Katamari (rayon affiché) et meule (`CHEESE_RADIUS_M`) : `roll_r`, plus de `spin` lié à l'horloge. Livraison d'œufs : carton `eggs_<intacts>` sur le porte-bagages (`EGG_RACK_BACK_M`, `EGG_RACK_UP_M`, `EGG_SCALE` cartoon), `rider` vrai ; `EGGS_TOTAL` copie de `Eggs.EGGS` du core. |
| `wtf_scene.gd` | Règle unique de roulement : un objet à `roll_r` tourne de −d / r autour de son axe à droite pour d mètres parcourus dans le sens de la marche (à rebours compris), sans tourner sur un saut de plus de 5 m. `follow_rider(xform)` : objets `rider` posés dans le repère du vélo affiché (voie, cap, pente, penché, taille). Carton d'œufs : plateau 2 × 3, sangles, œufs intacts debout, œufs cassés en flaque blanche et jaune (un maillage, cache par nombre d'œufs). |
| `main.gd` | `follow_rider` appelé après la pose de l'avatar, avec la pose du vélo. |
| `tests/vitrine_wtf.gd` | Gag `oeufs` (4 œufs sur 6). |

Vérifications : `test_wtf_scene` (boule qui roule vers l'avant de d / r dans les deux sens, pas de rotation sur un saut, carton sur le porte-bagages et penché avec le vélo, nombre d'œufs borné, carton à 6 et 0 œufs en un maillage à plusieurs couleurs). Planche cloud `vitrine_wtf.gd --gags oeufs` low/medium/high ; rotation de la boule à juger sur le PC (image fixe en vitrine).

## Livraison

Fusionné dans `main` : PR #848 (12 novembre). Statut relevé par la mise à jour de la documentation du 19 novembre 2026.

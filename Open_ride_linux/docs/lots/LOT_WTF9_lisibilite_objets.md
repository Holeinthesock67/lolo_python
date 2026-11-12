# Lot WTF9 : lisibilité du mode WTF et objets reconnaissables

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
| `wtf_scene_model.gd` | Objets du Katamari sur la ligne de la boule ; plaques de l'effondrement basculées au-dessus du sol ; plats × 1,6 (`DISH_SCALE`). |
| `tests/vitrine_wtf.gd` | HUD par-dessus la 3D (`--hud 0` pour le retirer) ; gags ajoutés : effondrement proche, quatre plats, Katamari × 3. |

## Vérifications

- `test_wtf_hud_model` (59) et `test_wtf_scene` (61) : consigne et légende pour chaque gag, ordre des légendes, durée et reprise à la séance suivante, annonce, chaque objet en un maillage d'au moins deux couleurs sans rose uni.
- Captures `vitrine_wtf.gd` en `low`, `medium`, `high` à valider par le propriétaire avant fusion.
- Banc GPU low/medium/high sur le PC (budgets 8, 13, 16 ms) : les objets restent des primitives fusionnées, coût attendu négligeable ; à mesurer par la file PC (`sim_bench.py`).
- Puis WTF8 étape B sur le vélo (5 min, plan des essais du 14 novembre).

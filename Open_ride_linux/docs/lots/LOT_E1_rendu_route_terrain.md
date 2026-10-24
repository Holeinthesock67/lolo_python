# Lot E1 – Rendu 3D : ruban de route et terrain par tronçons

## 1. Objectif

Remplacer la polyligne de démonstration par :
- un ruban de route en 3D ;
- un terrain construit à partir des tuiles de la couche terrain.

Les deux sont générés et libérés par tronçons au fil de la progression, sans à-coups. Ce lot couvre la première partie du sprint 3 (SRS §8). Le shader triplanaire et les thèmes (lot E2), les arbres (lot E3) et le HUD final viendront ensuite.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/SRS_v1.1.md` §8 (moteur de rendu, performance) et §12 (exigences de fluidité).
3. `docs/contracts/world_format_v1.md` :
   - §3 : repère (Godot et `.world` partagent les axes ; le nord est −z) ;
   - §4 : route ;
   - §5 : terrain, en entier ;
   - §10 : tuile manquante, terrain absent.
4. Code livré par les lots A et D :
   - `engine/scripts/route_data.gd` ;
   - le suivi de caméra ;
   - le chargement du parcours par `route_id`.

## 3. Prérequis

- **Lot A livré** (23 octobre ; API de `route_data.gd` décrite dans le lot D, §D5). **Lot D livré.**
- **Données de test :** si le lot B2 n'est pas livré, ce lot fournit son propre générateur de tuiles synthétiques (§4.5). Le format des tuiles est figé par le contrat ; le rendu ne dépend donc pas de B2.

## 4. Travail demandé

### 4.1 Ruban de route

- **Tronçons :** un tronçon par 1 000 m de `s`, soit le même découpage `k = ⌊s / 1000⌋` que les couches du format.
- **Section :**
  - une coupe tous les 2 m le long de `s`, positionnée par `route_data.sample_point(s)`, l'interpolation de Catmull-Rom du lot A ;
  - largeur de 6 m (valeur par défaut, à lire plus tard dans le thème) ;
  - chaussée plate en travers, l'axe transversal étant perpendiculaire au cap ;
  - bas-côtés : deux bandes de 0,5 m qui descendent de 5 cm, pour masquer la jonction avec le terrain.
- **Maillage :** normales correctes, UV avec `u` en travers (0 à 1) et `v` = `s` / 6 m. Les UV servent au lot E2.
- **Jointures :** pas de fente entre deux tronçons. La dernière coupe d'un tronçon est la première du suivant, aux mêmes coordonnées exactes.
- **Matériau provisoire :** gris uni (`StandardMaterial3D`) avec une ligne médiane blanche discontinue. La ligne peut être une texture générée en mémoire.

### 4.2 Terrain

- **Tuiles proches** (10 m, 1 000 m, 101 × 101) et **lointaines** (50 m, 5 000 m, 101 × 101) lues depuis `terrain/near/` et `terrain/far/`. Pour le placement, la taille et les `NaN`, le format §5 fait foi.
- **Une tuile = un maillage** (grille de 100 × 100 cellules), avec :
  - normales calculées à partir des voisins, de façon cohérente aux bords : prendre la valeur de la tuile voisine si elle est chargée, sinon une différence d'un seul côté ;
  - couleur de sommet provisoire selon la pente : vert sous 22°, gris au-dessus, blanc au-dessus de 2 200 m. Le lot E2 remplacera cette couleur par le shader triplanaire du thème.
- **Superposition :** les tuiles lointaines sont dessinées 2 m plus bas que leurs valeurs, et les tuiles proches à leur altitude exacte. Le relief proche recouvre ainsi le lointain sans scintillement. Documenter la valeur choisie.
  - **Écart voulu au format §5,** qui propose de relever le terrain proche de quelques centimètres. Le compilateur place déjà le terrain 5 cm sous la route (fondu) : relever le proche le mettrait au niveau exact de la chaussée et créerait un scintillement route-terrain. On abaisse donc le lointain à la place (voir §6).
- **`NaN`** remplacé par la moyenne des voisins valides ; s'il n'y en a aucun, par la valeur de la tuile lointaine au même endroit, puis par l'altitude de la route la plus proche.
- **Couche terrain absente :** sol plat 5 m sous l'altitude minimale de la route, avec brouillard (format §10).

### 4.3 Chargement par tronçons

- **Fenêtre active :**
  - ruban, tronçons `k` dont l'intervalle touche `[s − 1 000 ; s + 3 000]` ;
  - tuiles proches dans un rayon de 1 500 m de la caméra ;
  - tuiles lointaines dans un rayon de 12 km.
- **Génération des maillages :**
  - dans des tâches de fond (`WorkerThreadPool`), qui calculent seulement les tableaux de sommets ;
  - la création des objets de scène (`ArrayMesh`, `MeshInstance3D`) se fait sur le fil principal ;
  - au plus deux objets ajoutés par image, pour lisser le coût.
- **Libération :** les objets sortis de la fenêtre sont retirés et libérés. La mémoire reste stable sur un parcours long.
- **Anticipation :** pour une vitesse affichée `v`, la fenêtre avance d'au moins `v × 10 s`. À 60 km/h, aucun trou ne doit être visible devant la caméra.
- **Changement de parcours** (`route_id`) : tout est vidé puis reconstruit.

### 4.4 Réglages d'image (SRS §8)

- `Camera3D` : plan proche à 0,1 m, plan lointain égal au rayon des tuiles lointaines.
- **Brouillard** (`Environment.fog`) pour masquer la limite lointaine.
- **Préréglage `low`, par défaut :**
  - ombres de la lumière directionnelle sur 150 m seulement ;
  - pas de SSAO ;
  - MSAA désactivé.
- Les préréglages `medium` et `high` peuvent rester provisoires, mais doivent exister comme constantes.

### 4.5 Générateur de terrain synthétique (si le lot B2 n'est pas livré)

- Étendre `core/src/openride_core/tools/fake_world.py` avec une option `--terrain`. Elle écrit les tuiles proches et lointaines d'un relief analytique (collines sinusoïdales sur environ 300 m de dénivelé) autour du parcours de démonstration.
- Appliquer le fondu simplifié du format §5 : la route est posée à son altitude, avec une transition linéaire entre 4 et 25 m.
- Le manifeste déclare `terrain.present: true`.
- Ce générateur sert aux tests. Quand B2 sera livré, une vraie trace compilée le remplacera pour les essais manuels.

### 4.6 Tests automatiques sans écran

Ils s'exécutent dans le cadre de `engine/tests/` créé par le lot D.

1. **Raccord route-terrain :**
   - charger le parcours de démonstration avec terrain synthétique ;
   - placer `s` à 0, puis à 2 500 m ;
   - vérifier que les tronçons et tuiles chargés sont exactement ceux de la fenêtre ;
   - vérifier que la hauteur du ruban au centre égale `route_data.sample_point(s).y` à 1 cm près ;
   - vérifier que, à 3 m du bord, le terrain est sous la route de moins de 20 cm.
2. **Durée sans fuite :**
   - faire défiler `s` de 0 à la fin à 20 m/s simulés (sans attendre en temps réel) ;
   - le nombre de `MeshInstance3D` vivants reste borné, et le nombre d'objets (`Performance.OBJECT_COUNT`) en fin de parcours est à ± 5 % de sa valeur au premier tiers.
3. **Jointures :** les sommets de la dernière coupe d'un tronçon et de la première du suivant sont identiques.
4. **Terrain absent :** un parcours sans couche terrain s'affiche sans erreur, avec le sol plat.

## 5. Fichiers concernés

- **Nouveaux :**
  - `engine/scripts/road_builder.gd` ;
  - `engine/scripts/terrain_tiles.gd` ;
  - `engine/scripts/world_streamer.gd`. Les noms sont indicatifs ; un module par responsabilité.
- **Modifiés :**
  - `engine/scripts/main.gd` (retrait de la polyligne, branchement du gestionnaire de tronçons) ;
  - `engine/scenes/main.tscn` (brouillard, lumière, nœuds) ;
  - `engine/project.godot` (réglages de rendu).
- **Si le §4.5 s'applique :** `core/src/openride_core/tools/fake_world.py` et un test Python associé.
- **Contrat :** `docs/contracts/world_format_v1.md`, uniquement la phrase autorisée au §6.
- Tests dans `engine/tests/`.

## 6. Modifications de contrat autorisées

- **Seule modification permise :** la phrase du format §5 sur l'ordre de dessin (« l'engine dessine le proche par-dessus, légèrement relevé de quelques centimètres »). La remplacer par la règle du §4.2 (terrain lointain abaissé), avec une ligne au journal des changements. Les données ne changent pas.
- Pour toute autre règle du format qui rendrait le rendu impossible ou très coûteux : s'arrêter et le signaler.

## 7. Critères d'acceptation

1. Les 4 tests du §4.6 passent, ainsi que les tests des lots A et D.
2. `pytest` passe dans `core/`.
3. **Mesures de performance chiffrées dans le rapport,** sur une machine équipée d'une carte graphique dédiée ou par mesure du temps CPU en mode sans écran :
   - temps de construction d'un tronçon de route ;
   - temps de construction d'une tuile proche.
4. **Essai manuel du propriétaire** sur le PC cible (GTX 1060, préréglage `low`), avec la démo et terrain synthétique, puis avec une trace réelle compilée si B2 est livré :
   - au moins 60 images par seconde en moyenne ;
   - aucun à-coup visible à 40 km/h ;
   - aucun trou devant la caméra ;
   - aucune fente entre la route et le terrain.
   - L'exigence minimale de la SRS est de 30 images par seconde ; 60 est l'objectif sur ce PC.

## 8. Hors périmètre

- Shader triplanaire et thèmes (E2).
- Arbres (E3).
- Bâtiments, eau, points d'intérêt.
- HUD final et profil d'altitude.
- Menus.

## 9. Livraison (23 octobre 2026)

Réalisé par Claude, branche `lot-e1-rendu-route-terrain` (PR #7), remise à jour sur `main` après les lots A2, F et B2. Critères 1 à 3 tenus par les tests automatiques sans écran (Godot 4.3-stable) ; **critère 4 (essai sur le PC cible) à faire par le propriétaire**.

**Tests revérifiés après la mise à jour sur `main` :**
- `pytest` : 109 tests dans `core/`, 95 dans `compiler/`.
- `engine/tests/run_engine_tests.sh` : tout passe, aucune erreur ni avertissement de Godot. À s = 2 500 m, en plein lacet du lot A2, le terrain est de 4,5 à 4,8 cm sous la route à 3 m du bord. Au plus 27 `MeshInstance3D` vivants (borne 32), aucun trou, nombre d'objets stable (−1,1 %).
- Temps CPU sans écran : tronçon de route 7,4 ms, tuile proche 9,6 ms, `ArrayMesh` d'une tuile 0,8 ms.
- La démo avec terrain synthétique passe `openride-compiler verify`.

**Écarts assumés :**
- Module supplémentaire `engine/scripts/render_quality.gd` pour les préréglages d'image (`low` par défaut ; `medium` et `high` provisoires).
- Format §5 : le terrain lointain est dessiné 2 m plus bas (`FAR_DROP_M`), seule modification autorisée, notée au journal du format.
- Générateur synthétique : fondu linéaire de 4 à 25 m (B2 utilise un smoothstep). Le manifeste suit le format 1.1 (`tiles`, `road_half_width_m`), avec `sources: ["synthetic"]`.
- Au-delà de ± 5 km, faute de tuiles lointaines, on voit le ciel ; le brouillard (3 à 12 km) l'atténue.
- Sans écran, le maillage est détaché avant `free()` pour éviter `Parameter "m" is null` du rendu factice.
- Le recouvrement du tracé de démo signalé à la livraison est corrigé par le lot A2.

**Avant l'essai sur le PC cible :** supprimer `~/.local/share/openride/routes/demo.world`, puis suivre le §5 de la PR #7. Avec une trace réelle, compiler d'abord avec `openride-compiler` (B2 est livré).

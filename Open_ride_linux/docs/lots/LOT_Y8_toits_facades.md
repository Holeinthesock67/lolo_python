# Lot Y8 – Habillage des bâtiments : toits à pans, façades et styles par région et par biome

**Statut : étape 1 livrée le 28 octobre** (bâtiments, PR #470), mesurée sur la GTX 1060 (§5), en attente de l'avis du propriétaire sur l'aspect. Ce cahier remplace la première version du 28 octobre (PR #462) ; les écarts sont au §7. Étapes suivantes au §6 (arbres, panneaux, poteaux, barrières, éoliennes). L'étalonnage d'Y8 est passé dans Y13.

## 1. Objectif

Retours du propriétaire : « bâtiments non texturés, tous à toit plat » (25 octobre), « Et les textures pour bâtiments et autres ? », « Il devait pas y avoir des textures différentes par biome ? », « Il faudrait de la végétation différente, des animaux différents et bâtiments différents par biomes » (28 octobre).

Avant ce lot : un bâtiment est un prisme de la couleur unie du thème (`StandardMaterial3D` à couleurs de sommets), toit plat, aucune fenêtre ; les panneaux, bornes et éoliennes sont des boîtes de couleur unie.

## 2. Règles communes (pas d'exception)

- **Procédural d'abord, sans texture** (décision P20) : tout est dessiné par `engine/shaders/building.gdshader` avec la couche de surface commune de la route et du terrain (`surface_detail.gdshaderinc` : bruits, faux relief par perturbation de la normale, fondu du détail plus fin qu'un pixel). Un pack de textures CC0 pourra remplacer les motifs plus tard sans changer le maillage.
- **Une seule géométrie de toit** (`building_mesh.gd`) : la hauteur du toit est le minimum de plans (un plan pour un toit plat, deux pour deux pans, quatre pour des croupes), nulle au bord du rectangle orienté du contour. Le contour est triangulé comme avant puis découpé par pans ; les murs montent exactement jusqu'au toit (pignons et croupes), sans jour. Débord de 0,4 m (égout et rives) avec le dessous en voliges.
- **Styles calés sur le contrat U1 §4.3** : un style par variante d'architecture (`tuile_plate`, `tuile_ronde`, `ardoise`, `pierre_seche`, `toit_plat_blanc`, `bois`) dans `engine/scripts/building_styles.gd`. Le style d'un bâtiment est la variante régionale de sa tuile (U4), sinon le style de son biome dominant (16 biomes du lot U0), sinon `tuile_plate` : `BuildingStyles.resolve()`, posé dans la clé `style` du bâtiment. Le lot U14 n'aura qu'à fournir la variante et le biome.
- **Le type OSM décide de la famille** (`hint.building`) : maison, dépendance agricole, lieu de culte, immeuble ou bâtiment public, commerce, atelier ou industrie. `hint.colour` d'OSM remplace la couleur du mur.
- **Couleurs** : l'enduit et les tuiles plates prennent les palettes du thème (`buildings.walls`, `buildings.roofs` ; en 3.0, `walls` et `roofs` de la variante, fil des biomes) ; les matières qui ont leur couleur propre (brique, pierre, bois, tôle, béton, ardoise, tuiles rondes) prennent les palettes de `building_styles.gd`.
- **Contrats inchangés** : format `.world`, schéma de thème et IPC ne bougent pas. La couche ne donne que `roof: flat` (non renseigné, le compilateur l'écrit toujours) ou `gabled` (deux pans imposés).

## 3. Contenu

| Famille (exemples OSM) | Murs | Ouvertures | Toit |
| --- | --- | --- | --- |
| Maison (`house`, `yes`, `detached`…) | selon le style : enduit, colombage, brique, moellons, bardage de bois | fenêtres à petits bois et volets, porte sur certains murs, appuis | deux pans ou croupes, pente du style |
| Dépendance agricole (`barn`, `shed`, `garage`…) | bois ou pierre selon le style | jours hauts, grand portail à écharpe | deux pans, tuiles ou bac acier |
| Lieu de culte (`church`, `chapel`…) | pierre | hautes baies cintrées à vitraux | deux pans à 50° |
| Immeuble, bâtiment public (`apartments`, `school`…) | béton, enduit ou brique | bandeaux vitrés ou fenêtres à volets | pente adoucie ou croupes |
| Commerce (`retail`, `commercial`…) | béton ou enduit | vitrines et bandeau d'enseigne, fenêtres à l'étage | plat au-delà de 14 m de large |
| Atelier, industrie (`industrial`, `warehouse`…) | bardage de tôle ou béton | jours hauts, portail | bac acier plat ou à 8° |

Partout : socle de pierre de 0,55 m, salissures au pied des murs. Toit en pente seulement si le contour remplit au moins 80 % de son rectangle orienté et fait au plus 22 m de large (sinon toit plat).

| Style (U1) | Toit | Pente | Murs des maisons | Biomes qui le prennent par défaut |
| --- | --- | --- | --- | --- |
| `tuile_plate` | tuiles plates (queue de castor) | 45° | enduit, colombage, pierre, brique | prairie, forêt tempérée, cultures |
| `tuile_ronde` | tuiles canal ocre | 25° | enduit, pierre | méditerranéen |
| `ardoise` | ardoise | 45° | enduit, pierre, brique | haute montagne, zones humides, littoral |
| `pierre_seche` | lauzes | 35° | pierre | steppe, volcanique |
| `toit_plat_blanc` | toit plat blanc | 0° | enduit blanc | savane, déserts |
| `bois` | bardeaux | 35° | bardage de bois | taïga, toundra, polaire, jungle |

Préréglages : le faux relief est coupé en `low` (`BuildingMesh.RELIEF`) ; fenêtres, joints et rangs de tuiles restent dessinés en couleur. La portée d'affichage des bâtiments (`QualityPresets.building_visibility_end_m`) s'applique maintenant aussi aux tronçons déjà affichés quand on change de préréglage.

## 4. Coût

- Géométrie : une maison à deux pans passe de 10 à 24 triangles (murs coupés au faîtage, débord et son dessous) ; même nombre d'appels de dessin (un maillage par tronçon).
- Maillage (tâche de fond) : 500 bâtiments rectangulaires en environ 110 ms au lieu de 17 ms dans le nuage ; budget `building_mesh_500` porté à 150 ms.
- Processeur graphique : un shader par pixel de façade. Mesuré le 28 octobre sur la GTX 1060 (village, 1280 × 720, main contre la branche) : `low` 57,8 contre 57,9 images/s, GPU 4,7 contre 4,4 ms ; `medium` 57,8 contre 57,7 images/s, GPU 5,25 contre 5,17 ms. L'écart reste dans le bruit, sous l'enveloppe de +0,5 ms en `medium` et +0,2 ms en `low`.

## 5. Vérification

- Rendu hors écran : `engine/tests/render/test_building_render.gd` (une maison par style : pas de points parasites sur façade et toit éclairés, fenêtres dessinées, teinte du toit propre au style) avec le détecteur commun de pixels isolés `engine/tests/render/speckle.gd`, réutilisable pour les autres shaders.
- Tests : `engine/tests/unit/test_building_mesh.gd` (critères de L1 avec le style à toits plats, puis faîte, débord, murs jusqu'au toit, croupes, familles, styles par variante et par biome).
- Captures avant et après : vitrine de rendu `engine/tests/vitrine_rendu.gd`, vues `village`, `maisons`, `facades_pres`, `toits` et `styles` (une maison et une grange par style).
- Mesure sur la GTX 1060, à la résolution native (banc simulé, 2 min par préréglage, main contre la branche, `low`, `medium` puis `high`) : au moins 55 images/s en `low`, p99 sous 25 ms, et l'écart de temps GPU par image. Fait le 28 octobre (§4).

## 6. Suite (une PR par étape)

1. Étape 2 : arbres (écorce, feuillage à deux tons et trouées), même couche de surface ; styles d'arbres par biome avec le lot U7.
2. Étape 3 : panneaux, bornes et poteaux (bois, métal galvanisé, rouille, rétroréfléchissant), barrières et glissières.
3. Étape 4 : éoliennes et ouvrages (ponts, murets) quand ils existeront dans le monde.
4. Si la mesure dépasse : fondu des motifs à plus courte distance, ou dessous du débord limité à la bande de débord.
5. Avec U14 : passer la variante de la tuile et le biome dominant à chaque bâtiment (clé `style`).

## 7. Écarts à la première version du cahier (PR #462)

- Un seul shader `building.gdshader` (murs et toits) au lieu de `building_facade.gdshader`, et le test de rendu s'appelle `test_building_render.gd`.
- Pente selon le style (25 à 45°, 50° pour les lieux de culte) au lieu de 35° partout ; rectangle orienté rempli à 80 % au lieu de 85 % ; débord de 0,4 m au lieu de 0,3 m ; toit en pente jusqu'à 22 m de large, sans limite de hauteur.
- Les variantes régionales des murs et des toits, prévues hors périmètre (U14), sont faites ici par la table des styles, à la demande du propriétaire du 28 octobre ; U14 n'a plus qu'à poser la clé `style`.
- La coupure des fenêtres au loin se fait par le fondu du détail plus fin qu'un pixel de `surface_detail.gdshaderinc`, sans distance fixe.

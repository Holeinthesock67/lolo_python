# Lot SM2 – Épave, piste de sable et passants au Récif des tortues

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Point d'intérêt `wreck` (OSM `historic=wreck`), épave d'un caboteur avant l'arrivée du « Récif des tortues » ; aspect de chaussée par biome (piste de sable du fond marin) ; plus de passants sous l'eau | Python, GDScript, JSON | SM1, P12 | Petite | Fait (fusionné le 15 novembre, #891 ; relu par le lot NT1) |

## 1. Objectif

Demande du propriétaire du 14 novembre (16 h 03) : « Ajoute épave », limite connue du lot SM1. Une épave de navire
reconnaissable à l'arrivée du récif, vue de loin dans l'eau claire du lagon, sans rien changer au revêtement de la
route (choix du propriétaire encore ouvert).

Suite du 14 novembre (18 h 26) : « Ok piste mais correction personnage » : piste de sable au lieu du bitume (conseil
du 14 novembre, physique inchangée) et suppression du promeneur vu debout au bord de la route sur l'aperçu de l'épave.
Les trois changements sont dans la même PR (#891) : la branche de ce fil est la seule permise, et un seul banc de
recette (rSM2) les couvre.

## 2. Contenu livré

Pas d'exception propre au récif : l'épave est un point d'intérêt du format, comme les éoliennes et les drapeaux
(lot P12), rendu par un objet du décor construit par code.

| Où | Changement |
| --- | --- |
| Contrat | `world_format_v1.md` §8 et journal §12 ; `poi.schema.json` : sorte `wreck` (OSM `historic=wreck`), `length_m` facultatif (balise `length`, 42 m sans balise), journal à la 1.9 (après le volcan). Ajout compatible : un lecteur plus ancien ignore la sorte inconnue |
| Compilateur | `constants.POI_KINDS`, `POI_RADIUS_WRECK_M` (400 m) ; `osm_layers._poi_kind_and_radius` et `wreck_length` (lecture des longueurs commune avec la hauteur des éoliennes, `_metres_tag`) ; `verify` accepte la sorte. La requête Overpass ne change pas : son texte indexe le cache des données, la changer ferait retélécharger tous les parcours compilés et casserait la reconstruction hors réseau du pack des cols (test `test_overpass_query_unchanged`) |
| Démo | `demo_biomes._recif` : nœud `historic=wreck` « Épave de la Belle-Tortue » (variante de recette « Épave Fictive ») à `REEF_WRECK_S` = 7 880 m (120 m avant l'arrivée), 45 m du bord, côté extérieur, sur le sable entre la forêt du retour et le lagon ; fond à −11 m environ |
| Engine | `wrecks.gd` (nouveau, sur le modèle de `wind_turbines.gd`) : coque fermée à étrave relevée et tableau arrière, pont, timonerie, cheminée penchée, mât cassé et son tronçon tombé en travers du pont ; enfoncé de 1,5 m, gîte de 16° d'un bord tiré de l'`id`, proue qui pique de 2,5°, cap tiré de l'`id` ; mis à l'échelle de `length_m` ; 4 épaves au plus, les plus proches, retriées tous les 50 m ; rien ne bouge. `props.gdshader` sorte 7 : acier rouillé à plaques, coulures, algues et concrétions sur le dessus, pont de planches pourries, hublots, brèche sombre au flanc tribord, vitres noyées, sable sur le bas de la coque ; faux relief coupé en `low`. `osm_layers.gd` accepte la sorte ; `living_decor.gd` branche l'objet (préréglage, visibilité, points, mise à jour) |
| Piste de sable | Thème : clé facultative `biomes.<id>.road.color` (schéma et copie du compilateur, `world_format_v1.md` §9) ; thème par défaut : `biomes.reef.road` = `#c2b38f`. Engine : `road_surface.gd` (`biome_looks`, `look_from_weights`, `section(..., look)`) : sans portion réellement non revêtue, la chaussée prend la couleur des biomes qui en donnent une, part = leur poids, sans marquage ; même largeur (physique, son, cyclistes du décor et `rideable_half` du core inchangés) ; `road_builder.gd` : UV2.y = 1, `road_markings.gdshader` fond le bas-côté dans la piste ; `world_streamer.gd` passe `{weights_at, looks}` aux tâches des tronçons. Rien ne change pour un thème ou un parcours sans biome `road` |
| Passants | `living_decor._prepare_job` : parcours sous l'eau, `PassersbyModel.configure(null, …)` ; avant, seuls les passants des villages étaient retirés, les promeneurs de campagne (un tous les 300 à 800 m) restaient |
| Tests | moteur : `test_road_look_underwater.gd` (aspect du thème par défaut, part et couleur, bitume ailleurs, piste sans marquage et de même géométrie, aucun passant sous l'eau mais des promeneurs à l'air libre) ; compilateur : `test_osm_wreck.py` (classement, longueur, requête inchangée, compilation et schéma) ; core : `test_recif_wreck_before_finish` (place, nom, profondeur) ; engine : `test_wrecks.gd` (coque fermée dans le sens des faces de Godot, forme, points retenus, pose, échelle, hauteur sous 8 m, limite et coût) |

## 3. Coût attendu et recette PC

Une épave visible à la fois : cinq maillages (coque de 260 triangles, boîte, deux cylindres), trois matières,
aucune mise à jour par image hors du tri tous les 50 m (moins de 1 µs mesuré). Aperçu au cloud (Vulkan logiciel, medium, épave déplacée à 330 m du départ pour la capture) : caboteur reconnaissable de 80 à 150 m, aucune erreur de Godot. Recette à faire sur le PC du
propriétaire : banc `demo-recif` en low, medium et high (budgets GPU 8, 13 et 16 ms), captures de l'approche de
l'arrivée (7 600 à 7 900 m) à valider avant fusion.

Parcours déjà installé avant ce lot : `install_biome_demos` ne réécrit pas une démonstration présente. Pour voir
l'épave sur un jeu déjà installé, effacer `demo-recif.world` du dossier des parcours (`~/.local/share/openride/routes/` par défaut) avant de relancer (les bancs
réécrivent leurs parcours, eux).

## 4. Limites

- Pas de bancs de poissons attirés par l'épave (la faune du fond marin garde ses trajectoires du lot SM1).
- Le son du roulement reste celui du bitume sur la piste de sable (le fond sous l'eau le couvre en grande partie).
- Le talus sous les bords de la route garde la couleur du sol assombrie.

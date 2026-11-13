extends RefCounted

## Sol affiché sous les objets du bord de route (13/11 : « les bornes kilométriques lévitent »). Pas de
## class_name : charger par preload("res://scripts/roadside_ground.gd").
##
## Bornes, panneaux, torii, luminaires, balises, spectateurs et passants étaient posés à la hauteur de la
## chaussée décalée sur le côté. Or le terrain affiché est plus bas que la route à quelques mètres du bord :
## le compilateur et le terrain synthétique abaissent sous la chaussée toutes les cases de 10 m qu'elle touche
## (clear_road), le terrain descend sur le flanc aval, et le relief de séance (×2,5) multiplie l'écart. Mesuré
## sur les parcours de démonstration : 6 à 14 cm au relief réel, 15 à 35 cm au relief ×2,5, sous une borne
## de 58 cm de haut.
##
## Règle unique pour tous ces objets : leur pied est posé sur le sol visible (le plus haut du terrain affiché et
## du bas-côté ou du talus de la route, road_builder.gd), au point le plus bas de leurs appuis (une borne ou un
## poteau planté dans un talus a son pied aval enterré, jamais en l'air), enfoncé de FOOT_SINK_M. Sans couche terrain (pas de dossier de parcours), le sol est celui de la route : rien ne bouge.

const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")

## Enfoncement du pied sous le sol affiché (m) : ni jour sous le socle, ni socle noyé.
const FOOT_SINK_M := 0.03


## Hauteur affichée du terrain en (x, z), comme world_streamer.gd la dessine, relief exagéré compris
## (`route.display_y`, lots Q2 et Y15) : tuile proche, sinon tuile lointaine abaissée de son `y_offset`
## (TerrainTiles.LEVELS, ajouté après l'exagération comme dans TerrainTiles.build_arrays), sinon altitude de la
## route la plus proche. Vide sans dossier de parcours. Chaque appel a son propre cache de tuiles : une fonction
## par fil.
static func ground_fn(world_dir: String, route) -> Callable:
	if route == null or world_dir == "":
		return Callable()
	var cache := {}
	return func(x: float, z: float) -> float:
		for level in ["near", "far"]:
			var t := TerrainTiles.tile_of(level, x, z)
			var key := Vector3i(t.x, t.y, 0 if level == "near" else 1)
			if not cache.has(key):
				cache[key] = TerrainTiles.load_filled(world_dir, level, t.x, t.y, route) if level == "near" \
					else TerrainTiles.load_tile(world_dir, level, t.x, t.y)
			var h: PackedFloat32Array = cache[key]
			if h.is_empty():
				continue
			var y := TerrainTiles.mesh_height_at(h, level, t.x, t.y, x, z)
			if not is_nan(y):
				return route.display_y(y) + float(TerrainTiles.LEVELS[level]["y_offset"])
		return route.display_y(TerrainTiles.nearest_route_alt(route, x, z))


## Surface affichée de la chaussée et de ses abords à `d` mètres de l'axe (route à `road_y`, demi-largeur
## `half_m`), comme road_builder.gd la dessine : chaussée, bas-côté qui descend de SHOULDER_DROP_M, talus qui
## descend de SKIRT_DROP_M sur SKIRT_OUT_M ; -INF au-delà du talus.
static func road_surface_y(road_y: float, d: float, half_m: float) -> float:
	if d <= half_m:
		return road_y
	var outer := half_m + RoadBuilder.SHOULDER_WIDTH_M
	if d <= outer:
		return road_y - RoadBuilder.SHOULDER_DROP_M * (d - half_m) / RoadBuilder.SHOULDER_WIDTH_M
	if d <= outer + RoadBuilder.SKIRT_OUT_M:
		return road_y - RoadBuilder.SHOULDER_DROP_M - RoadBuilder.SKIRT_DROP_M * (d - outer) / RoadBuilder.SKIRT_OUT_M
	return -INF


## Sol visible en `p` près de l'axe `axis` (point de l'axe à la hauteur de la route, `right` horizontal
## unitaire vers la droite) : le plus haut du terrain affiché et de la surface de la route et de ses talus
## (le talus est enterré là où le terrain est au-dessus).
static func visible_ground_y(ground_at: Callable, p: Vector3, axis: Vector3, right: Vector3, half_m: float) -> float:
	var d := absf((p - axis).dot(right))
	return maxf(float(ground_at.call(p.x, p.z)), road_surface_y(axis.y, d, half_m))


## Hauteur du pied d'un objet posé en `xf` (repère du monde) dont les appuis sont `feet` (repère local), au bord
## de la route d'axe `axis` et de demi-largeur `half_m` : sol visible le plus bas sous les appuis, moins
## FOOT_SINK_M. Sans `ground_at` : hauteur de `xf` inchangée.
static func foot_y(ground_at: Callable, xf: Transform3D, axis: Vector3, right: Vector3, half_m: float,
		feet: PackedVector3Array = PackedVector3Array([Vector3.ZERO])) -> float:
	if not ground_at.is_valid():
		return xf.origin.y
	var y := INF
	for f in feet:
		y = minf(y, visible_ground_y(ground_at, xf * f, axis, right, half_m))
	if is_inf(y):
		return xf.origin.y
	return y - FOOT_SINK_M


## Point `pos` (un seul appui) posé sur le sol visible, même règle.
static func on_ground(ground_at: Callable, pos: Vector3, axis: Vector3, right: Vector3, half_m: float) -> Vector3:
	return Vector3(pos.x, foot_y(ground_at, Transform3D(Basis(), pos), axis, right, half_m), pos.z)

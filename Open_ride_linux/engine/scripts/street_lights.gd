extends Node3D

## Luminaires publics (lot P35, demande du 13 novembre) : candélabres le long de la route dans les villages et
## les villes, allumés la nuit. Posés par tronçon OSM chargé (living_decor.gd) : un tous les SPACING_M, en
## alternant les côtés, là où un bâtiment est à moins de NEAR_BUILDING_M de la route ; rien en rase campagne.
## Un MultiMesh par tronçon (un appel de dessin) ; la tête s'allume par night_lamp.gdshader (`night_glow`), et
## tout disparaît quand le jour et la nuit est coupé (`night_lamps`, image d'aujourd'hui).
## La lumière portée sur la route vient d'une petite réserve de projecteurs (SpotLight3D, sans ombre) posés
## sous les luminaires les plus proches de la caméra : LIGHTS_BY_PRESET (aucun en `low`).
##
## - `positions(route, k, buildings, road_width_m)` -> `[{s, side, pos, heading}]` et `lamp_transform(item)`
##   (fonctions pures, testées) ;
## - `add_chunk(route, k, buildings)` / `remove_chunk(k)` ; `set_preset(name)` ;
## - `update(cam_pos)` une fois par image : réserve de projecteurs, énergie selon NightLights.current.
## Pas de class_name : charger par preload("res://scripts/street_lights.gd").

const NightLights := preload("res://scripts/night_lights.gd")
const RoadsideModel := preload("res://scripts/roadside_model.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")

const CHUNK_M := 1000.0                 # osm_streamer.gd CHUNK_M
const SPACING_M := 32.0
const NEAR_BUILDING_M := 35.0
const SIDE_OFFSET_M := 0.6              # du bord de la chaussée
const POLE_H := 6.0
const ARM_M := 1.3                      # crosse au-dessus de la chaussée
const LIGHTS_BY_PRESET := {"low": 0, "medium": 4, "high": 8}
const SPOT_ENERGY := 8.0
const SPOT_RANGE_M := 16.0
const SPOT_ANGLE_DEG := 70.0
const REFRESH_S := 0.25

var road_width_m := RoadBuilder.ROAD_WIDTH_M
var _chunks: Dictionary = {}            # k -> {node, points: Array[Vector3] (têtes)}
var _spots: Array[SpotLight3D] = []
var _budget := 0
var _refresh_at := -INF
static var _mesh: ArrayMesh = null


static func _near_building(p: Vector2, buildings: Array) -> bool:
	var r := NEAR_BUILDING_M
	for b in buildings:
		var rect: Rect2 = b["rect"]
		if rect.grow(r).has_point(p):
			var pts: PackedVector2Array = b["points"]
			for q in pts:
				if q.distance_squared_to(p) <= r * r:
					return true
			if rect.has_point(p):
				return true
	return false


static func positions(route, k: int, buildings: Array, width_m: float = RoadBuilder.ROAD_WIDTH_M) -> Array:
	var out := []
	if route == null or buildings.is_empty():
		return out
	var s := ceilf(k * CHUNK_M / SPACING_M) * SPACING_M
	var end := minf((k + 1) * CHUNK_M, float(route.length_m))
	while s < end:
		var c: Vector3 = route.sample_point(s)
		if _near_building(Vector2(c.x, c.z), buildings):
			var side := 1 if int(round(s / SPACING_M)) % 2 == 0 else -1
			var h := deg_to_rad(float(route.sample_heading_deg(s)))
			var right := Vector3(cos(h), 0.0, sin(h))
			var pos := c + right * float(side) * (width_m * 0.5 + SIDE_OFFSET_M)
			out.append({"s": s, "side": side, "pos": pos, "heading": h})
		s += SPACING_M
	return out


## Candélabre : mât, crosse vers la route (−x local) et tête qui s'allume ; pied à l'origine.
static func lamp_mesh() -> ArrayMesh:
	if _mesh == null:
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		var pole := Color(0.22, 0.23, 0.24)
		NightLights.box(st, Vector3(0.0, POLE_H * 0.5, 0.0), Vector3(0.12, POLE_H, 0.12), pole)
		NightLights.box(st, Vector3(-ARM_M * 0.5, POLE_H - 0.05, 0.0), Vector3(ARM_M, 0.07, 0.07), pole)
		NightLights.box(st, Vector3(-ARM_M, POLE_H - 0.14, 0.0), Vector3(0.55, 0.16, 0.26), NightLights.WARM_COLOR, 9)
		_mesh = st.commit()
	return _mesh


## Pose d'un luminaire de `positions` : crosse (−x local) tournée vers la chaussée.
static func lamp_transform(it: Dictionary) -> Transform3D:
	var h := float(it["heading"])
	var to_road := -Vector3(cos(h), 0.0, sin(h)) * float(it["side"])
	return Transform3D(Basis(Vector3.UP, atan2(to_road.z, -to_road.x)), it["pos"])


func set_preset(name: String) -> void:
	_budget = int(LIGHTS_BY_PRESET.get(name, 0))
	while _spots.size() < _budget:
		var sp := SpotLight3D.new()
		sp.light_color = NightLights.WARM_COLOR
		sp.spot_range = SPOT_RANGE_M
		sp.spot_angle = SPOT_ANGLE_DEG
		sp.spot_attenuation = 1.0
		sp.shadow_enabled = false
		sp.rotation = Vector3(-PI * 0.5, 0.0, 0.0)   # vers le sol
		sp.visible = false
		add_child(sp)
		_spots.append(sp)
	while _spots.size() > _budget:
		_spots.pop_back().queue_free()
	_refresh_at = -INF


func add_chunk(route, k: int, buildings: Array) -> void:
	remove_chunk(k)
	var items := positions(route, k, buildings, road_width_m)
	if items.is_empty():
		return
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = lamp_mesh()
	mm.instance_count = items.size()
	var heads: Array[Vector3] = []
	for i in range(items.size()):
		var xf := lamp_transform(items[i])
		mm.set_instance_transform(i, xf)
		heads.append(xf * Vector3(-ARM_M, POLE_H - 0.2, 0.0))
	var mi := MultiMeshInstance3D.new()
	mi.name = "StreetLights%d" % k
	mi.multimesh = mm
	mi.material_override = NightLights.lamp_material()
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
	_chunks[k] = {"node": mi, "heads": heads}
	_refresh_at = -INF


func remove_chunk(k: int) -> void:
	if not _chunks.has(k):
		return
	(_chunks[k]["node"] as Node).queue_free()
	_chunks.erase(k)
	_refresh_at = -INF


func clear() -> void:
	for k in _chunks.keys():
		remove_chunk(k)


func count() -> int:
	var n := 0
	for k in _chunks:
		n += (_chunks[k]["heads"] as Array).size()
	return n


## Projecteurs sous les têtes les plus proches de `cam_pos`, la nuit seulement.
func update(cam_pos: Vector3, now_s: float) -> void:
	var g := NightLights.current
	if g <= 0.0 or _spots.is_empty():
		for sp in _spots:
			sp.visible = false
		return
	if now_s - _refresh_at >= REFRESH_S:
		_refresh_at = now_s
		var near := []
		for k in _chunks:
			for p in _chunks[k]["heads"]:
				var d := cam_pos.distance_squared_to(p)
				if d < 150.0 * 150.0:
					near.append([d, p])
		near.sort_custom(func(a, b): return a[0] < b[0])
		for i in range(_spots.size()):
			_spots[i].visible = i < near.size()
			if i < near.size():
				_spots[i].position = near[i][1]
	for sp in _spots:
		sp.light_energy = SPOT_ENERGY * g

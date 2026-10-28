extends Node3D

## Touffes d'herbe en bord de route qui ondulent au vent apparent (Lot P5), nœud autonome.
## Pas de class_name : charger par preload("res://scripts/grass_tufts.gd"). Branché par P16 dans main.gd.
##
## - Touffes en MultiMesh, même shader que les arbres (`tree_sway.gdshader`), avec le vent apparent du
##   cycliste (`set_apparent_wind`).
## - Lot Y11 (H4) : une touffe est une gerbe de `BLADES` brins effilés et courbés (trois triangles par
##   brin), base à la teinte du sol, pointe plus claire ; teinte d'instance tirée de `TINTS` (herbe
##   fraîche, sombre, jaunie, sèche) ; touffes éclaircies avec la distance puis effacées avant la fin de
##   la fenêtre (`thin_start_m`, `fade_end_m` du shader) pour ne pas surgir.
## - Placement déterministe (graine, numéro de tronçon, numéro de place) sur une bande de
##   `BAND_MIN_M` à `BAND_MAX_M` du bord de la route, des deux côtés, autour de la caméra : tronçons
##   de `CHUNK_M` mètres, `CHUNKS_BEHIND` derrière et `CHUNKS_AHEAD` devant.
## - Pas de touffe sur la route, dans un bâtiment ou dans l'eau (polygones `exclusions`, x et z) ;
##   densité réduite avec la pente du terrain (`height_at`, facultatif).
## - Nombre de touffes jamais au-dessus du budget (`living(preset).grass_tufts`, 0 en `low` : nœud vide).
## - Coût lissé : un tronçon qui entre dans la fenêtre est rempli `MAX_PER_FRAME` places par image.

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const TreeSwayShader := preload("res://shaders/tree_sway.gdshader")

const CHUNK_M := 40.0
const CHUNKS_BEHIND := 1
const CHUNKS_AHEAD := 4
const BAND_MIN_M := 2.0
const BAND_MAX_M := 15.0
const MAX_SLOPE := 0.7          # pente (tan) au-delà de laquelle il n'y a plus de touffe
const MAX_PER_FRAME := 120
const STATION_STEP_M := 4.0
const STATION_COST := 40        # coût d'un échantillonnage de tronçon, compté en places
const TUFT_HEIGHT_M := 0.45
const TUFT_RADIUS_M := 0.14
const BLADES := 12
const BLADE_WIDTH_M := 0.035
## Teintes d'instance (multiplient la couleur des sommets) : fraîche, sombre, jaunie, sèche.
const TINTS := [Color(1.0, 1.0, 1.0), Color(0.78, 0.88, 0.78), Color(1.12, 1.08, 0.78), Color(1.3, 1.15, 0.72)]
## Fondu avec la distance (mètres) : éclaircissement à partir de THIN_START_M, effacement complet à FADE_END_M,
## avant la fin de la fenêtre de tronçons devant la caméra (CHUNKS_AHEAD × CHUNK_M).
const THIN_START_M := 30.0
const FADE_END_M := 150.0
const APPARENT_MAX_MPS := 60.0 / 3.6
const NO_CHUNK := -(1 << 40)
## Place vide : échelle nulle, sous le terrain.
static var HIDDEN := Transform3D(Basis().scaled(Vector3.ZERO), Vector3(0.0, -10000.0, 0.0))

var route = null                     # route_data.gd
var road_half_width_m := 3.0
var tuft_seed := 0
var exclusions: Array = []           # Array[PackedVector2Array] : bâtiments et plans d'eau (x, z)
var height_at: Callable = Callable() # (x, z) -> hauteur du terrain ; vide : hauteur de la route

var _budget := 0
var _per_chunk := 0
var _mm: MultiMesh = null
var _mmi: MultiMeshInstance3D = null
var _material: ShaderMaterial = null
var _slot_chunk: PackedInt64Array = PackedInt64Array()   # tronçon occupant chaque groupe de places
var _queue: Array = []                                    # [groupe, tronçon, place suivante, stations]
var _visible_count := 0
var _origins := PackedVector3Array()   # copie côté CPU des positions (tests, comptage)
var _placed := PackedByteArray()


## Budget de touffes (0 : rien n'est créé) ; à appeler avant `update`.
func configure(budget: int, route_data, road_width_m: float = 6.0, seed_value: int = 0) -> void:
	route = route_data
	road_half_width_m = road_width_m * 0.5
	tuft_seed = seed_value
	_budget = maxi(budget, 0)
	var groups := CHUNKS_BEHIND + CHUNKS_AHEAD + 1
	_per_chunk = _budget / groups
	_queue.clear()
	_visible_count = 0
	if _mmi != null:
		_mmi.queue_free()
		_mmi = null
		_mm = null
	if _per_chunk <= 0:
		return
	_material = TreeRenderer.sway_material(true)
	_material.set_shader_parameter("use_local_wind", true)
	_material.set_shader_parameter("sway_height_m", TUFT_HEIGHT_M)
	_material.set_shader_parameter("sway_amplitude_m", 0.12)
	_material.set_shader_parameter("sway_frequency_hz", 0.9)
	_material.set_shader_parameter("thin_start_m", THIN_START_M)
	_material.set_shader_parameter("fade_end_m", FADE_END_M)
	_material.set_shader_parameter("normals_up_both_sides", true)
	_mm = MultiMesh.new()
	_mm.transform_format = MultiMesh.TRANSFORM_3D
	_mm.use_colors = true
	_mm.mesh = build_tuft_mesh()
	_mm.instance_count = _per_chunk * groups
	for i in range(_mm.instance_count):
		_mm.set_instance_transform(i, HIDDEN)
	_origins.resize(_mm.instance_count)
	_placed.resize(_mm.instance_count)
	_placed.fill(0)
	_slot_chunk = PackedInt64Array()
	_slot_chunk.resize(groups)
	_slot_chunk.fill(NO_CHUNK)
	_mmi = MultiMeshInstance3D.new()
	_mmi.multimesh = _mm
	_mmi.material_override = _material
	_mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_mmi)


func get_capacity() -> int:
	return 0 if _mm == null else _mm.instance_count


## Touffes réellement placées (hors places masquées par une exclusion ou la pente).
func get_visible_count() -> int:
	return _visible_count


## Positions des touffes placées (copie côté CPU).
func get_positions() -> PackedVector3Array:
	var out := PackedVector3Array()
	for i in range(_placed.size()):
		if _placed[i] == 1:
			out.append(_origins[i])
	return out


## Vent apparent du cycliste (m/s, repère de Godot), sortie de wind_model.apparent().
func set_apparent_wind(apparent: Vector3) -> void:
	if _material == null:
		return
	var horiz := Vector3(apparent.x, 0.0, apparent.z)
	var speed := horiz.length()
	_material.set_shader_parameter("local_wind_dir", horiz / speed if speed > 1e-4 else Vector3.ZERO)
	_material.set_shader_parameter("local_wind_strength", clampf(speed / APPARENT_MAX_MPS, 0.0, 1.0))


## Une fois par image : fenêtre de tronçons autour de la position `cam_s` le long de la route.
func update(cam_s: float) -> void:
	if _mm == null or route == null:
		return
	var first := int(floor(cam_s / CHUNK_M)) - CHUNKS_BEHIND
	var groups := _slot_chunk.size()
	for k in range(first, first + groups):
		var g := posmod(k, groups)
		if _slot_chunk[g] != k:
			_slot_chunk[g] = k
			for i in range(_queue.size() - 1, -1, -1):
				if _queue[i][0] == g:
					_queue.remove_at(i)
			_queue.append([g, k, 0, PackedVector4Array()])
	var budget := MAX_PER_FRAME
	while budget > 0 and not _queue.is_empty():
		var job: Array = _queue[0]
		var g: int = job[0]
		var k: int = job[1]
		var j: int = job[2]
		var stations: PackedVector4Array = job[3]
		if stations.is_empty():
			stations = chunk_stations(k)
			job[3] = stations
			budget -= STATION_COST
		var end := mini(j + maxi(budget, 1), _per_chunk)
		for slot in range(j, end):
			var xf: Variant = tuft_transform(k, slot, stations)
			var idx := g * _per_chunk + slot
			var was_visible := _placed[idx] == 1
			if xf == null:
				_mm.set_instance_transform(idx, HIDDEN)
				_placed[idx] = 0
				_visible_count -= 1 if was_visible else 0
			else:
				var x: Transform3D = xf
				_mm.set_instance_transform(idx, x)
				_mm.set_instance_color(idx, TINTS[tint_index(k, slot)])
				_origins[idx] = x.origin
				_placed[idx] = 1
				_visible_count += 0 if was_visible else 1
		budget -= end - j
		if end >= _per_chunk:
			_queue.pop_front()
		else:
			job[2] = end


## Vrai quand tous les tronçons de la fenêtre sont remplis.
func is_settled() -> bool:
	return _queue.is_empty()


## Route échantillonnée tous les `STATION_STEP_M` mètres sur le tronçon `k` : (x, y, z, cap en radians).
## Un seul échantillonnage de la route par tronçon, au lieu d'un par touffe.
func chunk_stations(k: int) -> PackedVector4Array:
	var out := PackedVector4Array()
	var n := int(CHUNK_M / STATION_STEP_M)
	for i in range(n + 1):
		var smp: Dictionary = route.sample(float(k) * CHUNK_M + i * STATION_STEP_M)
		out.append(Vector4(smp["x"], smp["y"], smp["z"], deg_to_rad(float(smp["heading_deg"]))))
	return out


## Transformation de la place `slot` du tronçon `k`, ou null (hors route, exclue ou trop pentue).
func tuft_transform(k: int, slot: int, stations: PackedVector4Array = PackedVector4Array()) -> Variant:
	var h := VegetationPlacer.hash3(tuft_seed ^ 0x6A55, k, slot)
	var h2 := VegetationPlacer.hash3(tuft_seed ^ 0x7B66, k, slot)
	var u := float(h & 0xFFFF) / 65536.0
	var lat := BAND_MIN_M + float((h >> 16) & 0xFFFF) / 65536.0 * (BAND_MAX_M - BAND_MIN_M)
	var side := 1.0 if h2 & 1 == 0 else -1.0
	var s_pos := (float(k) + u) * CHUNK_M
	if not route.is_loop() and (s_pos < 0.0 or s_pos > route.length_m):
		return null
	if stations.is_empty():
		stations = chunk_stations(k)
	var fi := u * (stations.size() - 1)
	var i0 := mini(int(fi), stations.size() - 2)
	var st := stations[i0].lerp(stations[i0 + 1], fi - i0)
	var right := Vector3(cos(st.w), 0.0, sin(st.w))
	var off := road_half_width_m + lat
	var px: float = st.x + right.x * off * side
	var pz: float = st.z + right.z * off * side
	var p2 := Vector2(px, pz)
	for poly in exclusions:
		if Geometry2D.is_point_in_polygon(p2, poly):
			return null
	var py: float = st.y
	if height_at.is_valid():
		py = float(height_at.call(px, pz))
		var dx: float = float(height_at.call(px + 1.0, pz)) - py
		var dz: float = float(height_at.call(px, pz + 1.0)) - py
		var slope := sqrt(dx * dx + dz * dz)
		var keep := 1.0 - clampf(slope / MAX_SLOPE, 0.0, 1.0)
		if float((h2 >> 1) & 0xFF) / 255.0 >= keep:
			return null
	var angle := float((h2 >> 16) & 0xFFFF) / 65536.0 * TAU
	var scale_f := 0.7 + float((h2 >> 9) & 0x7F) / 127.0 * 0.6
	return Transform3D(Basis(Vector3.UP, angle).scaled(Vector3.ONE * scale_f), Vector3(px, py, pz))


## Teinte (indice dans TINTS) de la place `slot` du tronçon `k` : surtout fraîche, parfois sèche.
func tint_index(k: int, slot: int) -> int:
	var u := VegetationPlacer.hash3(tuft_seed ^ 0x2C71, k, slot) & 0xFF
	return 0 if u < 120 else (1 if u < 180 else (2 if u < 230 else 3))


## Touffe : gerbe de BLADES brins effilés (deux segments et une pointe, trois triangles), penchés vers
## l'extérieur et courbés, de hauteurs variées ; base à la teinte du sol, pointe plus claire. Normales
## tournées vers le haut pour que la gerbe soit éclairée comme le sol (pas de faces noires à contre-jour).
static func build_tuft_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var base := Color(0.3, 0.42, 0.18)
	var mid := Color(0.4, 0.56, 0.24)
	var tip := Color(0.58, 0.68, 0.32)
	var rng := RandomNumberGenerator.new()
	rng.seed = 0x6EA55
	for b in range(BLADES):
		var a := TAU * (float(b) + rng.randf() * 0.6) / BLADES
		var out := Vector3(cos(a), 0.0, sin(a))
		var side := Vector3(-out.z, 0.0, out.x)
		var root := out * TUFT_RADIUS_M * rng.randf_range(0.0, 0.7)
		var h := TUFT_HEIGHT_M * rng.randf_range(0.55, 1.0)
		var lean := rng.randf_range(0.15, 0.45) * h
		var w := BLADE_WIDTH_M * rng.randf_range(0.8, 1.2)
		# Points du milieu de brin : base, coude, pointe (le coude penche moins que la pointe : courbure)
		var p0 := root
		var p1 := root + out * lean * 0.35 + Vector3(0.0, h * 0.55, 0.0)
		var p2 := root + out * lean + Vector3(0.0, h, 0.0)
		var n := (Vector3.UP * 0.8 + out * 0.2).normalized()
		var tris := [[p0 - side * w, base], [p0 + side * w, base], [p1 + side * w * 0.6, mid],
			[p0 - side * w, base], [p1 + side * w * 0.6, mid], [p1 - side * w * 0.6, mid],
			[p1 - side * w * 0.6, mid], [p1 + side * w * 0.6, mid], [p2, tip]]
		for v in tris:
			st.set_color(v[1])
			st.set_normal(n)
			st.add_vertex(v[0])
	return st.commit()

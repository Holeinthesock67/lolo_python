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
## - Garde-fou de la chaussée : une touffe est toujours à `ROAD_CLEAR_M` au moins du bord de la route,
##   mesuré sur TOUT le parcours (road_clearance.gd) et pas seulement au point qui l'a posée : dans une
##   épingle, au creux d'un virage serré ou là où le parcours repasse près de lui-même, l'herbe tombait
##   sur l'autre portion de route.
## - Nombre de touffes jamais au-dessus du budget (`living(preset).grass_tufts` : 1 500 en `low`, 8 000 en
##   `medium`, 20 000 en `high` ; 0 quand le décor vivant est coupé : nœud vide).
## - Coût lissé : un tronçon qui entre dans la fenêtre est rempli au plus `MAX_PER_FRAME` places et
##   `MAX_FRAME_US` microsecondes par image.
## - Niveau de détail selon la distance (lot « herbe au loin », 05/11 : biome cultures au-dessus du budget GPU) :
##   chaque tronçon a deux MultiMesh, la gerbe complète jusqu'à `LOD_SWITCH_M` et une gerbe simplifiée
##   (`FAR_BLADES` brins d'un triangle, plus larges) au-delà, qui ne garde que les touffes que le fondu montre
##   encore. Le passage se fait touffe par touffe dans le shader (`lod_begin_m`, `lod_end_m`, fondu en taille sur
##   `LOD_BLEND_M`) ; la plage de visibilité de chaque MultiMesh (centre de sa boîte) coupe en plus le tronçon
##   entier quand toutes ses touffes sont du mauvais côté, et sa boîte (`custom_aabb`) le retire hors du champ
##   de la caméra (tronçon derrière elle compris). Le tirage du fondu vient de la touffe (INSTANCE_CUSTOM.x) pour
##   que le choix des touffes lointaines soit le même côté CPU et côté GPU.

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const TreeSwayShader := preload("res://shaders/tree_sway.gdshader")
const RoadClearance := preload("res://scripts/road_clearance.gd")

const CHUNK_M := 40.0
const CHUNKS_BEHIND := 1
const CHUNKS_AHEAD := 4
const BAND_MIN_M := 2.0
const BAND_MAX_M := 15.0
## Écart minimal entre une touffe et le bord de la chaussée, sur tout le parcours (rayon et pointe penchée compris).
const ROAD_CLEAR_M := 1.0
const MAX_SLOPE := 0.7          # pente (tan) au-delà de laquelle il n'y a plus de touffe
const MAX_PER_FRAME := 120
## Temps de remplissage par image (µs) : vérifié toutes les BATCH places. Sur un parcours sans tuile de
## terrain, chaque place coûte bien plus (hauteur lue sur la route) : 120 places faisaient 60 à 80 ms au
## début de chaque tronçon de 40 m (saccades du 04/11).
const MAX_FRAME_US := 1500
const BATCH := 16
const STATION_STEP_M := 4.0
const STATION_COST := 40        # coût d'un échantillonnage de tronçon, compté en places
const TUFT_HEIGHT_M := 0.45
const TUFT_RADIUS_M := 0.14
const BLADES := 12
const BLADE_WIDTH_M := 0.035
## Teintes d'instance (multiplient la couleur des sommets) : fraîche, sombre, jaunie, sèche.
const TINTS := [Color(1.0, 1.0, 1.0), Color(0.78, 0.88, 0.78), Color(1.12, 1.08, 0.78), Color(1.3, 1.15, 0.72)]
## Désert (sable ou pierre, retour du propriétaire 03/11) : herbe sèche, paille et ocre, plus clairsemée.
## Le biome d'une touffe est tiré selon les poids du modèle de biome (`biome_model`, nul : herbe d'avant).
const DRY_BIOMES := ["sand_desert", "rock_desert"]
const DRY_TINTS := [Color(1.55, 0.95, 1.2), Color(1.75, 1.05, 1.15), Color(1.35, 0.8, 0.95), Color(1.9, 1.2, 1.45)]
## Part des places gardées dans le désert (touffes plus espacées qu'en prairie).
const DRY_KEEP := 0.45
## Fondu avec la distance (mètres) : éclaircissement à partir de THIN_START_M, effacement complet à FADE_END_M,
## avant la fin de la fenêtre de tronçons devant la caméra (CHUNKS_AHEAD × CHUNK_M).
const THIN_START_M := 30.0
## 120 m au lieu de 150 (lot « herbe au loin ») : touffes moins denses au-delà de quelques dizaines de mètres.
const FADE_END_M := 120.0
## Passage de la gerbe complète à la gerbe simplifiée (m), fondu en taille sur ± LOD_BLEND_M.
const LOD_SWITCH_M := 40.0
const LOD_BLEND_M := 4.0
## Gerbe lointaine : brins d'un seul triangle, plus larges pour couvrir autant que la gerbe complète vue de loin.
const FAR_BLADES := 5
const FAR_BLADE_WIDTH_M := 0.07
## Marge de la boîte d'un tronçon (m) : rayon et penché des touffes, vent.
const AABB_MARGIN_M := 1.0
const APPARENT_MAX_MPS := 60.0 / 3.6
const NO_CHUNK := -(1 << 40)
## Place vide : échelle nulle, sous le terrain.
static var HIDDEN := Transform3D(Basis().scaled(Vector3.ZERO), Vector3(0.0, -10000.0, 0.0))

## Modèle de biome du parcours (biome_model.gd), posé par living_world.gd ; nul : herbe d'avant partout.
var biome_model = null
var route = null                     # route_data.gd
var road_half_width_m := 3.0
var tuft_seed := 0
var exclusions: Array = []           # Array[PackedVector2Array] : bâtiments et plans d'eau (x, z)
var height_at: Callable = Callable() # (x, z) -> hauteur du terrain ; vide : hauteur de la route

var _road: RoadClearance = null       # distance à la route sur tout le parcours
var _budget := 0
var _per_chunk := 0
## Par groupe de places (un tronçon chacun) : gerbes complètes (proches) et simplifiées (lointaines).
var _near_mm: Array[MultiMesh] = []
var _far_mm: Array[MultiMesh] = []
var _near_mmi: Array[MultiMeshInstance3D] = []
var _far_mmi: Array[MultiMeshInstance3D] = []
var _near_material: ShaderMaterial = null
var _far_material: ShaderMaterial = null
var _slot_chunk: PackedInt64Array = PackedInt64Array()   # tronçon occupant chaque groupe de places
var _filled := PackedInt32Array()                         # places déjà calculées du tronçon de chaque groupe
var _far_count := PackedInt32Array()                      # touffes lointaines de chaque groupe
var _group_visible := PackedInt32Array()                  # touffes placées de chaque groupe
var _aabb: Array[AABB] = []                               # boîte du tronçon de chaque groupe
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
	for c in get_children():
		c.queue_free()
	_near_mm.clear()
	_far_mm.clear()
	_near_mmi.clear()
	_far_mmi.clear()
	_aabb.clear()
	_filled = PackedInt32Array()
	_far_count = PackedInt32Array()
	_group_visible = PackedInt32Array()
	_near_material = null
	_far_material = null
	_road = null
	if _per_chunk <= 0:
		return
	_road = RoadClearance.new(route)
	_near_material = _tuft_material(0.0, LOD_SWITCH_M)
	_far_material = _tuft_material(LOD_SWITCH_M, 0.0)
	var near_mesh := build_tuft_mesh()
	var far_mesh := build_far_tuft_mesh()
	for g in range(groups):
		_near_mm.append(_make_mm(near_mesh))
		_far_mm.append(_make_mm(far_mesh))
		_near_mmi.append(_make_mmi(_near_mm[g], _near_material))
		_far_mmi.append(_make_mmi(_far_mm[g], _far_material))
		_aabb.append(AABB())
	_origins.resize(_per_chunk * groups)
	_placed.resize(_per_chunk * groups)
	_placed.fill(0)
	_slot_chunk = PackedInt64Array()
	_slot_chunk.resize(groups)
	_slot_chunk.fill(NO_CHUNK)
	_filled.resize(groups)
	_far_count.resize(groups)
	_group_visible.resize(groups)


## Matériau des touffes : balancement au vent apparent, fondu avec la distance, montrées de `lod_begin`
## à `lod_end` mètres (0 : sans borne).
func _tuft_material(lod_begin: float, lod_end: float) -> ShaderMaterial:
	var m := TreeRenderer.sway_material(true)
	m.set_shader_parameter("use_local_wind", true)
	m.set_shader_parameter("sway_height_m", TUFT_HEIGHT_M)
	m.set_shader_parameter("sway_amplitude_m", 0.12)
	m.set_shader_parameter("sway_frequency_hz", 0.9)
	m.set_shader_parameter("thin_start_m", THIN_START_M)
	m.set_shader_parameter("fade_end_m", FADE_END_M)
	m.set_shader_parameter("pick_from_custom", true)
	m.set_shader_parameter("lod_begin_m", lod_begin)
	m.set_shader_parameter("lod_end_m", lod_end)
	m.set_shader_parameter("lod_blend_m", LOD_BLEND_M)
	m.set_shader_parameter("normals_up_both_sides", true)
	return m


func _make_mm(mesh: Mesh) -> MultiMesh:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.use_custom_data = true
	mm.mesh = mesh
	mm.instance_count = _per_chunk
	mm.visible_instance_count = 0
	return mm


func _make_mmi(mm: MultiMesh, material: ShaderMaterial) -> MultiMeshInstance3D:
	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh = mm
	mmi.material_override = material
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mmi.visible = false
	add_child(mmi)
	return mmi


## Part des touffes gardées par le fondu à `d` mètres de la caméra (même courbe que tree_sway.gdshader).
static func keep_at(d: float) -> float:
	return 1.0 - smoothstep(THIN_START_M, FADE_END_M, d)


## Tirage du fondu de la place `slot` du tronçon `k` (0 à 1) : la touffe est montrée tant que keep_at(d) le dépasse.
func pick_of(k: int, slot: int) -> float:
	return float(VegetationPlacer.hash3(tuft_seed ^ 0x3E91, k, slot) & 0xFFFF) / 65536.0


func get_capacity() -> int:
	return _per_chunk * _near_mm.size()


## Touffes réellement placées (hors places masquées par une exclusion ou la pente).
func get_visible_count() -> int:
	return _visible_count


## Positions des touffes placées (copie côté CPU).
func get_positions() -> PackedVector3Array:
	var out := PackedVector3Array()
	for g in range(_filled.size()):
		for slot in range(_filled[g]):
			var i := g * _per_chunk + slot
			if _placed[i] == 1:
				out.append(_origins[i])
	return out


## Touffes de la gerbe lointaine (tous groupes).
func get_far_count() -> int:
	var n := 0
	for c in _far_count:
		n += c
	return n


## Vent apparent du cycliste (m/s, repère de Godot), sortie de wind_model.apparent().
func set_apparent_wind(apparent: Vector3) -> void:
	if _near_material == null:
		return
	var horiz := Vector3(apparent.x, 0.0, apparent.z)
	var speed := horiz.length()
	for m in [_near_material, _far_material]:
		m.set_shader_parameter("local_wind_dir", horiz / speed if speed > 1e-4 else Vector3.ZERO)
		m.set_shader_parameter("local_wind_strength", clampf(speed / APPARENT_MAX_MPS, 0.0, 1.0))


## Une fois par image : fenêtre de tronçons autour de la position `cam_s` le long de la route.
func update(cam_s: float) -> void:
	if _near_mm.is_empty() or route == null:
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
			_recycle(g)
			_queue.append([g, k, 0, PackedVector4Array()])
	var budget := MAX_PER_FRAME
	var t_start := Time.get_ticks_usec()
	var far_min_keep := keep_at(LOD_SWITCH_M - LOD_BLEND_M)
	while budget > 0 and not _queue.is_empty() and Time.get_ticks_usec() - t_start < MAX_FRAME_US:
		var job: Array = _queue[0]
		var g: int = job[0]
		var k: int = job[1]
		var j: int = job[2]
		var stations: PackedVector4Array = job[3]
		if stations.is_empty():
			stations = chunk_stations(k)
			job[3] = stations
			_start_box(g, stations)
			budget -= STATION_COST
		var end := mini(j + mini(maxi(budget, 1), BATCH), _per_chunk)
		var near_mm := _near_mm[g]
		var far_mm := _far_mm[g]
		var box := _aabb[g]
		for slot in range(j, end):
			var idx := g * _per_chunk + slot
			_placed[idx] = 0
			near_mm.set_instance_transform(slot, HIDDEN)
			var xf: Variant = tuft_transform(k, slot, stations)
			if xf == null:
				continue
			var x: Transform3D = xf
			var dry := dry_draw(k, slot, x.origin)
			if dry < 0:
				continue
			var col: Color = (DRY_TINTS if dry == 1 else TINTS)[tint_index(k, slot)]
			var pick := pick_of(k, slot)
			var custom := Color(pick, 0.0, 0.0, 0.0)
			near_mm.set_instance_transform(slot, x)
			near_mm.set_instance_color(slot, col)
			near_mm.set_instance_custom_data(slot, custom)
			if pick < far_min_keep:
				var f := _far_count[g]
				far_mm.set_instance_transform(f, x)
				far_mm.set_instance_color(f, col)
				far_mm.set_instance_custom_data(f, custom)
				_far_count[g] = f + 1
			box = box.expand(x.origin)
			_origins[idx] = x.origin
			_placed[idx] = 1
			_group_visible[g] += 1
			_visible_count += 1
		_filled[g] = end
		near_mm.visible_instance_count = end
		far_mm.visible_instance_count = _far_count[g]
		_set_box(g, box)
		budget -= end - j
		if end >= _per_chunk:
			_queue.pop_front()
		else:
			job[2] = end


## Le groupe `g` reçoit un autre tronçon : ses anciennes touffes ne sont plus dessinées ni comptées.
func _recycle(g: int) -> void:
	_visible_count -= _group_visible[g]
	_group_visible[g] = 0
	_filled[g] = 0
	_far_count[g] = 0
	_near_mm[g].visible_instance_count = 0
	_far_mm[g].visible_instance_count = 0
	_near_mmi[g].visible = false
	_far_mmi[g].visible = false


## Boîte de départ du tronçon : la route échantillonnée et le bord extérieur de la bande d'herbe des deux côtés.
func _start_box(g: int, stations: PackedVector4Array) -> void:
	var lat := road_half_width_m + BAND_MAX_M
	var box := AABB(Vector3(stations[0].x, stations[0].y, stations[0].z), Vector3.ZERO)
	for st in stations:
		var c := Vector3(st.x, st.y, st.z)
		var right := Vector3(cos(st.w), 0.0, sin(st.w)) * lat
		box = box.expand(c + right).expand(c - right)
	_set_box(g, box)
	_near_mmi[g].visible = true
	_far_mmi[g].visible = true


## Boîte du tronçon `g` (touffes comprises) et plages de visibilité des deux gerbes, mesurées au centre de la
## boîte : la gerbe complète n'est plus dessinée quand toutes les touffes du tronçon sont au-delà du passage,
## la simplifiée quand elles sont toutes en deçà ou au-delà du fondu.
func _set_box(g: int, box: AABB) -> void:
	_aabb[g] = box
	var grown := box.grow(AABB_MARGIN_M + TUFT_HEIGHT_M * 1.3)
	_near_mm[g].custom_aabb = grown
	_far_mm[g].custom_aabb = grown
	var radius := grown.size.length() * 0.5
	_near_mmi[g].visibility_range_end = LOD_SWITCH_M + LOD_BLEND_M + radius
	_far_mmi[g].visibility_range_begin = maxf(0.0, LOD_SWITCH_M - LOD_BLEND_M - radius)
	_far_mmi[g].visibility_range_end = FADE_END_M + radius


## Touffe du désert ? 0 : herbe d'avant ; 1 : herbe sèche ; −1 : place laissée vide (désert clairsemé).
func dry_draw(k: int, slot: int, origin: Vector3) -> int:
	if biome_model == null or not biome_model.active():
		return 0
	var w: Dictionary = biome_model.weights_at(origin.x, origin.z)
	var dry_w := 0.0
	for b in DRY_BIOMES:
		dry_w += float(w.get(b, 0.0))
	if dry_w <= 0.0:
		return 0
	var h := VegetationPlacer.hash3(tuft_seed ^ 0x5D17, k, slot)
	if float(h & 0xFFFF) / 65536.0 >= dry_w:
		return 0
	return 1 if float((h >> 16) & 0xFFFF) / 65536.0 < DRY_KEEP else -1


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
	st.w = lerp_angle(stations[i0].w, stations[i0 + 1].w, fi - i0)   # cap qui passe par le nord (359° → 1°)
	var right := Vector3(cos(st.w), 0.0, sin(st.w))
	var off := road_half_width_m + lat
	var px: float = st.x + right.x * off * side
	var pz: float = st.z + right.z * off * side
	if _road != null and not _road.is_clear(px, pz, road_half_width_m + ROAD_CLEAR_M):
		return null
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


## Gerbe lointaine (au-delà de LOD_SWITCH_M) : FAR_BLADES brins d'un seul triangle, deux fois plus larges que
## ceux de la gerbe complète, mêmes hauteur, penché et teintes (base à la teinte du sol, pointe plus claire).
## 15 sommets au lieu de 108 : à 40 m un brin de 3,5 cm fait moins d'un pixel.
static func build_far_tuft_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var base := Color(0.34, 0.47, 0.2)
	var tip := Color(0.52, 0.64, 0.29)
	var rng := RandomNumberGenerator.new()
	rng.seed = 0x6EA56
	for b in range(FAR_BLADES):
		var a := TAU * (float(b) + rng.randf() * 0.6) / FAR_BLADES
		var out := Vector3(cos(a), 0.0, sin(a))
		var side := Vector3(-out.z, 0.0, out.x)
		var root := out * TUFT_RADIUS_M * rng.randf_range(0.0, 0.7)
		var h := TUFT_HEIGHT_M * rng.randf_range(0.65, 1.0)
		var lean := rng.randf_range(0.15, 0.45) * h
		var w := FAR_BLADE_WIDTH_M * rng.randf_range(0.8, 1.2)
		var n := (Vector3.UP * 0.8 + out * 0.2).normalized()
		for v in [[root - side * w, base], [root + side * w, base], [root + out * lean + Vector3(0.0, h, 0.0), tip]]:
			st.set_color(v[1])
			st.set_normal(n)
			st.add_vertex(v[0])
	return st.commit()

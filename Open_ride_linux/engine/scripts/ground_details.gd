extends Node3D

## Détails de sol des biomes (lot U8, série U) : rochers épars, herbes hautes et termitières, posés le long
## de la route autour de la caméra. Les rides et dunes du sable sont dans terrain_biomes.gdshader.
## Pas de class_name : charger par preload("res://scripts/ground_details.gd"). Branché par living_world.gd.
## - Sans modèle de biome actif (`biome_model` nul) : rien n'est créé (rendu d'avant la série U).
## - Placement déterministe (graine, sorte, tronçon, place) sur une bande de `ROAD_CLEAR_M` à `BAND_M` (selon la sorte)
##   du bord de la route, des deux côtés ; tronçons de `CHUNK_M` mètres, `CHUNKS_BEHIND` derrière et
##   `CHUNKS_AHEAD` devant la caméra. Le biome d'une place est tiré selon les poids du modèle ; la sorte n'y
##   est gardée qu'avec la probabilité de DENSITY[sorte][biome].
## - Jamais à moins de `ROAD_CLEAR_M` du bord de la route (rayon de l'objet compris, toute la route est
##   vérifiée, pas seulement le tronçon : grille de la route), ni dans un bâtiment ou un plan d'eau
##   (`exclusions`, comme grass_tufts.gd).
## - Rochers : trois formes construites par code (`build_rock_mesh`), un MultiMesh par forme, teinte de la
##   roche du biome ou de la variante régionale de la tuile. Herbes hautes (savane, steppe) : gerbes de brins
##   comme les touffes de P5 mais hautes et dorées, balancées par le vent apparent (tree_sway.gdshader), effacées
##   avant 60 m. Termitières (savane) : rares.
## - Murets de pierre sèche (landes atlantiques, lot AT1) : tronçons de `WALL_PIECE_M` mis bout à bout le long de la
##   route, des deux côtés, alignés sur le cap ; leur écart au bord suit un bruit continu le long de la route
##   (`wall_offset`), avec des brèches tirées par place. Pierre de la roche du biome ou de la variante régionale.
## - Disposition : `scatter` (place tirée au hasard dans la bande, orientation au hasard) ou `row` (places en file le
##   long de la route, orientées selon le cap), selon LAYOUT.
## - Budgets : `living(preset)` de quality_presets.gd (`ground_rocks`, `ground_grass`, `ground_termites`,
##   `ground_walls`, lus par `budgets`), à zéro quand le décor vivant est coupé.

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const RenderDiag := preload("res://scripts/render_diag.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const BiomeIds := preload("res://scripts/biome_ids.gd")
const RoadClearance := preload("res://scripts/road_clearance.gd")

const CHUNK_M := 60.0
const CHUNKS_BEHIND := 1
const CHUNKS_AHEAD := 3
const ROAD_CLEAR_M := 3.0
## Largeur de la bande de chaque sorte de part et d'autre de la route (m) : termitières près de la route, pour être vues.
const BAND_M := {"rock": 60.0, "grass": 60.0, "termite": 30.0}
const MAX_PER_FRAME := 50           # places remplies par image : un tronçon de high en ~25 images (0,4 s)
const GRID_M := 25.0
const ROCK_SHAPES := 3
const KINDS: Array[String] = ["rock", "grass", "termite", "wall"]
## Clé du budget de chaque sorte dans `living(preset)` (quality_presets.gd).
const BUDGET_KEYS := {"rock": "ground_rocks", "grass": "ground_grass", "termite": "ground_termites", "wall": "ground_walls"}
## Disposition de chaque sorte : `scatter` (au hasard dans la bande) ou `row` (en file le long de la route).
const LAYOUT := {"rock": "scatter", "grass": "scatter", "termite": "scatter", "wall": "row"}
## Probabilité qu'une place d'une sorte soit remplie dans un biome (0 ou absent : jamais).
const DENSITY := {
	"rock": {"alpine": 0.9, "rock_desert": 1.0, "sand_desert": 0.5, "tundra": 0.5, "volcanic": 1.0, "atlantic_heath": 0.25, "high_plateau": 0.6, "reef": 0.7},
	"grass": {"savanna": 1.0, "steppe": 0.7, "high_plateau": 0.8},   # hauts plateaux (lot HP1) : touffes d'ichu près de la route
	"termite": {"savanna": 1.0},
	"wall": {"atlantic_heath": 0.85},
}
## Rayon au sol de l'objet à l'échelle 1 (m), pour la distance à la route.
const RADIUS_M := {"rock": 0.6, "grass": 0.3, "termite": 0.9, "wall": 0.4}
## Murets (lot AT1) : longueur d'un tronçon, places par côté et par tronçon de route, écart au bord de la route
## (entre WALL_OFFSET_M.x et .y, bruit continu de période WALL_OFFSET_PERIOD_M), hauteur hors sol.
const WALL_PIECE_M := 6.0
const WALL_PER_SIDE := int(CHUNK_M / WALL_PIECE_M)
const WALL_OFFSET_M := Vector2(1.5, 7.0)
const WALL_OFFSET_PERIOD_M := 120.0
const WALL_HEIGHT_M := 1.0
const WALL_FOOT_M := 0.4            # pierres sous le sol, pour les pentes en travers
const WALL_LIGHTEN := 0.35          # pierre des murets plus claire que les rochers (lichens, pierre lavée)
const GRASS_HEIGHT_M := 1.1
const GRASS_BLADES := 16
const GRASS_TINTS := [Color(1.0, 1.0, 1.0), Color(1.12, 1.05, 0.85), Color(0.86, 0.84, 0.7), Color(1.2, 1.1, 0.8)]
const GRASS_THIN_START_M := 30.0
const GRASS_FADE_END_M := 58.0
const TERMITE_COLOR := Color(0.62, 0.36, 0.24)
const APPARENT_MAX_MPS := 60.0 / 3.6
const NO_CHUNK := -(1 << 40)
static var HIDDEN := Transform3D(Basis().scaled(Vector3.ZERO), Vector3(0.0, -10000.0, 0.0))

var route = null
var biome_model = null
var road_half_width_m := 3.0
var detail_seed := 0
var exclusions: Array = []           # Array[PackedVector2Array] : bâtiments et plans d'eau (x, z)
var height_at: Callable = Callable() # (x, z) -> hauteur du terrain ; vide : hauteur de la route

## Une couche par MultiMesh : {kind, shape, mm, per_chunk}
var _layers: Array[Dictionary] = []
var _slot_chunk := PackedInt64Array()
var _queue: Array = []               # [groupe, tronçon, indice de couche, place suivante, stations]
var _grass_material: ShaderMaterial = null
var _road: RoadClearance = null      # distance à la route sur tout le parcours (road_clearance.gd)
var _placed := {}                    # couche -> PackedVector3Array des positions placées (tests)
var _rock_colors := {}


## Budgets {"rock", "grass", "termite"} (0 : rien), route, modèle de biome (nul : rien n'est créé).
func configure(budgets: Dictionary, route_data, model, road_width_m: float = 6.0, seed_value: int = 0) -> void:
	route = route_data
	biome_model = model
	road_half_width_m = road_width_m * 0.5
	detail_seed = seed_value
	for c in get_children():
		c.queue_free()
	_layers.clear()
	_queue.clear()
	_placed.clear()
	_rock_colors.clear()
	_road = null
	if route == null or biome_model == null:
		return
	var groups := CHUNKS_BEHIND + CHUNKS_AHEAD + 1
	_slot_chunk = PackedInt64Array()
	_slot_chunk.resize(groups)
	_slot_chunk.fill(NO_CHUNK)
	for kind in KINDS:
		var shapes := ROCK_SHAPES if kind == "rock" else 1
		var per_chunk := int(budgets.get(kind, 0)) / shapes / groups
		if LAYOUT[kind] == "row":
			per_chunk = mini(per_chunk, 2 * WALL_PER_SIDE)
		if per_chunk <= 0:
			continue
		for shape in range(shapes):
			var mm := MultiMesh.new()
			mm.transform_format = MultiMesh.TRANSFORM_3D
			mm.use_colors = true
			mm.mesh = _mesh_for(kind, shape)
			mm.instance_count = per_chunk * groups
			for i in range(mm.instance_count):
				mm.set_instance_transform(i, HIDDEN)
			var mmi := MultiMeshInstance3D.new()
			mmi.name = "%s_%d" % [kind, shape]
			mmi.multimesh = mm
			mmi.material_override = _material_for(kind)
			mmi.cast_shadow = (GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
				if kind == "grass" or RenderDiag.has("sans_ombres_details") else GeometryInstance3D.SHADOW_CASTING_SETTING_ON)
			add_child(mmi)
			var pos := PackedVector3Array()
			pos.resize(mm.instance_count)
			var on := PackedByteArray()
			on.resize(mm.instance_count)
			_layers.append({"kind": kind, "shape": shape, "mm": mm, "per_chunk": per_chunk, "pos": pos, "on": on})
	if not _layers.is_empty():
		_road = RoadClearance.new(route, GRID_M)


## Budgets de `configure` tirés des budgets du décor vivant `living(preset)` (quality_presets.gd).
static func budgets(living: Dictionary) -> Dictionary:
	var out := {}
	for kind in KINDS:
		out[kind] = int(living.get(BUDGET_KEYS[kind], 0))
	return out


func get_capacity(kind: String) -> int:
	var n := 0
	for l in _layers:
		if l["kind"] == kind:
			n += (l["mm"] as MultiMesh).instance_count
	return n


## Positions des objets placés d'une sorte.
func get_positions(kind: String) -> PackedVector3Array:
	var out := PackedVector3Array()
	for l in _layers:
		if l["kind"] != kind:
			continue
		var on: PackedByteArray = l["on"]
		var pos: PackedVector3Array = l["pos"]
		for i in range(on.size()):
			if on[i] == 1:
				out.append(pos[i])
	return out


## Vent apparent du cycliste (m/s), comme grass_tufts.gd.
func set_apparent_wind(apparent: Vector3) -> void:
	if _grass_material == null:
		return
	var horiz := Vector3(apparent.x, 0.0, apparent.z)
	var speed := horiz.length()
	_grass_material.set_shader_parameter("local_wind_dir", horiz / speed if speed > 1e-4 else Vector3.ZERO)
	_grass_material.set_shader_parameter("local_wind_strength", clampf(speed / APPARENT_MAX_MPS, 0.0, 1.0))


## Une fois par image : fenêtre de tronçons autour de `cam_s` ; au plus MAX_PER_FRAME places remplies.
func update(cam_s: float) -> void:
	if _layers.is_empty():
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
			_queue.append([g, k, 0, 0, PackedVector4Array()])
	var budget := MAX_PER_FRAME
	while budget > 0 and not _queue.is_empty():
		var job: Array = _queue[0]
		var g: int = job[0]
		var k: int = job[1]
		var li: int = job[2]
		var j: int = job[3]
		if (job[4] as PackedVector4Array).is_empty():
			job[4] = chunk_stations(k)
		var l: Dictionary = _layers[li]
		var per: int = l["per_chunk"]
		var end := mini(j + budget, per)
		var mm: MultiMesh = l["mm"]
		for slot in range(j, end):
			var idx := g * per + slot
			var d: Variant = detail_at(l["kind"], int(l["shape"]), k, slot, job[4])
			if d == null:
				mm.set_instance_transform(idx, HIDDEN)
				l["on"][idx] = 0
			else:
				mm.set_instance_transform(idx, d["xf"])
				mm.set_instance_color(idx, d["color"])
				l["pos"][idx] = (d["xf"] as Transform3D).origin
				l["on"][idx] = 1
		budget -= end - j
		if end >= per:
			if li + 1 < _layers.size():
				job[2] = li + 1
				job[3] = 0
			else:
				_queue.pop_front()
		else:
			job[3] = end


func is_settled() -> bool:
	return _queue.is_empty()


## Route échantillonnée tous les 5 m sur le tronçon `k` : (x, y, z, cap en radians).
func chunk_stations(k: int) -> PackedVector4Array:
	var out := PackedVector4Array()
	var n := int(CHUNK_M / 5.0)
	for i in range(n + 1):
		var smp: Dictionary = route.sample(float(k) * CHUNK_M + i * 5.0)
		out.append(Vector4(smp["x"], smp["y"], smp["z"], deg_to_rad(float(smp["heading_deg"]))))
	return out


## Objet de la place `slot` du tronçon `k` pour la sorte `kind` (forme `shape` des rochers) :
## {xf, color, biome} ou null (hors route, trop près de la route, exclu, pas dans ce biome).
func detail_at(kind: String, shape: int, k: int, slot: int, stations: PackedVector4Array = PackedVector4Array()) -> Variant:
	if LAYOUT[kind] == "row":
		return _row_at(kind, k, slot, stations)
	var salt := (KINDS.find(kind) + 1) * 0x1F3 + shape * 0x3B
	var h := VegetationPlacer.hash3(detail_seed ^ (0x5D17 + salt), k, slot)
	var h2 := VegetationPlacer.hash3(detail_seed ^ (0x2E83 + salt), k, slot)
	var u := float(h & 0xFFFF) / 65536.0
	var lat := float((h >> 16) & 0xFFFF) / 65536.0
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
	var scale_f := _scale(kind, h2)
	var radius: float = RADIUS_M[kind] * scale_f
	var clear := road_half_width_m + ROAD_CLEAR_M + radius
	var off := clear + lat * (float(BAND_M[kind]) - clear)
	var px: float = st.x + right.x * off * side
	var pz: float = st.z + right.z * off * side
	var biome := _pick_biome(px, pz, h2)
	var keep := float(DENSITY[kind].get(biome, 0.0))
	if float((h2 >> 8) & 0xFF) / 256.0 >= keep:
		return null
	if road_distance(px, pz) < clear:
		return null
	var p2 := Vector2(px, pz)
	for poly in exclusions:
		if Geometry2D.is_point_in_polygon(p2, poly):
			return null
	var py: float = float(height_at.call(px, pz)) if height_at.is_valid() else st.y
	var yaw := float((h2 >> 16) & 0xFFFF) / 65536.0 * TAU
	var basis := Basis(Vector3.UP, yaw)
	var color := Color.WHITE
	match kind:
		"rock":
			basis = basis * Basis(Vector3.RIGHT, (float((h >> 3) & 0xFF) / 255.0 - 0.5) * 0.5)
			py -= 0.05 * scale_f
			color = rock_color(biome, px, pz)
		"grass":
			color = GRASS_TINTS[(h >> 5) & 3]
		"termite":
			color = TERMITE_COLOR
	return {"xf": Transform3D(basis.scaled(Vector3.ONE * scale_f), Vector3(px, py, pz)), "color": color, "biome": biome}


## Place `slot` d'une sorte en file (murets) sur le tronçon `k` : côté `slot % 2`, tronçon de mur `slot / 2`,
## aligné sur le cap, penché selon la pente le long de la route ; null dans une brèche, hors du biome, trop près
## de la route (aux deux bouts) ou dans une exclusion.
func _row_at(kind: String, k: int, slot: int, stations: PackedVector4Array) -> Variant:
	var side := 1.0 if slot % 2 == 0 else -1.0
	var piece := slot / 2
	var s_mid := float(k) * CHUNK_M + (float(piece) + 0.5) * WALL_PIECE_M
	if not route.is_loop() and (s_mid - WALL_PIECE_M * 0.5 < 0.0 or s_mid + WALL_PIECE_M * 0.5 > route.length_m):
		return null
	if stations.is_empty():
		stations = chunk_stations(k)
	var salt := (KINDS.find(kind) + 1) * 0x1F3
	var h := VegetationPlacer.hash3(detail_seed ^ (0x5D17 + salt), k, slot)
	var fi := (s_mid - float(k) * CHUNK_M) / 5.0
	var i0 := mini(int(fi), stations.size() - 2)
	var st := stations[i0].lerp(stations[i0 + 1], fi - i0)
	st.w = lerp_angle(stations[i0].w, stations[i0 + 1].w, fi - i0)
	var right := Vector3(cos(st.w), 0.0, sin(st.w))
	var along := Vector3(sin(st.w), 0.0, -cos(st.w))
	var off: float = road_half_width_m + ROAD_CLEAR_M + RADIUS_M[kind] + wall_offset(s_mid, side)
	var c: Vector3 = Vector3(st.x, 0.0, st.z) + right * off * side
	var biome := _pick_biome(c.x, c.z, h)
	if float((h >> 8) & 0xFF) / 256.0 >= float(DENSITY[kind].get(biome, 0.0)):
		return null
	var a: Vector3 = c - along * WALL_PIECE_M * 0.5
	var b: Vector3 = c + along * WALL_PIECE_M * 0.5
	var clear: float = road_half_width_m + ROAD_CLEAR_M + RADIUS_M[kind]
	for p in [a, c, b]:
		if road_distance(p.x, p.z) < clear:
			return null
		for poly in exclusions:
			if Geometry2D.is_point_in_polygon(Vector2(p.x, p.z), poly):
				return null
	var ya: float = float(height_at.call(a.x, a.z)) if height_at.is_valid() else st.y
	var yb: float = float(height_at.call(b.x, b.z)) if height_at.is_valid() else st.y
	var yc: float = float(height_at.call(c.x, c.z)) if height_at.is_valid() else st.y
	var basis := Basis(Vector3.UP, PI * 0.5 - st.w) * Basis(Vector3.BACK, atan2(yb - ya, WALL_PIECE_M))
	var y := minf(yc, (ya + yb) * 0.5) - 0.05
	return {"xf": Transform3D(basis, Vector3(c.x, y, c.z)), "color": rock_color(biome, c.x, c.z).lightened(WALL_LIGHTEN), "biome": biome}


## Écart du muret au-delà du dégagement de la route (m) au point `s` du côté `side` : bruit de valeur continu le long
## de la route (nœuds tous les WALL_OFFSET_PERIOD_M), entre WALL_OFFSET_M.x et WALL_OFFSET_M.y.
func wall_offset(s: float, side: float) -> float:
	var t := s / WALL_OFFSET_PERIOD_M
	var n := int(floor(t))
	var f := t - n
	var salt := 0x3A11 if side > 0.0 else 0x7C29
	var v0 := float(VegetationPlacer.hash3(detail_seed ^ salt, n, 0) & 0xFFFF) / 65535.0
	var v1 := float(VegetationPlacer.hash3(detail_seed ^ salt, n + 1, 0) & 0xFFFF) / 65535.0
	f = f * f * (3.0 - 2.0 * f)
	return lerpf(WALL_OFFSET_M.x, WALL_OFFSET_M.y, lerpf(v0, v1, f))


## Échelle d'un objet : rochers surtout petits (0,4 à 2), herbes 0,8 à 1,3, termitières 1 à 2 (1,6 à 3,2 m de haut).
static func _scale(kind: String, h2: int) -> float:
	var r := float((h2 >> 24) & 0x7F) / 127.0
	match kind:
		"rock":
			return 0.4 + 1.6 * r * r
		"grass":
			return 0.8 + 0.5 * r
	return 1.0 + 1.0 * r


func _pick_biome(x: float, z: float, h2: int) -> String:
	var w: Dictionary = biome_model.weights_at(x, z)
	var r := float((h2 >> 1) & 0x7F) / 128.0
	var acc := 0.0
	var last := ""
	for b in w.keys():
		acc += float(w[b])
		last = b
		if r < acc:
			return b
	return last


## Teinte des rochers : roche de la variante régionale de la tuile, sinon couche de pente du biome.
func rock_color(biome: String, x: float, z: float) -> Color:
	var variant = null
	if biome_model.layer.present:
		var t: Dictionary = biome_model.layer.tile("near", floori(x / 1000.0), floori(z / 1000.0))
		variant = t.get("variant", null)
	var key := "%s|%s" % [biome, str(variant)]
	if not _rock_colors.has(key):
		var p: Dictionary = biome_model.params(biome, "", 0.0, variant)
		var c: Color = p["terrain"]["rock_color"]
		var v: Dictionary = p["variant"].get("ground", {})
		var hex = v.get("values", {}).get("rock_color", null) if typeof(v.get("values", null)) == TYPE_DICTIONARY else null
		if typeof(hex) == TYPE_STRING and Color.html_is_valid(hex):
			c = Color.html(hex)
		_rock_colors[key] = c.darkened(0.12)
	return _rock_colors[key]


## Distance horizontale du point à l'axe de la route, exacte jusqu'à GRID_M (au-delà : INF ou plus),
## toute la route comprise (road_clearance.gd).
func road_distance(x: float, z: float) -> float:
	return INF if _road == null else _road.distance(x, z)


func _mesh_for(kind: String, shape: int) -> Mesh:
	match kind:
		"rock":
			return build_rock_mesh(shape)
		"grass":
			return build_grass_mesh()
		"wall":
			return build_wall_mesh()
	return build_termite_mesh()


func _material_for(kind: String) -> Material:
	if kind == "grass":
		if _grass_material == null:
			_grass_material = TreeRenderer.sway_material(true)
			_grass_material.set_shader_parameter("use_local_wind", true)
			_grass_material.set_shader_parameter("sway_height_m", GRASS_HEIGHT_M)
			_grass_material.set_shader_parameter("sway_amplitude_m", 0.18)
			_grass_material.set_shader_parameter("sway_frequency_hz", 0.7)
			_grass_material.set_shader_parameter("thin_start_m", GRASS_THIN_START_M)
			_grass_material.set_shader_parameter("fade_end_m", GRASS_FADE_END_M)
			_grass_material.set_shader_parameter("normals_up_both_sides", true)
			_grass_material.set_shader_parameter("root_darken", clampf(RenderDiag.number("herbe_degrade", 0.0), 0.0, 1.0))
			_grass_material.set_shader_parameter("grass", true)   # herbe jaunie selon la saison (lot P18)
		return _grass_material
	var m := StandardMaterial3D.new()
	m.vertex_color_use_as_albedo = true
	m.vertex_color_is_srgb = true   # couleurs de sommet sRGB (couleur_srgb.gdshaderinc)
	m.roughness = 0.95
	return m


## Rocher : icosaèdre subdivisé une fois (80 faces), sommets déplacés selon la forme, aplati, faces planes.
static func build_rock_mesh(shape: int) -> ArrayMesh:
	var t := (1.0 + sqrt(5.0)) / 2.0
	var verts: Array[Vector3] = [Vector3(-1, t, 0), Vector3(1, t, 0), Vector3(-1, -t, 0), Vector3(1, -t, 0),
		Vector3(0, -1, t), Vector3(0, 1, t), Vector3(0, -1, -t), Vector3(0, 1, -t),
		Vector3(t, 0, -1), Vector3(t, 0, 1), Vector3(-t, 0, -1), Vector3(-t, 0, 1)]
	var faces := [[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11], [1, 5, 9], [5, 11, 4], [11, 10, 2],
		[10, 7, 6], [7, 1, 8], [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9], [4, 9, 5], [2, 4, 11],
		[6, 2, 10], [8, 6, 7], [9, 8, 1]]
	var mid := {}
	var sub := []
	for f in faces:
		var m := []
		for e in [[f[0], f[1]], [f[1], f[2]], [f[2], f[0]]]:
			var key := Vector2i(mini(e[0], e[1]), maxi(e[0], e[1]))
			if not mid.has(key):
				mid[key] = verts.size()
				verts.append((verts[e[0]] + verts[e[1]]) * 0.5)
			m.append(mid[key])
		sub.append_array([[f[0], m[0], m[2]], [f[1], m[1], m[0]], [f[2], m[2], m[1]], [m[0], m[1], m[2]]])
	var rng := RandomNumberGenerator.new()
	rng.seed = 0x40C + shape * 977
	var squash: float = [0.55, 0.7, 0.45][shape % 3]
	var stretch: float = [1.0, 1.25, 1.5][shape % 3]
	for i in range(verts.size()):
		var v := verts[i].normalized() * rng.randf_range(0.78, 1.12)
		verts[i] = Vector3(v.x * stretch, maxf(v.y, -0.35) * squash, v.z) * 0.5
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for f in sub:
		var a: Vector3 = verts[f[0]]
		var b: Vector3 = verts[f[1]]
		var c: Vector3 = verts[f[2]]
		var shade := 0.85 + 0.15 * clampf((b - a).cross(c - a).normalized().y, 0.0, 1.0)
		_add_face(st, a, b, c, a + b + c, Color(shade, shade, shade))
	return st.commit()


## Face plane tournée vers `outward` : normale sortante, sommets dans l'ordre des faces avant de Godot.
static func _add_face(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, outward: Vector3, color: Color) -> void:
	var n := (b - a).cross(c - a).normalized()
	if n.dot(outward) < 0.0:
		n = -n
		var t := b
		b = c
		c = t
	for p in [a, c, b]:
		st.set_color(color)
		st.set_normal(n)
		st.add_vertex(p)


## Herbes hautes : gerbe de GRASS_BLADES brins effilés de GRASS_HEIGHT_M, base sombre, pointe dorée
## (même construction que grass_tufts.build_tuft_mesh, plus haute et plus large).
static func build_grass_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var base := Color(0.42, 0.38, 0.2)
	var mid := Color(0.66, 0.58, 0.3)
	var tip := Color(0.86, 0.76, 0.46)
	var rng := RandomNumberGenerator.new()
	rng.seed = 0x6A55E
	for b in range(GRASS_BLADES):
		var a := TAU * (float(b) + rng.randf() * 0.6) / GRASS_BLADES
		var out := Vector3(cos(a), 0.0, sin(a))
		var side := Vector3(-out.z, 0.0, out.x)
		var root := out * 0.25 * rng.randf_range(0.0, 0.8)
		var h := GRASS_HEIGHT_M * rng.randf_range(0.6, 1.0)
		var lean := rng.randf_range(0.2, 0.5) * h
		var w := 0.03 * rng.randf_range(0.8, 1.2)
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


## Muret de pierre sèche (lot AT1) : tronçon de WALL_PIECE_M selon x, centré, en deux assises de pierres de
## longueurs et de hauteurs inégales sur un talus trapézoïdal (0,8 m de large au pied, 0,5 m en haut), pied
## enterré de WALL_FOOT_M, pierres de couronnement posées de chant ; teintes de gris par pierre (la couleur
## d'instance donne la roche). Moins de 500 triangles.
static func build_wall_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var rng := RandomNumberGenerator.new()
	rng.seed = 0x3D11E7
	var half := WALL_PIECE_M * 0.5
	# Talus : corps du mur, de -WALL_FOOT_M à 0,75 m
	var body_top := WALL_HEIGHT_M * 0.75
	_add_box(st, Vector3(-half, -WALL_FOOT_M, -0.4), Vector3(half, 0.0, 0.4), Color(0.7, 0.7, 0.7))
	_add_slab(st, -half, half, 0.0, body_top, 0.4, 0.25, Color(0.62, 0.61, 0.58))
	# Pierres saillantes des deux faces, deux assises
	for face in [-1.0, 1.0]:
		for course in range(2):
			var x := -half
			var y0 := 0.05 + course * 0.33
			while x < half - 0.2:
				var l := minf(rng.randf_range(0.5, 1.0), half - x)
				var hh := rng.randf_range(0.16, 0.34)
				var yj := y0 + rng.randf_range(-0.05, 0.05)
				var z_out: float = (0.4 - 0.15 * (yj + hh * 0.5) / body_top) * face + rng.randf_range(-0.02, 0.05) * face
				# Pierres de gris inégaux, un peu chaudes ou froides, quelques-unes tachées de lichen clair
				var g := rng.randf_range(0.95, 1.35)
				var warm := rng.randf_range(-0.06, 0.06)
				var col := Color(g * (1.0 + warm), g, g * (1.0 - warm))
				if rng.randf() < 0.15:
					col = Color(g * 1.15, g * 1.18, g * 0.95)
				var z0: float = z_out - face * 0.08
				_add_box(st, Vector3(x + 0.03, yj, minf(z0, z_out)), Vector3(x + l - 0.03, yj + hh, maxf(z0, z_out)), col, 1 if face > 0.0 else 3)
				x += l
	# Couronnement : pierres de chant serrées
	var xc := -half
	while xc < half - 0.1:
		var w := minf(rng.randf_range(0.25, 0.45), half - xc)
		var top := body_top + rng.randf_range(0.18, WALL_HEIGHT_M - body_top)
		var g := rng.randf_range(0.9, 1.25)
		var tilt := rng.randf_range(-0.06, 0.06)
		_add_box(st, Vector3(xc + 0.02 + tilt, body_top - 0.02, -0.22), Vector3(xc + w - 0.02 + tilt, top, 0.22), Color(g, g, g))
		xc += w
	return st.commit()


## Pavé aligné sur les axes de `a` à `b` (dessus et quatre côtés, pas de dessous) : 10 triangles ; `hidden` : indice
## (1 à 4) d'un côté caché à ne pas dessiner (côté collé au mur des pierres saillantes), 8 triangles.
static func _add_box(st: SurfaceTool, a: Vector3, b: Vector3, color: Color, hidden: int = -1) -> void:
	var c := (a + b) * 0.5
	var p := [Vector3(a.x, a.y, a.z), Vector3(b.x, a.y, a.z), Vector3(b.x, a.y, b.z), Vector3(a.x, a.y, b.z),
		Vector3(a.x, b.y, a.z), Vector3(b.x, b.y, a.z), Vector3(b.x, b.y, b.z), Vector3(a.x, b.y, b.z)]
	var quads := [[4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
	for qi in range(quads.size()):
		if qi == hidden:
			continue
		var q: Array = quads[qi]
		var shade := 1.0 if qi == 0 else 0.9
		var col := Color(color.r * shade, color.g * shade, color.b * shade)
		_add_face(st, p[q[0]], p[q[1]], p[q[2]], (p[q[0]] + p[q[2]]) * 0.5 - c, col)
		_add_face(st, p[q[0]], p[q[2]], p[q[3]], (p[q[0]] + p[q[2]]) * 0.5 - c, col)


## Talus trapézoïdal de x0 à x1 : demi-largeur `w0` en y0, `w1` en y1 (deux faces inclinées, deux bouts, dessus).
static func _add_slab(st: SurfaceTool, x0: float, x1: float, y0: float, y1: float, w0: float, w1: float, color: Color) -> void:
	var c := Vector3((x0 + x1) * 0.5, (y0 + y1) * 0.5, 0.0)
	var p := [Vector3(x0, y0, -w0), Vector3(x1, y0, -w0), Vector3(x1, y0, w0), Vector3(x0, y0, w0),
		Vector3(x0, y1, -w1), Vector3(x1, y1, -w1), Vector3(x1, y1, w1), Vector3(x0, y1, w1)]
	for q in [[4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]:
		_add_face(st, p[q[0]], p[q[1]], p[q[2]], (p[q[0]] + p[q[2]]) * 0.5 - c, color)
		_add_face(st, p[q[0]], p[q[2]], p[q[3]], (p[q[0]] + p[q[2]]) * 0.5 - c, color)


## Termitière : cône bosselé de 1,6 m à 8 côtés et deux cheminées plus fines.
static func build_termite_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for spire in [[Vector3.ZERO, 0.75, 1.6], [Vector3(0.35, 0.0, 0.15), 0.3, 1.0], [Vector3(-0.3, 0.0, -0.25), 0.25, 0.8]]:
		var c: Vector3 = spire[0]
		var r0: float = spire[1]
		var hh: float = spire[2]
		var rings := [[0.0, r0], [hh * 0.35, r0 * 0.75], [hh * 0.7, r0 * 0.45], [hh, r0 * 0.12]]
		for ri in range(rings.size() - 1):
			for s in range(8):
				var a0 := TAU * s / 8.0
				var a1 := TAU * (s + 1) / 8.0
				var bump0 := 1.0 + 0.12 * sin(a0 * 3.0 + ri)
				var bump1 := 1.0 + 0.12 * sin(a1 * 3.0 + ri)
				var q00 := c + Vector3(cos(a0) * rings[ri][1] * bump0, rings[ri][0], sin(a0) * rings[ri][1] * bump0)
				var q01 := c + Vector3(cos(a1) * rings[ri][1] * bump1, rings[ri][0], sin(a1) * rings[ri][1] * bump1)
				var q10 := c + Vector3(cos(a0) * rings[ri + 1][1] * bump0, rings[ri + 1][0], sin(a0) * rings[ri + 1][1] * bump0)
				var q11 := c + Vector3(cos(a1) * rings[ri + 1][1] * bump1, rings[ri + 1][0], sin(a1) * rings[ri + 1][1] * bump1)
				var out := Vector3(cos((a0 + a1) * 0.5), 0.5, sin((a0 + a1) * 0.5))
				_add_face(st, q00, q11, q01, out, Color.WHITE)
				_add_face(st, q00, q10, q11, out, Color.WHITE)
	return st.commit()

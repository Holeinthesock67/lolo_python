extends Node3D

## Détails de sol des biomes (lot U8, série U) : rochers épars, herbes hautes et termitières, posés le long
## de la route autour de la caméra. Les rides et dunes du sable sont dans terrain_biomes.gdshader.
## Pas de class_name : charger par preload("res://scripts/ground_details.gd"). Branché par living_world.gd.
## - Sans modèle de biome actif (`biome_model` nul) : rien n'est créé (rendu d'avant la série U).
## - Placement déterministe (graine, sorte, tronçon, place) sur une bande de `ROAD_CLEAR_M` à `BAND_MAX_M`
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
## - Budgets : `living(preset)` de quality_presets.gd (`ground_rocks`, `ground_grass`, `ground_termites`),
##   à zéro quand le décor vivant est coupé.

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const BiomeIds := preload("res://scripts/biome_ids.gd")

const CHUNK_M := 60.0
const CHUNKS_BEHIND := 1
const CHUNKS_AHEAD := 3
const ROAD_CLEAR_M := 3.0
const BAND_MAX_M := 60.0
const MAX_PER_FRAME := 50           # places remplies par image : un tronçon de high en ~25 images (0,4 s)
const GRID_M := 25.0
const ROCK_SHAPES := 3
const KINDS: Array[String] = ["rock", "grass", "termite"]
## Probabilité qu'une place d'une sorte soit remplie dans un biome (0 ou absent : jamais).
const DENSITY := {
	"rock": {"alpine": 0.9, "rock_desert": 1.0, "tundra": 0.5, "volcanic": 1.0},
	"grass": {"savanna": 1.0, "steppe": 0.7},
	"termite": {"savanna": 1.0},
}
## Rayon au sol de l'objet à l'échelle 1 (m), pour la distance à la route.
const RADIUS_M := {"rock": 0.6, "grass": 0.3, "termite": 0.9}
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
var _grid := {}                      # Vector2i -> PackedInt32Array (indices des points de la route)
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
	_grid.clear()
	if route == null or biome_model == null:
		return
	var groups := CHUNKS_BEHIND + CHUNKS_AHEAD + 1
	_slot_chunk = PackedInt64Array()
	_slot_chunk.resize(groups)
	_slot_chunk.fill(NO_CHUNK)
	for kind in KINDS:
		var shapes := ROCK_SHAPES if kind == "rock" else 1
		var per_chunk := int(budgets.get(kind, 0)) / shapes / groups
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
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if kind == "grass" else GeometryInstance3D.SHADOW_CASTING_SETTING_ON
			add_child(mmi)
			var pos := PackedVector3Array()
			pos.resize(mm.instance_count)
			var on := PackedByteArray()
			on.resize(mm.instance_count)
			_layers.append({"kind": kind, "shape": shape, "mm": mm, "per_chunk": per_chunk, "pos": pos, "on": on})
	if not _layers.is_empty():
		_build_grid()


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
	var right := Vector3(cos(st.w), 0.0, sin(st.w))
	var scale_f := _scale(kind, h2)
	var radius: float = RADIUS_M[kind] * scale_f
	var clear := road_half_width_m + ROAD_CLEAR_M + radius
	var off := clear + lat * (BAND_MAX_M - clear)
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


## Échelle d'un objet : rochers surtout petits (0,4 à 2), herbes 0,8 à 1,3, termitières 0,8 à 1,6.
static func _scale(kind: String, h2: int) -> float:
	var r := float((h2 >> 24) & 0x7F) / 127.0
	match kind:
		"rock":
			return 0.4 + 1.6 * r * r
		"grass":
			return 0.8 + 0.5 * r
	return 0.8 + 0.8 * r


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


## Distance horizontale du point à l'axe de la route, exacte jusqu'à GRID_M − ds (au-delà : INF ou plus).
## Un segment à moins de cette distance a un bout dans la case du point ou une case voisine.
func road_distance(x: float, z: float) -> float:
	var c := Vector2i(floori(x / GRID_M), floori(z / GRID_M))
	var best := INF
	var p := Vector2(x, z)
	for dz in range(-1, 2):
		for dx in range(-1, 2):
			var ids: PackedInt32Array = _grid.get(c + Vector2i(dx, dz), PackedInt32Array())
			for i in ids:
				if i + 1 >= route.n:
					continue
				var a := Vector2(route.x[i], route.z[i])
				var b := Vector2(route.x[i + 1], route.z[i + 1])
				best = minf(best, p.distance_to(Geometry2D.get_closest_point_to_segment(p, a, b)))
	return best


## Grille des segments de la route (cases de GRID_M) : chaque segment est rangé dans les cases de ses deux bouts.
func _build_grid() -> void:
	for i in range(route.n):
		var c := Vector2i(floori(route.x[i] / GRID_M), floori(route.z[i] / GRID_M))
		var ids: PackedInt32Array = _grid.get(c, PackedInt32Array())
		ids.append(i)
		if i > 0:
			ids.append(i - 1)
		_grid[c] = ids


func _mesh_for(kind: String, shape: int) -> Mesh:
	match kind:
		"rock":
			return build_rock_mesh(shape)
		"grass":
			return build_grass_mesh()
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
		return _grass_material
	var m := StandardMaterial3D.new()
	m.vertex_color_use_as_albedo = true
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

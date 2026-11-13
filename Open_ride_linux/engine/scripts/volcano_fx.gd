extends Node3D

## Feu des paysages volcaniques actifs (démo « Volcan en flammes », demande du 13 novembre : « parcours démo
## exagéré feu et flammes dans un parcours volcanique »). Pas de class_name : charger par
## preload("res://scripts/volcano_fx.gd"). Branché par living_world.gd, comme ground_details.gd.
##
## Une seule règle : une tuile dont le paysage (`variant.landscape`, lot U25) porte une section `fire` dans le
## thème (`landscapes.<paysage>.fire`) est en feu ; aujourd'hui seul `volcan_actif` en a une. N'importe quel
## parcours de ce paysage s'affiche donc de la même façon, la démo n'a rien de particulier.
##
## - Coulées de lave (rubans le long de la route, à distance), lacs de lave (dont les plus grands crachent des
##   gerbes) et évents (panaches de fumée) : placement déterministe (graine, tronçon, place) par tronçon de
##   `CHUNK_M` mètres, `CHUNKS_BEHIND` derrière et `CHUNKS_AHEAD` devant la caméra. Jamais à moins de
##   `ROAD_CLEAR_M` de l'axe de la route, sur TOUT le parcours (road_clearance.gd : épingles, boucles), largeur ou
##   rayon compris. Les rubans et les lacs épousent le terrain (`height_at`).
## - Lave : un maillage par tronçon (un appel de dessin), shader lava.gdshader partagé (croûte, fissures, courant).
## - Braises : un GPUParticles3D autour de la caméra quand elle est en feu ; panaches, gerbes et lumières
##   orange : réserves de nœuds posées sur les évents et les lacs les plus proches (toutes les `PICK_PERIOD_S`).
## - `fire_level` (0 à 1, lissé) et `glow_color` : lus par main.gd pour teinter brume et lumière
##   (atmosphere_view.gd `set_fire`).
## - Budgets : `living(preset)` de quality_presets.gd (`volcano_embers`, `volcano_plumes`, `volcano_fountains`,
##   `volcano_lights`) ; la lave elle-même reste à toutes les qualités (shader seul).

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const RoadClearance := preload("res://scripts/road_clearance.gd")
const LavaShader := preload("res://shaders/lava.gdshader")

const CHUNK_M := 100.0
const CHUNKS_BEHIND := 3
const CHUNKS_AHEAD := 14
const ROAD_CLEAR_M := 14.0        # bord de la lave ou d'un évent à au moins 14 m de l'axe de la route
const GRID_M := 25.0
const STEP_M := 5.0               # pas des rubans de coulée
const LIFT_M := 0.5               # lave posée au-dessus du terrain (le shader la rapproche encore de la caméra)
const MAX_BUILD_PER_FRAME := 2
const PICK_PERIOD_S := 0.5
const FIRE_RATE := 0.5            # montée et descente de `fire_level` par seconde
const FOUNTAIN_RADIUS_M := 14.0   # lac à partir duquel il crache des gerbes
const BUDGET_KEYS := {"embers": "volcano_embers", "plumes": "volcano_plumes", "fountains": "volcano_fountains",
	"lights": "volcano_lights"}
const NO_CHUNK := -9223372036854775807

var route = null
var biome_model = null
var height_at := Callable()
var fx_seed := 0
var fire_level := 0.0
var glow_color := Color("#ff6a20")
var budgets := {"embers": 0, "plumes": 0, "fountains": 0, "lights": 0}

var _road: RoadClearance = null
var _slot_chunk := PackedInt64Array()
var _chunk_nodes: Array = []          # MeshInstance3D par emplacement (null : rien)
var _chunk_feats: Array = []          # éléments du tronçon par emplacement
var _queue: Array = []                # [emplacement, tronçon] à construire
var _lava_mat: ShaderMaterial = null
var _embers: GPUParticles3D = null
var _plumes: Array = []
var _fountains: Array = []
var _lights: Array = []
var _pick_at := -INF
var _clock := 0.0


## Budgets {"embers", "plumes", "fountains", "lights"} (budgets(living)), route, modèle de biome (nul : rien).
func configure(p_budgets: Dictionary, route_data, model, seed_value: int = 0) -> void:
	route = route_data
	biome_model = model
	fx_seed = seed_value
	for k in BUDGET_KEYS:
		budgets[k] = maxi(int(p_budgets.get(k, 0)), 0)
	for c in get_children():
		c.queue_free()
		remove_child(c)
	_plumes.clear()
	_fountains.clear()
	_lights.clear()
	_embers = null
	_queue.clear()
	_chunk_nodes.clear()
	_chunk_feats.clear()
	_road = null
	fire_level = 0.0
	_pick_at = -INF
	if route == null or biome_model == null or not _has_fire_theme():
		_slot_chunk = PackedInt64Array()
		return
	_road = RoadClearance.new(route, GRID_M)
	var groups := CHUNKS_BEHIND + CHUNKS_AHEAD + 1
	_slot_chunk.resize(groups)
	_slot_chunk.fill(NO_CHUNK)
	for i in range(groups):
		_chunk_nodes.append(null)
		_chunk_feats.append([])
	var fire := _first_fire()
	glow_color = Color(str(fire["glow"]))
	_lava_mat = ShaderMaterial.new()
	_lava_mat.shader = LavaShader
	_lava_mat.set_shader_parameter("lava_color", Color(str(fire["lava"])))
	_lava_mat.set_shader_parameter("lava_hot", Color(str(fire["lava_hot"])))
	_lava_mat.set_shader_parameter("crust_color", Color(str(fire["crust"])))
	if budgets["embers"] > 0:
		_embers = _make_embers(budgets["embers"], glow_color)
		add_child(_embers)
	for i in range(budgets["plumes"]):
		var p := _make_plume(Color(str(fire["smoke"])), glow_color)
		_plumes.append(p)
		add_child(p)
	for i in range(budgets["fountains"]):
		var f := _make_fountain(Color(str(fire["lava_hot"])), Color(str(fire["lava"])))
		_fountains.append(f)
		add_child(f)
	for i in range(budgets["lights"]):
		var l := OmniLight3D.new()
		l.name = "LueurLave%d" % i
		l.light_color = glow_color
		l.light_energy = 4.0
		l.omni_range = 45.0
		l.omni_attenuation = 1.2
		l.shadow_enabled = false
		l.visible = false
		_lights.append(l)
		add_child(l)


## Budgets de `configure` tirés du décor vivant `living(preset)` (quality_presets.gd).
static func budgets_of(living: Dictionary) -> Dictionary:
	var out := {}
	for k in BUDGET_KEYS:
		out[k] = int(living.get(BUDGET_KEYS[k], 0))
	return out


func active() -> bool:
	return not _slot_chunk.is_empty()


## Feu de la tuile qui contient (x, z) (biome_model.gd `fire_at`, complété par ses valeurs par défaut) ; {} hors feu.
func fire_at(x: float, z: float) -> Dictionary:
	return {} if biome_model == null else biome_model.fire_at(x, z)


func _has_fire_theme() -> bool:
	return not _first_fire().is_empty()


func _first_fire() -> Dictionary:
	return {} if biome_model == null else biome_model.any_fire()


## Distance à l'axe de la route sur tout le parcours (INF sans route).
func road_distance(x: float, z: float) -> float:
	return INF if _road == null else _road.distance(x, z)


## Éléments du tronçon `k` : [{"kind": "flow", "points": PackedVector2Array, "width": float}, {"kind": "pool",
## "center": Vector2, "radius": float}, {"kind": "vent", "center": Vector2}] ; vide hors feu ou hors route.
func features_of_chunk(k: int) -> Array:
	var out := []
	if route == null or _road == null:
		return out
	var s0 := float(k) * CHUNK_M
	if not route.is_loop() and (s0 < 0.0 or s0 + CHUNK_M > route.length_m):
		return out
	var mid: Dictionary = route.sample(s0 + CHUNK_M * 0.5)
	var fire := fire_at(float(mid["x"]), float(mid["z"]))
	if fire.is_empty():
		return out
	var density := clampf(float(fire.get("density", 1.0)), 0.0, 2.0)
	for side_i in range(2):
		var h := VegetationPlacer.hash3(fx_seed ^ 0x7A11, k, side_i)
		if float(h & 0xFF) / 256.0 < 0.55 * density:
			var flow := _flow(k, side_i, h)
			if not flow.is_empty():
				out.append(flow)
	for slot in range(3):
		var h := VegetationPlacer.hash3(fx_seed ^ 0x3E21, k, slot)
		if float(h & 0xFF) / 256.0 < 0.25 * density:
			var r := 6.0 + float((h >> 8) & 0xFF) / 255.0 * 20.0
			var c := _offset_point(s0 + float((h >> 16) & 0xFF) / 255.0 * CHUNK_M, (1.0 if h & 0x1000000 == 0 else -1.0),
				ROAD_CLEAR_M + r + 6.0 + float((h >> 25) & 0x7F) / 127.0 * 130.0)
			if road_distance(c.x, c.y) >= ROAD_CLEAR_M + r * 1.15 and not fire_at(c.x, c.y).is_empty():
				out.append({"kind": "pool", "center": c, "radius": r})
	for slot in range(2):
		var h := VegetationPlacer.hash3(fx_seed ^ 0x51C3, k, slot)
		if float(h & 0xFF) / 256.0 < 0.3 * density:
			var c := _offset_point(s0 + float((h >> 8) & 0xFF) / 255.0 * CHUNK_M, (1.0 if h & 0x10000 == 0 else -1.0),
				ROAD_CLEAR_M + 16.0 + float((h >> 17) & 0xFF) / 255.0 * 200.0)
			if road_distance(c.x, c.y) >= ROAD_CLEAR_M + 4.0 and not fire_at(c.x, c.y).is_empty():
				out.append({"kind": "vent", "center": c})
	return out


## Coulée du côté `side_i` du tronçon `k` : ruban à peu près parallèle à la route, coupé là où il passerait trop
## près d'une portion de la route (le plus long morceau est gardé).
func _flow(k: int, side_i: int, h: int) -> Dictionary:
	var side := 1.0 if side_i == 0 else -1.0
	var width := 8.0 + float((h >> 8) & 0xFF) / 255.0 * 16.0
	var off0 := ROAD_CLEAR_M + width * 0.5 + 10.0 + float((h >> 16) & 0xFF) / 255.0 * 60.0
	var len_m := 70.0 + float((h >> 24) & 0x3F) / 63.0 * 30.0
	var start := float(k) * CHUNK_M + (CHUNK_M - len_m) * float((h >> 4) & 0xF) / 15.0
	var phase := float((h >> 12) & 0xF)
	var best := PackedVector2Array()
	var cur := PackedVector2Array()
	var u := 0.0
	while u <= len_m + 0.01:
		var off := off0 + 7.0 * sin(u / 23.0 + phase) + 3.0 * sin(u / 9.0 + phase * 2.0)
		var p := _offset_point(start + u, side, off)
		if road_distance(p.x, p.y) >= ROAD_CLEAR_M + width * 0.5:
			cur.append(p)
		else:
			if cur.size() > best.size():
				best = cur
			cur = PackedVector2Array()
		u += STEP_M
	if cur.size() > best.size():
		best = cur
	if best.size() < 4:
		return {}
	return {"kind": "flow", "points": best, "width": width}


func _offset_point(s: float, side: float, off: float) -> Vector2:
	var smp: Dictionary = route.sample(s)
	var a := deg_to_rad(float(smp["heading_deg"]))
	return Vector2(float(smp["x"]) + cos(a) * off * side, float(smp["z"]) + sin(a) * off * side)


func _y(x: float, z: float, fallback: float) -> float:
	return float(height_at.call(x, z)) if height_at.is_valid() else fallback


## Maillage de lave des éléments d'un tronçon (null s'il n'y a ni coulée ni lac).
func build_mesh(feats: Array, y_fallback: float = 0.0) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var any := false
	for f in feats:
		match str(f["kind"]):
			"flow":
				any = true
				_add_flow(st, f["points"], float(f["width"]), y_fallback)
			"pool":
				any = true
				_add_pool(st, f["center"], float(f["radius"]), y_fallback)
	if not any:
		return null
	return st.commit()


func _add_flow(st: SurfaceTool, pts: PackedVector2Array, width: float, yf: float) -> void:
	var rows := []
	for i in range(pts.size()):
		var a := pts[maxi(i - 1, 0)]
		var b := pts[mini(i + 1, pts.size() - 1)]
		var d := (b - a).normalized()
		var n := Vector2(-d.y, d.x)
		# Bouts de la coulée effilés
		var taper := clampf(minf(float(i), float(pts.size() - 1 - i)) / 2.0, 0.35, 1.0)
		var hw := width * 0.5 * taper
		var row := []
		for t in [-1.0, -0.45, 0.0, 0.45, 1.0]:
			var q: Vector2 = pts[i] + n * hw * t
			var alpha: float = 1.0 - absf(t) if absf(t) < 0.9 else 0.0
			row.append([Vector3(q.x, _y(q.x, q.y, yf) + LIFT_M, q.y), clampf(alpha * 1.6, 0.0, 1.0)])
		rows.append(row)
	for i in range(rows.size() - 1):
		for j in range(4):
			_quad(st, rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j])


func _add_pool(st: SurfaceTool, c: Vector2, r: float, yf: float) -> void:
	var n := 14
	var ring := []
	var inner := []
	var h := VegetationPlacer.hash3(fx_seed ^ 0x6B7, int(c.x), int(c.y))
	for i in range(n):
		var a := TAU * float(i) / float(n)
		var rr := r * (0.82 + 0.3 * float((h >> (i % 24)) & 0x7) / 7.0)
		var q := c + Vector2(cos(a), sin(a)) * rr
		var qi := c + Vector2(cos(a), sin(a)) * rr * 0.7
		ring.append([Vector3(q.x, _y(q.x, q.y, yf) + LIFT_M, q.y), 0.0])
		inner.append([Vector3(qi.x, _y(qi.x, qi.y, yf) + LIFT_M, qi.y), 1.0])
	var center := [Vector3(c.x, _y(c.x, c.y, yf) + LIFT_M, c.y), 1.0]
	for i in range(n):
		var j := (i + 1) % n
		_tri(st, center, inner[i], inner[j])
		_quad(st, inner[i], ring[i], ring[j], inner[j])


static func _vert(st: SurfaceTool, v: Array) -> void:
	st.set_color(Color(1, 1, 1, float(v[1])))
	st.set_normal(Vector3.UP)
	st.add_vertex(v[0])


static func _tri(st: SurfaceTool, a: Array, b: Array, c: Array) -> void:
	_vert(st, a)
	_vert(st, b)
	_vert(st, c)


static func _quad(st: SurfaceTool, a: Array, b: Array, c: Array, d: Array) -> void:
	_tri(st, a, b, c)
	_tri(st, a, c, d)


## Une fois par image : fenêtre de tronçons autour de `cam_s`, réserves posées sur les éléments proches,
## braises sur la caméra et `fire_level`.
func update(cam_pos: Vector3, cam_s: float, dt_s: float) -> void:
	if not active():
		return
	_clock += dt_s
	var groups := _slot_chunk.size()
	var first := int(floor(cam_s / CHUNK_M)) - CHUNKS_BEHIND
	for k in range(first, first + groups):
		var g := posmod(k, groups)
		if _slot_chunk[g] != k:
			_slot_chunk[g] = k
			for i in range(_queue.size() - 1, -1, -1):
				if _queue[i][0] == g:
					_queue.remove_at(i)
			_queue.append([g, k])
	var built := 0
	while built < MAX_BUILD_PER_FRAME and not _queue.is_empty():
		var job: Array = _queue.pop_front()
		_build_chunk(int(job[0]), int(job[1]))
		built += 1
	var target := 0.0 if fire_at(cam_pos.x, cam_pos.z).is_empty() else 1.0
	# Scène figée (captures, pas nul) : la lueur prend tout de suite sa valeur
	fire_level = target if dt_s <= 0.0 else move_toward(fire_level, target, FIRE_RATE * dt_s)
	if _embers != null:
		_embers.position = cam_pos
		_embers.emitting = fire_level > 0.05
		_embers.visible = fire_level > 0.0
		_embers.amount_ratio = fire_level
	if _clock - _pick_at >= PICK_PERIOD_S or _pick_at == -INF:
		_pick_at = _clock
		_place_pools(cam_pos)


func is_settled() -> bool:
	return _queue.is_empty()


func _build_chunk(g: int, k: int) -> void:
	if _chunk_nodes[g] != null:
		(_chunk_nodes[g] as Node).queue_free()
		_chunk_nodes[g] = null
	var feats := features_of_chunk(k)
	_chunk_feats[g] = feats
	if feats.is_empty():
		return
	var mid: Dictionary = route.sample(float(k) * CHUNK_M + CHUNK_M * 0.5)
	var mesh := build_mesh(feats, float(mid["y"]))
	if mesh == null:
		return
	var mi := MeshInstance3D.new()
	mi.name = "Lave_%d" % k
	mi.mesh = mesh
	mi.material_override = _lava_mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
	_chunk_nodes[g] = mi


## Panaches sur les évents, gerbes sur les grands lacs et lumières sur la lave la plus proche de la caméra.
func _place_pools(cam_pos: Vector3) -> void:
	var vents := []
	var big := []
	var hot := []
	var cam := Vector2(cam_pos.x, cam_pos.z)
	for feats in _chunk_feats:
		for f in feats:
			match str(f["kind"]):
				"vent":
					vents.append([cam.distance_squared_to(f["center"]), f["center"]])
				"pool":
					hot.append([cam.distance_squared_to(f["center"]), f["center"]])
					if float(f["radius"]) >= FOUNTAIN_RADIUS_M:
						big.append([cam.distance_squared_to(f["center"]), f["center"]])
				"flow":
					var pts: PackedVector2Array = f["points"]
					var p := pts[pts.size() / 2]
					hot.append([cam.distance_squared_to(p), p])
	for arr in [vents, big, hot]:
		arr.sort_custom(func(a, b): return a[0] < b[0])
	_assign(_plumes, vents, 0.0)
	_assign(_fountains, big, 0.3)
	_assign(_lights, hot, 3.0)


func _assign(nodes: Array, spots: Array, lift: float) -> void:
	for i in range(nodes.size()):
		var n: Node3D = nodes[i]
		if i < spots.size():
			var c: Vector2 = spots[i][1]
			n.position = Vector3(c.x, _y(c.x, c.y, n.position.y) + lift, c.y)
			n.visible = true
			if n is GPUParticles3D:
				(n as GPUParticles3D).emitting = true
		else:
			n.visible = false
			if n is GPUParticles3D:
				(n as GPUParticles3D).emitting = false


## Nombre de tronçons dessinés (tests).
func chunk_count() -> int:
	var n := 0
	for c in _chunk_nodes:
		if c != null:
			n += 1
	return n


## Éléments des tronçons de la fenêtre (tests, captures).
func visible_features() -> Array:
	var out := []
	for feats in _chunk_feats:
		out.append_array(feats)
	return out


func node_counts() -> Dictionary:
	return {"embers": 0 if _embers == null else _embers.amount, "plumes": _plumes.size(),
		"fountains": _fountains.size(), "lights": _lights.size()}


# --- Particules, dessinées par code ------------------------------------------------------------------------

static func _soft_texture() -> Texture2D:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.5, 1.0])
	g.colors = PackedColorArray([Color(1, 1, 1, 1), Color(1, 1, 1, 0.5), Color(1, 1, 1, 0)])
	var t := GradientTexture2D.new()
	t.gradient = g
	t.fill = GradientTexture2D.FILL_RADIAL
	t.fill_from = Vector2(0.5, 0.5)
	t.fill_to = Vector2(1.0, 0.5)
	t.width = 32
	t.height = 32
	return t


static func _billboard_material(color: Color, glow: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED if glow > 0.0 else BaseMaterial3D.SHADING_MODE_PER_PIXEL
	m.vertex_color_use_as_albedo = true
	m.albedo_color = color
	m.albedo_texture = _soft_texture()
	m.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
	if glow > 0.0:
		m.emission_enabled = true
		m.emission = color
		m.emission_energy_multiplier = glow
	return m


static func _ramp(colors: PackedColorArray, offsets: PackedFloat32Array) -> GradientTexture1D:
	var g := Gradient.new()
	g.offsets = offsets
	g.colors = colors
	var gt := GradientTexture1D.new()
	gt.gradient = g
	return gt


## Braises et flammèches qui montent autour du cycliste.
static func _make_embers(n: int, color: Color) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.name = "Braises"
	p.amount = n
	p.lifetime = 3.5
	p.preprocess = 3.5
	p.randomness = 1.0
	p.local_coords = false
	p.visibility_aabb = AABB(Vector3(-40, -10, -40), Vector3(80, 40, 80))
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	pm.emission_box_extents = Vector3(28.0, 1.5, 28.0)
	pm.direction = Vector3(0, 1, 0)
	pm.spread = 25.0
	pm.initial_velocity_min = 1.0
	pm.initial_velocity_max = 3.5
	pm.gravity = Vector3(0, 0.4, 0)
	pm.turbulence_enabled = true
	pm.turbulence_noise_strength = 1.2
	pm.turbulence_noise_scale = 4.0
	pm.scale_min = 0.6
	pm.scale_max = 1.4
	pm.color_ramp = _ramp(PackedColorArray([Color(1, 0.9, 0.5, 0), Color(1, 0.8, 0.4, 1), Color(1, 0.4, 0.1, 0.9),
		Color(0.6, 0.1, 0.05, 0)]), PackedFloat32Array([0.0, 0.1, 0.6, 1.0]))
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(0.09, 0.09)
	q.material = _billboard_material(color.lightened(0.3), 6.0)
	p.draw_pass_1 = q
	p.emitting = false
	p.visible = false
	return p


## Panache de fumée d'un évent : grosses volutes grises éclairées de rouge par-dessous.
static func _make_plume(smoke: Color, glow: Color) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.name = "Panache"
	p.amount = 28
	p.lifetime = 9.0
	p.preprocess = 9.0
	p.local_coords = false
	p.visibility_aabb = AABB(Vector3(-40, -5, -40), Vector3(80, 90, 80))
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	pm.emission_sphere_radius = 1.5
	pm.direction = Vector3(0, 1, 0)
	pm.spread = 12.0
	pm.initial_velocity_min = 4.0
	pm.initial_velocity_max = 7.0
	pm.gravity = Vector3(0.6, 0.2, 0.3)
	pm.damping_min = 0.3
	pm.damping_max = 0.6
	pm.scale_min = 3.0
	pm.scale_max = 5.0
	var sc := Curve.new()
	sc.add_point(Vector2(0, 0.4))
	sc.add_point(Vector2(1, 2.2))
	var sct := CurveTexture.new()
	sct.curve = sc
	pm.scale_curve = sct
	pm.color_ramp = _ramp(PackedColorArray([Color(glow.r, glow.g * 0.6, glow.b * 0.4, 0.0), Color(glow.r * 0.8, glow.g * 0.45, glow.b * 0.3, 0.75),
		Color(smoke.r, smoke.g, smoke.b, 0.6), Color(smoke.r * 1.4, smoke.g * 1.4, smoke.b * 1.4, 0.0)]),
		PackedFloat32Array([0.0, 0.08, 0.35, 1.0]))
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(4.0, 4.0)
	q.material = _billboard_material(Color.WHITE, 0.0)
	p.draw_pass_1 = q
	p.emitting = false
	p.visible = false
	return p


## Gerbe de lave d'un grand lac : gouttes incandescentes lancées haut, qui retombent.
static func _make_fountain(hot: Color, lava: Color) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.name = "Gerbe"
	p.amount = 110
	p.lifetime = 3.0
	p.preprocess = 3.0
	p.local_coords = false
	p.visibility_aabb = AABB(Vector3(-30, -5, -30), Vector3(60, 40, 60))
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	pm.emission_sphere_radius = 2.0
	pm.direction = Vector3(0, 1, 0)
	pm.spread = 18.0
	pm.initial_velocity_min = 11.0
	pm.initial_velocity_max = 19.0
	pm.gravity = Vector3(0, -9.8, 0)
	pm.scale_min = 0.6
	pm.scale_max = 1.6
	pm.color_ramp = _ramp(PackedColorArray([Color(hot.r, hot.g, hot.b, 1.0), Color(lava.r, lava.g, lava.b, 1.0),
		Color(lava.r * 0.4, lava.g * 0.2, lava.b * 0.2, 0.0)]), PackedFloat32Array([0.0, 0.5, 1.0]))
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(0.55, 0.55)
	q.material = _billboard_material(Color.WHITE, 5.0)
	p.draw_pass_1 = q
	p.emitting = false
	p.visible = false
	return p

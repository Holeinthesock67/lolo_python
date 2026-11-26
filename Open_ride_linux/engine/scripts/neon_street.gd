extends Node3D

## Mobilier de rue des paysages en ville néon (lots NV4 et NV5, parcours « Avenue de la Lagune ») : palmiers en
## rangée, lampadaires à globe, enseignes sur mât à noms inventés, guirlandes d'ampoules en travers de la rue et
## voitures garées. Pas de class_name : charger par preload("res://scripts/neon_street.gd").
##
## Règle unique de biome_model.gd (`neon_at`) : rien hors d'une tuile en ville néon. Placement déterministe
## (`items_of_chunk`, sans hasard : hachage de la graine, du tronçon et de la place), par tronçons de CHUNK_M le
## long de la route, dans la bande du trottoir (3,5 à 9,5 m de l'axe, devant les façades) :
## - côté ville : voitures garées le long de la chaussée (CAR_OFF_M), lampadaires (LAMP_OFF_M), palmiers
##   (PALM_OFF_M), une enseigne par ENSEIGNE_STEP_M (SIGN_OFF_M) ;
## - côté mer ou plage (terrain sous SHORE_Y_M à SHORE_PROBE_M de l'axe) : promenade, double rangée de palmiers et
##   lampadaires, ni voiture ni enseigne ;
## - guirlande en travers de la rue là où les deux côtés sont en ville ;
## - rien dans un bâtiment ni dans l'eau (`blocked`, zones d'exclusion de living_world.gd).
## Coût : un MultiMesh par sorte et par tronçon, sans lampe ni ombre portée ; la lumière vient du shader
## (neon_street.gdshader, global `neon_glow` du lot NV3) et du halo de l'image. Préréglage `low` : pas de
## guirlande, une voiture sur deux (`set_quality`).
## Création originale : les noms des enseignes (SIGN_NAMES) sont inventés pour OpenRide.

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const VehicleMesh := preload("res://scripts/vehicle_mesh.gd")
const VehicleShader := preload("res://shaders/vehicle.gdshader")
const StreetShader := preload("res://shaders/neon_street.gdshader")

const CHUNK_M := 100.0
const CHUNKS_BEHIND := 2
const CHUNKS_AHEAD := 6
const PICK_PERIOD_S := 0.5
const CAR_OFF_M := 4.3
const CAR_SLOT_M := 6.5
const CAR_SHARE := 0.5
const LAMP_OFF_M := 6.0
const LAMP_STEP_M := 25.0
const PALM_OFF_M := 7.8
const PALM_STEP_M := 20.0
const SHORE_PALM_OFFS_M := [5.2, 9.0]
const SHORE_PALM_STEP_M := 12.5
const SIGN_OFF_M := 9.0
const SIGN_STEP_M := 50.0
const GARLAND_STEP_M := 50.0
const GARLAND_HALF_M := 6.6
const GARLAND_H_M := 6.4
const GARLAND_SAG_M := 1.1
const GARLAND_BULBS := 19
const SHORE_PROBE_M := 85.0
const SHORE_Y_M := 1.0
const VISIBLE_M := 420.0
const SIGN_NAMES := ["HÔTEL LAGUNE", "CINÉ ÉTOILE", "CAFÉ CORAIL", "BAR DES PALMES", "GLACIER FLAMANT",
	"DISQUES SOLEIL", "PIZZERIA DU PHARE", "ARCADE COMÈTE", "MOTEL ALIZÉ", "BOWLING SATURNE", "LAVERIE NÉON",
	"TABAC DU PORT", "HÔTEL DES FLAMANTS", "CAFÉ DE LA PLAGE", "DANCING TROPIQUE", "ROLLERS PARADIS"]
const TINT_KEYS := ["pink", "cyan", "violet", "orange"]
const CAR_KINDS := ["car_a", "car_b", "van"]

var route = null
var biome_model = null
var height_at := Callable()
## `contains(x, z)` : vrai dans un bâtiment ou dans l'eau (exclusion_zones.gd) ; nul : rien n'est exclu.
var exclusions = null
var street_seed := 0
var palette := {}
var with_garlands := true
var car_share := CAR_SHARE
var _chunks := {}            # tronçon -> Node3D
var _pick_at := -INF
var _clock := 0.0
var _meshes := {}
var _street_mat: ShaderMaterial = null
var _car_mats := {}


func configure(route_data, model, seed_value: int = 0) -> void:
	route = route_data
	biome_model = model
	street_seed = seed_value
	for k in _chunks:
		_chunks[k].queue_free()
	_chunks.clear()
	_pick_at = -INF
	palette = {} if model == null else model.any_neon()


func active() -> bool:
	return route != null and not palette.is_empty()


func set_quality(preset: String) -> void:
	with_garlands = preset != "low"
	car_share = CAR_SHARE * (0.5 if preset == "low" else 1.0)


func chunk_count() -> int:
	return maxi(1, int(ceil(float(route.length_m) / CHUNK_M))) if route != null else 0


## Nombre d'objets affichés par sorte (essais et `test_info`).
func counts() -> Dictionary:
	var out := {"chunks": _chunks.size(), "palm": 0, "lamp": 0, "car": 0, "sign": 0, "garland": 0}
	for k in _chunks:
		var c: Dictionary = _chunks[k].get_meta("counts", {})
		for key in c:
			out[key] = int(out.get(key, 0)) + int(c[key])
	return out


func _hash(k: int, slot: int, salt: int) -> float:
	return float(VegetationPlacer.hash3(street_seed ^ salt, k, slot) & 0xFFFF) / 65536.0


func _frame(s: float) -> Dictionary:
	var smp: Dictionary = route.sample(s)
	var a := deg_to_rad(float(smp["heading_deg"]))
	return {"p": Vector3(float(smp["x"]), float(smp["y"]), float(smp["z"])), "right": Vector3(cos(a), 0.0, sin(a)),
		"yaw": -a}


func _ground(p: Vector3) -> float:
	return float(height_at.call(p.x, p.z)) if height_at.is_valid() else p.y


func _neon(p: Vector3) -> bool:
	return biome_model != null and not biome_model.neon_at(p.x, p.z).is_empty()


func _free(p: Vector3) -> bool:
	return exclusions == null or not exclusions.contains(p.x, p.z)


## Côté `side` (−1 gauche, 1 droite) de la route en `s` : "" hors de la ville néon, "shore" au bord de la mer ou
## d'une plage, "city" sinon.
func side_kind(s: float, side: int) -> String:
	var f := _frame(s)
	var near: Vector3 = f["p"] + f["right"] * (PALM_OFF_M * side)
	if not _neon(near):
		return ""
	if not height_at.is_valid():
		return "city"
	var far: Vector3 = f["p"] + f["right"] * (SHORE_PROBE_M * side)
	return "shore" if _ground(far) < SHORE_Y_M else "city"


func _item(kind: String, s: float, side: int, off: float, extra: Dictionary = {}) -> Dictionary:
	var f := _frame(s)
	var p: Vector3 = f["p"] + f["right"] * (off * side)
	if kind != "garland" and (not _free(p) or not _neon(p)):
		return {}
	p.y = _ground(p) if kind != "car" and kind != "garland" else f["p"].y
	var out := {"kind": kind, "pos": p, "yaw": float(f["yaw"]), "side": side, "s": s}
	out.merge(extra)
	return out


## Objets du tronçon `k` : `[{kind, pos, yaw, side, s, tint?, name?, car?, paint?}]`, les mêmes à chaque appel.
func items_of_chunk(k: int) -> Array:
	var out := []
	if not active():
		return out
	var s0 := k * CHUNK_M
	var s1 := minf(s0 + CHUNK_M, float(route.length_m))
	var mid := (s0 + s1) * 0.5
	var kinds := {-1: side_kind(mid, -1), 1: side_kind(mid, 1)}
	for side: int in [-1, 1]:
		var what: String = kinds[side]
		if what == "":
			continue
		var phase := 0.0 if side > 0 else 0.5
		var n := 0
		var s := s0 + LAMP_STEP_M * phase
		while s < s1:
			out.append(_item("lamp", s, side, LAMP_OFF_M if what == "city" else 3.9, {"tint": (k + n + (0 if side > 0 else 1)) % 2}))
			s += LAMP_STEP_M
			n += 1
		if what == "shore":
			for row in range(SHORE_PALM_OFFS_M.size()):
				s = s0 + SHORE_PALM_STEP_M * (0.5 * row + 0.25)
				n = 0
				while s < s1:
					out.append(_item("palm", s, side, SHORE_PALM_OFFS_M[row], {"size": 0.85 + 0.3 * _hash(k, n + 40 * row + 400 * (side + 1), 0x9A1)}))
					s += SHORE_PALM_STEP_M
					n += 1
			continue
		s = s0 + PALM_STEP_M * (0.5 + 0.5 * phase)
		n = 0
		while s < s1:
			out.append(_item("palm", s, side, PALM_OFF_M, {"size": 0.8 + 0.3 * _hash(k, n + 100 * (side + 1), 0x9A1)}))
			s += PALM_STEP_M
			n += 1
		s = s0 + CAR_SLOT_M * 0.5
		n = 0
		while s + CAR_SLOT_M * 0.5 < s1:
			var slot := n + 100 * (side + 1)
			if _hash(k, slot, 0xCA7) < car_share:
				var u := _hash(k, slot, 0xC01)
				out.append(_item("car", s, side, CAR_OFF_M, {"car": CAR_KINDS[2 if u > 0.9 else (1 if u > 0.5 else 0)],
					"paint": int(_hash(k, slot, 0xC02) * 64.0)}))
			s += CAR_SLOT_M
			n += 1
		s = s0 + SIGN_STEP_M * (0.3 + 0.4 * phase)
		n = 0
		while s < s1:
			var h := int(_hash(k, n + 10 * (side + 1), 0x51E) * 4096.0)
			out.append(_item("sign", s, side, SIGN_OFF_M, {"tint": h % TINT_KEYS.size(),
				"name": SIGN_NAMES[(h / 7 + k * 3 + n + (side + 1) * 5) % SIGN_NAMES.size()]}))
			s += SIGN_STEP_M
			n += 1
	if with_garlands and kinds[-1] == "city" and kinds[1] == "city":
		var sg := s0 + GARLAND_STEP_M * 0.25
		while sg < s1:
			out.append(_item("garland", sg, 1, 0.0))
			sg += GARLAND_STEP_M
	return out.filter(func(d): return not d.is_empty())


## Une fois par image : tronçons autour de la caméra (un tronçon construit par appel au plus), les autres libérés.
func update(cam_s: float, dt_s: float) -> void:
	if not active():
		return
	_clock += maxf(dt_s, 0.0)
	var n := chunk_count()
	var here := int(floor(cam_s / CHUNK_M))
	var wanted := {}
	for d in range(-CHUNKS_BEHIND, CHUNKS_AHEAD + 1):
		var k := here + d
		if route.is_loop():
			k = posmod(k, n)
		elif k < 0 or k >= n:
			continue
		wanted[k] = absi(d)
	if dt_s > 0.0 and _clock < _pick_at and _chunks.size() == wanted.size():
		return
	_pick_at = _clock + PICK_PERIOD_S
	for k in _chunks.keys():
		if not wanted.has(k):
			_chunks[k].queue_free()
			_chunks.erase(k)
	var best := -1
	for k in wanted:
		if not _chunks.has(k) and (best < 0 or wanted[k] < wanted[best]):
			best = k
		# Scène figée (captures, pas nul) : tout de suite
		if dt_s <= 0.0 and not _chunks.has(k):
			_build(k)
	if best >= 0 and not _chunks.has(best):
		_build(best)
		_pick_at = _clock     # la suite à l'image suivante


func _tint(i: int) -> Color:
	return Color(str(palette.get(TINT_KEYS[i % TINT_KEYS.size()], "#ff2a9e")))


func _mat() -> ShaderMaterial:
	if _street_mat == null:
		_street_mat = ShaderMaterial.new()
		_street_mat.shader = StreetShader
	return _street_mat


func _car_mat(kind: String) -> ShaderMaterial:
	if not _car_mats.has(kind):
		var m := ShaderMaterial.new()
		m.shader = VehicleShader
		m.set_shader_parameter("instanced", true)
		m.set_shader_parameter("second", VehicleMesh.second(kind))
		_car_mats[kind] = m
	return _car_mats[kind]


func _mesh(key: String) -> Mesh:
	if not _meshes.has(key):
		match key:
			"palm":
				_meshes[key] = build_palm()
			"lamp":
				_meshes[key] = build_lamp()
			"garland":
				_meshes[key] = build_garland()
			_:
				_meshes[key] = VehicleMesh.build_full(key) if key in CAR_KINDS else build_sign(_tint(int(key)))
	return _meshes[key]


func _multi(parent: Node3D, key: String, xfs: Array, customs: Array, mat: Material, colors: Array = []) -> void:
	if xfs.is_empty():
		return
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.use_colors = not colors.is_empty()
	mm.mesh = _mesh(key)
	mm.instance_count = xfs.size()
	for i in range(xfs.size()):
		mm.set_instance_transform(i, xfs[i])
		mm.set_instance_custom_data(i, customs[i])
		if not colors.is_empty():
			mm.set_instance_color(i, colors[i])
	var mmi := MultiMeshInstance3D.new()
	mmi.name = key
	mmi.multimesh = mm
	mmi.material_override = mat
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mmi.visibility_range_end = VISIBLE_M + CHUNK_M
	parent.add_child(mmi)


func _build(k: int) -> void:
	var node := Node3D.new()
	node.name = "Rue_%d" % k
	var xfs := {}
	var customs := {}
	var colors := {}
	var n := {"palm": 0, "lamp": 0, "car": 0, "sign": 0, "garland": 0}
	for it in items_of_chunk(k):
		var kind: String = it["kind"]
		n[kind] += 1
		var yaw: float = it["yaw"] + (PI if int(it["side"]) < 0 else 0.0)
		var basis := Basis(Vector3.UP, yaw)
		var key := kind
		var custom := Color(0, 0, 0, 0)
		match kind:
			"palm":
				basis = Basis(Vector3.UP, float(it["s"]) * 1.7).scaled(Vector3.ONE * float(it["size"]))
			"lamp":
				custom = _tint(int(it["tint"]))
			"car":
				key = str(it["car"])
				custom = Color(1.0 if int(it["paint"]) % 5 == 0 else 0.0, 0.0, 0.0, 0.0)   # quelques feux restés allumés
				colors[key] = colors.get(key, []) + [VehicleMesh.paint(key, int(it["paint"]))]
			"sign":
				_add_sign(node, it, basis)
				continue
			"garland":
				basis = Basis(Vector3.UP, float(it["yaw"]))
		xfs[key] = xfs.get(key, []) + [Transform3D(basis, it["pos"])]
		customs[key] = customs.get(key, []) + [custom]
	for key in xfs:
		var car: bool = key in CAR_KINDS
		_multi(node, key, xfs[key], customs[key], _car_mat(key) if car else _mat(), colors.get(key, []))
	node.set_meta("counts", n)
	add_child(node)
	_chunks[k] = node


## Enseigne sur mât, en drapeau (plaque perpendiculaire à la route, lisible en roulant dans les deux sens).
func _add_sign(parent: Node3D, it: Dictionary, basis: Basis) -> void:
	var root := Node3D.new()
	root.transform = Transform3D(basis, it["pos"])
	var mi := MeshInstance3D.new()
	mi.mesh = _mesh(str(int(it["tint"])))
	mi.material_override = _mat()
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.visibility_range_end = VISIBLE_M
	root.add_child(mi)
	for face: float in [-1.0, 1.0]:
		var label := Label3D.new()
		label.text = two_lines(str(it["name"]))
		label.font_size = 96
		label.pixel_size = 0.0048
		label.outline_size = 0
		label.modulate = Color(1.0, 0.97, 0.9)
		label.shaded = false
		label.double_sided = false
		label.line_spacing = -14.0
		label.position = Vector3(-1.45, 4.25, 0.07 * face)
		label.rotation.y = 0.0 if face > 0.0 else PI
		label.visibility_range_end = 160.0
		root.add_child(label)
	parent.add_child(root)


## Nom d'enseigne sur deux lignes au plus : coupé à l'espace le plus proche du milieu au-delà de 12 caractères.
static func two_lines(name: String) -> String:
	if name.length() <= 12 or not name.contains(" "):
		return name
	var best := -1
	for i in range(name.length()):
		if name[i] == " " and (best < 0 or absi(2 * i - name.length()) < absi(2 * best - name.length())):
			best = i
	return name.substr(0, best) + "\n" + name.substr(best + 1)


static func _v(st: SurfaceTool, p: Vector3, n: Vector3, c: Color) -> void:
	st.set_color(c)
	st.set_normal(n)
	st.add_vertex(p)


static func _box(st: SurfaceTool, c: Vector3, size: Vector3, col: Color) -> void:
	var h := size * 0.5
	for axis in range(3):
		for sgn: float in [-1.0, 1.0]:
			var nrm := Vector3.ZERO
			nrm[axis] = sgn
			var u := Vector3.ZERO
			var w := Vector3.ZERO
			u[(axis + 1) % 3] = h[(axis + 1) % 3]
			w[(axis + 2) % 3] = h[(axis + 2) % 3]
			var o := c + nrm * h[axis]
			for q in [o - u - w, o + u - w, o + u + w, o - u - w, o + u + w, o - u + w]:
				_v(st, q, nrm, col)


static func _tube(st: SurfaceTool, a: Vector3, b: Vector3, r0: float, r1: float, col: Color, sides: int = 6) -> void:
	var axis := (b - a).normalized()
	var u := axis.cross(Vector3.RIGHT if absf(axis.x) < 0.9 else Vector3.FORWARD).normalized()
	var w := axis.cross(u)
	for j in range(sides):
		var a0 := TAU * j / sides
		var a1 := TAU * (j + 1) / sides
		var o0 := u * cos(a0) + w * sin(a0)
		var o1 := u * cos(a1) + w * sin(a1)
		for q in [[a + o0 * r0, o0], [b + o0 * r1, o0], [b + o1 * r1, o1], [a + o0 * r0, o0], [b + o1 * r1, o1], [a + o1 * r0, o1]]:
			_v(st, q[0], q[1], col)


static func _ball(st: SurfaceTool, c: Vector3, r: float, col: Color) -> void:
	var tips := [Vector3.UP, Vector3.DOWN]
	var ring := [Vector3.RIGHT, Vector3.BACK, Vector3.LEFT, Vector3.FORWARD]
	for tip: Vector3 in tips:
		for j in range(4):
			for q: Vector3 in [tip, ring[j], ring[(j + 1) % 4]]:
				_v(st, c + q * r, q, col)


## Palmier à silhouette fournie (lot NV4) : stipe courbe de 9,5 m, 16 palmes arquées en 5 tronçons (celui des
## biomes, à 8 palmes, fait parapluie vu d'en bas).
static func build_palm() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var trunk := Color(0.22, 0.16, 0.12)
	var leaf := Color(0.07, 0.22, 0.10)
	var prev := Vector3.ZERO
	for i in range(1, 9):
		var t := float(i) / 8.0
		var p := Vector3(0.9 * t * t, 9.5 * t, 0.0)
		_tube(st, prev, p, 0.25 - 0.1 * (t - 0.125), 0.24 - 0.1 * t, trunk)
		prev = p
	var top := prev
	for f in range(16):
		var ang := TAU * f / 16.0 + 0.2
		var dir := Vector3(cos(ang), 0, sin(ang))
		var lat := Vector3(-dir.z, 0, dir.x)
		var up0 := 0.9 if f % 2 == 0 else 0.35
		var length := 4.4 if f % 2 == 0 else 3.6
		var a := top
		for sgm in range(5):
			var t1 := float(sgm + 1) / 5.0
			var b := top + dir * length * t1 + Vector3(0, up0 * 2.2 * t1 - 3.4 * t1 * t1, 0)
			var w0 := 0.42 * (1.0 - float(sgm) / 5.0) + 0.05
			var w1 := 0.42 * (1.0 - t1) + 0.03
			for q in [a - lat * w0, b - lat * w1, b + lat * w1, a - lat * w0, b + lat * w1, a + lat * w0]:
				_v(st, q, Vector3.UP, leaf)
			a = b
	return st.commit()


## Lampadaire : fût sombre de 5 m, crosse vers la chaussée (−x du maillage tourné vers la route) et globe lumineux
## (couleur d'alpha nul : partie lumineuse, teinte de l'instance).
static func build_lamp() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var metal := Color(0.08, 0.08, 0.1)
	var glow := Color(1, 1, 1, 0)
	_tube(st, Vector3.ZERO, Vector3(0, 4.8, 0), 0.09, 0.06, metal)
	_tube(st, Vector3(0, 4.8, 0), Vector3(-1.1, 5.2, 0), 0.05, 0.04, metal)
	_ball(st, Vector3(-1.1, 5.0, 0), 0.32, glow)
	_tube(st, Vector3(0, 0.6, 0), Vector3(0, 0.75, 0), 0.13, 0.13, glow)
	return st.commit()


## Guirlande en travers de la rue : deux mâts fins, un fil en chaînette et GARLAND_BULBS ampoules chaudes.
static func build_garland() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var metal := Color(0.08, 0.08, 0.1)
	var warm := Color(1.0, 0.78, 0.42, 0.0)
	for sx: float in [-1.0, 1.0]:
		_tube(st, Vector3(sx * GARLAND_HALF_M, 0, 0), Vector3(sx * GARLAND_HALF_M, GARLAND_H_M, 0), 0.06, 0.04, metal, 5)
	var prev := Vector3(-GARLAND_HALF_M, GARLAND_H_M, 0)
	for i in range(1, GARLAND_BULBS + 2):
		var t := float(i) / float(GARLAND_BULBS + 1)
		var p := Vector3(lerpf(-GARLAND_HALF_M, GARLAND_HALF_M, t), GARLAND_H_M - GARLAND_SAG_M * 4.0 * t * (1.0 - t), 0)
		_tube(st, prev, p, 0.012, 0.012, metal, 3)
		if i <= GARLAND_BULBS:
			_ball(st, p + Vector3(0, -0.1, 0), 0.085, warm)
		prev = p
	return st.commit()


## Enseigne : mât à l'origine, caisson sombre de 2,9 × 1,3 m vers la chaussée (−x), cadre lumineux de la teinte.
static func build_sign(tint: Color) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var metal := Color(0.08, 0.08, 0.1)
	var glow := Color(tint.r, tint.g, tint.b, 0.0)
	_tube(st, Vector3.ZERO, Vector3(0, 5.1, 0), 0.08, 0.07, metal)
	_box(st, Vector3(-1.45, 4.25, 0), Vector3(2.9, 1.3, 0.1), Color(0.03, 0.03, 0.05))
	for y: float in [3.6, 4.9]:
		_box(st, Vector3(-1.45, y, 0), Vector3(2.98, 0.07, 0.16), glow)
	for x: float in [-2.92, 0.02]:
		_box(st, Vector3(x, 4.25, 0), Vector3(0.07, 1.37, 0.16), glow)
	return st.commit()

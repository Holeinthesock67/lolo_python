extends Node3D

## Épaves de navire des points `wreck` (lot SM2, format .world 1.8 §8, OSM `historic=wreck`), construites par
## code comme les éoliennes (wind_turbines.gd). Pas de class_name : charger par preload("res://scripts/wrecks.gd").
##
## Un caboteur de LENGTH_REF_M (mis à l'échelle de `length_m`, DEFAULT_LENGTH_M sans valeur) : coque à étrave
## relevée et tableau arrière, pont de bois, timonerie à l'arrière, cheminée penchée, mât avant cassé et son
## tronçon tombé en travers du pont. Couché sur le fond : enfoncé de SINK_M dans le sable, gîte de HEEL_DEG et
## assiette de TRIM_DEG (la proue pique), cap tiré du hachage de l'`id` (le même à chaque chargement, et la
## gîte d'un bord ou de l'autre). Matière : shaders/props.gdshader, sorte KIND_WRECK (acier rouillé, concrétions,
## algues sur les faces tournées vers le haut, hublots, brèche sombre dans le flanc).
##
## - `set_points(points)` : points d'intérêt du parcours chargé (les autres sortes sont ignorées) ;
## - `update(cam_pos)` une fois par image : au plus MAX_ACTIVE épaves affichées, les plus proches de la caméra,
##   retriées tous les RESELECT_M ; leurs nœuds sont créés au démarrage. Rien ne bouge : une épave ne coûte que
##   son affichage (quelques maillages, une seule matière par pièce).
## - `set_preset(name)` : faux relief coupé en `low` (RoadsideProps.RELIEF), comme les autres objets du décor.

const PropShader := preload("res://shaders/props.gdshader")
const RoadsideProps := preload("res://scripts/roadside_props.gd")

const MAX_ACTIVE := 4
const DEFAULT_LENGTH_M := 42.0
const LENGTH_REF_M := 42.0       # dimensions du modèle ci-dessous, mises à l'échelle de `length_m`
const BEAM_M := 8.0
const HULL_H_M := 4.5            # de la quille au liston
const SHEER_BOW_M := 1.4         # relèvement du pont vers l'étrave
const SINK_M := 1.5
const HEEL_DEG := 16.0
const TRIM_DEG := 2.5
const RESELECT_M := 50.0
const VISIBILITY_END_M := 600.0  # au-delà du brouillard sous l'eau (230 m) : jamais coupé à l'écran
const KIND_WRECK := 7
## Pièces de la sorte KIND_WRECK (uniforme `part` de props.gdshader).
const PART_HULL := 0
const PART_HOUSE := 1
const PART_TUBE := 2
const HULL_COLOR := Color(0.62, 0.34, 0.26)    # peinture de coque passée, rouge brun
const HOUSE_COLOR := Color(0.86, 0.84, 0.76)   # timonerie : blanc cassé terni
const TUBE_COLOR := Color(0.64, 0.40, 0.24)    # mât et cheminée : acier rouillé

## Coupe de la coque, du liston à la quille, en fractions de la demi-largeur et de la hauteur.
const SECTION := [[1.0, 1.0], [1.0, 0.45], [0.8, 0.16], [0.35, 0.02], [0.0, 0.0]]
const STATIONS := 14

var _points: Array = []          # {pos: Vector3, scale: float, yaw: float, heel: float}
var _slots: Array = []           # {root: Node3D, point: int}
var _last_select := Vector3(INF, INF, INF)
var _dirty := true
var _meshes: Array = []   # gardés ici : les maillages partagés survivent aux nœuds qui les affichent
var _mats: Array = []     # coque, timonerie, tubes
var last_update_usec := 0


## Demi-largeur de la coque (m) à la fraction `t` de la longueur (0 tableau arrière, 1 étrave).
static func half_beam(t: float) -> float:
	var b := BEAM_M * 0.5
	if t < 0.12:
		return b * lerpf(0.82, 1.0, t / 0.12)
	if t <= 0.6:
		return b
	var u := clampf((t - 0.6) / 0.4, 0.0, 1.0)
	return b * sqrt(maxf(1.0 - u * u, 0.0))


## Hauteur du liston (m) à la fraction `t` de la longueur : tonture qui relève la proue.
static func sheer(t: float) -> float:
	return HULL_H_M + SHEER_BOW_M * pow(clampf((t - 0.4) / 0.6, 0.0, 1.0), 2.0)


## Cap (rad) et bord de gîte (±1) tirés de l'identifiant : mêmes valeurs à chaque chargement.
static func pose_of(id: String) -> Dictionary:
	var h := hash(id)
	return {"yaw": float(posmod(h, 3600)) / 3600.0 * TAU, "heel_side": 1.0 if (h >> 12) & 1 == 0 else -1.0}


## Coque et pont (m, centrés sur l'origine : x à tribord, y en haut, z vers l'étrave) : une surface fermée.
static func hull_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var rings: Array = []
	for i in range(STATIONS + 1):
		var t := float(i) / STATIONS
		var z := (t - 0.5) * LENGTH_REF_M
		var w := half_beam(t)
		var top := sheer(t)
		var keel := 0.6 * pow(clampf((t - 0.85) / 0.15, 0.0, 1.0), 2.0) * top   # le brion remonte à l'étrave
		var ring: Array = []
		for k in range(SECTION.size()):
			var f: Array = SECTION[k]
			ring.append(Vector3(w * float(f[0]), lerpf(keel, top, float(f[1])), z))
		for k in range(SECTION.size() - 2, -1, -1):
			var f: Array = SECTION[k]
			ring.append(Vector3(-w * float(f[0]), lerpf(keel, top, float(f[1])), z))
		rings.append(ring)
	var off := Vector3(0.0, HULL_H_M * 0.5, 0.0)
	var n := (rings[0] as Array).size()
	for i in range(STATIONS):
		var a: Array = rings[i]
		var b: Array = rings[i + 1]
		for k in range(n - 1):
			_quad(st, a[k] - off, a[k + 1] - off, b[k + 1] - off, b[k] - off)
		# Pont : du liston bâbord (dernier point) au liston tribord (premier)
		_quad(st, a[n - 1] - off, a[0] - off, b[0] - off, b[n - 1] - off)
	# Tableau arrière : éventail depuis le milieu du pont
	var stern: Array = rings[0]
	var c: Vector3 = (stern[0] + stern[n - 1]) * 0.5 - off
	for k in range(n - 1):
		st.add_vertex(c)
		st.add_vertex(stern[k + 1] - off)
		st.add_vertex(stern[k] - off)
	st.add_vertex(c)
	st.add_vertex(stern[0] - off)
	st.add_vertex(stern[n - 1] - off)
	st.generate_normals()
	return st.commit()


## Quadrilatère a-b-c-d (sens trigonométrique vu de l'extérieur).
static func _quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3) -> void:
	for v in [a, b, c, a, c, d]:
		st.add_vertex(v)


## Maillage d'une primitive converti en ArrayMesh (le serveur de rendu factice du mode sans écran ne
## sait pas compter les surfaces d'une PrimitiveMesh).
static func _baked(pm: PrimitiveMesh) -> ArrayMesh:
	var am := ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, pm.get_mesh_arrays())
	return am


func _material(part: int, color: Color, size: Vector3) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = PropShader
	m.set_shader_parameter("kind", KIND_WRECK)
	m.set_shader_parameter("part", part)
	m.set_shader_parameter("base_color", color)
	m.set_shader_parameter("size_m", size)
	return m


func _init() -> void:
	var house := BoxMesh.new()
	house.size = Vector3(BEAM_M * 0.62, 2.6, 7.0)
	var funnel := CylinderMesh.new()
	funnel.top_radius = 0.8
	funnel.bottom_radius = 0.95
	funnel.height = 2.4
	funnel.radial_segments = 12
	funnel.rings = 1
	var mast := CylinderMesh.new()
	mast.top_radius = 0.16
	mast.bottom_radius = 0.22
	mast.height = 4.0
	mast.radial_segments = 8
	mast.rings = 1
	var fallen := mast.duplicate() as CylinderMesh
	fallen.height = 7.5
	fallen.top_radius = 0.12
	fallen.bottom_radius = 0.16
	_meshes = [hull_mesh(), _baked(house), _baked(funnel), _baked(mast), _baked(fallen)]
	_mats = [_material(PART_HULL, HULL_COLOR, Vector3(BEAM_M, HULL_H_M + SHEER_BOW_M, LENGTH_REF_M)),
		_material(PART_HOUSE, HOUSE_COLOR, house.size),
		_material(PART_TUBE, TUBE_COLOR, Vector3(1.9, 2.4, 1.9))]
	var deck_y := HULL_H_M   # dessus du pont, dans le repère du navire (quille à 0)
	# [maillage, matière, position, rotation (degrés)], navire posé quille à y = 0
	var parts := [
		[0, 0, Vector3(0.0, HULL_H_M * 0.5, 0.0), Vector3.ZERO],
		[1, 1, Vector3(0.0, deck_y + 1.3, -LENGTH_REF_M * 0.27), Vector3.ZERO],
		[2, 2, Vector3(0.0, deck_y + 2.6 + 1.0, -LENGTH_REF_M * 0.36), Vector3(-14.0, 0.0, 0.0)],
		[3, 2, Vector3(0.0, deck_y + 2.0, LENGTH_REF_M * 0.22), Vector3(0.0, 0.0, 6.0)],
		[4, 2, Vector3(1.2, deck_y + 0.5, LENGTH_REF_M * 0.08), Vector3(80.0, 25.0, 0.0)],
	]
	for i in range(MAX_ACTIVE):
		var root := Node3D.new()
		root.name = "Wreck_%d" % i
		root.visible = false
		add_child(root)
		var ship := Node3D.new()
		ship.name = "Ship"
		root.add_child(ship)
		for p in parts:
			var mi := MeshInstance3D.new()
			mi.mesh = _meshes[p[0]]
			mi.material_override = _mats[p[1]]
			mi.position = p[2]
			mi.rotation_degrees = p[3]
			mi.visibility_range_end = VISIBILITY_END_M
			ship.add_child(mi)
		_slots.append({"root": root, "ship": ship, "point": -1})


func set_preset(preset_name: String) -> void:
	for m in _mats:
		(m as ShaderMaterial).set_shader_parameter("relief", float(RoadsideProps.RELIEF.get(preset_name, 1.0)))


func set_points(points: Array) -> void:
	_points.clear()
	for p in points:
		if typeof(p) != TYPE_DICTIONARY or str(p.get("kind", "")) != "wreck":
			continue
		var length := float(p.get("length_m", DEFAULT_LENGTH_M))
		if not is_finite(length) or length <= 0.0:
			length = DEFAULT_LENGTH_M
		var pose := pose_of(str(p.get("id", "")))
		_points.append({"pos": Vector3(float(p["x"]), float(p["y"]), float(p["z"])),
			"scale": length / LENGTH_REF_M, "yaw": pose["yaw"], "heel": float(pose["heel_side"]) * HEEL_DEG})
	_dirty = true


func point_count() -> int:
	return _points.size()


func active_count() -> int:
	var n := 0
	for s in _slots:
		if s["root"].visible:
			n += 1
	return n


## Transformation du navire affiché pour l'épave `i` de set_points (tests) : racine posée au point, navire
## enfoncé, gîté et pointé.
func wreck_transform(i: int) -> Transform3D:
	for s in _slots:
		if s["point"] == i:
			return (s["root"] as Node3D).transform * (s["ship"] as Node3D).transform
	return Transform3D()


func _select(cam_pos: Vector3) -> void:
	var order := []
	for i in range(_points.size()):
		order.append([(_points[i]["pos"] as Vector3).distance_squared_to(cam_pos), i])
	order.sort_custom(func(a, b): return a[0] < b[0] or (a[0] == b[0] and a[1] < b[1]))
	for j in range(MAX_ACTIVE):
		var s: Dictionary = _slots[j]
		var root: Node3D = s["root"]
		if j < order.size():
			var p: Dictionary = _points[order[j][1]]
			s["point"] = order[j][1]
			root.position = p["pos"]
			root.rotation = Vector3(0.0, float(p["yaw"]), 0.0)
			root.scale = Vector3.ONE * float(p["scale"])
			var ship: Node3D = s["ship"]
			ship.position = Vector3(0.0, -SINK_M, 0.0)
			ship.rotation_degrees = Vector3(-TRIM_DEG, 0.0, float(p["heel"]))
			root.visible = true
		else:
			s["point"] = -1
			root.visible = false
	_last_select = cam_pos
	_dirty = false


func update(cam_pos: Vector3) -> void:
	var t0 := Time.get_ticks_usec()
	if _dirty or cam_pos.distance_to(_last_select) > RESELECT_M:
		_select(cam_pos)
	last_update_usec = Time.get_ticks_usec() - t0

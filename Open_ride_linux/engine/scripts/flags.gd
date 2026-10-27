extends Node3D

## Drapeaux (Lot P12) : un mât et un tissu par point `flag`, et un drapeau près de chaque point `village`
## sans mât OSM à moins de VILLAGE_FLAG_RADIUS_M (position tirée du hachage de l'`id`, donc la même à
## chaque chargement). Pas de class_name : charger par preload("res://scripts/flags.gd").
##
## - `set_points(points)` : points d'intérêt du parcours ; au plus MAX_FLAGS drapeaux (les premiers
##   dans l'ordre des points, OSM d'abord), nœuds créés au démarrage.
## - `update(wind, dt_s)` une fois par image avec l'évaluation de wind_model.gd : le tissu se tourne
##   vers où souffle le vent (lissage de constante TURN_TAU_S) ; la vague, l'amplitude et la retombée
##   par vent faible viennent de shaders/flag.gdshader (uniformes communs, un seul matériau).

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const FlagShader := preload("res://shaders/flag.gdshader")

const MAX_FLAGS := 30
const POLE_HEIGHT_M := 7.0
const CLOTH_SIZE := Vector2(1.5, 1.0)
const VILLAGE_FLAG_RADIUS_M := 150.0
const VILLAGE_OFFSET_M := Vector2(12.0, 30.0)
const TURN_TAU_S := 1.0

var flag_positions: Array[Vector3] = []
var _cloth_nodes: Array[Node3D] = []
var _roots: Array[Node3D] = []
var _yaw := 0.0
var _material: ShaderMaterial
var _meshes: Array = []   # gardés ici : les maillages partagés survivent aux nœuds qui les affichent
var last_update_usec := 0


## Positions des drapeaux pour une liste de points d'intérêt (sans nœud, déterministe).
static func positions_for(points: Array) -> Array[Vector3]:
	var flags: Array[Vector3] = []
	for p in points:
		if typeof(p) == TYPE_DICTIONARY and str(p.get("kind", "")) == "flag":
			flags.append(Vector3(float(p["x"]), float(p["y"]), float(p["z"])))
	var osm_count := flags.size()
	for p in points:
		if typeof(p) != TYPE_DICTIONARY or str(p.get("kind", "")) != "village":
			continue
		var c := Vector3(float(p["x"]), float(p["y"]), float(p["z"]))
		var has_flag := false
		for j in range(osm_count):
			if Vector2(flags[j].x, flags[j].z).distance_to(Vector2(c.x, c.z)) <= VILLAGE_FLAG_RADIUS_M:
				has_flag = true
				break
		if has_flag:
			continue
		var h := VegetationPlacer.hash_string(str(p.get("id", "")))
		var ang := TAU * float(h & 0xFFFF) / 65536.0
		var r := lerpf(VILLAGE_OFFSET_M.x, VILLAGE_OFFSET_M.y, float((h >> 16) & 0xFFFF) / 65536.0)
		flags.append(c + Vector3(cos(ang) * r, 0.0, sin(ang) * r))
	return flags


## Cap du tissu (rad autour de y ; tissu vers +x local) pour un vent qui souffle vers `dir`.
static func cloth_yaw(dir: Vector3) -> float:
	return atan2(-dir.z, dir.x)



## Maillage d'une primitive converti en ArrayMesh (le serveur de rendu factice du mode sans écran ne
## sait pas compter les surfaces d'une PrimitiveMesh).
static func _baked(pm: PrimitiveMesh) -> ArrayMesh:
	var am := ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, pm.get_mesh_arrays())
	return am

func _init() -> void:
	_material = ShaderMaterial.new()
	_material.shader = FlagShader
	var pole_mat := StandardMaterial3D.new()
	pole_mat.albedo_color = Color(0.75, 0.75, 0.78)
	var pole := CylinderMesh.new()
	pole.top_radius = 0.04
	pole.bottom_radius = 0.05
	pole.height = POLE_HEIGHT_M
	pole.radial_segments = 6
	pole.rings = 1
	var cloth := PlaneMesh.new()
	cloth.size = CLOTH_SIZE
	cloth.orientation = PlaneMesh.FACE_Z
	cloth.center_offset = Vector3(CLOTH_SIZE.x * 0.5, -CLOTH_SIZE.y * 0.5, 0.0)
	cloth.subdivide_width = 8
	cloth.subdivide_depth = 1
	_meshes = [_baked(pole), _baked(cloth)]
	var pole_am: ArrayMesh = _meshes[0]
	var cloth_am: ArrayMesh = _meshes[1]
	for i in range(MAX_FLAGS):
		var root := Node3D.new()
		root.name = "Flag_%d" % i
		root.visible = false
		add_child(root)
		var pm := MeshInstance3D.new()
		pm.mesh = pole_am
		pm.material_override = pole_mat
		pm.position = Vector3(0.0, POLE_HEIGHT_M * 0.5, 0.0)
		root.add_child(pm)
		var holder := Node3D.new()
		holder.position = Vector3(0.0, POLE_HEIGHT_M, 0.0)
		root.add_child(holder)
		var cm := MeshInstance3D.new()
		cm.mesh = cloth_am
		cm.material_override = _material
		holder.add_child(cm)
		_roots.append(root)
		_cloth_nodes.append(holder)


func set_points(points: Array) -> void:
	flag_positions = positions_for(points)
	for i in range(MAX_FLAGS):
		var on := i < flag_positions.size()
		_roots[i].visible = on
		if on:
			_roots[i].position = flag_positions[i]


func visible_count() -> int:
	return mini(flag_positions.size(), MAX_FLAGS)


## Cap courant du tissu (rad), le même pour tous les drapeaux (tests).
func current_yaw() -> float:
	return _yaw


func update(wind: Dictionary, dt_s: float) -> void:
	var t0 := Time.get_ticks_usec()
	var dir: Vector3 = wind.get("dir", Vector3.ZERO)
	if Vector2(dir.x, dir.z).length() > 1e-3:
		var target := cloth_yaw(dir)
		_yaw += wrapf(target - _yaw, -PI, PI) * (1.0 - exp(-maxf(dt_s, 0.0) / TURN_TAU_S))
	_material.set_shader_parameter("strength", float(wind.get("strength", 0.0)))
	_material.set_shader_parameter("gust", float(wind.get("gust", 0.0)))
	_material.set_shader_parameter("phase", float(wind.get("phase", 0.0)))
	var n := visible_count()
	for i in range(n):
		_cloth_nodes[i].rotation = Vector3(0.0, _yaw, 0.0)
	last_update_usec = Time.get_ticks_usec() - t0

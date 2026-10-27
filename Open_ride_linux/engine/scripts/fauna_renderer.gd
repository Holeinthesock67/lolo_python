extends Node3D

## Affichage des animaux du Lot P11 : un MultiMeshInstance3D par espèce (oiseau, vache, mouton,
## chevreuil), maillages bas en polygones construits par code, animés par shaders/fauna.gdshader.
## Pas de class_name : charger par preload("res://scripts/fauna_renderer.gd").
##
## - `set_preset(name, enabled)` : budgets `living(preset).birds` et `.animals` (P4).
## - `set_chunk(k, groups)` / `remove_chunk(k)` : groupes de fauna_placer.gd d'un tronçon.
## - `update(cam_pos, rider_pos, now_s)` une fois par image : comportements (fauna_behaviour.gd), puis
##   transformées des seules bêtes gardées. Les plus proches de la caméra sont gardées, dans la limite
##   du budget ; le tri est refait quand la caméra a bougé de RESELECT_M ou que les groupes changent.
##   Oiseaux et chevreuils sont mis à jour à chaque image, le bétail (rotation lente) par quart, une
##   image sur HERD_UPDATE_EVERY chacun ; un chevreuil disparu est réduit à rien jusqu'au tri suivant.
## Tous les nœuds sont créés à l'initialisation ; aucun n'est créé ensuite.

const FaunaBehaviour := preload("res://scripts/fauna_behaviour.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const FaunaShader := preload("res://shaders/fauna.gdshader")

const SPECIES := ["bird", "cow", "sheep", "deer"]
const ALBEDO := {
	"bird": Color(0.12, 0.12, 0.14),
	"cow": Color(0.55, 0.42, 0.32),
	"sheep": Color(0.86, 0.84, 0.78),
	"deer": Color(0.52, 0.34, 0.2),
}
const RESELECT_M := 20.0
const HERD_UPDATE_EVERY := 4

var behaviour := FaunaBehaviour.new()
var budget_birds := 12
var budget_animals := 20
var last_update_usec := 0

var _chunks: Dictionary = {}          # k -> Array de groupes
var _dirty := true
var _last_select_pos := Vector3(INF, INF, INF)
var _mmi: Dictionary = {}             # espèce -> MultiMeshInstance3D
var _sel_birds: Array[Vector2i] = []  # (indice du groupe, indice de l'oiseau)
var _sel_animals: Array[Vector2i] = []   # (indice du groupe, indice de la bête ; -1 pour un chevreuil)
var _slots: PackedInt32Array = PackedInt32Array()   # case de chaque bête gardée dans son MultiMesh
var _now_s := 0.0
var _frame := 0


func _init() -> void:
	for sp in SPECIES:
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_custom_data = true
		mm.mesh = build_mesh(sp)
		mm.instance_count = 0
		var mat := ShaderMaterial.new()
		mat.shader = FaunaShader
		mat.set_shader_parameter("mode", 0 if sp == "bird" else 1)
		mat.set_shader_parameter("albedo", ALBEDO[sp])
		var mmi := MultiMeshInstance3D.new()
		mmi.name = "Fauna_%s" % sp
		mmi.multimesh = mm
		mmi.material_override = mat
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mmi)
		_mmi[sp] = mmi
	set_preset(QualityPresets.DEFAULT_PRESET)


func set_preset(preset_name: String, enabled: bool = true) -> void:
	var living := QualityPresets.living(preset_name, enabled)
	budget_birds = int(living.get("birds", 0))
	budget_animals = int(living.get("animals", 0))
	_mmi["bird"].multimesh.instance_count = budget_birds
	for sp in ["cow", "sheep", "deer"]:
		_mmi[sp].multimesh.instance_count = budget_animals
	_dirty = true


func set_chunk(k: int, groups: Array) -> void:
	_chunks[k] = groups
	_rebuild_groups()


func remove_chunk(k: int) -> void:
	if _chunks.erase(k):
		_rebuild_groups()


func clear() -> void:
	_chunks.clear()
	_rebuild_groups()


func _rebuild_groups() -> void:
	var all := []
	var keys := _chunks.keys()
	keys.sort()
	for k in keys:
		all.append_array(_chunks[k])
	behaviour.setup(all)
	_dirty = true


## Nombre d'instances affichées de l'espèce `sp`.
func visible_count(sp: String) -> int:
	return _mmi[sp].multimesh.visible_instance_count if _mmi.has(sp) else 0


func _select(cam_pos: Vector3) -> void:
	var birds := []
	var animals := []
	var groups: Array = behaviour.groups
	for gi in range(groups.size()):
		var g: Dictionary = groups[gi]
		match str(g["type"]):
			"birds":
				var c: Vector3 = g["center"]
				var d := c.distance_squared_to(cam_pos)
				for i in range((g["members"] as Array).size()):
					birds.append([d, gi, i])
			"herd":
				var members: Array = g["members"]
				for i in range(members.size()):
					animals.append([(members[i]["pos"] as Vector3).distance_squared_to(cam_pos), gi, i])
			"deer":
				if str(g.get("state", "idle")) != "gone":
					animals.append([(g["pos"] as Vector3).distance_squared_to(cam_pos), gi, -1])
	var by_dist := func(a, b): return a[0] < b[0] or (a[0] == b[0] and (a[1] < b[1] or (a[1] == b[1] and a[2] < b[2])))
	birds.sort_custom(by_dist)
	animals.sort_custom(by_dist)
	_sel_birds.clear()
	var mm_b: MultiMesh = _mmi["bird"].multimesh
	for j in range(mini(budget_birds, birds.size())):
		var gi: int = birds[j][1]
		var i: int = birds[j][2]
		_sel_birds.append(Vector2i(gi, i))
		mm_b.set_instance_custom_data(j, Color(float(groups[gi]["members"][i]["phase"]) / TAU, 0.0, 0.0, 0.0))
	mm_b.visible_instance_count = _sel_birds.size()
	# Chaque bête gardée reçoit une case fixe de son espèce jusqu'au tri suivant.
	_sel_animals.clear()
	_slots.clear()
	var used := {"cow": 0, "sheep": 0, "deer": 0}
	for j in range(mini(budget_animals, animals.size())):
		var gi: int = animals[j][1]
		var i: int = animals[j][2]
		var g: Dictionary = groups[gi]
		var sp: String = "deer" if i < 0 else str(g["species"])
		var slot: int = used[sp]
		used[sp] = slot + 1
		_sel_animals.append(Vector2i(gi, i))
		_slots.append(slot)
		var mm: MultiMesh = _mmi[sp].multimesh
		if i >= 0:
			var m: Dictionary = g["members"][i]
			mm.set_instance_custom_data(slot, Color(fposmod(float(m["yaw"]), 1.0), 0.0, 0.0, 0.0))
			mm.set_instance_transform(slot, Transform3D(Basis(Vector3.UP, FaunaBehaviour.herd_yaw(m, _now_s)), m["pos"]))
	for sp in used:
		_mmi[sp].multimesh.visible_instance_count = used[sp]
	_last_select_pos = cam_pos
	_dirty = false


func update(cam_pos: Vector3, rider_pos: Vector3, now_s: float) -> void:
	var t0 := Time.get_ticks_usec()
	_now_s = now_s
	behaviour.update(rider_pos, now_s)
	if _dirty or cam_pos.distance_to(_last_select_pos) > RESELECT_M:
		_select(cam_pos)
	var groups: Array = behaviour.groups

	var mm_b: MultiMesh = _mmi["bird"].multimesh
	for j in range(_sel_birds.size()):
		var s := _sel_birds[j]
		var g: Dictionary = groups[s.x]
		var basis := Basis(Vector3.UP, FaunaBehaviour.bird_yaw(g, s.y, now_s))
		mm_b.set_instance_transform(j, Transform3D(basis, FaunaBehaviour.bird_position(g, s.y, now_s)))

	# Chevreuils à chaque image ; bétail (rotation lente) par quart, une image sur quatre chacun.
	_frame += 1
	var mm_d: MultiMesh = _mmi["deer"].multimesh
	for j in range(_sel_animals.size()):
		var s := _sel_animals[j]
		var g: Dictionary = groups[s.x]
		if s.y < 0:
			var alpha := FaunaBehaviour.deer_alpha(g, now_s)
			var idle := str(g["state"]) == "idle"
			var fd: Vector3 = g["flee_dir"]
			var yaw := float(g["yaw"]) if idle else atan2(fd.x, fd.z)
			mm_d.set_instance_transform(_slots[j], Transform3D(Basis(Vector3.UP, yaw).scaled(Vector3.ONE * maxf(alpha, 0.001)),
				FaunaBehaviour.deer_position(g, now_s) - (Vector3.ZERO if alpha > 0.0 else Vector3(0.0, 50.0, 0.0))))
			mm_d.set_instance_custom_data(_slots[j], Color(0.3, 0.0 if idle else 1.0, 0.0, 0.0))
		elif (j + _frame) % HERD_UPDATE_EVERY == 0:
			var m: Dictionary = g["members"][s.y]
			var mm: MultiMesh = _mmi[str(g["species"])].multimesh
			mm.set_instance_transform(_slots[j], Transform3D(Basis(Vector3.UP, FaunaBehaviour.herd_yaw(m, now_s)), m["pos"]))
	last_update_usec = Time.get_ticks_usec() - t0


# --- maillages bas en polygones -------------------------------------------------------------

static func _box(st: SurfaceTool, c: Vector3, size: Vector3, uv: Vector2) -> void:
	var h := size * 0.5
	var corners := [
		c + Vector3(-h.x, -h.y, -h.z), c + Vector3(h.x, -h.y, -h.z), c + Vector3(h.x, h.y, -h.z), c + Vector3(-h.x, h.y, -h.z),
		c + Vector3(-h.x, -h.y, h.z), c + Vector3(h.x, -h.y, h.z), c + Vector3(h.x, h.y, h.z), c + Vector3(-h.x, h.y, h.z),
	]
	var faces := [[0, 1, 2, 3], [5, 4, 7, 6], [4, 0, 3, 7], [1, 5, 6, 2], [3, 2, 6, 7], [4, 5, 1, 0]]
	for f in faces:
		for idx in [f[0], f[1], f[2], f[0], f[2], f[3]]:
			st.set_uv(uv)
			st.set_color(Color.WHITE)
			st.add_vertex(corners[idx])


static func _tri(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, uv_a: Vector2, uv_bc: Vector2) -> void:
	st.set_uv(uv_a)
	st.set_color(Color.WHITE)
	st.add_vertex(a)
	st.set_uv(uv_bc)
	st.set_color(Color.WHITE)
	st.add_vertex(b)
	st.set_uv(uv_bc)
	st.set_color(Color.WHITE)
	st.add_vertex(c)


## Maillage d'une espèce (`bird`, `cow`, `sheep`, `deer`), avant vers +z, pieds à y = 0.
static func build_mesh(sp: String) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	if sp == "bird":
		_box(st, Vector3.ZERO, Vector3(0.12, 0.1, 0.4), Vector2.ZERO)
		_tri(st, Vector3(0.05, 0.0, 0.1), Vector3(0.45, 0.0, -0.05), Vector3(0.05, 0.0, -0.12), Vector2(0.0, 0.0), Vector2(1.0, 0.0))
		_tri(st, Vector3(-0.05, 0.0, 0.1), Vector3(-0.05, 0.0, -0.12), Vector3(-0.45, 0.0, -0.05), Vector2(0.0, 0.0), Vector2(1.0, 0.0))
	else:
		var dims: Dictionary = {
			"cow": {"body": Vector3(0.8, 0.75, 1.9), "leg": 0.7, "head": Vector3(0.35, 0.4, 0.5)},
			"sheep": {"body": Vector3(0.6, 0.55, 1.0), "leg": 0.4, "head": Vector3(0.22, 0.25, 0.3)},
			"deer": {"body": Vector3(0.4, 0.45, 1.1), "leg": 0.75, "head": Vector3(0.18, 0.22, 0.3)},
		}[sp]
		var body: Vector3 = dims["body"]
		var leg: float = dims["leg"]
		var head: Vector3 = dims["head"]
		var by := leg + body.y * 0.5
		_box(st, Vector3(0.0, by, 0.0), body, Vector2.ZERO)
		for lx in [-1.0, 1.0]:
			for lz in [-1.0, 1.0]:
				_box(st, Vector3(lx * body.x * 0.3, leg * 0.5, lz * body.z * 0.38), Vector3(0.12, leg, 0.12), Vector2.ZERO)
		_box(st, Vector3(0.0, by + body.y * 0.35, body.z * 0.5 + head.z * 0.4), head, Vector2(0.0, 1.0))
	st.generate_normals()
	return st.commit()

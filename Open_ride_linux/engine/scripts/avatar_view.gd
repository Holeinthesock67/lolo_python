extends Node3D

## Avatar du cycliste à l'écran (lot V6) : assemble les maillages de avatar_mesh.gd, les colore selon les
## réglages du profil (palettes de avatar_model.gd) et les anime à chaque image d'après avatar_model.gd
## (pédalier à la cadence réelle, danseuse). Ne décide rien : affiche l'état du modèle.
##
## - `apply(model)` : place jambes, bras, tronc, tête, pédales et roues pour l'angle de pédalier et la
##   position du modèle ; en danseuse le vélo se balance d'un côté à l'autre au rythme du pédalier.
## - `set_visible_for_view(view)` : caché en vue subjective (la caméra est dans la tête), visible ailleurs
##   (vues de caméra du lot V12 et caméra de contrôle du banc visuel).
## - `set_lod(n)` : 0 cycliste, 1 intermédiaire, 2 allégé des bots ; reconstruit les nœuds.
## Pas de class_name : charger par preload("res://scripts/avatar_view.gd").

const AvatarModel := preload("res://scripts/avatar_model.gd")
const AvatarMesh := preload("res://scripts/avatar_mesh.gd")

const SWAY_RAD := 0.07
const FRAME_COLOR := Color(0.16, 0.17, 0.20)
const TYRE_COLOR := Color(0.05, 0.05, 0.06)
const SHOE_COLOR := Color(0.12, 0.12, 0.14)

var lod := 0
var settings: Dictionary = AvatarModel.DEFAULTS.duplicate()
var view := "subjective"

var _dims: Dictionary = {}
var _bike: Node3D          # vélo seul : se balance en danseuse
var _rig: Node3D           # cycliste et vélo
var _nodes := {}           # nom → MeshInstance3D (ou liste pour les pièces doubles)
var _number: Label3D
var _mats := {}


func _init() -> void:
	name = "AvatarView"
	visible = AvatarModel.visible_in_view(view)


## Réglages complets (avatar_model.gd parse_settings) : reconstruit l'apparence.
func configure(new_settings: Dictionary, new_lod := 0) -> void:
	settings = new_settings
	lod = clampi(new_lod, 0, 2)
	_rebuild()


func set_lod(n: int) -> void:
	if n != lod:
		lod = clampi(n, 0, 2)
		_rebuild()


func set_visible_for_view(new_view: String) -> void:
	view = new_view
	visible = AvatarModel.visible_in_view(view)


func _mat(color: Color) -> StandardMaterial3D:
	var key := color.to_html()
	if not _mats.has(key):
		var m := StandardMaterial3D.new()
		m.albedo_color = color
		m.roughness = 0.8
		_mats[key] = m
	return _mats[key]


func _add(part: String, mesh: Mesh, color: Color, parent: Node3D) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = _mat(color)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if lod >= 1 else GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	parent.add_child(mi)
	if _nodes.has(part):
		if not (_nodes[part] is Array):
			_nodes[part] = [_nodes[part]]
		_nodes[part].append(mi)
	else:
		_nodes[part] = mi
	return mi


func _rebuild() -> void:
	if _rig != null:
		remove_child(_rig)
		_rig.queue_free()
	_nodes.clear()
	_dims = AvatarMesh.dims(settings)
	_rig = Node3D.new()
	_rig.name = "Rig"
	add_child(_rig)
	_bike = Node3D.new()
	_bike.name = "Bike"
	_rig.add_child(_bike)
	var parts := AvatarMesh.build(lod, _dims)
	var skin: Color = AvatarModel.SKIN_COLORS[int(settings["skin"])]
	var hair: Color = AvatarModel.HAIR_COLORS[int(settings["hair_color"])]
	var primary: Color = AvatarModel.KIT_COLORS[int(settings["kit_primary"])]
	var secondary: Color = AvatarModel.KIT_COLORS[int(settings["kit_secondary"])]
	var skin_parts := ["head"]
	for part in parts:
		var mesh: Mesh = parts[part]["mesh"]
		var n := int(parts[part]["count"])
		var color := FRAME_COLOR
		var parent: Node3D = _bike
		match part:
			"torso", "upper_arm": color = primary; parent = _rig
			"thigh", "pelvis": color = secondary; parent = _rig
			"shin", "forearm": color = skin; parent = _rig
			"head": color = skin; parent = _rig
			"helmet": color = secondary; parent = _rig
			"hair": color = hair; parent = _rig
			"shoe": color = SHOE_COLOR; parent = _rig
			"tyre", "rim": color = TYRE_COLOR if part == "tyre" else Color(0.55, 0.57, 0.60)
		for i in range(n):
			_add(part, mesh, color, parent)
	_number = null
	if lod == 0:
		_number = Label3D.new()
		_number.name = "Number"
		_number.text = str(int(settings["number"]))
		_number.pixel_size = 0.0016
		_number.font_size = 64
		_number.modulate = AvatarModel.KIT_COLORS[int(settings["kit_secondary"])]
		_number.visible = int(settings["number"]) > 0
		_rig.add_child(_number)
	# Roues et cadre : positions fixes (le pédalier et la danseuse ne les déplacent pas).
	var tyres := _list("tyre")
	var rims := _list("rim")
	for i in range(tyres.size()):
		var z := AvatarMesh.WHEEL_BASE * 0.5 * (-1.0 if i == 0 else 1.0)
		tyres[i].transform = Transform3D(Basis(Vector3.BACK, PI / 2.0), Vector3(0.0, AvatarMesh.WHEEL_R, z))
		if i < rims.size():
			rims[i].transform = Transform3D(Basis(Vector3.BACK, PI / 2.0), Vector3(0.0, AvatarMesh.WHEEL_R, z))
	var frames := _list("frame")
	var tubes := [[Vector3(0.0, 0.70, 0.25), Vector3(0.0, 0.72, -0.30)],
		[Vector3(0.0, 0.72, -0.30), AvatarMesh.BB], [AvatarMesh.BB, Vector3(0.0, 0.70, 0.25)]]
	for i in range(frames.size()):
		var tf := AvatarMesh.segment_transform(tubes[i][0], tubes[i][1])
		var length: float = (tubes[i][1] - tubes[i][0]).length()
		frames[i].transform = Transform3D(tf.basis.scaled(Vector3(1.0, length, 1.0)), tf.origin)
	for m in _list("saddle"):
		m.position = Vector3(0.0, 0.72, 0.25)
	for m in _list("bar"):
		m.position = AvatarMesh.BAR
	apply_pose(0.0, false)


func _list(part: String) -> Array:
	var v = _nodes.get(part)
	if v == null:
		return []
	return v if v is Array else [v]


## Place l'avatar pour l'état du modèle (angle de pédalier et position).
func apply(model) -> void:
	apply_pose(float(model.crank_angle), bool(model.standing))


func apply_pose(angle: float, standing: bool) -> void:
	if _rig == null:
		return
	var p := AvatarMesh.pose(angle, standing, _dims)
	_place("torso", [[p["hip"], p["shoulder"]]])
	_place("thigh", [[p["hip_r"], p["knee_r"]], [p["hip_l"], p["knee_l"]]])
	_place("shin", [[p["knee_r"], p["ankle_r"]], [p["knee_l"], p["ankle_l"]]])
	_place("upper_arm", [[p["shoulder_r"], p["elbow_r"]], [p["shoulder_l"], p["elbow_l"]]])
	_place("forearm", [[p["elbow_r"], p["hand_r"]], [p["elbow_l"], p["hand_l"]]])
	for m in _list("head"):
		m.position = p["head"]
	for m in _list("helmet"):
		m.position = p["head"] + Vector3(0.0, 0.025, 0.012)
	for m in _list("hair"):
		m.position = p["head"] + Vector3(0.0, -0.01, 0.025)
		m.visible = int(settings["hair"]) > 0
		m.scale = Vector3.ONE * [1.0, 0.9, 1.0, 1.1, 1.0, 1.25][int(settings["hair"])]
	for m in _list("pelvis"):
		m.position = p["hip"]
	var shoes := _list("shoe")
	var crank := _list("crank")
	for i in range(shoes.size()):
		var side := 1 if i == 0 else -1
		var pedal := AvatarMesh.pedal_pos(angle, side)
		shoes[i].position = pedal + Vector3(0.0, 0.035, -0.04)
	for i in range(crank.size()):
		var side := 1 if i == 0 else -1
		var pedal2 := AvatarMesh.pedal_pos(angle, side)
		crank[i].transform = AvatarMesh.segment_transform(Vector3(side * AvatarMesh.PEDAL_HALF_X, AvatarMesh.BB.y, 0.0), pedal2)
	if _number != null:
		var lean := AvatarMesh.STANDING_LEAN if standing else AvatarMesh.SEATED_LEAN
		_number.position = p["hip"].lerp(p["shoulder"], 0.55) + Vector3(0.0, sin(lean), cos(lean)) * (float(_dims["r_torso"]) + 0.012)
		_number.rotation = Vector3(-lean, 0.0, 0.0)
	# Danseuse : le vélo se balance d'un côté à l'autre, au rythme du pédalier (une oscillation par tour).
	_bike.rotation.z = sin(angle) * SWAY_RAD if standing else 0.0
	_rig.rotation.z = sin(angle) * SWAY_RAD * 0.35 if standing else 0.0


func _place(part: String, ends: Array) -> void:
	var nodes := _list(part)
	for i in range(mini(nodes.size(), ends.size())):
		nodes[i].transform = AvatarMesh.segment_transform(ends[i][0], ends[i][1])


## Pour les tests : triangles affichés (nœuds visibles) et nombre de nœuds.
func test_info() -> Dictionary:
	var tris := 0
	var count := 0
	for part in _nodes:
		for mi in _list(part):
			var m: MeshInstance3D = mi
			if m.mesh != null and m.visible:
				tris += AvatarMesh.triangles_of(m.mesh)
				count += 1
	return {"triangles": tris, "nodes": count, "visible": visible, "lod": lod, "view": view,
		"hip_y": (AvatarMesh.pose(0.0, false, _dims)["hip"] as Vector3).y}

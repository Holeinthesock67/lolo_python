extends Node3D

## Avatar du cycliste à l'écran (lots V6 et V7) : assemble les maillages de avatar_mesh.gd et de
## equipment_meshes.gd, les colore selon les réglages du profil (palettes de avatar_model.gd) et l'équipement
## choisi (`look` de chaque pièce), et les anime à chaque image d'après avatar_model.gd (pédalier à la
## cadence réelle, danseuse). Ne décide rien : affiche l'état du modèle.
##
## - `apply(model)` : place jambes, bras, tronc, tête, pédales pour l'angle de pédalier et la position du
##   modèle ; en danseuse le vélo se balance d'un côté à l'autre au rythme du pédalier.
## - `set_equipment(looks)` : `look` résolu par emplacement (equipment_meshes.gd equip_looks) ; reconstruit.
## - `set_speed(kmh)` : au-dessus de AIR_STREAK_KMH, quelques traînées d'air translucides le long de l'avatar.
## - `set_visible_for_view(view)` : caché en vue subjective (la caméra est dans la tête), visible ailleurs
##   (vues de caméra du lot V12 et caméra de contrôle du banc visuel) ; les traînées suivent.
## - `set_lod(n)` : 0 cycliste, 1 intermédiaire, 2 allégé des bots (sans équipement détaillé).
## Pas de class_name : charger par preload("res://scripts/avatar_view.gd").

const AvatarModel := preload("res://scripts/avatar_model.gd")
const AvatarMesh := preload("res://scripts/avatar_mesh.gd")
const EquipmentMeshes := preload("res://scripts/equipment_meshes.gd")

const SWAY_RAD := 0.07
const FRAME_COLOR := Color(0.16, 0.17, 0.20)
const TYRE_COLOR := Color(0.05, 0.05, 0.06)
const SHOE_COLOR := Color(0.12, 0.12, 0.14)
const STREAK_COUNT := 6
const STREAK_LENGTH_M := 1.6
const STREAK_PERIOD_S := 0.5

var lod := 0
var settings: Dictionary = AvatarModel.DEFAULTS.duplicate()
var looks: Dictionary = EquipmentMeshes.DEFAULT_LOOK.duplicate()
var view := "subjective"

var _dims: Dictionary = {}
var _frame_spec: Dictionary = {}
var _bike: Node3D          # vélo seul : se balance en danseuse
var _rig: Node3D           # cycliste et vélo
var _streaks: Node3D
var _speed_kmh := 0.0
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


## Équipement résolu par emplacement (equipment_meshes.gd equip_looks) ; reconstruit si rien n'a changé de look.
func set_equipment(new_looks: Dictionary) -> void:
	var resolved := {}
	for slot in EquipmentMeshes.LOOKS:
		resolved[slot] = EquipmentMeshes.resolve(slot, new_looks.get(slot))
	if resolved != looks:
		looks = resolved
		_rebuild()


func set_lod(n: int) -> void:
	if n != lod:
		lod = clampi(n, 0, 2)
		_rebuild()


func set_visible_for_view(new_view: String) -> void:
	view = new_view
	visible = AvatarModel.visible_in_view(view)


## Vitesse (km/h) : traînées d'air au-delà de EquipmentMeshes.AIR_STREAK_KMH, défilant vers l'arrière.
func set_speed(kmh: float, now_s := 0.0) -> void:
	_speed_kmh = kmh
	if _streaks == null:
		return
	var on := kmh >= EquipmentMeshes.AIR_STREAK_KMH and lod <= 1
	_streaks.visible = on
	if on:
		var phase := fmod(now_s / STREAK_PERIOD_S, 1.0)
		for i in range(_streaks.get_child_count()):
			var s: Node3D = _streaks.get_child(i)
			var base: Vector3 = s.get_meta("base")
			s.position = base + Vector3(0.0, 0.0, fmod(phase + float(i) / STREAK_COUNT, 1.0) * 1.2)


func _mat(color: Color, texture: Texture2D = null, emissive := false, metallic := 0.0) -> StandardMaterial3D:
	var key := "%s|%s|%s|%s" % [color.to_html(true), texture.get_rid().get_id() if texture != null else 0, emissive, metallic]
	if not _mats.has(key):
		var m := StandardMaterial3D.new()
		m.albedo_color = color
		m.roughness = 0.8 if metallic == 0.0 else 0.25
		m.metallic = metallic
		if texture != null:
			m.albedo_texture = texture
			m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
		if emissive:
			m.emission_enabled = true
			m.emission = color
			m.emission_energy_multiplier = 0.6
		if color.a < 1.0:
			m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		_mats[key] = m
	return _mats[key]


func _add(part: String, mesh: Mesh, material: Material, parent: Node3D) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = material
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
	_frame_spec = EquipmentMeshes.frame_spec(str(looks["frame"]))
	_rig = Node3D.new()
	_rig.name = "Rig"
	add_child(_rig)
	_bike = Node3D.new()
	_bike.name = "Bike"
	_rig.add_child(_bike)
	var parts := AvatarMesh.build(lod, _dims, looks)
	var skin: Color = AvatarModel.SKIN_COLORS[int(settings["skin"])]
	var hair: Color = AvatarModel.HAIR_COLORS[int(settings["hair_color"])]
	var primary: Color = AvatarModel.KIT_COLORS[int(settings["kit_primary"])]
	var secondary: Color = AvatarModel.KIT_COLORS[int(settings["kit_secondary"])]
	var detailed := lod <= 1
	var kit_look := str(looks["kit"])
	var kit_mat: StandardMaterial3D = _mat(Color.WHITE, EquipmentMeshes.kit_texture(kit_look, primary, secondary),
		EquipmentMeshes.is_emissive_kit(kit_look)) if detailed else _mat(primary)
	if detailed and EquipmentMeshes.is_emissive_kit(kit_look):
		kit_mat.emission = primary
	var ws := EquipmentMeshes.wheel_spec(str(looks["wheels"]))
	var hs := EquipmentMeshes.helmet_spec(str(looks["helmet"]))
	var ss := EquipmentMeshes.socks_spec(str(looks["socks"]))
	var gs := EquipmentMeshes.glasses_spec(str(looks["glasses"]))
	var sock_mat := _mat(ss["color"], EquipmentMeshes.kit_texture("kit_stripes", Color.WHITE, secondary) if ss["striped"] else null)
	for part in parts:
		var mesh: Mesh = parts[part]["mesh"]
		var n := int(parts[part]["count"])
		var mat: Material = _mat(FRAME_COLOR)
		var parent: Node3D = _bike
		match part:
			"torso", "upper_arm": mat = kit_mat if detailed else _mat(primary); parent = _rig
			"thigh", "pelvis": mat = _mat(secondary); parent = _rig
			"shin", "forearm", "head": mat = _mat(skin); parent = _rig
			"helmet": mat = _mat(secondary if hs["color_kit"] else Color(0.92, 0.92, 0.94)); parent = _rig
			"visor": mat = _mat(Color(0.08, 0.08, 0.1)); parent = _rig
			"hair": mat = _mat(hair); parent = _rig
			"shoe": mat = _mat(SHOE_COLOR); parent = _rig
			"sock": mat = sock_mat; parent = _rig
			"glasses": mat = _mat(gs["color"], null, false, float(gs["metallic"])); parent = _rig
			"frame", "extension": mat = _mat(_frame_spec["color"])
			"pad": mat = _mat(Color(0.08, 0.08, 0.1))
			"tyre": mat = _mat(TYRE_COLOR)
			"rim", "spoke": mat = _mat(ws["color"] if part == "rim" else Color(0.7, 0.72, 0.75))
			_: mat = _mat(FRAME_COLOR)
		for i in range(n):
			_add(part, mesh, mat, parent)
	_number = null
	if lod == 0:
		_number = Label3D.new()
		_number.name = "Number"
		_number.text = str(int(settings["number"]))
		_number.pixel_size = 0.0016
		_number.font_size = 64
		_number.modulate = secondary
		_number.visible = int(settings["number"]) > 0
		_rig.add_child(_number)
	_place_bike(ws)
	_build_streaks()
	apply_pose(0.0, false)


## Cadre, roues, selle et cintre : positions fixes (le pédalier et la danseuse ne les déplacent pas).
func _place_bike(ws: Dictionary) -> void:
	var hub_z := AvatarMesh.WHEEL_BASE * 0.5
	var tyres := _list("tyre")
	var rims := _list("rim")
	var wheel_rot := Basis(Vector3.BACK, PI / 2.0)
	for i in range(maxi(tyres.size(), rims.size())):
		var z := hub_z * (-1.0 if i == 0 else 1.0)
		var center := Vector3(0.0, AvatarMesh.WHEEL_R, z)
		if i < tyres.size():
			tyres[i].transform = Transform3D(wheel_rot, center)
		if i < rims.size():
			rims[i].transform = Transform3D(wheel_rot, center)
	var spokes := _list("spoke")
	var per_wheel := spokes.size() / 2
	for i in range(spokes.size()):
		var wheel := i / maxi(per_wheel, 1)
		var k := i % maxi(per_wheel, 1)
		var theta := TAU * float(k) / float(per_wheel) + (0.0 if wheel == 0 else 0.15)
		var center := Vector3(0.0, AvatarMesh.WHEEL_R, hub_z * (-1.0 if wheel == 0 else 1.0))
		var len_m := AvatarMesh.WHEEL_R - 0.05
		var dir := Vector3(0.0, cos(theta), sin(theta))
		spokes[i].transform = Transform3D(Basis(Vector3.RIGHT, theta), center + dir * len_m * 0.5)
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
	var bar_half := float(_frame_spec.get("bar_half_x", AvatarMesh.BAR_HALF_X))
	var bar_z := float(_frame_spec.get("bar_z", AvatarMesh.BAR.z))
	var ext := _list("extension")
	for i in range(ext.size()):
		var side := 1.0 if i == 0 else -1.0
		ext[i].transform = AvatarMesh.segment_transform(Vector3(side * bar_half, AvatarMesh.BAR.y, bar_z + 0.34),
			Vector3(side * bar_half, AvatarMesh.BAR.y, bar_z))
	var pads := _list("pad")
	for i in range(pads.size()):
		var side := 1.0 if i == 0 else -1.0
		pads[i].position = Vector3(side * bar_half, AvatarMesh.BAR.y - 0.04, bar_z + 0.22)


func _build_streaks() -> void:
	_streaks = null
	if lod > 1:
		return
	_streaks = Node3D.new()
	_streaks.name = "AirStreaks"
	_streaks.visible = false
	_rig.add_child(_streaks)
	var mat := _mat(Color(1.0, 1.0, 1.0, 0.28))
	var mesh := BoxMesh.new()
	mesh.size = Vector3(0.012, 0.012, STREAK_LENGTH_M)
	for i in range(STREAK_COUNT):
		var s := MeshInstance3D.new()
		s.mesh = mesh
		s.material_override = mat
		s.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var side := -1.0 if i % 2 == 0 else 1.0
		var base := Vector3(side * (0.45 + 0.08 * (i / 2)), 0.55 + 0.25 * (i % 3), 0.3)
		s.set_meta("base", base)
		s.position = base
		_streaks.add_child(s)


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
	var p := AvatarMesh.pose(angle, standing, _dims, _frame_spec)
	_place("torso", [[p["hip"], p["shoulder"]]])
	_place("thigh", [[p["hip_r"], p["knee_r"]], [p["hip_l"], p["knee_l"]]])
	_place("shin", [[p["knee_r"], p["ankle_r"]], [p["knee_l"], p["ankle_l"]]])
	_place("upper_arm", [[p["shoulder_r"], p["elbow_r"]], [p["shoulder_l"], p["elbow_l"]]])
	_place("forearm", [[p["elbow_r"], p["hand_r"]], [p["elbow_l"], p["hand_l"]]])
	var socks := EquipmentMeshes.socks_spec(str(looks["socks"]))
	var sock_nodes := _list("sock")
	for i in range(sock_nodes.size()):
		var side := "r" if i == 0 else "l"
		var ankle: Vector3 = p["ankle_" + side]
		var knee: Vector3 = p["knee_" + side]
		sock_nodes[i].transform = AvatarMesh.segment_transform(ankle, ankle + (knee - ankle) * float(socks["length"]))
	for m in _list("head"):
		m.position = p["head"]
	var hs := EquipmentMeshes.helmet_spec(str(looks["helmet"]))
	for m in _list("helmet"):
		m.position = p["head"] + Vector3(0.0, 0.025, 0.012) + hs["shift"] * float(_dims["hs"])
		m.scale = hs["scale"]
	for m in _list("visor"):
		m.position = p["head"] + Vector3(0.0, 0.085 * float(_dims["hs"]), -0.095 * float(_dims["hs"]))
	for m in _list("glasses"):
		m.position = p["head"] + Vector3(0.0, 0.012, -float(_dims["r_head"]) * 0.93)
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
		shoes[i].position = AvatarMesh.pedal_pos(angle, side) + Vector3(0.0, 0.035, -0.04)
	for i in range(crank.size()):
		var side := 1 if i == 0 else -1
		crank[i].transform = AvatarMesh.segment_transform(
			Vector3(side * AvatarMesh.PEDAL_HALF_X, AvatarMesh.BB.y, 0.0), AvatarMesh.pedal_pos(angle, side))
	if _number != null:
		var lean := AvatarMesh.STANDING_LEAN if standing else AvatarMesh.SEATED_LEAN + float(_frame_spec.get("lean_add", 0.0))
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
	return {"triangles": tris, "nodes": count, "visible": visible, "lod": lod, "view": view, "looks": looks,
		"streaks": _streaks != null and _streaks.visible,
		"hip_y": (AvatarMesh.pose(0.0, false, _dims, _frame_spec)["hip"] as Vector3).y,
		"hand_z": (AvatarMesh.pose(0.0, false, _dims, _frame_spec)["hand_r"] as Vector3).z,
		"shoulder_y": (AvatarMesh.pose(0.0, false, _dims, _frame_spec)["shoulder"] as Vector3).y}

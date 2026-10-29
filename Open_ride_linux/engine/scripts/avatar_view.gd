extends Node3D

## Avatar du cycliste à l'écran (lots V6, V7 et Y16) : assemble les maillages de avatar_mesh.gd, colorés
## selon les réglages du profil (palettes de avatar_model.gd, cuites dans les couleurs de sommet) et
## l'équipement choisi (`look` de chaque pièce, equipment_meshes.gd), et les anime à chaque image d'après
## avatar_model.gd (pédalier à la cadence réelle, danseuse). Ne décide rien : affiche l'état du modèle.
## Peu de nœuds (un vélo fixe, deux roues, un pédalier, les segments du corps) et trois matériaux partagés :
## l'avatar détaillé coûte peu d'appels de dessin.
##
## - `apply(model)` : place jambes, bras, tronc, tête, pédalier et pieds pour l'angle de pédalier et la
##   position du modèle ; en danseuse le vélo se balance d'un côté à l'autre au rythme du pédalier.
## - `set_equipment(looks)` : `look` résolu par emplacement (equipment_meshes.gd equip_looks) ; reconstruit.
## - `set_speed(kmh, now_s)` : les roues tournent à la vitesse du vélo (sens de la marche, comme le
##   pédalier) ; au-dessus de AIR_STREAK_KMH, quelques traînées d'air translucides le long de l'avatar.
## - `set_visible_for_view(view)` : caché en vue subjective (la caméra est dans la tête), visible ailleurs
##   (vues de caméra du lot V12 et caméra de contrôle du banc visuel) ; les traînées suivent.
## - `set_lod(n)` : 0 cycliste, 1 intermédiaire, 2 allégé des bots (sans équipement détaillé).
## Pas de class_name : charger par preload("res://scripts/avatar_view.gd").

const AvatarModel := preload("res://scripts/avatar_model.gd")
const AvatarMesh := preload("res://scripts/avatar_mesh.gd")
const EquipmentMeshes := preload("res://scripts/equipment_meshes.gd")

const SWAY_RAD := 0.07
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
var _wheel_angle := 0.0
var _last_speed_s := -1.0
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
	var dt := clampf(now_s - _last_speed_s, 0.0, 0.25) if _last_speed_s >= 0.0 else 0.0
	_last_speed_s = now_s
	_wheel_angle = fposmod(_wheel_angle + kmh / 3.6 / AvatarMesh.WHEEL_R * dt, TAU)
	var wheels := _list("wheel")
	for i in range(wheels.size()):
		wheels[i].basis = AvatarMesh.spin_x(_wheel_angle + 0.7 * i)
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


## Matériau partagé ; les couleurs de sommet des maillages (avatar_mesh.gd) multiplient la couleur.
## `roughness` < 0 : 0,8 (mat), ou 0,25 si métallique.
func _mat(color: Color, texture: Texture2D = null, emissive := false, metallic := 0.0, roughness := -1.0) -> StandardMaterial3D:
	var key := "%s|%s|%s|%s|%s" % [color.to_html(true), texture.get_rid().get_id() if texture != null else 0, emissive, metallic, roughness]
	if not _mats.has(key):
		var m := StandardMaterial3D.new()
		m.albedo_color = color
		m.vertex_color_use_as_albedo = true
		m.roughness = roughness if roughness >= 0.0 else (0.8 if metallic == 0.0 else 0.25)
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
	var primary: Color = AvatarModel.KIT_COLORS[int(settings["kit_primary"])]
	var secondary: Color = AvatarModel.KIT_COLORS[int(settings["kit_secondary"])]
	var hs := EquipmentMeshes.helmet_spec(str(looks["helmet"]))
	var parts := AvatarMesh.build(lod, _dims, looks, {
		"skin": AvatarModel.SKIN_COLORS[int(settings["skin"])], "hair": AvatarModel.HAIR_COLORS[int(settings["hair_color"])],
		"primary": primary, "secondary": secondary,
		"helmet": secondary if hs["color_kit"] else Color(0.92, 0.92, 0.94)})
	var detailed := lod <= 1
	var kit_look := str(looks["kit"])
	var kit_mat: StandardMaterial3D = _mat(Color.WHITE, EquipmentMeshes.kit_texture(kit_look, primary, secondary),
		EquipmentMeshes.is_emissive_kit(kit_look)) if detailed else _mat(primary)
	if detailed and EquipmentMeshes.is_emissive_kit(kit_look):
		kit_mat.emission = primary
	var body := _mat(Color.WHITE)
	var gloss := _mat(Color.WHITE, null, false, 0.0, 0.35)
	var gs := EquipmentMeshes.glasses_spec(str(looks["glasses"]))
	for part in parts:
		var mesh: Mesh = parts[part]["mesh"]
		var mat: Material = body
		var parent: Node3D = _rig
		match part:
			"torso", "sleeve": mat = kit_mat
			"glasses":
				mat = _mat(gs["color"], null, false, float(gs["metallic"]))
				(mat as StandardMaterial3D).cull_mode = BaseMaterial3D.CULL_DISABLED
			"bike", "wheel", "crank": mat = gloss; parent = _bike
		for i in range(int(parts[part]["count"])):
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
	_place_bike()
	_build_streaks()
	apply_pose(0.0, false)


## Roues sur leurs axes et pédalier sur le boîtier ; le reste du vélo est un seul maillage fixe.
func _place_bike() -> void:
	var wheels := _list("wheel")
	for i in range(wheels.size()):
		wheels[i].position = AvatarMesh.FRONT_AXLE if i == 0 else AvatarMesh.REAR_AXLE
		wheels[i].basis = AvatarMesh.spin_x(_wheel_angle + 0.7 * i)
	for m in _list("crank"):
		m.position = AvatarMesh.BB


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
	_place("pelvis", [[p["hip"], p["shoulder"]]])
	_place("neck", [[p["neck"], p["chin"]]])
	_place("thigh", [[p["hip_r"], p["knee_r"]], [p["hip_l"], p["knee_l"]]])
	_place("shin", [[p["knee_r"], p["ankle_r"]], [p["knee_l"], p["ankle_l"]]])
	_place("upper_arm", [[p["shoulder_r"], p["elbow_r"]], [p["shoulder_l"], p["elbow_l"]]])
	_place("sleeve", [[p["shoulder_r"], p["elbow_r"]], [p["shoulder_l"], p["elbow_l"]]])
	_place("forearm", [[p["elbow_r"], p["hand_r"]], [p["elbow_l"], p["hand_l"]]])
	var socks := EquipmentMeshes.socks_spec(str(looks["socks"]))
	var sock_nodes := _list("sock")
	for i in range(sock_nodes.size()):
		var side := "r" if i == 0 else "l"
		var ankle: Vector3 = p["ankle_" + side]
		var knee: Vector3 = p["knee_" + side]
		sock_nodes[i].transform = AvatarMesh.segment_transform(ankle, ankle + (knee - ankle) * float(socks["length"]))
	var hands := _list("hand")
	for i in range(hands.size()):
		hands[i].position = p["hand_r" if i == 0 else "hand_l"]
	for part in ["head", "glasses", "hair"]:
		for m in _list(part):
			m.position = p["head"]
	var hs := EquipmentMeshes.helmet_spec(str(looks["helmet"]))
	for m in _list("helmet"):
		m.position = p["head"] + hs["shift"] * float(_dims["hs"])
		m.scale = hs["scale"]
	for m in _list("hair"):
		m.visible = int(settings["hair"]) > 0
		m.scale = Vector3.ONE * [1.0, 0.95, 1.0, 1.04, 1.0, 1.1][int(settings["hair"])]
	var shoes := _list("shoe")
	for i in range(shoes.size()):
		shoes[i].transform = AvatarMesh.foot_transform(angle, 1 if i == 0 else -1)
	for m in _list("crank"):
		m.basis = AvatarMesh.spin_x(angle)
	if _number != null:
		var lean := AvatarMesh.STANDING_LEAN if standing else AvatarMesh.SEATED_LEAN + float(_frame_spec.get("lean_add", 0.0))
		_number.position = p["hip"].lerp(p["shoulder"], 0.55) + Vector3(0.0, sin(lean), cos(lean)) * (AvatarMesh.BACK_DEPTH * float(_dims["bs"]) + 0.02)
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

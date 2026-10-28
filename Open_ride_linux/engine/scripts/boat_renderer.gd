extends Node3D

## Affichage de boat_model.gd (Lot P29) : maillages de boat_mesh.gd, shaders/vehicle.gdshader.
## - Petits bateaux (barque, pédalo, canoë, kayak) : un MultiMeshInstance3D par sorte, sans ombre, en mode
##   `instanced` (peinture en couleur d'instance).
## - Voiliers, péniches, ferry et porte-conteneurs : MAX_AT_ONCE nœuds de chaque sorte avec leur matériau
##   (couleurs, feux), leur sillage (shaders/wake.gdshader) et, pour le voilier, sa grand-voile qui pivote
##   autour du mât. Lecteurs 3D sur le bus Ambience : diesel des péniches (`barge_engine`), corne de brume
##   du ferry une fois par passage (`ship_horn`) de sound_player.gd.
## Pas de class_name : charger par preload("res://scripts/boat_renderer.gd").
##
## - `setup(model, sound_player)`, `set_lights(on)` ; `update()` une fois par image, après `model.update`.
## Tous les nœuds sont créés au démarrage ; aucun n'est créé ensuite.

const BoatMesh := preload("res://scripts/boat_mesh.gd")
const BoatModel := preload("res://scripts/boat_model.gd")
const VehicleShader := preload("res://shaders/vehicle.gdshader")
const WakeShader := preload("res://shaders/wake.gdshader")
const AudioMix := preload("res://scripts/audio_mix.gd")

const NODES := ["sailboat", "barge", "ferry", "cargo"]
## [son, volume (dB), taille unitaire (m), distance maximale (m)]
const SOUND := {"barge": ["barge_engine", 0.0, 12.0, 300.0], "ferry": ["ship_horn", 6.0, 300.0, 5000.0]}
const VISIBILITY_END_M := BoatModel.RANGE_M + 100.0

var model = null
var lights := false
var _sound = null
var _slots: Dictionary = {}       # sorte -> [{root, mat, sail, wake, audio, id, lights}]
var _mmi: Dictionary = {}         # petite sorte -> MultiMeshInstance3D
var _meshes: Dictionary = {}      # maillages partagés, gardés jusqu'à la fin du nœud


func _init() -> void:
	for kind in ["wake", "sail"] + NODES:
		_meshes[kind] = BoatMesh.build(kind)
	var wake_mesh: ArrayMesh = _meshes["wake"]
	var sail_mesh: ArrayMesh = _meshes["sail"]
	for kind in BoatModel.SMALL:
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.use_custom_data = true
		mm.mesh = BoatMesh.build(kind)
		mm.instance_count = BoatModel.MAX_AT_ONCE[kind]
		mm.visible_instance_count = 0
		var mat := ShaderMaterial.new()
		mat.shader = VehicleShader
		mat.set_shader_parameter("instanced", true)
		mat.set_shader_parameter("second", BoatMesh.colors(kind, 0)[1])
		var mmi := MultiMeshInstance3D.new()
		mmi.name = "Boats_%s" % kind
		mmi.multimesh = mm
		mmi.material_override = mat
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mmi.visibility_range_end = VISIBILITY_END_M
		add_child(mmi)
		_mmi[kind] = mmi
	for kind in NODES:
		var mesh: ArrayMesh = _meshes[kind]
		var list := []
		for i in range(BoatModel.MAX_AT_ONCE[kind]):
			var root := MeshInstance3D.new()
			root.name = "Boat_%s_%d" % [kind, i]
			root.mesh = mesh
			root.visible = false
			var mat := ShaderMaterial.new()
			mat.shader = VehicleShader
			root.material_override = mat
			add_child(root)
			var slot := {"root": root, "mat": mat, "sail": null, "wake": null, "audio": null, "id": "", "lights": -1.0}
			if kind == "sailboat":
				var s := MeshInstance3D.new()
				s.mesh = sail_mesh
				s.position = Vector3(0.0, BoatMesh.SAIL_FOOT_M, BoatMesh.MAST_Z)
				s.material_override = mat
				root.add_child(s)
				slot["sail"] = s
			var w := MeshInstance3D.new()
			w.mesh = wake_mesh
			w.position = Vector3(0.0, 0.0, BoatMesh.SIZE[kind].x * 0.5)
			w.scale = Vector3(BoatMesh.SIZE[kind].y, 1.0, 1.0)
			w.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			var wm := ShaderMaterial.new()
			wm.shader = WakeShader
			w.material_override = wm
			w.visible = false
			root.add_child(w)
			slot["wake"] = w
			if SOUND.has(kind):
				var audio := AudioStreamPlayer3D.new()
				audio.volume_db = SOUND[kind][1]
				audio.unit_size = SOUND[kind][2]
				audio.max_distance = SOUND[kind][3]
				audio.bus = AudioMix.bus(AudioMix.AMBIENCE)
				root.add_child(audio)
				slot["audio"] = audio
			list.append(slot)
		_slots[kind] = list


func setup(boat_model, sound_player = null) -> void:
	model = boat_model
	_sound = sound_player
	for kind in SOUND:
		for slot in _slots[kind]:
			slot["audio"].stream = _sound.stream(SOUND[kind][0]) if _sound != null else null


func set_lights(on: bool) -> void:
	lights = on


func visible_count(kind: String = "") -> int:
	var n := 0
	for k in _slots:
		if kind == "" or k == kind:
			for slot in _slots[k]:
				if slot["root"].visible:
					n += 1
	for k in _mmi:
		if kind == "" or k == kind:
			n += maxi(0, _mmi[k].multimesh.visible_instance_count)
	return n


func update() -> void:
	var used := {}
	for kind in BoatModel.MAX_AT_ONCE:
		used[kind] = 0
	var bs: Array = model.boats if model != null else []
	var lit := 1.0 if lights else 0.0
	for b in bs:
		var kind: String = b["kind"]
		var i: int = used.get(kind, 0)
		if i >= BoatModel.MAX_AT_ONCE.get(kind, 0):
			continue
		used[kind] = i + 1
		if _mmi.has(kind):
			var mm: MultiMesh = _mmi[kind].multimesh
			mm.set_instance_transform(i, b["xform"])
			mm.set_instance_color(i, BoatMesh.colors(kind, int(b["color"]))[0])
			mm.set_instance_custom_data(i, Color(0.0, 0.0, 0.0, 0.0))
			continue
		var slot: Dictionary = _slots[kind][i]
		var root: MeshInstance3D = slot["root"]
		var mat: ShaderMaterial = slot["mat"]
		var fresh: bool = slot["id"] != b["id"]
		if fresh:
			slot["id"] = b["id"]
			var col: Array = BoatMesh.colors(kind, int(b["color"]))
			mat.set_shader_parameter("paint", col[0])
			mat.set_shader_parameter("second", col[1])
		if float(slot["lights"]) != lit:
			slot["lights"] = lit
			mat.set_shader_parameter("lights", lit)
		root.transform = b["xform"]
		root.visible = true
		if slot["sail"] != null:
			(slot["sail"] as Node3D).rotation = Vector3(0.0, float(b["sail"]), 0.0)
		var trail := float(b["wake_m"])
		var w: MeshInstance3D = slot["wake"]
		w.visible = trail > 1.0
		w.scale = Vector3(BoatMesh.SIZE[kind].y, 1.0, maxf(trail, 1.0))
		var audio = slot["audio"]
		if audio != null and audio.stream != null and is_inside_tree():
			# Péniche : diesel en boucle ; ferry : corne une fois par passage
			if kind == "ferry":
				if fresh:
					audio.play()
			elif not audio.playing:
				audio.play()
	for kind in _mmi:
		_mmi[kind].multimesh.visible_instance_count = used[kind]
	for kind in NODES:
		for i in range(int(used[kind]), BoatModel.MAX_AT_ONCE[kind]):
			var slot: Dictionary = _slots[kind][i]
			if slot["root"].visible:
				slot["root"].visible = false
				slot["id"] = ""
				if slot["audio"] != null and slot["audio"].playing:
					slot["audio"].stop()

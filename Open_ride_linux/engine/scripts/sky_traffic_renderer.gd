extends Node3D

## Affichage de sky_traffic_model.gd (Lot P26) : avions de ligne et leurs traînées (shaders/vehicle_far.gdshader
## et contrail.gdshader, sans brouillard), hélicoptère et son rotor, parapentes, montgolfières
## (shaders/vehicle.gdshader), maillages de sky_mesh.gd ; un matériau par engin (couleurs, feux à éclats,
## brûleur). Lecteurs 3D : battement du rotor de l'hélicoptère, grondement lointain des avions
## (`helicopter_rotor`, `airliner_rumble` de sound_player.gd), sur le bus Ambience.
## Pas de class_name : charger par preload("res://scripts/sky_traffic_renderer.gd").
##
## - `setup(model, sound_player)` ; `update()` une fois par image, après `model.update`.
## Tous les nœuds sont créés au démarrage (POOL engins de chaque sorte) ; aucun n'est créé ensuite.

const SkyMesh := preload("res://scripts/sky_mesh.gd")
const SkyModel := preload("res://scripts/sky_traffic_model.gd")
const VehicleShader := preload("res://shaders/vehicle.gdshader")
const VehicleFarShader := preload("res://shaders/vehicle_far.gdshader")
const ContrailShader := preload("res://shaders/contrail.gdshader")
const AudioMix := preload("res://scripts/audio_mix.gd")

const POOL := SkyModel.MAX_AT_ONCE
const SOUND := {"airliner": ["airliner_rumble", 2.0, 600.0, 4000.0], "helicopter": ["helicopter_rotor", 2.0, 60.0, 1500.0]}

var model = null
var _sound = null
var _slots: Dictionary = {}       # sorte -> [{root, mat, contrail, rotor, audio, id}]
var _meshes: Dictionary = {}


func _init() -> void:
	for kind in ["airliner", "helicopter", "rotor", "paraglider", "balloon", "contrail"]:
		_meshes[kind] = SkyMesh.build(kind)
	for kind in POOL:
		var list := []
		for i in range(POOL[kind]):
			var root := MeshInstance3D.new()
			root.name = "Sky_%s_%d" % [kind, i]
			root.mesh = _meshes[kind]
			root.visible = false
			root.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if kind == "airliner" else GeometryInstance3D.SHADOW_CASTING_SETTING_ON
			var mat := ShaderMaterial.new()
			mat.shader = VehicleFarShader if kind == "airliner" else VehicleShader
			root.material_override = mat
			add_child(root)
			var slot := {"root": root, "mat": mat, "contrail": null, "rotor": null, "audio": null, "id": "", "lights": -1.0}
			if kind == "airliner":
				var c := MeshInstance3D.new()
				c.mesh = _meshes["contrail"]
				c.position = Vector3(0.0, 0.0, SkyMesh.ENGINE_REAR_Z)
				c.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
				var cm := ShaderMaterial.new()
				cm.shader = ContrailShader
				c.material_override = cm
				root.add_child(c)
				slot["contrail"] = c
			if kind == "helicopter":
				var r := MeshInstance3D.new()
				r.mesh = _meshes["rotor"]
				r.position = Vector3(0.0, SkyMesh.ROTOR_Y, -0.6)
				r.material_override = mat
				root.add_child(r)
				slot["rotor"] = r
			if SOUND.has(kind):
				var audio := AudioStreamPlayer3D.new()
				audio.unit_size = SOUND[kind][2]
				audio.max_distance = SOUND[kind][3]
				audio.volume_db = SOUND[kind][1]
				audio.bus = AudioMix.bus(AudioMix.AMBIENCE)
				root.add_child(audio)
				slot["audio"] = audio
			list.append(slot)
		_slots[kind] = list


func setup(sky_model, sound_player = null) -> void:
	model = sky_model
	_sound = sound_player
	for kind in SOUND:
		for slot in _slots[kind]:
			slot["audio"].stream = _sound.stream(SOUND[kind][0]) if _sound != null else null


func visible_count(kind: String = "") -> int:
	var n := 0
	for k in _slots:
		if kind != "" and k != kind:
			continue
		for slot in _slots[k]:
			if slot["root"].visible:
				n += 1
	return n


func update() -> void:
	var used := {}
	for kind in POOL:
		used[kind] = 0
	var cs: Array = model.craft if model != null else []
	for c in cs:
		var kind: String = c["kind"]
		if not _slots.has(kind) or int(used[kind]) >= POOL[kind]:
			continue
		var slot: Dictionary = _slots[kind][used[kind]]
		used[kind] = int(used[kind]) + 1
		var root: MeshInstance3D = slot["root"]
		var mat: ShaderMaterial = slot["mat"]
		if slot["id"] != c["id"]:
			slot["id"] = c["id"]
			var col: Array = SkyMesh.colors(kind, int(c["color"]))
			mat.set_shader_parameter("paint", col[0])
			mat.set_shader_parameter("second", col[1])
		if float(c["lights"]) != float(slot["lights"]):
			slot["lights"] = c["lights"]
			mat.set_shader_parameter("lights", float(c["lights"]))
		root.transform = c["xform"]
		root.visible = true
		if slot["contrail"] != null:
			var trail := float(c["contrail_m"])
			var cn: MeshInstance3D = slot["contrail"]
			cn.visible = trail > 1.0
			cn.scale = Vector3(1.0, 1.0, maxf(trail, 1.0))
		if slot["rotor"] != null:
			(slot["rotor"] as Node3D).rotation = Vector3(0.0, float(c["rotor"]), 0.0)
		var audio = slot["audio"]
		if audio != null and audio.stream != null and is_inside_tree() and not audio.playing:
			audio.play()
	for kind in POOL:
		for i in range(int(used[kind]), POOL[kind]):
			var slot: Dictionary = _slots[kind][i]
			if slot["root"].visible:
				slot["root"].visible = false
				slot["id"] = ""
				if slot["audio"] != null and slot["audio"].playing:
					slot["audio"].stop()

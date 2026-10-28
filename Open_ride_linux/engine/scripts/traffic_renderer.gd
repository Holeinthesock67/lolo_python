extends Node3D

## Affichage des véhicules de traffic_model.gd (Lot P13, refait par le Lot P25) : caisses détaillées de
## vehicle_mesh.gd (berline, citadine, utilitaire, camion, autocar, moto, tracteur) et shaders/vehicle.gdshader,
## un matériau par véhicule (peinture, seconde couleur, feux), roues à part qui tournent, et un lecteur 3D par
## véhicule (sifflement de passage, plus grave pour un camion ou un autocar, plus aigu pour une moto, ou moteur
## du tracteur, effet Doppler du moteur audio).
## Pas de class_name : charger par preload("res://scripts/traffic_renderer.gd").
##
## - `setup(model, sound_player)` : modèle de circulation et, facultatif, le sound_player.gd dont les flux
##   `vehicle_pass` et `tractor_engine` sont joués.
## - `set_lights(on)` : phares (traffic_model.gd `headlights`).
## - `update()` une fois par image, après `model.update` : place les MAX_VEHICLES véhicules du pool.
## Tous les nœuds sont créés au démarrage (pool de MAX_VEHICLES, le budget du préréglage `high`) ; les
## maillages de chaque sorte sont construits une fois et partagés.

const TrafficModel := preload("res://scripts/traffic_model.gd")
const VehicleMesh := preload("res://scripts/vehicle_mesh.gd")
const VehicleShader := preload("res://shaders/vehicle.gdshader")
const AudioMix := preload("res://scripts/audio_mix.gd")

const MAX_VEHICLES := 8
const MAX_WHEELS := 6
## Son de chaque sorte : [flux de sound_player.gd, volume (dB), hauteur]
const SOUND := {
	"car_a": ["vehicle_pass", -4.0, 1.0], "car_b": ["vehicle_pass", -4.0, 1.05], "van": ["vehicle_pass", -3.0, 0.9],
	"truck": ["vehicle_pass", -1.0, 0.7], "bus": ["vehicle_pass", -1.5, 0.75], "moto": ["vehicle_pass", -3.0, 1.35],
	"tractor": ["tractor_engine", -2.0, 1.0],
}
const WHEEL_SPIN_RADIUS_M := 0.33   # rayon de traffic_model.gd `wheel` ; chaque roue tourne selon le sien

var model = null
var lights := false
var _sound = null
var _slots: Array = []        # {root, body, wheels: Array[MeshInstance3D], audio, mat, kind, id, last_wheel}
var _bodies: Dictionary = {}  # sorte -> ArrayMesh (gardés ici : partagés par les nœuds qui les affichent)
var _wheels: Dictionary = {}  # sorte -> [{mesh, pos, radius}]


func _init() -> void:
	for kind in TrafficModel.KINDS:
		_bodies[kind] = VehicleMesh.build_body(kind)
		var ws := []
		var list := VehicleMesh.wheel_list(kind)
		for i in range(list.size()):
			ws.append({"mesh": VehicleMesh.build_wheel(kind, i), "pos": list[i]["pos"], "radius": list[i]["radius"]})
		_wheels[kind] = ws
	for i in range(MAX_VEHICLES):
		var root := Node3D.new()
		root.name = "Vehicle_%d" % i
		root.visible = false
		add_child(root)
		var mat := ShaderMaterial.new()
		mat.shader = VehicleShader
		# Avant vers -z local (même convention que traffic_model.world_transform)
		var body := MeshInstance3D.new()
		body.material_override = mat
		root.add_child(body)
		var wheels: Array[MeshInstance3D] = []
		for j in range(MAX_WHEELS):
			var w := MeshInstance3D.new()
			w.material_override = mat
			root.add_child(w)
			wheels.append(w)
		var audio := AudioStreamPlayer3D.new()
		audio.unit_size = 8.0
		audio.max_distance = 250.0
		audio.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_IDLE_STEP
		audio.bus = AudioMix.bus(AudioMix.AMBIENCE)
		root.add_child(audio)
		_slots.append({"root": root, "body": body, "wheels": wheels, "audio": audio, "mat": mat, "kind": "", "id": "",
			"last_wheel": 0.0})


func setup(traffic_model, sound_player = null) -> void:
	model = traffic_model
	_sound = sound_player


func set_lights(on: bool) -> void:
	if on == lights:
		return
	lights = on
	for slot in _slots:
		(slot["mat"] as ShaderMaterial).set_shader_parameter("lights", 1.0 if on else 0.0)


func visible_count() -> int:
	var n := 0
	for s in _slots:
		if s["root"].visible:
			n += 1
	return n


func _dress(slot: Dictionary, v: Dictionary) -> void:
	var kind: String = v["kind"]
	slot["kind"] = kind
	slot["id"] = v["id"]
	slot["last_wheel"] = float(v["wheel"])
	var mat: ShaderMaterial = slot["mat"]
	mat.set_shader_parameter("paint", VehicleMesh.paint(kind, int(v["color"])))
	mat.set_shader_parameter("second", VehicleMesh.second(kind))
	(slot["body"] as MeshInstance3D).mesh = _bodies[kind]
	var ws: Array = _wheels[kind]
	var nodes: Array[MeshInstance3D] = slot["wheels"]
	for j in range(MAX_WHEELS):
		var w := nodes[j]
		w.visible = j < ws.size()
		w.mesh = ws[j]["mesh"] if j < ws.size() else null
		if j < ws.size():
			w.position = ws[j]["pos"]
	var audio: AudioStreamPlayer3D = slot["audio"]
	if _sound != null:
		var snd: Array = SOUND[kind]
		audio.stream = _sound.stream(snd[0])
		audio.volume_db = snd[1]
		audio.pitch_scale = snd[2]


func update() -> void:
	var vs: Array = model.vehicles if model != null else []
	for j in range(MAX_VEHICLES):
		var slot: Dictionary = _slots[j]
		var root: Node3D = slot["root"]
		var audio: AudioStreamPlayer3D = slot["audio"]
		if j >= vs.size():
			if root.visible:
				root.visible = false
				if audio.playing:
					audio.stop()
			slot["kind"] = ""
			slot["id"] = ""
			continue
		var v: Dictionary = vs[j]
		if slot["kind"] != v["kind"] or slot["id"] != v["id"]:
			_dress(slot, v)
		root.visible = true
		root.transform = model.world_transform(v)
		# Même distance parcourue pour toutes les roues : chacune tourne selon son rayon (angle du modèle,
		# modulo un tour, suivi par différence)
		var turn := wrapf(float(v["wheel"]) - float(slot["last_wheel"]), -PI, PI)
		slot["last_wheel"] = float(v["wheel"])
		var ws: Array = _wheels[slot["kind"]]
		var nodes: Array[MeshInstance3D] = slot["wheels"]
		for i in range(ws.size()):
			nodes[i].rotation.x = wrapf(nodes[i].rotation.x - turn * WHEEL_SPIN_RADIUS_M / float(ws[i]["radius"]), -PI, PI)
		if is_inside_tree() and audio.stream != null and not audio.playing:
			audio.play()

extends Node3D

## Affichage des véhicules de traffic_model.gd (Lot P13) : carrosseries simples construites par code
## (berline `car_a`, petite voiture haute `car_b`, tracteur), quatre couleurs, roues qui tournent, et un
## lecteur 3D par véhicule (sifflement de passage ou moteur du tracteur, effet Doppler du moteur audio).
## Pas de class_name : charger par preload("res://scripts/traffic_renderer.gd").
##
## - `setup(model, sound_player)` : modèle de circulation et, facultatif, le sound_player.gd dont les flux
##   `vehicle_pass` et `tractor_engine` sont joués.
## - `update()` une fois par image, après `model.update` : place les MAX_VEHICLES véhicules du pool.
## Tous les nœuds sont créés au démarrage (pool de MAX_VEHICLES, le budget du préréglage `high`).

const TrafficModel := preload("res://scripts/traffic_model.gd")
const AudioMix := preload("res://scripts/audio_mix.gd")

const MAX_VEHICLES := 8
const PALETTE := [Color(0.62, 0.08, 0.08), Color(0.12, 0.2, 0.45), Color(0.85, 0.85, 0.82), Color(0.18, 0.18, 0.2)]
const TRACTOR_COLOR := Color(0.2, 0.45, 0.15)
const WHEEL_COLOR := Color(0.06, 0.06, 0.06)
const PASS_VOLUME_DB := -4.0
const TRACTOR_VOLUME_DB := -2.0

var model = null
var _sound = null
var _slots: Array = []        # {root, bodies: {kind: Node3D}, wheels: Array[Node3D], audio, kind}
var _paint: Array[StandardMaterial3D] = []
var _meshes: Array = []       # gardés ici : les maillages partagés survivent aux nœuds qui les affichent


static func _box_mesh(size: Vector3) -> ArrayMesh:
	var b := BoxMesh.new()
	b.size = size
	var am := ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, b.get_mesh_arrays())
	return am


static func _wheel_mesh(radius: float, width: float) -> ArrayMesh:
	var c := CylinderMesh.new()
	c.top_radius = radius
	c.bottom_radius = radius
	c.height = width
	c.radial_segments = 10
	c.rings = 1
	var am := ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, c.get_mesh_arrays())
	return am


func _part(parent: Node3D, mesh: ArrayMesh, pos: Vector3, mat: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.position = pos
	mi.material_override = mat
	parent.add_child(mi)
	return mi


func _init() -> void:
	for c in PALETTE:
		var m := StandardMaterial3D.new()
		m.albedo_color = c
		m.roughness = 0.4
		_paint.append(m)
	var glass := StandardMaterial3D.new()
	glass.albedo_color = Color(0.15, 0.2, 0.25)
	var tractor_mat := StandardMaterial3D.new()
	tractor_mat.albedo_color = TRACTOR_COLOR
	var tyre := StandardMaterial3D.new()
	tyre.albedo_color = WHEEL_COLOR
	_meshes = [
		_box_mesh(Vector3(1.8, 0.7, 4.3)), _box_mesh(Vector3(1.6, 0.55, 2.2)),   # car_a : caisse, habitacle
		_box_mesh(Vector3(1.8, 0.8, 3.9)), _box_mesh(Vector3(1.7, 0.7, 2.6)),    # car_b
		_box_mesh(Vector3(1.2, 0.9, 2.0)), _box_mesh(Vector3(1.3, 1.3, 1.3)),    # tracteur : capot, cabine
		_wheel_mesh(0.33, 0.22), _wheel_mesh(0.8, 0.45), _wheel_mesh(0.45, 0.3),
	]
	for i in range(MAX_VEHICLES):
		var root := Node3D.new()
		root.name = "Vehicle_%d" % i
		root.visible = false
		add_child(root)
		var bodies := {}
		var wheels := {}
		for kind in ["car_a", "car_b", "tractor"]:
			var b := Node3D.new()
			b.visible = false
			root.add_child(b)
			bodies[kind] = b
			wheels[kind] = []
		# Avant vers -z local (même convention que traffic_model.world_transform)
		var pa := _part(bodies["car_a"], _meshes[0], Vector3(0.0, 0.65, 0.0), _paint[0])
		_part(bodies["car_a"], _meshes[1], Vector3(0.0, 1.27, 0.2), glass)
		var pb := _part(bodies["car_b"], _meshes[2], Vector3(0.0, 0.7, 0.0), _paint[0])
		_part(bodies["car_b"], _meshes[3], Vector3(0.0, 1.45, 0.15), glass)
		_part(bodies["tractor"], _meshes[4], Vector3(0.0, 1.1, -0.9), tractor_mat)
		_part(bodies["tractor"], _meshes[5], Vector3(0.0, 1.75, 0.6), glass)
		for kind in ["car_a", "car_b"]:
			for wz in [-1.35, 1.35]:
				for wx in [-0.85, 0.85]:
					var w := _part(bodies[kind], _meshes[6], Vector3(wx, 0.33, wz), tyre)
					w.rotation = Vector3(0.0, 0.0, PI / 2.0)
					wheels[kind].append(w)
		for spec in [[_meshes[7], 0.8, 0.9, 1.0], [_meshes[8], 0.45, 0.75, -1.3]]:
			for wx in [-1.0, 1.0]:
				var w := _part(bodies["tractor"], spec[0], Vector3(wx * float(spec[2]), float(spec[1]), float(spec[3])), tyre)
				w.rotation = Vector3(0.0, 0.0, PI / 2.0)
				wheels["tractor"].append(w)
		var audio := AudioStreamPlayer3D.new()
		audio.unit_size = 8.0
		audio.max_distance = 250.0
		audio.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_IDLE_STEP
		audio.bus = AudioMix.bus(AudioMix.AMBIENCE)
		root.add_child(audio)
		_slots.append({"root": root, "bodies": bodies, "wheels": wheels, "audio": audio, "kind": "",
			"paint": [pa, pb]})


func setup(traffic_model, sound_player = null) -> void:
	model = traffic_model
	_sound = sound_player


func visible_count() -> int:
	var n := 0
	for s in _slots:
		if s["root"].visible:
			n += 1
	return n


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
			continue
		var v: Dictionary = vs[j]
		var kind: String = v["kind"]
		if slot["kind"] != kind or slot.get("id", "") != v["id"]:
			for k in slot["bodies"]:
				slot["bodies"][k].visible = k == kind
			for p in slot["paint"]:
				p.material_override = _paint[int(v["color"]) % _paint.size()]
			slot["kind"] = kind
			slot["id"] = v["id"]
			if _sound != null:
				audio.stream = _sound.stream("tractor_engine" if kind == "tractor" else "vehicle_pass")
				audio.volume_db = TRACTOR_VOLUME_DB if kind == "tractor" else PASS_VOLUME_DB
		root.visible = true
		root.transform = model.world_transform(v)
		var spin := float(v["wheel"])
		for w in slot["wheels"][kind]:
			(w as Node3D).rotation = Vector3(spin, 0.0, PI / 2.0)
		if is_inside_tree() and audio.stream != null and not audio.playing:
			audio.play()

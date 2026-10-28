extends Node3D

## Affichage des véhicules lointains de distant_traffic_model.gd (Lot P25) : une MultiMesh par sorte
## (vehicle_mesh.gd, matériaux partagés avec la route du parcours, phares par `VehicleMesh.set_lights`) pour les
## véhicules à moins de DETAIL_M, une boîte simple (`far`, mise à l'échelle de la sorte) au-delà ; un seul lecteur
## 3D, posé sur le tracteur au champ le plus proche à moins de TRACTOR_SOUND_M (`tractor_engine`).
## Pas de class_name : charger par preload("res://scripts/distant_traffic_renderer.gd").
## Toutes les places sont réécrites à chaque image (MAX_DISTANT au plus : moins cher que de garder des places
## fixes cachées) ; tous les nœuds sont créés au démarrage.

const VehicleMesh := preload("res://scripts/vehicle_mesh.gd")
const AudioMix := preload("res://scripts/audio_mix.gd")

const MAX_DISTANT := 24
const DETAIL_M := 400.0          # même seuil que distant_traffic_model.gd DETAIL_M
const TRACTOR_SOUND_M := 150.0
const TRACTOR_VOLUME_DB := -4.0

var model = null
var _sound = null
var _mm: Dictionary = {}          # sorte ou `far` -> MultiMesh
var _audio: AudioStreamPlayer3D
var _counts: Dictionary = {}      # sorte -> nombre affiché à la dernière image (tests)


func _init() -> void:
	var kinds: Array = VehicleMesh.KINDS.keys()
	kinds.append("far")
	for kind in kinds:
		var mmi := VehicleMesh.make_instance(kind, MAX_DISTANT)
		mmi.name = "Distant_" + kind
		add_child(mmi)
		_mm[kind] = mmi.multimesh
	_audio = AudioStreamPlayer3D.new()
	_audio.name = "FieldTractorSound"
	_audio.unit_size = 10.0
	_audio.max_distance = TRACTOR_SOUND_M
	_audio.volume_db = TRACTOR_VOLUME_DB
	_audio.bus = AudioMix.bus(AudioMix.AMBIENCE)
	add_child(_audio)


func setup(distant_model, sound_player = null) -> void:
	model = distant_model
	_sound = sound_player
	if _sound != null:
		_audio.stream = _sound.stream("tractor_engine")


func visible_count() -> int:
	var n := 0
	for k in _counts:
		n += int(_counts[k])
	return n


## Nombre affiché d'une sorte (ou `far`) à la dernière image (tests).
func shown(kind: String) -> int:
	return int(_counts.get(kind, 0))


func tractor_audio() -> AudioStreamPlayer3D:
	return _audio


func update(rider_pos: Vector3) -> void:
	_counts.clear()
	for k in _mm:
		_counts[k] = 0
	var vs: Array = model.vehicles if model != null else []
	for v in vs:
		var kind: String = v["kind"]
		var xf: Transform3D = v["xform"]
		var sc := float(v["scale"])
		var key := kind if float(v["dist_m"]) <= DETAIL_M else "far"
		if key == "far":
			var k: Dictionary = VehicleMesh.KINDS[kind]
			xf = Transform3D(xf.basis * Basis.from_scale(Vector3(2.0 * float(k["half_width"]), float(k["height"]), float(k["length"])) * maxf(sc, 0.001)), xf.origin)
		elif sc < 1.0:
			xf = Transform3D(xf.basis * Basis.from_scale(Vector3.ONE * maxf(sc, 0.001)), xf.origin)
		var i: int = _counts[key]
		if i >= MAX_DISTANT:
			continue
		var mm: MultiMesh = _mm[key]
		mm.set_instance_transform(i, xf)
		mm.set_instance_custom_data(i, VehicleMesh.custom(v["paint"], float(v["wheel"])))
		_counts[key] = i + 1
	for k in _mm:
		(_mm[k] as MultiMesh).visible_instance_count = _counts[k]
	# Moteur du tracteur au champ le plus proche
	var near: Dictionary = model.nearest_field_tractor(rider_pos) if model != null else {}
	if not near.is_empty() and float(near["dist_m"]) <= TRACTOR_SOUND_M and _audio.stream != null:
		_audio.position = near["pos"]
		if is_inside_tree() and not _audio.playing:
			_audio.play()
	elif _audio.playing:
		_audio.stop()

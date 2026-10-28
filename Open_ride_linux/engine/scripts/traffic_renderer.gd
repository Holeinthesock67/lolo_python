extends Node3D

## Affichage des véhicules de traffic_model.gd (lots P13 et P25) : carrosseries de vehicle_mesh.gd (berline,
## petite voiture haute, camionnette, camion, bus, moto et son pilote, tracteur), une MultiMesh par sorte au
## matériau partagé (peinture et rotation des roues par instance, phares par `VehicleMesh.set_lights`), et un
## lecteur 3D par véhicule (sifflement de passage, camion, moto ou moteur du tracteur, effet Doppler du
## moteur audio).
## Pas de class_name : charger par preload("res://scripts/traffic_renderer.gd").
##
## - `setup(model, sound_player)` : modèle de circulation et, facultatif, le sound_player.gd dont les flux
##   `vehicle_pass`, `truck_pass`, `moto_pass` et `tractor_engine` sont joués.
## - `update()` une fois par image, après `model.update` : place les véhicules du modèle (MAX_VEHICLES au plus).
## Tous les nœuds sont créés au démarrage : une MultiMesh de MAX_VEHICLES places par sorte, MAX_VEHICLES
## lecteurs 3D (le budget du préréglage `high`) ; ni nœud ni matériau par véhicule ensuite.

const TrafficModel := preload("res://scripts/traffic_model.gd")
const VehicleMesh := preload("res://scripts/vehicle_mesh.gd")
const AudioMix := preload("res://scripts/audio_mix.gd")

const MAX_VEHICLES := 8
const ROAD_KINDS := ["car_a", "car_b", "van", "truck", "bus", "moto", "tractor"]
const PASS_VOLUME_DB := -4.0
const HEAVY_VOLUME_DB := -1.0
const TRACTOR_VOLUME_DB := -2.0

var model = null
var _sound = null
var _mm: Dictionary = {}           # sorte -> MultiMesh
var _audio: Array = []             # AudioStreamPlayer3D, un par véhicule du modèle (même indice)
var _audio_ids: Array = []         # identifiant du véhicule dont chaque lecteur joue le son
var _xforms: Array = []            # transformée de chaque véhicule affiché (tests)
var _customs: Array = []           # INSTANCE_CUSTOM de chaque véhicule affiché (tests)
var _shown := 0


func _init() -> void:
	for kind in ROAD_KINDS:
		var mmi := VehicleMesh.make_instance(kind, MAX_VEHICLES)
		add_child(mmi)
		_mm[kind] = mmi.multimesh
	for i in range(MAX_VEHICLES):
		var audio := AudioStreamPlayer3D.new()
		audio.name = "VehicleSound_%d" % i
		audio.unit_size = 8.0
		audio.max_distance = 250.0
		audio.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_IDLE_STEP
		audio.bus = AudioMix.bus(AudioMix.AMBIENCE)
		add_child(audio)
		_audio.append(audio)
		_audio_ids.append("")


func setup(traffic_model, sound_player = null) -> void:
	model = traffic_model
	_sound = sound_player


func visible_count() -> int:
	return _shown


## Transformée du véhicule `j` du modèle à la dernière mise à jour (tests).
func shown_transform(j: int) -> Transform3D:
	return _xforms[j] if j < _xforms.size() else Transform3D()


## INSTANCE_CUSTOM (peinture, angle des roues) du véhicule `j` à la dernière mise à jour (tests).
func shown_custom(j: int) -> Color:
	return _customs[j] if j < _customs.size() else Color()


## Son joué par une sorte de véhicule.
static func sound_kind(kind: String) -> String:
	match kind:
		"tractor":
			return "tractor_engine"
		"truck", "bus":
			return "truck_pass"
		"moto":
			return "moto_pass"
	return "vehicle_pass"


## Lecteur 3D du véhicule `j` (tests).
func audio_of(j: int) -> AudioStreamPlayer3D:
	return _audio[j]


func update() -> void:
	var vs: Array = model.vehicles if model != null else []
	var used := {}
	for kind in ROAD_KINDS:
		used[kind] = 0
	_xforms.clear()
	_customs.clear()
	_shown = 0
	for j in range(MAX_VEHICLES):
		var audio: AudioStreamPlayer3D = _audio[j]
		if j >= vs.size():
			if audio.playing:
				audio.stop()
			_audio_ids[j] = ""
			continue
		var v: Dictionary = vs[j]
		var kind: String = v["kind"]
		var xf: Transform3D = model.world_transform(v)
		var slot: int = used[kind]
		used[kind] = slot + 1
		var mm: MultiMesh = _mm[kind]
		mm.set_instance_transform(slot, xf)
		var wheel := float(v["wheel"]) * 0.33 / float(VehicleMesh.KINDS[kind]["wheel_r"])
		var cu := VehicleMesh.custom(VehicleMesh.paint(kind, int(v["color"])), wheel)
		mm.set_instance_custom_data(slot, cu)
		_xforms.append(xf)
		_customs.append(cu)
		_shown += 1
		audio.transform = xf
		if _audio_ids[j] != str(v["id"]):
			_audio_ids[j] = str(v["id"])
			if _sound != null:
				audio.stream = _sound.stream(sound_kind(kind))
				audio.volume_db = {"tractor": TRACTOR_VOLUME_DB, "truck": HEAVY_VOLUME_DB, "bus": HEAVY_VOLUME_DB}.get(kind, PASS_VOLUME_DB)
		if is_inside_tree() and audio.stream != null and not audio.playing:
			audio.play()
	for kind in ROAD_KINDS:
		(_mm[kind] as MultiMesh).visible_instance_count = used[kind]

extends Node3D

## Affichage des cyclistes du décor de road_cyclists_model.gd (Lot P28) : coureur casqué et vélo de
## people_mesh.gd (`build_person(false, true)`, `build_bike`), shader de pédalage des bots (crowd.gdshader,
## animations 7 et 8), un MultiMeshInstance3D pour les coureurs et un pour les vélos, créés au démarrage.
## Pas de class_name : charger par preload("res://scripts/road_cyclists_renderer.gd").
##
## Maillot (couleur d'instance) tiré d'une palette de JERSEYS couleurs, tenue (peau, cheveux) par cycliste,
## cuissard noir. Pédalier : l'angle est cumulé ici d'après la cadence du modèle (braquet de 50 × 17) et passé
## en phase (INSTANCE_CUSTOM.x, cadence du shader à 0), pour qu'un changement de vitesse ne fasse pas sauter les
## jambes. Un groupe qui double dit « Salut ! » (`voice_salut` de sound_player.gd) sur un lecteur 3D.
## - `setup(model, sound_player)` ; `update(dt_s, paused)` une fois par image, après `model.update`.

const RoadCyclistsModel := preload("res://scripts/road_cyclists_model.gd")
const PeopleMesh := preload("res://scripts/people_mesh.gd")
const CrowdShader := preload("res://shaders/crowd.gdshader")
const AudioMix := preload("res://scripts/audio_mix.gd")

const MAX_CYCLISTS := 16
const JERSEYS := [Color(0.85, 0.15, 0.15), Color(0.1, 0.4, 0.85), Color(0.95, 0.8, 0.1), Color(0.1, 0.6, 0.3),
	Color(0.95, 0.95, 0.95), Color(0.1, 0.1, 0.12), Color(0.95, 0.45, 0.1), Color(0.55, 0.2, 0.65)]
const SALUT_VOLUME_DB := -6.0

var model = null
var _sound = null
var _riders: MultiMesh
var _bikes: MultiMesh
var _audio: AudioStreamPlayer3D
var _shown := 0
var _xforms: Array = []          # transformée de chaque cycliste affiché (tests)
var _cadences: Array = []        # cadence (tr/min) de chaque cycliste affiché (tests)


func _init() -> void:
	var mat := ShaderMaterial.new()
	mat.shader = CrowdShader
	PeopleMesh.apply_palettes(mat)
	for kind in ["rider", "bike"]:
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.use_custom_data = true
		mm.mesh = PeopleMesh.build_person(false, true) if kind == "rider" else PeopleMesh.build_bike()
		mm.instance_count = MAX_CYCLISTS
		mm.visible_instance_count = 0
		var mmi := MultiMeshInstance3D.new()
		mmi.name = "RoadCyclists_" + kind
		mmi.multimesh = mm
		mmi.material_override = mat
		add_child(mmi)
		if kind == "rider":
			_riders = mm
		else:
			_bikes = mm
	_audio = AudioStreamPlayer3D.new()
	_audio.name = "CyclistVoice"
	_audio.unit_size = 6.0
	_audio.max_distance = 60.0
	_audio.volume_db = SALUT_VOLUME_DB
	_audio.bus = AudioMix.bus(AudioMix.AMBIENCE)
	add_child(_audio)


func setup(cyclists_model, sound_player = null) -> void:
	model = cyclists_model
	_sound = sound_player


func visible_count() -> int:
	return _shown


func shown_transform(i: int) -> Transform3D:
	return _xforms[i] if i < _xforms.size() else Transform3D()


func shown_cadence(i: int) -> float:
	return _cadences[i] if i < _cadences.size() else 0.0


## Lecteur 3D de la voix (tests).
func audio() -> AudioStreamPlayer3D:
	return _audio


func update(dt_s: float, paused: bool = false) -> void:
	_xforms.clear()
	_cadences.clear()
	_shown = 0
	if model == null:
		_riders.visible_instance_count = 0
		_bikes.visible_instance_count = 0
		return
	for r in model.riders():
		if _shown >= MAX_CYCLISTS:
			break
		var g: Dictionary = r["group"]
		var m: Dictionary = r["member"]
		var rpm := RoadCyclistsModel.cadence_rpm(float(g["speed_mps"]))
		if not paused:
			m["crank"] = fposmod(float(m.get("crank", float(m["phase"]) * TAU)) + rpm / 60.0 * TAU * dt_s, TAU)
		var phase := float(m.get("crank", float(m["phase"]) * TAU)) / TAU
		var xf: Transform3D = model.world_transform(float(r["s"]), float(r["lateral"]), int(r["dir"]))
		var look := int(m["look"])
		var outfit := PeopleMesh.outfit(look % 4, (look >> 2) % 6, PeopleMesh.RIDER_OUTFIT_TROUSERS, PeopleMesh.STYLE_STRIPE)
		var jersey: Color = JERSEYS[int(m["jersey"]) % JERSEYS.size()]
		_riders.set_instance_transform(_shown, xf)
		_riders.set_instance_color(_shown, jersey)
		_riders.set_instance_custom_data(_shown, Color(phase, 0.0, 7.0, outfit))
		_bikes.set_instance_transform(_shown, xf)
		_bikes.set_instance_color(_shown, jersey.darkened(0.3))
		_bikes.set_instance_custom_data(_shown, Color(phase, 0.0, 8.0, outfit))
		_xforms.append(xf)
		_cadences.append(rpm)
		_shown += 1
	_riders.visible_instance_count = _shown
	_bikes.visible_instance_count = _shown
	var ev: Dictionary = model.last_event
	if not ev.is_empty() and _sound != null:
		var st: Resource = _sound.stream(str(ev["kind"]))
		if st != null:
			_audio.stream = st
			_audio.position = ev["pos"]
			if is_inside_tree():
				_audio.play()

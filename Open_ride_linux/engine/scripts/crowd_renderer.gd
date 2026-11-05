extends Node3D

## Affichage des spectateurs de crowd_model.gd (Lot P15) : personnages construits par code
## (people_mesh.gd, lots Y14 et Y21 : corps articulé, tenue et geste tirés par personne), en MultiMesh
## par sorte (sans rien, porte-drapeau, porteur de pancarte) et par niveau de détail (détaillé en deçà de
## `QualityPresets.people_lod_m`, réduit au-delà : `_loin`), couleur du haut en couleur d'instance, tenue
## (peau, cheveux, pantalon, style, bas, coiffe, geste, détail) répartie dans INSTANCE_CUSTOM
## (`PeopleMesh.instance_custom`), taille et carrure tirées
## par personne (`morph`), animés par shaders/crowd.gdshader.
## Pas de class_name : charger par preload("res://scripts/crowd_renderer.gd").
##
## - `set_preset(name, enabled)` : budget `living(preset).spectators`.
## - `setup(model, sound_player)` : modèle et, facultatif, sound_player.gd (flux `crowd_cheer`).
## - `update(cam_pos, now_s, cheer)` une fois par image, après `model.update` : les plus proches de la
##   caméra dans la limite du budget (tri refait tous les RESELECT_M), état « encourage » écrit dans la
##   donnée d'instance des seuls spectateurs gardés ; la clameur (0 à 1) règle le lecteur 3D placé sur le
##   groupe le plus proche. Tous les nœuds sont créés au démarrage.
##
## Lot P21 : une deuxième instance, `CrowdRenderer.new("passersby")`, affiche les passants de
## passersby_model.gd : personnes (rôles en variantes d'animation de crowd.gdshader, `INSTANCE_CUSTOM.z`),
## chiens (quatre pattes) et bancs des personnes assises, budget `living(preset).passersby`.
## `setup_passersby(model, sound_player)`, puis `update_passersby(cam_pos, cam_s, now_s, event)` une fois
## par image, après `model.update` dont `event` est le résultat : le son éventuel est joué par un
## lecteur 3D sur la personne, au volume `ambience.volume` du thème (sound_player.gd).

const QualityPresets := preload("res://scripts/quality_presets.gd")
const CrowdShader := preload("res://shaders/crowd.gdshader")
const PeopleMesh := preload("res://scripts/people_mesh.gd")

const PALETTE := [Color(0.8, 0.1, 0.1), Color(0.95, 0.8, 0.1), Color(0.1, 0.35, 0.8), Color(0.95, 0.95, 0.95),
	Color(0.15, 0.6, 0.25), Color(0.9, 0.45, 0.1), Color(0.2, 0.2, 0.25), Color(0.6, 0.2, 0.6)]
const RESELECT_M := 20.0
const CHEER_MIN_DB := -40.0
const CHEER_MAX_DB := 0.0
const DOG_PALETTE := [Color(0.45, 0.3, 0.15), Color(0.12, 0.1, 0.1), Color(0.85, 0.8, 0.7), Color(0.7, 0.5, 0.25)]
const BENCH_COLOR := Color(0.42, 0.3, 0.18)
const KID_SCALE := 0.65
const VOICE_DB := -4.0
const PasserbyModel := preload("res://scripts/passersby_model.gd")
const AudioMix := preload("res://scripts/audio_mix.gd")

var mode := "spectators"         # ou "passersby" (Lot P21)
var model = null
var budget := 40
var sounds_played: Array = []     # sons de passants joués (tests)
var last_update_usec := 0
var _sound = null
## Spectateurs : sorte × niveau de détail (indice `2 * sorte + lod` dans `_mmi`). Passants : personnes
## détaillées, chiens, bancs, personnes au loin.
const SPECTATOR_KINDS := ["plain", "flag", "sign"]
const PASSERBY_KINDS := ["people", "dogs", "benches", "people_loin"]
## Taille (y) et carrure (x, z) tirées par personne autour de 1.
const MORPH_HEIGHT := Vector2(0.95, 1.05)
const MORPH_GIRTH := Vector2(0.92, 1.12)
const SIGN_ANIM := 9               # crowd.gdshader : porteur de pancarte tourné vers la caméra

var _mmi: Array[MultiMeshInstance3D] = []
var _sel: Array = []                         # indices de spectateurs gardés, par MultiMesh
var _shown: Array = []                       # état écrit dans la donnée d'instance, par MultiMesh
var _slots: Array = []                       # passants : [MultiMesh, indice] de chaque entrée affichée
var lod_m := 25.0
var _last_select := Vector3(INF, INF, INF)
var _audio: AudioStreamPlayer3D
var _meshes: Array = []
var _serial := -1                # sélection de passersby_model.gd déjà écrite


func _init(p_mode: String = "spectators") -> void:
	mode = p_mode
	var mat := ShaderMaterial.new()
	mat.shader = CrowdShader
	PeopleMesh.apply_palettes(mat)
	var kinds := []
	if mode == "spectators":
		for kind in SPECTATOR_KINDS:
			kinds.append(kind)
			kinds.append(kind + "_loin")
	else:
		kinds = PASSERBY_KINDS
	for kind in kinds:
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.use_custom_data = true
		var lod := 1 if str(kind).ends_with("_loin") else 0
		var mesh: ArrayMesh
		match str(kind).trim_suffix("_loin"):
			"dogs":
				mesh = PeopleMesh.build_dog()
			"benches":
				mesh = PeopleMesh.build_bench()
			"sign":
				mesh = PeopleMesh.build_sign_holder(lod)
			"flag":
				mesh = PeopleMesh.build_person(true, false, lod)
			_:
				mesh = PeopleMesh.build_person(false, false, lod)
		_meshes.append(mesh)
		mm.mesh = mesh
		var mmi := MultiMeshInstance3D.new()
		mmi.name = ("Crowd_%s" if mode == "spectators" else "Passersby_%s") % kind
		mmi.multimesh = mm
		mmi.material_override = mat
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mmi)
		_mmi.append(mmi)
	_audio = AudioStreamPlayer3D.new()
	_audio.name = "CrowdCheer" if mode == "spectators" else "PasserbyVoice"
	_audio.unit_size = 20.0 if mode == "spectators" else 8.0
	_audio.max_distance = 300.0 if mode == "spectators" else 60.0
	_audio.volume_db = CHEER_MIN_DB if mode == "spectators" else VOICE_DB
	_audio.bus = AudioMix.bus(AudioMix.AMBIENCE)
	add_child(_audio)
	set_preset(QualityPresets.DEFAULT_PRESET)


func set_preset(preset_name: String, enabled: bool = true) -> void:
	budget = int(QualityPresets.living(preset_name, enabled).get("spectators" if mode == "spectators" else "passersby", 0))
	lod_m = QualityPresets.people_lod_m(preset_name)
	for mmi in _mmi:
		mmi.multimesh.instance_count = budget
		mmi.multimesh.visible_instance_count = 0
	_serial = -1
	_last_select = Vector3(INF, INF, INF)


func setup(crowd_model, sound_player = null) -> void:
	model = crowd_model
	_sound = sound_player
	if _sound != null:
		_audio.stream = _sound.stream("crowd_cheer")
	_last_select = Vector3(INF, INF, INF)


## Personnes affichées (spectateurs de toutes les sortes, ou passants détaillés et au loin).
func visible_count() -> int:
	var n := 0
	for k in range(_mmi.size()):
		if mode == "spectators" or k == 0 or k == 3:
			n += _mmi[k].multimesh.visible_instance_count
	return n


## Base d'une personne : orientation, taille et carrure tirées de son numéro (mêmes d'une séance à l'autre).
static func morph(i: int, yaw: float, scale: float = 1.0) -> Basis:
	var h := (i * 2246822519 + 374761393) & 0x7FFFFFFF
	var sy := lerpf(MORPH_HEIGHT.x, MORPH_HEIGHT.y, float(h & 0xFF) / 255.0)
	var sw := lerpf(MORPH_GIRTH.x, MORPH_GIRTH.y, float((h >> 8) & 0xFF) / 255.0)
	return Basis(Vector3.UP, yaw).scaled_local(Vector3(sw, sy, sw) * scale)


func setup_passersby(passersby_model, sound_player = null) -> void:
	model = passersby_model
	_sound = sound_player
	_serial = -1
	sounds_played.clear()


## Une fois par image (Lot P21) : personnes, chiens et bancs les plus proches ; `event` est le résultat
## de `passersby_model.update` (son éventuel à jouer sur la personne).
func update_passersby(cam_pos: Vector3, cam_s: float, now_s: float, event: Dictionary = {}) -> void:
	var t0 := Time.get_ticks_usec()
	if model == null:
		return
	var list: Array = model.visible(cam_pos, cam_s, now_s, budget)
	var near: MultiMesh = _mmi[0].multimesh
	var dogs: MultiMesh = _mmi[1].multimesh
	var benches: MultiMesh = _mmi[2].multimesh
	var far: MultiMesh = _mmi[3].multimesh
	# Nouvelle sélection : tout est réécrit et chaque entrée prend son niveau de détail ; sinon, seulement
	# les entrées qui ont changé, à la même place
	var full := int(model.selection_serial) != _serial or _slots.size() != list.size()
	_serial = int(model.selection_serial)
	if full:
		_slots.clear()
		var counts := [0, 0]
		for e in list:
			var lod := 0 if (e["pos"] as Vector3).distance_to(cam_pos) < lod_m else 1
			_slots.append([near if lod == 0 else far, counts[lod]])
			counts[lod] += 1
	for k in range(list.size()):
		var e: Dictionary = list[k]
		if not full and not bool(e["dirty"]):
			continue
		var people: MultiMesh = _slots[k][0]
		var j: int = _slots[k][1]
		var i := int(e["i"])
		var p: Dictionary = model.people[i]
		var basis := morph(i, float(e["yaw"]), KID_SCALE if str(p["role"]) == "kid" else 1.0)
		people.set_instance_transform(j, Transform3D(basis, e["pos"]))
		people.set_instance_custom_data(j, PeopleMesh.instance_custom(float(p["phase"]), 1.0 if bool(e["wave"]) else 0.0,
			float(PasserbyModel.ANIM[str(e["anim"])]), PeopleMesh.outfit_of(i)))
		var dog: int = e["dog"]
		if dog >= 0:
			dogs.set_instance_transform(dog, Transform3D(Basis(Vector3.UP, float(e["dog_yaw"])), e["dog_pos"]))
		if full:
			people.set_instance_color(j, PALETTE[int(p["color"]) % PALETTE.size()])
			if dog >= 0:
				dogs.set_instance_color(dog, DOG_PALETTE[int(p["color"]) % DOG_PALETTE.size()])
				dogs.set_instance_custom_data(dog, Color(fmod(float(p["phase"]) + 0.3, 1.0), 0.0, float(PasserbyModel.ANIM["dog"]), 0.0))
			var bench: int = e["bench"]
			if bench >= 0:
				benches.set_instance_transform(bench, Transform3D(Basis(Vector3.UP, float(p["yaw"])), p["pos"]))
				benches.set_instance_color(bench, BENCH_COLOR)
				benches.set_instance_custom_data(bench, Color(0, 0, 0, 0))
	if full:
		var n_near := 0
		for sl in _slots:
			n_near += 1 if sl[0] == near else 0
		near.visible_instance_count = n_near
		far.visible_instance_count = list.size() - n_near
		dogs.visible_instance_count = int(model.dog_count)
		benches.visible_instance_count = int(model.bench_count)
	var kind := str(event.get("sound", ""))
	if not kind.is_empty():
		sounds_played.append(kind)
		_audio.position = event.get("pos", Vector3.ZERO)
		var vol := 0.6
		if _sound != null:
			vol = float(_sound.ambience.volume)
			_audio.stream = _sound.stream(kind)
		_audio.volume_db = VOICE_DB + linear_to_db(maxf(vol / 0.6, 0.001))
		if is_inside_tree() and _audio.stream != null:
			_audio.play()
	last_update_usec = Time.get_ticks_usec() - t0


## Sorte d'un spectateur (indice dans SPECTATOR_KINDS).
static func kind_of(sp: Dictionary) -> int:
	return 1 if bool(sp.get("flag", false)) else (2 if bool(sp.get("sign", false)) else 0)


## Animation de crowd.gdshader des spectateurs du MultiMesh `m` : debout, ou porteur de pancarte (9).
static func _anim_of(m: int) -> float:
	return float(SIGN_ANIM) if m / 2 == 2 else 0.0


func _select(cam_pos: Vector3) -> void:
	var order := []
	var sp: Array = model.spectators
	for i in range(sp.size()):
		order.append([(sp[i]["pos"] as Vector3).distance_squared_to(cam_pos), i])
	order.sort_custom(func(a, b): return a[0] < b[0] or (a[0] == b[0] and a[1] < b[1]))
	_sel = []
	_shown = []
	for m in range(_mmi.size()):
		_sel.append([])
		_shown.append(PackedByteArray())
	for j in range(mini(budget, order.size())):
		var i: int = order[j][1]
		var lod := 0 if float(order[j][0]) < lod_m * lod_m else 1
		_sel[2 * kind_of(sp[i]) + lod].append(i)
	for m in range(_mmi.size()):
		var mm: MultiMesh = _mmi[m].multimesh
		var list: Array = _sel[m]
		var shown := PackedByteArray()
		shown.resize(list.size())
		for k in range(list.size()):
			var s: Dictionary = sp[list[k]]
			mm.set_instance_transform(k, Transform3D(morph(list[k], float(s["yaw"])), s["pos"]))
			mm.set_instance_color(k, PALETTE[int(s["color"]) % PALETTE.size()])
			var st = model.states.get(list[k])
			shown[k] = 1 if st != null and bool(st["cheer"]) else 0
			mm.set_instance_custom_data(k, PeopleMesh.instance_custom(float(s["phase"]), float(shown[k]), _anim_of(m), PeopleMesh.outfit_of(list[k])))
		_shown[m] = shown
		mm.visible_instance_count = list.size()
	_last_select = cam_pos


func update(cam_pos: Vector3, now_s: float, cheer: float = 0.0) -> void:
	var t0 := Time.get_ticks_usec()
	if model == null:
		return
	if cam_pos.distance_to(_last_select) > RESELECT_M:
		_select(cam_pos)
	# Donnée d'instance réécrite seulement quand l'état d'un spectateur gardé change
	var sp: Array = model.spectators
	var states: Dictionary = model.states
	for m in range(_sel.size()):
		var mm: MultiMesh = _mmi[m].multimesh
		var list: Array = _sel[m]
		var shown: PackedByteArray = _shown[m]
		for k in range(list.size()):
			var i: int = list[k]
			var st = states.get(i)
			var on := 1 if st != null and bool(st["cheer"]) else 0
			if shown[k] != on:
				shown[k] = on
				mm.set_instance_custom_data(k, PeopleMesh.instance_custom(float(sp[i]["phase"]), float(on), _anim_of(m), PeopleMesh.outfit_of(i)))
	# Clameur sur le groupe le plus proche
	if cheer > 0.0 and not model.groups.is_empty():
		var gi := _nearest_group_to(cam_pos)
		_audio.position = model.groups[gi]["center"]
		_audio.volume_db = lerpf(CHEER_MIN_DB, CHEER_MAX_DB, clampf(cheer, 0.0, 1.0))
		if is_inside_tree() and _audio.stream != null and not _audio.playing:
			_audio.play()
	elif _audio.playing:
		_audio.stop()
	last_update_usec = Time.get_ticks_usec() - t0


func _nearest_group_to(p: Vector3) -> int:
	var best := 0
	var best_d := INF
	for gi in range(model.groups.size()):
		var d := (model.groups[gi]["center"] as Vector3).distance_squared_to(p)
		if d < best_d:
			best_d = d
			best = gi
	return best

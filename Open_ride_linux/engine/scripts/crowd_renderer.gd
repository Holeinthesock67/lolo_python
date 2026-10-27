extends Node3D

## Affichage des spectateurs de crowd_model.gd (Lot P15) : silhouettes basses en polygones (corps,
## tête, bras, drapeau pour un sur quatre) construites par code, en deux MultiMesh (avec et sans
## drapeau), couleurs d'instance variées, bras et drapeaux animés par shaders/crowd.gdshader.
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

var mode := "spectators"         # ou "passersby" (Lot P21)
var model = null
var budget := 40
var sounds_played: Array = []     # sons de passants joués (tests)
var last_update_usec := 0
var _sound = null
var _mmi: Array[MultiMeshInstance3D] = []   # 0 : sans drapeau, 1 : avec
var _sel: Array = [[], []]                   # indices de spectateurs gardés, par MultiMesh
var _shown: Array = [PackedByteArray(), PackedByteArray()]   # état écrit dans la donnée d'instance
var _last_select := Vector3(INF, INF, INF)
var _audio: AudioStreamPlayer3D
var _meshes: Array = []
var _serial := -1                # sélection de passersby_model.gd déjà écrite


func _init(p_mode: String = "spectators") -> void:
	mode = p_mode
	var mat := ShaderMaterial.new()
	mat.shader = CrowdShader
	var kinds := ["plain", "flag"] if mode == "spectators" else ["people", "dogs", "benches"]
	for kind in kinds:
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.use_custom_data = true
		var mesh: ArrayMesh
		match kind:
			"dogs":
				mesh = build_dog_mesh()
			"benches":
				mesh = build_bench_mesh()
			_:
				mesh = build_mesh(kind == "flag")
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
	add_child(_audio)
	set_preset(QualityPresets.DEFAULT_PRESET)


func set_preset(preset_name: String, enabled: bool = true) -> void:
	budget = int(QualityPresets.living(preset_name, enabled).get("spectators" if mode == "spectators" else "passersby", 0))
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


func visible_count() -> int:
	return _mmi[0].multimesh.visible_instance_count + (_mmi[1].multimesh.visible_instance_count if mode == "spectators" else 0)


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
	var people: MultiMesh = _mmi[0].multimesh
	var dogs: MultiMesh = _mmi[1].multimesh
	var benches: MultiMesh = _mmi[2].multimesh
	# Nouvelle sélection : tout est réécrit ; sinon, seulement les entrées qui ont changé
	var full := int(model.selection_serial) != _serial
	_serial = int(model.selection_serial)
	for k in range(list.size()):
		var e: Dictionary = list[k]
		if not full and not bool(e["dirty"]):
			continue
		var p: Dictionary = model.people[int(e["i"])]
		var basis := Basis(Vector3.UP, float(e["yaw"]))
		if str(p["role"]) == "kid":
			basis = basis.scaled(Vector3.ONE * KID_SCALE)
		people.set_instance_transform(k, Transform3D(basis, e["pos"]))
		people.set_instance_custom_data(k, Color(float(p["phase"]), 1.0 if bool(e["wave"]) else 0.0,
			float(PasserbyModel.ANIM[str(e["anim"])]), 0.0))
		var dog: int = e["dog"]
		if dog >= 0:
			dogs.set_instance_transform(dog, Transform3D(Basis(Vector3.UP, float(e["dog_yaw"])), e["dog_pos"]))
		if full:
			people.set_instance_color(k, PALETTE[int(p["color"]) % PALETTE.size()])
			if dog >= 0:
				dogs.set_instance_color(dog, DOG_PALETTE[int(p["color"]) % DOG_PALETTE.size()])
				dogs.set_instance_custom_data(dog, Color(fmod(float(p["phase"]) + 0.3, 1.0), 0.0, float(PasserbyModel.ANIM["dog"]), 0.0))
			var bench: int = e["bench"]
			if bench >= 0:
				benches.set_instance_transform(bench, Transform3D(Basis(Vector3.UP, float(p["yaw"])), p["pos"]))
				benches.set_instance_color(bench, BENCH_COLOR)
				benches.set_instance_custom_data(bench, Color(0, 0, 0, 0))
	if full:
		people.visible_instance_count = list.size()
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


func _select(cam_pos: Vector3) -> void:
	var order := []
	var sp: Array = model.spectators
	for i in range(sp.size()):
		order.append([(sp[i]["pos"] as Vector3).distance_squared_to(cam_pos), i])
	order.sort_custom(func(a, b): return a[0] < b[0] or (a[0] == b[0] and a[1] < b[1]))
	_sel = [[], []]
	for j in range(mini(budget, order.size())):
		var i: int = order[j][1]
		_sel[1 if bool(sp[i]["flag"]) else 0].append(i)
	for m in range(2):
		var mm: MultiMesh = _mmi[m].multimesh
		var list: Array = _sel[m]
		var shown := PackedByteArray()
		shown.resize(list.size())
		for k in range(list.size()):
			var s: Dictionary = sp[list[k]]
			mm.set_instance_transform(k, Transform3D(Basis(Vector3.UP, float(s["yaw"])), s["pos"]))
			mm.set_instance_color(k, PALETTE[int(s["color"]) % PALETTE.size()])
			var st = model.states.get(list[k])
			shown[k] = 1 if st != null and bool(st["cheer"]) else 0
			mm.set_instance_custom_data(k, Color(float(s["phase"]), float(shown[k]), 0.0, 0.0))
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
	for m in range(2):
		var mm: MultiMesh = _mmi[m].multimesh
		var list: Array = _sel[m]
		var shown: PackedByteArray = _shown[m]
		for k in range(list.size()):
			var i: int = list[k]
			var st = states.get(i)
			var on := 1 if st != null and bool(st["cheer"]) else 0
			if shown[k] != on:
				shown[k] = on
				mm.set_instance_custom_data(k, Color(float(sp[i]["phase"]), float(on), 0.0, 0.0))
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


static func _box(st: SurfaceTool, c: Vector3, size: Vector3, uv: Vector2, col: Color, uv2: Vector2 = Vector2.ZERO) -> void:
	var h := size * 0.5
	var v := [
		c + Vector3(-h.x, -h.y, -h.z), c + Vector3(h.x, -h.y, -h.z), c + Vector3(h.x, h.y, -h.z), c + Vector3(-h.x, h.y, -h.z),
		c + Vector3(-h.x, -h.y, h.z), c + Vector3(h.x, -h.y, h.z), c + Vector3(h.x, h.y, h.z), c + Vector3(-h.x, h.y, h.z),
	]
	for f in [[0, 1, 2, 3], [5, 4, 7, 6], [4, 0, 3, 7], [1, 5, 6, 2], [3, 2, 6, 7], [4, 5, 1, 0]]:
		for idx in [f[0], f[1], f[2], f[0], f[2], f[3]]:
			st.set_uv(uv)
			st.set_uv2(uv2)
			st.set_color(col)
			st.add_vertex(v[idx])


## Silhouette d'un spectateur (1,7 m, face vers +z), avec ou sans drapeau tenu à droite.
## Couleur des sommets : alpha 1 pour les vêtements (teints par la couleur d'instance), 0 pour la peau.
## UV2 (Lot P21) : x = ±1 sur chaque jambe (marche), y = 1 sur le bras qui salue.
static func build_mesh(with_flag: bool) -> ArrayMesh:
	var cloth := Color(1, 1, 1, 1)
	var skin := Color(1, 1, 1, 0)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for sx in [-1.0, 1.0]:
		_box(st, Vector3(sx * 0.085, 0.45, 0.0), Vector3(0.15, 0.9, 0.2), Vector2.ZERO, cloth, Vector2(sx, 0.0))   # jambes
	_box(st, Vector3(0.0, 1.17, 0.0), Vector3(0.42, 0.55, 0.25), Vector2.ZERO, cloth)    # buste
	_box(st, Vector3(0.0, 1.57, 0.0), Vector3(0.2, 0.22, 0.2), Vector2.ZERO, skin)       # tête
	for sx in [-1.0, 1.0]:
		_box(st, Vector3(sx * 0.27, 1.18, 0.0), Vector3(0.1, 0.5, 0.1), Vector2(0.0, 1.0), cloth, Vector2(0.0, 1.0 if sx > 0.0 else 0.0))   # bras
	if with_flag:
		_box(st, Vector3(0.3, 1.55, 0.0), Vector3(0.03, 0.9, 0.03), Vector2(0.0, 1.0), skin)          # hampe
		_box(st, Vector3(0.3, 1.85, 0.32), Vector3(0.02, 0.4, 0.6), Vector2(1.0, 1.0), cloth)        # drapeau
	st.generate_normals()
	return st.commit()


## Chien (Lot P21) : corps, tête, queue et quatre pattes (UV2.x = ±1 en diagonale pour le trot), face vers +z.
static func build_dog_mesh() -> ArrayMesh:
	var fur := Color(1, 1, 1, 1)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	_box(st, Vector3(0.0, 0.45, 0.0), Vector3(0.22, 0.24, 0.6), Vector2.ZERO, fur)        # corps
	_box(st, Vector3(0.0, 0.62, 0.36), Vector3(0.16, 0.16, 0.2), Vector2.ZERO, fur)       # tête
	_box(st, Vector3(0.0, 0.55, -0.36), Vector3(0.04, 0.04, 0.2), Vector2.ZERO, fur)      # queue
	for leg in [[-1.0, 1.0], [1.0, 1.0], [-1.0, -1.0], [1.0, -1.0]]:
		var swing: float = leg[0] * leg[1]
		_box(st, Vector3(leg[0] * 0.07, 0.17, leg[1] * 0.22), Vector3(0.06, 0.34, 0.06), Vector2.ZERO, fur, Vector2(swing, 0.0))
	st.generate_normals()
	return st.commit()


## Banc des personnes assises (Lot P21) : assise à 0,42 m et deux pieds, sous la personne.
static func build_bench_mesh() -> ArrayMesh:
	var wood := Color(1, 1, 1, 1)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	_box(st, Vector3(0.0, 0.42, -0.05), Vector3(1.3, 0.06, 0.4), Vector2.ZERO, wood)
	for sx in [-0.55, 0.55]:
		_box(st, Vector3(sx, 0.2, -0.05), Vector3(0.06, 0.4, 0.36), Vector2.ZERO, wood)
	st.generate_normals()
	return st.commit()

extends Node3D

## Affichage des animaux du Lot P11 : un MultiMeshInstance3D par espèce (oiseau, vache, mouton,
## chevreuil), maillages bas en polygones construits par code, animés par shaders/fauna.gdshader.
## Pas de class_name : charger par preload("res://scripts/fauna_renderer.gd").
##
## - `set_preset(name, enabled)` : budgets `living(preset).birds` et `.animals` (P4).
## - `set_chunk(k, groups)` / `remove_chunk(k)` : groupes de fauna_placer.gd d'un tronçon.
## - `update(cam_pos, rider_pos, now_s)` une fois par image : comportements (fauna_behaviour.gd), puis
##   transformées des seules bêtes gardées. Les plus proches de la caméra sont gardées, dans la limite
##   du budget ; le tri est refait quand la caméra a bougé de RESELECT_M ou que les groupes changent.
##   Oiseaux en vol et chevreuils sont mis à jour à chaque image, le bétail et les corneilles posées
##   (rotation lente) par quart, une image sur HERD_UPDATE_EVERY chacun ; un chevreuil disparu est réduit à rien jusqu'au tri suivant.
## Lot P23 : le MultiMesh des oiseaux porte aussi les rapaces, les volées en V et les corneilles (même
## silhouette, à l'échelle BIRD_SCALE de leur sorte ; ailes repliées au sol). `setup_sound(sound_player)` :
## croassements à l'envol des corneilles et cris des rapaces (fauna_behaviour.gd `events`) sur un lecteur 3D,
## au volume `ambience.volume` du thème.
## Lot P24 : chevaux des prés et lièvres des champs (fauna_placer.gd), deux espèces de plus ; un lièvre est
## traité comme un chevreuil (une bête seule, mise à jour à chaque image, réduite à rien une fois partie).
## Meuglements, bêlements et hennissements des troupeaux sur le même lecteur 3D.
## Lot U12 (série U) : espèces des biomes (fauna_placer.gd BIOME_SPECIES et BIOME_GROUPS) : zèbre (rayures du
## shader), girafe (taches), renne, dromadaire, bouquetin, marmotte, flamant, héron au sol ; mouette et perroquet
## en vol, même silhouette que l'oiseau dans leur propre MultiMesh (BIRD_SPECIES), à leurs couleurs. Le budget
## `birds` est partagé par toutes les espèces d'oiseaux, le budget `animals` par toutes les bêtes au sol.
## Tous les nœuds sont créés à l'initialisation ; aucun n'est créé ensuite.

const FaunaBehaviour := preload("res://scripts/fauna_behaviour.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const FaunaShader := preload("res://shaders/fauna.gdshader")
const PeopleMesh := preload("res://scripts/people_mesh.gd")

const BIRD_SPECIES := ["bird", "gull", "parrot"]
const GROUND_SPECIES := ["cow", "sheep", "deer", "horse", "hare",
	"zebra", "giraffe", "reindeer", "dromedary", "ibex", "marmot", "flamingo", "heron"]
const SPECIES := BIRD_SPECIES + GROUND_SPECIES
const ALBEDO := {
	"bird": Color(0.12, 0.12, 0.14),
	"cow": Color(0.55, 0.42, 0.32),
	"sheep": Color(0.86, 0.84, 0.78),
	"deer": Color(0.52, 0.34, 0.2),
	"horse": Color(0.4, 0.24, 0.13),
	"hare": Color(0.5, 0.4, 0.28),
	"gull": Color(0.9, 0.9, 0.88),
	"parrot": Color(0.78, 0.1, 0.08),
	"zebra": Color(0.06, 0.055, 0.05),
	"giraffe": Color(0.55, 0.3, 0.12),
	"reindeer": Color(0.45, 0.38, 0.3),
	"dromedary": Color(0.7, 0.55, 0.36),
	"ibex": Color(0.45, 0.36, 0.26),
	"marmot": Color(0.5, 0.4, 0.27),
	"flamingo": Color(0.95, 0.55, 0.6),
	"heron": Color(0.55, 0.58, 0.62),
}
## Lot Y14 : zones de couleur des maillages (CUSTOM0.x) : robe (ALBEDO), teinte d'appoint (ACCENT : mufle et
## mamelle, tête et pattes noires du mouton, bec), sombre (sabots, yeux, truffe), corne, clair (LIGHT : face et
## pattes blanches de la vache, miroir du chevreuil) ; PATCHES : part de la robe en taches claires (vache pie).
const FAUNA_COAT := 0
const FAUNA_ACCENT := 1
const FAUNA_DARK := 2
const FAUNA_HORN := 3
const FAUNA_LIGHT := 4
const SIDES := 8
const ACCENT := {
	"bird": Color(0.3, 0.27, 0.22),
	"cow": Color(0.8, 0.58, 0.54),
	"sheep": Color(0.16, 0.14, 0.13),
	"deer": Color(0.42, 0.27, 0.16),
	"horse": Color(0.07, 0.055, 0.045),
	"hare": Color(0.08, 0.07, 0.06),
	"gull": Color(0.95, 0.75, 0.15),
	"parrot": Color(0.98, 0.8, 0.1),
	"zebra": Color(0.1, 0.09, 0.08),
	"giraffe": Color(0.35, 0.2, 0.1),
	"reindeer": Color(0.3, 0.24, 0.18),
	"dromedary": Color(0.6, 0.46, 0.3),
	"ibex": Color(0.2, 0.16, 0.12),
	"marmot": Color(0.32, 0.24, 0.16),
	"flamingo": Color(0.95, 0.9, 0.85),
	"heron": Color(0.9, 0.72, 0.2),
}
const LIGHT := {
	"bird": Color(0.3, 0.3, 0.32),
	"cow": Color(0.9, 0.87, 0.8),
	"sheep": Color(0.86, 0.84, 0.78),
	"deer": Color(0.9, 0.87, 0.8),
	"horse": Color(0.88, 0.85, 0.8),
	"hare": Color(0.86, 0.83, 0.76),
	"gull": Color(0.62, 0.65, 0.7),
	"parrot": Color(0.1, 0.35, 0.8),
	"zebra": Color(0.93, 0.91, 0.86),
	"giraffe": Color(0.93, 0.85, 0.66),
	"reindeer": Color(0.88, 0.85, 0.78),
	"dromedary": Color(0.82, 0.7, 0.5),
	"ibex": Color(0.8, 0.74, 0.62),
	"marmot": Color(0.7, 0.6, 0.45),
	"flamingo": Color(0.12, 0.1, 0.1),
	"heron": Color(0.22, 0.23, 0.26),
}
const PATCHES := {"bird": 0.0, "cow": 0.4, "sheep": 0.0, "deer": 0.0, "horse": 0.0, "hare": 0.0, "gull": 0.0, "parrot": 0.0,
	"zebra": 0.0, "giraffe": 0.55, "reindeer": 0.0, "dromedary": 0.0, "ibex": 0.0, "marmot": 0.0, "flamingo": 0.0, "heron": 0.0}
## Lot U12 : rayures de la robe (par mètre, 0 = aucune ; zèbre) et descente de la tête qui broute (m).
const STRIPES := {"zebra": 5.0}
const GRAZE_M := {"giraffe": 0.9, "dromedary": 0.2, "marmot": 0.12, "hare": 0.2, "flamingo": 0.7, "heron": 0.5}
const DEFAULT_GRAZE_M := 0.45
const RESELECT_M := 20.0
const HERD_UPDATE_EVERY := 4
## Lot P23 : échelle de la silhouette d'oiseau (0,9 m d'envergure) et battement d'ailes (INSTANCE_CUSTOM.z)
const BIRD_SCALE := {"birds": 1.0, "raptor": 1.5, "vee": 1.8, "crows": 1.05}
const BIRD_FLAP := {"birds": 1.0, "raptor": 0.08, "vee": 0.7, "crows": 1.0}
const FOLDED_WINGS := 0.35        # largeur des ailes repliées d'une corneille au sol
const CALL_DB := -8.0
const CALL_MAX_DISTANCE_M := 400.0

var behaviour := FaunaBehaviour.new()
var budget_birds := 12
var budget_animals := 20
var last_update_usec := 0

var _chunks: Dictionary = {}          # k -> Array de groupes
var _dirty := true
var _last_select_pos := Vector3(INF, INF, INF)
var _mmi: Dictionary = {}             # espèce -> MultiMeshInstance3D
var _sel_birds: Array[Vector2i] = []  # (indice du groupe, indice de l'oiseau)
var _bird_slots: PackedInt32Array = PackedInt32Array()   # case de chaque oiseau gardé dans le MultiMesh de son espèce
var _sel_animals: Array[Vector2i] = []   # (indice du groupe, indice de la bête ; -1 pour un chevreuil)
var _slots: PackedInt32Array = PackedInt32Array()   # case de chaque bête gardée dans son MultiMesh
var _now_s := 0.0
var _frame := 0
var _sound = null
var _audio: AudioStreamPlayer3D
var sounds_played: Array = []         # sons joués, pour les tests


func _init() -> void:
	for sp in SPECIES:
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_custom_data = true
		mm.mesh = build_mesh(sp)
		mm.instance_count = 0
		var mmi := MultiMeshInstance3D.new()
		mmi.name = "Fauna_%s" % sp
		mmi.multimesh = mm
		mmi.material_override = make_material(sp)
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mmi)
		_mmi[sp] = mmi
	_audio = AudioStreamPlayer3D.new()
	_audio.name = "FaunaCall"
	_audio.max_distance = CALL_MAX_DISTANCE_M
	add_child(_audio)
	set_preset(QualityPresets.DEFAULT_PRESET)


## Matériau d'une espèce : shaders/fauna.gdshader à ses couleurs, taches, rayures et descente de la tête.
static func make_material(sp: String) -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	mat.shader = FaunaShader
	mat.set_shader_parameter("mode", 0 if sp in BIRD_SPECIES else 1)
	mat.set_shader_parameter("albedo", ALBEDO[sp])
	mat.set_shader_parameter("accent", ACCENT[sp])
	mat.set_shader_parameter("light", LIGHT[sp])
	mat.set_shader_parameter("patches", PATCHES[sp])
	mat.set_shader_parameter("stripes", float(STRIPES.get(sp, 0.0)))
	mat.set_shader_parameter("graze_m", float(GRAZE_M.get(sp, DEFAULT_GRAZE_M)))
	return mat


## sound_player.gd dont les sons `crow_caw` et `raptor_cry` sont joués (facultatif).
func setup_sound(sound_player) -> void:
	_sound = sound_player


func set_preset(preset_name: String, enabled: bool = true) -> void:
	var living := QualityPresets.living(preset_name, enabled)
	budget_birds = int(living.get("birds", 0))
	budget_animals = int(living.get("animals", 0))
	# Aucune instance affichée avant la première mise à jour (sinon toutes, à l'origine du monde)
	for sp in BIRD_SPECIES:
		_mmi[sp].multimesh.instance_count = budget_birds
		_mmi[sp].multimesh.visible_instance_count = 0
	for sp in GROUND_SPECIES:
		_mmi[sp].multimesh.instance_count = budget_animals
		_mmi[sp].multimesh.visible_instance_count = 0
	_dirty = true


func set_chunk(k: int, groups: Array) -> void:
	_chunks[k] = groups
	_rebuild_groups()


func remove_chunk(k: int) -> void:
	if _chunks.erase(k):
		_rebuild_groups()


func clear() -> void:
	_chunks.clear()
	_rebuild_groups()


func _rebuild_groups() -> void:
	var all := []
	var keys := _chunks.keys()
	keys.sort()
	for k in keys:
		all.append_array(_chunks[k])
	behaviour.setup(all)
	_dirty = true


## Nombre d'instances affichées de l'espèce `sp`.
func visible_count(sp: String) -> int:
	return _mmi[sp].multimesh.visible_instance_count if _mmi.has(sp) else 0


func _select(cam_pos: Vector3) -> void:
	var birds := []
	var animals := []
	var groups: Array = behaviour.groups
	for gi in range(groups.size()):
		var g: Dictionary = groups[gi]
		match str(g["type"]):
			"birds", "raptor", "vee", "crows":
				var d := _bird_anchor(g).distance_squared_to(cam_pos)
				for i in range(_bird_count(g)):
					birds.append([d, gi, i])
			"herd":
				var members: Array = g["members"]
				for i in range(members.size()):
					animals.append([(members[i]["pos"] as Vector3).distance_squared_to(cam_pos), gi, i])
			"deer", "hare":
				if str(g.get("state", "idle")) != "gone":
					animals.append([(g["pos"] as Vector3).distance_squared_to(cam_pos), gi, -1])
	var by_dist := func(a, b): return a[0] < b[0] or (a[0] == b[0] and (a[1] < b[1] or (a[1] == b[1] and a[2] < b[2])))
	birds.sort_custom(by_dist)
	animals.sort_custom(by_dist)
	# Chaque oiseau et chaque bête gardés reçoivent une case fixe de leur espèce jusqu'au tri suivant.
	_sel_birds.clear()
	_bird_slots.clear()
	var used_b := {}
	for sp in BIRD_SPECIES:
		used_b[sp] = 0
	for j in range(mini(budget_birds, birds.size())):
		var gi: int = birds[j][1]
		var i: int = birds[j][2]
		var sp: String = str(groups[gi].get("species", "bird"))
		var slot: int = used_b[sp]
		used_b[sp] = slot + 1
		_sel_birds.append(Vector2i(gi, i))
		_bird_slots.append(slot)
		_mmi[sp].multimesh.set_instance_custom_data(slot, _bird_custom(groups[gi], i, _now_s))
	for sp in used_b:
		_mmi[sp].multimesh.visible_instance_count = used_b[sp]
	_sel_animals.clear()
	_slots.clear()
	var used := {}
	for sp in GROUND_SPECIES:
		used[sp] = 0
	for j in range(mini(budget_animals, animals.size())):
		var gi: int = animals[j][1]
		var i: int = animals[j][2]
		var g: Dictionary = groups[gi]
		var sp: String = str(g["species"])
		var slot: int = used[sp]
		used[sp] = slot + 1
		_sel_animals.append(Vector2i(gi, i))
		_slots.append(slot)
		var mm: MultiMesh = _mmi[sp].multimesh
		if i >= 0:
			var m: Dictionary = g["members"][i]
			mm.set_instance_custom_data(slot, Color(fposmod(float(m["yaw"]), 1.0), 0.0, 0.0, 0.0))
			mm.set_instance_transform(slot, Transform3D(Basis(Vector3.UP, FaunaBehaviour.herd_yaw(m, _now_s)), m["pos"]))
	for sp in used:
		_mmi[sp].multimesh.visible_instance_count = used[sp]
	_last_select_pos = cam_pos
	_dirty = false


func update(cam_pos: Vector3, rider_pos: Vector3, now_s: float) -> void:
	var t0 := Time.get_ticks_usec()
	_now_s = now_s
	behaviour.update(rider_pos, now_s)
	if _dirty or cam_pos.distance_to(_last_select_pos) > RESELECT_M:
		_select(cam_pos)
	var groups: Array = behaviour.groups

	# Oiseaux en vol à chaque image ; corneilles au sol (rotation lente) une image sur HERD_UPDATE_EVERY.
	_frame += 1
	for j in range(_sel_birds.size()):
		var s := _sel_birds[j]
		var g: Dictionary = groups[s.x]
		var t: String = g["type"]
		var mm_b: MultiMesh = _mmi[str(g.get("species", "bird"))].multimesh
		var slot := _bird_slots[j]
		if t == "birds":
			mm_b.set_instance_transform(slot, FaunaBehaviour.bird_transform(g, s.y, now_s))
			continue
		if t == "crows":
			if g["state"] != "flight" and (j + _frame) % HERD_UPDATE_EVERY != 0:
				continue
			mm_b.set_instance_custom_data(slot, _bird_custom(g, s.y, now_s))
		mm_b.set_instance_transform(slot, bird_transform(g, s.y, now_s))

	# Chevreuils et lièvres à chaque image ; bétail (rotation lente) par quart, une image sur quatre chacun.
	for j in range(_sel_animals.size()):
		var s := _sel_animals[j]
		var g: Dictionary = groups[s.x]
		if s.y < 0:
			var mm_w: MultiMesh = _mmi[str(g["species"])].multimesh
			mm_w.set_instance_transform(_slots[j], wild_transform(g, now_s))
			mm_w.set_instance_custom_data(_slots[j], Color(0.3, 0.0 if str(g["state"]) == "idle" else 1.0, 0.0, 0.0))
		elif (j + _frame) % HERD_UPDATE_EVERY == 0:
			var m: Dictionary = g["members"][s.y]
			var mm: MultiMesh = _mmi[str(g["species"])].multimesh
			mm.set_instance_transform(_slots[j], Transform3D(Basis(Vector3.UP, FaunaBehaviour.herd_yaw(m, now_s)), m["pos"]))
	for ev in behaviour.events:
		_play(ev)
	last_update_usec = Time.get_ticks_usec() - t0


## Transformée d'un chevreuil ou d'un lièvre (lot P24) : réduit à rien et caché sous le sol une fois parti.
static func wild_transform(g: Dictionary, now_s: float) -> Transform3D:
	var alpha := FaunaBehaviour.wild_alpha(g, now_s)
	var pos: Vector3
	var yaw: float
	if str(g["type"]) == "hare":
		pos = FaunaBehaviour.hare_position(g, now_s)
		yaw = FaunaBehaviour.hare_yaw(g, now_s)
	else:
		pos = FaunaBehaviour.deer_position(g, now_s)
		var fd: Vector3 = g["flee_dir"]
		yaw = float(g["yaw"]) if str(g["state"]) == "idle" else atan2(fd.x, fd.z)
	return Transform3D(Basis(Vector3.UP, yaw).scaled(Vector3.ONE * maxf(alpha, 0.001)),
		pos - (Vector3.ZERO if alpha > 0.0 else Vector3(0.0, 50.0, 0.0)))


## Point de référence d'un groupe d'oiseaux pour le tri par distance.
static func _bird_anchor(g: Dictionary) -> Vector3:
	match str(g["type"]):
		"vee":
			return g["origin"]
		"crows":
			return g["pos"]
	return g["center"]


static func _bird_count(g: Dictionary) -> int:
	return 1 if str(g["type"]) == "raptor" else (g["members"] as Array).size()


## Données d'instance d'un oiseau : (phase du battement 0 à 1, 0, amplitude du battement, 0).
static func _bird_custom(g: Dictionary, i: int, now_s: float) -> Color:
	var t: String = g["type"]
	var phase := fposmod(float(g["members"][i]["phase"]) / TAU, 1.0) if t == "birds" else fposmod(0.137 * i + 0.31, 1.0)
	var flap: float = BIRD_FLAP[t]
	if t == "crows" and not FaunaBehaviour.crow_flying(g, i, now_s):
		flap = 0.0
	return Color(phase, 0.0, flap, 0.0)


## Transformée du `i`-ième oiseau du groupe `g` (bande, rapace, volée en V ou corneilles).
static func bird_transform(g: Dictionary, i: int, now_s: float) -> Transform3D:
	var t: String = g["type"]
	var k: float = BIRD_SCALE[t]
	match t:
		"raptor":
			return Transform3D(Basis(Vector3.UP, FaunaBehaviour.raptor_yaw(g, now_s)).scaled(Vector3.ONE * k),
				FaunaBehaviour.raptor_position(g, now_s))
		"vee":
			var f := maxf(FaunaBehaviour.vee_scale(g, now_s), 0.001)
			return Transform3D(Basis(Vector3.UP, FaunaBehaviour.vee_yaw(g)).scaled(Vector3.ONE * k * f),
				FaunaBehaviour.vee_position(g, i, now_s))
		"crows":
			var wings := 1.0 if FaunaBehaviour.crow_flying(g, i, now_s) else FOLDED_WINGS
			return Transform3D(Basis(Vector3.UP, FaunaBehaviour.crow_yaw(g, i, now_s)) * Basis.from_scale(Vector3(wings * k, k, k)),
				FaunaBehaviour.crow_position(g, i, now_s) + Vector3(0.0, 0.08 * k, 0.0))
	return FaunaBehaviour.bird_transform(g, i, now_s)


func _play(ev: Dictionary) -> void:
	var kind := str(ev.get("sound", ""))
	sounds_played.append(kind)
	_audio.position = ev.get("pos", Vector3.ZERO)
	var vol := 0.6
	if _sound != null:
		vol = float(_sound.ambience.volume)
		_audio.stream = _sound.stream(kind)
	_audio.volume_db = CALL_DB + linear_to_db(maxf(vol / 0.6, 0.001))
	if is_inside_tree() and _audio.stream != null:
		_audio.play()


# --- maillages ------------------------------------------------------------------------------
# Lot Y14 : construits avec le Builder de people_mesh.gd (prismes effilés et ellipsoïdes à normales lissées).
# CUSTOM0.x : zone (FAUNA_*), qui choisit la couleur dans shaders/fauna.gdshader ; UV.x : poids de l'aile
# (oiseau) ; UV.y : poids de la tête qui broute (bêtes au sol, progressif le long du cou).

## Maillage d'une espèce (SPECIES ; mouette et perroquet : silhouette de l'oiseau), avant vers +z, pieds à y = 0 ; l'oiseau est centré,
## ailes le long de x (0,9 m d'envergure, repliées par l'écrasement de x d'une corneille posée).
static func build_mesh(sp: String) -> ArrayMesh:
	match sp:
		"bird":
			return _build_bird()
		"cow":
			return _build_cow()
		"sheep":
			return _build_sheep()
		"horse":
			return _build_horse()
		"hare":
			return _build_hare()
		"gull", "parrot":
			return _build_bird()
		"zebra":
			return _build_zebra()
		"giraffe":
			return _build_giraffe()
		"reindeer":
			return _build_reindeer()
		"dromedary":
			return _build_dromedary()
		"ibex":
			return _build_ibex()
		"marmot":
			return _build_marmot()
		"flamingo":
			return _build_wader(0.95, 0.5, true)
		"heron":
			return _build_wader(0.62, 0.42, false)
		_:
			return _build_deer()


static func _build_bird() -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
	m.region = FAUNA_COAT
	m.ellipsoid(Vector3(0.0, 0.0, -0.01), Vector3(0.055, 0.05, 0.15))   # corps
	m.ellipsoid(Vector3(0.0, 0.025, 0.15), Vector3(0.04, 0.04, 0.045))  # tête
	for sx in [-1.0, 1.0]:
		# Queue en éventail, puis aile : bord d'attaque arrondi, rémiges écartées au bout
		_flat(m, [Vector3(sx * 0.02, 0.0, -0.12), Vector3(sx * 0.075, 0.0, -0.29), Vector3(0.0, 0.0, -0.31)], 0.0)
		var wing := [Vector2(0.04, 0.07), Vector2(0.16, 0.085), Vector2(0.28, 0.06), Vector2(0.37, 0.02),
			Vector2(0.45, -0.01), Vector2(0.37, -0.03), Vector2(0.43, -0.06), Vector2(0.35, -0.07),
			Vector2(0.39, -0.1), Vector2(0.3, -0.1), Vector2(0.16, -0.11), Vector2(0.04, -0.08)]
		var pts := []
		for w in wing:
			pts.append(Vector3(sx * w.x, 0.04 * w.x, w.y))   # léger dièdre
		_flat(m, pts, -1.0)
	m.region = FAUNA_ACCENT
	m.prism(Vector3(0.0, 0.02, 0.185), Vector3(0.0, 0.012, 0.24), Vector2(0.014, 0.012), Vector2(0.002, 0.002), 4)   # bec
	m.region = FAUNA_DARK
	for sx in [-1.0, 1.0]:
		m.ellipsoid(Vector3(sx * 0.03, 0.035, 0.17), Vector3(0.009, 0.009, 0.009), -90.0, 3)   # yeux
	return m.commit()


## Polygone plat (éventail depuis le premier point), normale vers le haut ; `wing_w` < 0 : poids de l'aile
## selon l'écart à l'axe du corps (0 à l'attache, 1 au-delà de 0,12 m).
static func _flat(m, pts: Array, wing_w: float) -> void:
	for i in range(1, pts.size() - 1):
		for p in [pts[0], pts[i], pts[i + 1]]:
			var w := wing_w if wing_w >= 0.0 else clampf((absf(p.x) - 0.04) / 0.08, 0.0, 1.0)
			m.vertex(p, Vector3.UP, w)


## Patte de bête : cuisse ou épaule effilée, canon fin, sabot sombre ; `x`, `z` : attache, `hip_y` : hauteur.
static func _leg(m, x: float, z: float, hip_y: float, r_top: float, r_low: float, coat_low: int) -> void:
	var knee_y := hip_y * 0.48
	var bend := 0.03 if z > 0.0 else -0.05   # jarret des pattes arrière en arrière
	m.region = FAUNA_COAT
	m.prism(Vector3(x, hip_y, z), Vector3(x, knee_y, z + bend), Vector2(r_top, r_top * 1.25), Vector2(r_low * 1.2, r_low * 1.2), 6)
	m.region = coat_low
	m.prism(Vector3(x, knee_y, z + bend), Vector3(x, 0.06, z), Vector2(r_low, r_low), Vector2(r_low * 0.85, r_low * 0.85), 6)
	m.region = FAUNA_DARK
	m.prism(Vector3(x, 0.0, z), Vector3(x, 0.07, z), Vector2(r_low * 1.05, r_low * 1.2), Vector2(r_low * 0.9, r_low * 0.9), 6)


## Vache pie rouge (taches claires du shader) : tronc, hanches, mufle rose, cornes, mamelle, queue à toupet.
static func _build_cow() -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
	m.region = FAUNA_COAT
	m.prism(Vector3(0.0, 1.02, -0.72), Vector3(0.0, 1.06, 0.62), Vector2(0.36, 0.38), Vector2(0.34, 0.42))   # tronc
	m.ellipsoid(Vector3(0.0, 1.04, -0.72), Vector3(0.36, 0.38, 0.2))   # croupe
	m.ellipsoid(Vector3(0.0, 1.06, 0.62), Vector3(0.34, 0.42, 0.22))   # poitrail
	for sx in [-1.0, 1.0]:
		m.ellipsoid(Vector3(sx * 0.2, 1.28, -0.7), Vector3(0.1, 0.1, 0.12), -30.0, 3)   # pointes des hanches
	m.prism(Vector3(0.0, 1.0, -0.88), Vector3(0.0, 0.55, -0.93), Vector2(0.025, 0.025), Vector2(0.018, 0.018), 4)   # queue
	m.region = FAUNA_LIGHT
	m.ellipsoid(Vector3(0.0, 0.5, -0.94), Vector3(0.045, 0.1, 0.045), -90.0, 3)   # toupet
	m.region = FAUNA_ACCENT
	m.ellipsoid(Vector3(0.0, 0.66, -0.38), Vector3(0.16, 0.12, 0.17), -90.0, 4)   # mamelle
	for lx in [-1.0, 1.0]:
		for lz in [-0.6, 0.5]:
			_leg(m, lx * 0.21, lz, 0.95, 0.12, 0.05, FAUNA_LIGHT)
	# Cou puis tête, qui descendent brouter (UV.y de 0 à l'épaule à 1 à la tête)
	m.region = FAUNA_COAT
	m.prism(Vector3(0.0, 1.1, 0.66), Vector3(0.0, 1.2, 0.98), Vector2(0.22, 0.3), Vector2(0.14, 0.17), SIDES, 1.0)
	m.uv = Vector2(0.0, 1.0)
	m.region = FAUNA_LIGHT
	m.prism(Vector3(0.0, 1.26, 0.98), Vector3(0.0, 1.0, 1.32), Vector2(0.13, 0.13), Vector2(0.085, 0.08))   # face blanche
	m.region = FAUNA_ACCENT
	m.ellipsoid(Vector3(0.0, 0.99, 1.33), Vector3(0.095, 0.07, 0.06))   # mufle
	m.region = FAUNA_COAT
	for sx in [-1.0, 1.0]:
		m.xform = Transform3D(Basis(Vector3.BACK, sx * -0.35), Vector3(sx * 0.17, 1.27, 1.0))
		m.ellipsoid(Vector3.ZERO, Vector3(0.09, 0.025, 0.05), -90.0, 3)   # oreilles
		m.xform = Transform3D.IDENTITY
		m.region = FAUNA_HORN
		m.prism(Vector3(sx * 0.07, 1.33, 0.99), Vector3(sx * 0.17, 1.4, 1.03), Vector2(0.025, 0.025), Vector2(0.008, 0.008), 5)
		m.region = FAUNA_DARK
		m.ellipsoid(Vector3(sx * 0.1, 1.2, 1.12), Vector3(0.018, 0.02, 0.02), -90.0, 3)   # yeux
		m.region = FAUNA_COAT
	m.uv = Vector2.ZERO
	return m.commit()


## Mouton : toison en bosses (ellipsoïdes qui se chevauchent), tête et pattes noires, oreilles tombantes.
static func _build_sheep() -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
	m.region = FAUNA_COAT
	m.ellipsoid(Vector3(0.0, 0.66, 0.0), Vector3(0.3, 0.28, 0.5))
	for b in [[0.0, 0.84, 0.18, 0.16], [0.0, 0.82, -0.2, 0.17], [0.17, 0.66, 0.25, 0.14], [-0.17, 0.66, 0.25, 0.14],
			[0.18, 0.68, -0.22, 0.15], [-0.18, 0.68, -0.22, 0.15], [0.0, 0.66, -0.42, 0.15], [0.0, 0.72, 0.42, 0.14]]:
		m.ellipsoid(Vector3(b[0], b[1], b[2]), Vector3(b[3], b[3], b[3]), -90.0, 4)
	for lx in [-1.0, 1.0]:
		for lz in [-0.3, 0.3]:
			_leg(m, lx * 0.14, lz, 0.5, 0.06, 0.028, FAUNA_ACCENT)
	m.prism(Vector3(0.0, 0.76, 0.42), Vector3(0.0, 0.8, 0.56), Vector2(0.12, 0.13), Vector2(0.09, 0.1), SIDES, 1.0)   # cou laineux
	m.uv = Vector2(0.0, 1.0)
	m.ellipsoid(Vector3(0.0, 0.88, 0.57), Vector3(0.1, 0.07, 0.08), 0.0, 3)   # toupet sur le crâne
	m.region = FAUNA_ACCENT
	m.prism(Vector3(0.0, 0.84, 0.56), Vector3(0.0, 0.72, 0.76), Vector2(0.075, 0.08), Vector2(0.045, 0.05))   # tête
	for sx in [-1.0, 1.0]:
		m.xform = Transform3D(Basis(Vector3.BACK, sx * 0.5), Vector3(sx * 0.1, 0.84, 0.6))
		m.ellipsoid(Vector3.ZERO, Vector3(0.07, 0.02, 0.035), -90.0, 3)   # oreilles
		m.xform = Transform3D.IDENTITY
	m.region = FAUNA_DARK
	for sx in [-1.0, 1.0]:
		m.ellipsoid(Vector3(sx * 0.06, 0.82, 0.64), Vector3(0.014, 0.014, 0.014), -90.0, 3)
	m.uv = Vector2.ZERO
	return m.commit()


## Chevreuil : corps fin, longues pattes, miroir blanc à l'arrière, grandes oreilles, petits bois.
static func _build_deer() -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
	m.region = FAUNA_COAT
	m.prism(Vector3(0.0, 0.88, -0.42), Vector3(0.0, 0.92, 0.4), Vector2(0.17, 0.2), Vector2(0.16, 0.22))
	m.ellipsoid(Vector3(0.0, 0.88, -0.42), Vector3(0.17, 0.2, 0.12))
	m.ellipsoid(Vector3(0.0, 0.92, 0.4), Vector3(0.16, 0.22, 0.13))
	m.region = FAUNA_LIGHT
	m.ellipsoid(Vector3(0.0, 0.9, -0.5), Vector3(0.12, 0.14, 0.07))   # miroir
	m.ellipsoid(Vector3(0.0, 0.74, 0.0), Vector3(0.1, 0.06, 0.32), -90.0, 3)   # ventre
	for lx in [-1.0, 1.0]:
		for lz in [-0.36, 0.32]:
			_leg(m, lx * 0.09, lz, 0.82, 0.07, 0.022, FAUNA_COAT)
	m.region = FAUNA_COAT
	m.prism(Vector3(0.0, 0.98, 0.42), Vector3(0.0, 1.3, 0.6), Vector2(0.09, 0.12), Vector2(0.06, 0.07), SIDES, 1.0)   # cou dressé
	m.uv = Vector2(0.0, 1.0)
	m.prism(Vector3(0.0, 1.36, 0.58), Vector3(0.0, 1.27, 0.8), Vector2(0.07, 0.08), Vector2(0.035, 0.04))   # tête
	m.region = FAUNA_DARK
	m.ellipsoid(Vector3(0.0, 1.27, 0.8), Vector3(0.03, 0.025, 0.025), -90.0, 3)   # truffe
	for sx in [-1.0, 1.0]:
		m.ellipsoid(Vector3(sx * 0.05, 1.36, 0.66), Vector3(0.012, 0.014, 0.014), -90.0, 3)
		m.region = FAUNA_COAT
		m.xform = Transform3D(Basis(Vector3.BACK, sx * -0.6), Vector3(sx * 0.08, 1.43, 0.58))
		m.ellipsoid(Vector3(0.0, 0.05, 0.0), Vector3(0.035, 0.07, 0.015), -90.0, 3)   # oreilles
		m.xform = Transform3D.IDENTITY
		m.region = FAUNA_HORN
		m.prism(Vector3(sx * 0.03, 1.42, 0.62), Vector3(sx * 0.05, 1.58, 0.6), Vector2(0.012, 0.012), Vector2(0.006, 0.006), 4)
		m.prism(Vector3(sx * 0.04, 1.5, 0.61), Vector3(sx * 0.05, 1.54, 0.68), Vector2(0.007, 0.007), Vector2(0.004, 0.004), 4)
		m.region = FAUNA_DARK
	m.uv = Vector2.ZERO
	return m.commit()


## Cheval bai (lot P24) : tronc long, croupe ronde, garrot haut, encolure arquée, crinière et queue sombres,
## liste blanche et balzanes, longues pattes fines à sabots.
static func _build_horse() -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
	m.region = FAUNA_COAT
	m.prism(Vector3(0.0, 1.18, -0.62), Vector3(0.0, 1.22, 0.55), Vector2(0.27, 0.32), Vector2(0.26, 0.36))   # tronc
	m.ellipsoid(Vector3(0.0, 1.2, -0.62), Vector3(0.29, 0.33, 0.24))   # croupe
	m.ellipsoid(Vector3(0.0, 1.24, 0.55), Vector3(0.26, 0.36, 0.2))    # poitrail
	m.ellipsoid(Vector3(0.0, 1.5, 0.42), Vector3(0.14, 0.12, 0.2), -30.0, 3)   # garrot
	for lx in [-1.0, 1.0]:
		for lz in [-0.6, 0.5]:
			_leg(m, lx * 0.17, lz, 1.1, 0.1, 0.04, FAUNA_LIGHT if lz < 0.0 else FAUNA_COAT)   # balzanes derrière
	# Encolure arquée puis tête, qui descendent brouter (UV.y)
	m.prism(Vector3(0.0, 1.34, 0.58), Vector3(0.0, 1.78, 0.9), Vector2(0.15, 0.24), Vector2(0.1, 0.13), SIDES, 1.0)
	m.uv = Vector2(0.0, 1.0)
	m.prism(Vector3(0.0, 1.84, 0.9), Vector3(0.0, 1.52, 1.25), Vector2(0.1, 0.12), Vector2(0.06, 0.08))   # tête
	m.region = FAUNA_LIGHT
	m.prism(Vector3(0.0, 1.8, 1.0), Vector3(0.0, 1.55, 1.27), Vector2(0.035, 0.02), Vector2(0.025, 0.015), 4)   # liste
	m.region = FAUNA_DARK
	m.ellipsoid(Vector3(0.0, 1.51, 1.26), Vector3(0.06, 0.05, 0.04), -90.0, 3)   # bout du nez
	for sx in [-1.0, 1.0]:
		m.ellipsoid(Vector3(sx * 0.075, 1.75, 1.04), Vector3(0.016, 0.018, 0.018), -90.0, 3)   # yeux
		m.region = FAUNA_COAT
		m.prism(Vector3(sx * 0.05, 1.88, 0.92), Vector3(sx * 0.06, 2.0, 0.9), Vector2(0.03, 0.02), Vector2(0.006, 0.006), 4)   # oreilles
		m.region = FAUNA_DARK
	m.region = FAUNA_ACCENT
	m.prism(Vector3(0.0, 1.92, 0.88), Vector3(0.0, 1.5, 0.5), Vector2(0.03, 0.07), Vector2(0.025, 0.05), 4, 1.0)   # crinière
	m.uv = Vector2.ZERO
	m.prism(Vector3(0.0, 1.3, -0.85), Vector3(0.0, 0.7, -0.98), Vector2(0.06, 0.06), Vector2(0.03, 0.05), 5)   # queue
	return m.commit()


## Lièvre (lot P24) : corps ramassé, longues pattes arrière, très longues oreilles à pointe noire,
## ventre et dessous de la queue blancs, 0,6 m de long.
static func _build_hare() -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
	m.region = FAUNA_COAT
	m.ellipsoid(Vector3(0.0, 0.24, -0.06), Vector3(0.11, 0.13, 0.2))   # corps, arrière plus haut
	m.ellipsoid(Vector3(0.0, 0.22, 0.1), Vector3(0.09, 0.1, 0.11))
	for sx in [-1.0, 1.0]:
		m.ellipsoid(Vector3(sx * 0.08, 0.17, -0.12), Vector3(0.05, 0.09, 0.11), -90.0, 4)   # cuisses
		m.prism(Vector3(sx * 0.08, 0.02, -0.08), Vector3(sx * 0.08, 0.02, 0.06), Vector2(0.02, 0.015), Vector2(0.015, 0.012), 4)   # pieds arrière
		m.prism(Vector3(sx * 0.05, 0.16, 0.14), Vector3(sx * 0.05, 0.0015, 0.16), Vector2(0.015, 0.015), Vector2(0.012, 0.012), 4)   # pattes avant
	m.region = FAUNA_LIGHT
	m.ellipsoid(Vector3(0.0, 0.16, 0.0), Vector3(0.07, 0.05, 0.16), -90.0, 3)   # ventre
	m.ellipsoid(Vector3(0.0, 0.3, -0.26), Vector3(0.04, 0.04, 0.03), -90.0, 3)   # queue
	m.region = FAUNA_COAT
	m.uv = Vector2(0.0, 1.0)
	m.ellipsoid(Vector3(0.0, 0.33, 0.2), Vector3(0.06, 0.06, 0.08))   # tête
	for sx in [-1.0, 1.0]:
		m.prism(Vector3(sx * 0.025, 0.37, 0.18), Vector3(sx * 0.045, 0.5, 0.12), Vector2(0.022, 0.008), Vector2(0.02, 0.007), 4)   # oreille
		m.region = FAUNA_ACCENT
		m.prism(Vector3(sx * 0.045, 0.5, 0.12), Vector3(sx * 0.05, 0.53, 0.11), Vector2(0.02, 0.007), Vector2(0.004, 0.004), 4)   # pointe noire
		m.region = FAUNA_DARK
		m.ellipsoid(Vector3(sx * 0.04, 0.35, 0.24), Vector3(0.011, 0.012, 0.012), -90.0, 3)   # yeux
		m.region = FAUNA_COAT
	m.uv = Vector2.ZERO
	return m.commit()


# --- espèces des biomes (lot U12) ---------------------------------------------------------------

## Zèbre : cheval trapu, rayures noires et blanches du shader (STRIPES), crinière droite, museau sombre.
static func _build_zebra() -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
	m.region = FAUNA_COAT
	m.prism(Vector3(0.0, 1.0, -0.55), Vector3(0.0, 1.04, 0.5), Vector2(0.25, 0.3), Vector2(0.24, 0.32))   # tronc
	m.ellipsoid(Vector3(0.0, 1.02, -0.55), Vector3(0.26, 0.31, 0.22))   # croupe
	m.ellipsoid(Vector3(0.0, 1.05, 0.5), Vector3(0.24, 0.32, 0.18))     # poitrail
	for lx in [-1.0, 1.0]:
		for lz in [-0.52, 0.44]:
			_leg(m, lx * 0.15, lz, 0.95, 0.09, 0.035, FAUNA_COAT)
	m.prism(Vector3(0.0, 1.14, 0.52), Vector3(0.0, 1.55, 0.8), Vector2(0.13, 0.21), Vector2(0.09, 0.12), SIDES, 1.0)   # encolure
	m.uv = Vector2(0.0, 1.0)
	m.prism(Vector3(0.0, 1.6, 0.8), Vector3(0.0, 1.32, 1.12), Vector2(0.09, 0.11), Vector2(0.055, 0.07))   # tête
	m.region = FAUNA_ACCENT
	m.ellipsoid(Vector3(0.0, 1.31, 1.12), Vector3(0.06, 0.05, 0.05), -90.0, 3)   # museau
	m.uv = Vector2.ZERO
	m.prism(Vector3(0.0, 1.32, 0.45), Vector3(0.0, 1.7, 0.78), Vector2(0.02, 0.06), Vector2(0.02, 0.07), 4, 1.0)   # crinière droite
	m.uv = Vector2(0.0, 1.0)
	m.region = FAUNA_DARK
	for sx in [-1.0, 1.0]:
		m.ellipsoid(Vector3(sx * 0.065, 1.52, 0.92), Vector3(0.015, 0.016, 0.016), -90.0, 3)   # yeux
		m.region = FAUNA_COAT
		m.prism(Vector3(sx * 0.05, 1.64, 0.82), Vector3(sx * 0.07, 1.8, 0.8), Vector2(0.035, 0.02), Vector2(0.008, 0.008), 4)   # oreilles
		m.region = FAUNA_DARK
	m.uv = Vector2.ZERO
	m.region = FAUNA_ACCENT
	m.prism(Vector3(0.0, 1.1, -0.76), Vector3(0.0, 0.6, -0.84), Vector2(0.025, 0.025), Vector2(0.02, 0.03), 4)   # queue
	return m.commit()


## Girafe : robe à taches (PATCHES), très longues pattes, long cou qui monte à 4,5 m, ossicones, crinière courte.
static func _build_giraffe() -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
	m.region = FAUNA_COAT
	m.prism(Vector3(0.0, 1.95, -0.6), Vector3(0.0, 2.2, 0.55), Vector2(0.3, 0.34), Vector2(0.32, 0.4))   # tronc, dos en pente
	m.ellipsoid(Vector3(0.0, 1.95, -0.6), Vector3(0.3, 0.34, 0.22))
	m.ellipsoid(Vector3(0.0, 2.2, 0.55), Vector3(0.32, 0.4, 0.24))
	for lx in [-1.0, 1.0]:
		_leg(m, lx * 0.2, -0.55, 1.85, 0.11, 0.045, FAUNA_LIGHT)
		_leg(m, lx * 0.2, 0.5, 2.0, 0.11, 0.045, FAUNA_LIGHT)
	m.prism(Vector3(0.0, 2.4, 0.6), Vector3(0.0, 4.25, 1.1), Vector2(0.17, 0.24), Vector2(0.09, 0.1), SIDES, 1.0)   # cou
	m.uv = Vector2(0.0, 1.0)
	m.prism(Vector3(0.0, 4.4, 1.05), Vector3(0.0, 4.25, 1.55), Vector2(0.1, 0.12), Vector2(0.055, 0.07))   # tête
	m.region = FAUNA_ACCENT
	m.uv = Vector2.ZERO
	m.prism(Vector3(0.0, 2.6, 0.5), Vector3(0.0, 4.3, 1.02), Vector2(0.025, 0.05), Vector2(0.025, 0.05), 4, 1.0)   # crinière
	m.uv = Vector2(0.0, 1.0)
	m.region = FAUNA_DARK
	m.ellipsoid(Vector3(0.0, 4.24, 1.56), Vector3(0.05, 0.05, 0.04), -90.0, 3)   # museau
	for sx in [-1.0, 1.0]:
		m.ellipsoid(Vector3(sx * 0.08, 4.42, 1.25), Vector3(0.02, 0.022, 0.022), -90.0, 3)   # yeux
		m.region = FAUNA_ACCENT
		m.prism(Vector3(sx * 0.05, 4.48, 1.08), Vector3(sx * 0.06, 4.66, 1.06), Vector2(0.025, 0.025), Vector2(0.03, 0.03), 4)   # ossicones
		m.region = FAUNA_COAT
		m.prism(Vector3(sx * 0.08, 4.46, 1.04), Vector3(sx * 0.2, 4.5, 1.0), Vector2(0.04, 0.02), Vector2(0.01, 0.01), 4)   # oreilles
		m.region = FAUNA_DARK
	m.uv = Vector2.ZERO
	m.region = FAUNA_COAT
	m.prism(Vector3(0.0, 2.0, -0.8), Vector3(0.0, 1.2, -0.88), Vector2(0.025, 0.025), Vector2(0.015, 0.015), 4)   # queue
	m.region = FAUNA_ACCENT
	m.ellipsoid(Vector3(0.0, 1.15, -0.89), Vector3(0.04, 0.1, 0.04), -90.0, 3)   # toupet
	return m.commit()


## Renne : corps massif, cou et ventre clairs, grands bois ramifiés, museau large.
static func _build_reindeer() -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
	m.region = FAUNA_COAT
	m.prism(Vector3(0.0, 1.0, -0.55), Vector3(0.0, 1.05, 0.48), Vector2(0.24, 0.28), Vector2(0.24, 0.31))
	m.ellipsoid(Vector3(0.0, 1.0, -0.55), Vector3(0.24, 0.28, 0.16))
	m.ellipsoid(Vector3(0.0, 1.05, 0.48), Vector3(0.24, 0.31, 0.16))
	m.region = FAUNA_LIGHT
	m.ellipsoid(Vector3(0.0, 0.8, 0.0), Vector3(0.14, 0.08, 0.45), -90.0, 3)   # ventre
	m.ellipsoid(Vector3(0.0, 1.0, -0.66), Vector3(0.14, 0.14, 0.07), -90.0, 3)   # croupe claire
	for lx in [-1.0, 1.0]:
		for lz in [-0.5, 0.42]:
			_leg(m, lx * 0.14, lz, 0.92, 0.09, 0.035, FAUNA_COAT)
	m.region = FAUNA_LIGHT
	m.prism(Vector3(0.0, 1.12, 0.5), Vector3(0.0, 1.45, 0.75), Vector2(0.14, 0.2), Vector2(0.09, 0.11), SIDES, 1.0)   # cou clair
	m.uv = Vector2(0.0, 1.0)
	m.region = FAUNA_COAT
	m.prism(Vector3(0.0, 1.52, 0.72), Vector3(0.0, 1.36, 1.05), Vector2(0.08, 0.1), Vector2(0.06, 0.07))   # tête
	m.region = FAUNA_DARK
	m.ellipsoid(Vector3(0.0, 1.35, 1.06), Vector3(0.05, 0.04, 0.035), -90.0, 3)   # mufle
	for sx in [-1.0, 1.0]:
		m.ellipsoid(Vector3(sx * 0.06, 1.5, 0.85), Vector3(0.014, 0.016, 0.016), -90.0, 3)   # yeux
		m.region = FAUNA_HORN
		# Bois : merrain en arc vers l'arrière puis vers l'avant, trois andouillers
		var a := Vector3(sx * 0.05, 1.58, 0.74)
		var b := Vector3(sx * 0.22, 1.9, 0.6)
		var c := Vector3(sx * 0.3, 2.15, 0.72)
		var d := Vector3(sx * 0.26, 2.32, 0.9)
		m.prism(a, b, Vector2(0.022, 0.022), Vector2(0.018, 0.018), 4)
		m.prism(b, c, Vector2(0.018, 0.018), Vector2(0.014, 0.014), 4)
		m.prism(c, d, Vector2(0.014, 0.014), Vector2(0.006, 0.006), 4)
		m.prism(Vector3(sx * 0.1, 1.66, 0.7), Vector3(sx * 0.08, 1.72, 0.92), Vector2(0.012, 0.012), Vector2(0.005, 0.005), 4)   # andouiller de face
		m.prism(b, Vector3(sx * 0.32, 2.02, 0.5), Vector2(0.012, 0.012), Vector2(0.005, 0.005), 4)
		m.prism(c, Vector3(sx * 0.42, 2.25, 0.66), Vector2(0.01, 0.01), Vector2(0.004, 0.004), 4)
		m.region = FAUNA_COAT
		m.prism(Vector3(sx * 0.07, 1.55, 0.74), Vector3(sx * 0.17, 1.6, 0.7), Vector2(0.03, 0.015), Vector2(0.008, 0.008), 4)   # oreilles
		m.region = FAUNA_DARK
	m.uv = Vector2.ZERO
	return m.commit()


## Dromadaire : bosse unique, longues pattes à genoux calleux, cou en S qui descend puis remonte.
static func _build_dromedary() -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
	m.region = FAUNA_COAT
	m.prism(Vector3(0.0, 1.55, -0.6), Vector3(0.0, 1.6, 0.5), Vector2(0.28, 0.3), Vector2(0.27, 0.34))   # tronc
	m.ellipsoid(Vector3(0.0, 1.55, -0.6), Vector3(0.28, 0.3, 0.2))
	m.ellipsoid(Vector3(0.0, 1.6, 0.5), Vector3(0.27, 0.34, 0.2))
	m.ellipsoid(Vector3(0.0, 1.85, -0.05), Vector3(0.22, 0.38, 0.4), 0.0, 4)   # bosse
	for lx in [-1.0, 1.0]:
		for lz in [-0.55, 0.45]:
			_leg(m, lx * 0.17, lz, 1.45, 0.1, 0.045, FAUNA_COAT)
			m.region = FAUNA_ACCENT
			m.ellipsoid(Vector3(lx * 0.17, 0.72, lz + (0.03 if lz > 0.0 else -0.05)), Vector3(0.06, 0.06, 0.06), -90.0, 3)   # genou
	m.region = FAUNA_COAT
	m.prism(Vector3(0.0, 1.66, 0.6), Vector3(0.0, 1.5, 0.98), Vector2(0.13, 0.2), Vector2(0.1, 0.11), SIDES, 1.0)   # cou qui descend
	m.uv = Vector2(0.0, 1.0)
	m.prism(Vector3(0.0, 1.5, 0.98), Vector3(0.0, 1.98, 1.2), Vector2(0.1, 0.11), Vector2(0.08, 0.09))   # cou qui remonte
	m.prism(Vector3(0.0, 2.02, 1.18), Vector3(0.0, 1.9, 1.55), Vector2(0.08, 0.1), Vector2(0.055, 0.06))   # tête
	m.region = FAUNA_ACCENT
	m.ellipsoid(Vector3(0.0, 1.88, 1.55), Vector3(0.06, 0.05, 0.045), -90.0, 3)   # lèvres
	m.region = FAUNA_DARK
	for sx in [-1.0, 1.0]:
		m.ellipsoid(Vector3(sx * 0.06, 2.0, 1.3), Vector3(0.016, 0.016, 0.016), -90.0, 3)   # yeux
		m.region = FAUNA_COAT
		m.ellipsoid(Vector3(sx * 0.06, 2.08, 1.2), Vector3(0.02, 0.035, 0.015), -90.0, 3)   # oreilles
		m.region = FAUNA_DARK
	m.uv = Vector2.ZERO
	m.region = FAUNA_ACCENT
	m.prism(Vector3(0.0, 1.6, -0.78), Vector3(0.0, 1.0, -0.84), Vector2(0.025, 0.025), Vector2(0.02, 0.03), 4)   # queue
	return m.commit()


## Bouquetin : chèvre trapue, grandes cornes annelées en arc vers l'arrière, barbiche, pattes sombres.
static func _build_ibex() -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
	m.region = FAUNA_COAT
	m.prism(Vector3(0.0, 0.78, -0.42), Vector3(0.0, 0.82, 0.36), Vector2(0.2, 0.23), Vector2(0.2, 0.26))
	m.ellipsoid(Vector3(0.0, 0.78, -0.42), Vector3(0.2, 0.23, 0.14))
	m.ellipsoid(Vector3(0.0, 0.82, 0.36), Vector3(0.2, 0.26, 0.14))
	m.region = FAUNA_LIGHT
	m.ellipsoid(Vector3(0.0, 0.62, 0.0), Vector3(0.11, 0.06, 0.32), -90.0, 3)   # ventre
	for lx in [-1.0, 1.0]:
		for lz in [-0.38, 0.32]:
			_leg(m, lx * 0.12, lz, 0.72, 0.08, 0.03, FAUNA_ACCENT)
	m.region = FAUNA_COAT
	m.prism(Vector3(0.0, 0.9, 0.38), Vector3(0.0, 1.12, 0.56), Vector2(0.12, 0.16), Vector2(0.08, 0.09), SIDES, 1.0)   # cou
	m.uv = Vector2(0.0, 1.0)
	m.prism(Vector3(0.0, 1.18, 0.54), Vector3(0.0, 1.06, 0.78), Vector2(0.07, 0.085), Vector2(0.04, 0.05))   # tête
	m.region = FAUNA_ACCENT
	m.prism(Vector3(0.0, 1.03, 0.72), Vector3(0.0, 0.94, 0.7), Vector2(0.025, 0.015), Vector2(0.01, 0.01), 4)   # barbiche
	m.region = FAUNA_DARK
	m.ellipsoid(Vector3(0.0, 1.06, 0.79), Vector3(0.03, 0.025, 0.02), -90.0, 3)   # museau
	for sx in [-1.0, 1.0]:
		m.ellipsoid(Vector3(sx * 0.05, 1.18, 0.64), Vector3(0.012, 0.013, 0.013), -90.0, 3)   # yeux
		m.region = FAUNA_HORN
		# Corne en arc : quatre segments qui montent puis filent vers l'arrière
		var pts := [Vector3(sx * 0.035, 1.22, 0.6), Vector3(sx * 0.06, 1.42, 0.55), Vector3(sx * 0.08, 1.58, 0.4),
			Vector3(sx * 0.1, 1.64, 0.2), Vector3(sx * 0.11, 1.58, 0.02)]
		for i in range(pts.size() - 1):
			var r0 := 0.035 * (1.0 - i * 0.22)
			var r1 := 0.035 * (1.0 - (i + 1) * 0.22)
			m.prism(pts[i], pts[i + 1], Vector2(r0, r0 * 1.3), Vector2(r1, r1 * 1.3), 5)
		m.region = FAUNA_COAT
		m.prism(Vector3(sx * 0.06, 1.18, 0.58), Vector3(sx * 0.15, 1.2, 0.55), Vector2(0.025, 0.012), Vector2(0.006, 0.006), 4)   # oreilles
		m.region = FAUNA_DARK
	m.uv = Vector2.ZERO
	return m.commit()


## Marmotte : corps rond de 0,5 m, pattes courtes, tête ronde, petite queue sombre.
static func _build_marmot() -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
	m.region = FAUNA_COAT
	m.ellipsoid(Vector3(0.0, 0.17, -0.04), Vector3(0.13, 0.13, 0.22))   # corps
	m.ellipsoid(Vector3(0.0, 0.19, 0.12), Vector3(0.11, 0.12, 0.12))
	for sx in [-1.0, 1.0]:
		for lz in [-0.14, 0.12]:
			m.prism(Vector3(sx * 0.08, 0.1, lz), Vector3(sx * 0.08, 0.0, lz), Vector2(0.03, 0.03), Vector2(0.022, 0.022), 4)   # pattes
	m.region = FAUNA_ACCENT
	m.prism(Vector3(0.0, 0.2, -0.24), Vector3(0.0, 0.14, -0.38), Vector2(0.035, 0.035), Vector2(0.025, 0.025), 4)   # queue
	m.region = FAUNA_LIGHT
	m.ellipsoid(Vector3(0.0, 0.13, 0.08), Vector3(0.08, 0.07, 0.12), -90.0, 3)   # ventre
	m.region = FAUNA_COAT
	m.uv = Vector2(0.0, 1.0)
	m.ellipsoid(Vector3(0.0, 0.3, 0.24), Vector3(0.075, 0.07, 0.08))   # tête
	m.region = FAUNA_ACCENT
	m.ellipsoid(Vector3(0.0, 0.28, 0.31), Vector3(0.035, 0.03, 0.03), -90.0, 3)   # museau
	m.region = FAUNA_DARK
	for sx in [-1.0, 1.0]:
		m.ellipsoid(Vector3(sx * 0.04, 0.33, 0.29), Vector3(0.011, 0.012, 0.012), -90.0, 3)   # yeux
		m.region = FAUNA_COAT
		m.ellipsoid(Vector3(sx * 0.05, 0.36, 0.22), Vector3(0.018, 0.018, 0.01), -90.0, 3)   # oreilles
		m.region = FAUNA_DARK
	m.uv = Vector2.ZERO
	return m.commit()


## Échassier : flamant (`flamingo`, cou en S, bec courbé noir et rose) ou héron (`heron`, gris, aigrette sombre,
## bec jaune droit). `leg_h` : hauteur du corps, `neck_h` : hauteur du cou au-dessus du corps.
static func _build_wader(leg_h: float, neck_h: float, flamingo: bool) -> ArrayMesh:
	var m := PeopleMesh.Builder.new()
	m.region = FAUNA_COAT
	m.ellipsoid(Vector3(0.0, leg_h + 0.08, -0.02), Vector3(0.12, 0.11, 0.22))   # corps
	m.region = FAUNA_LIGHT
	m.prism(Vector3(0.0, leg_h + 0.1, -0.18), Vector3(0.0, leg_h + 0.04, -0.34), Vector2(0.08, 0.04), Vector2(0.03, 0.02), 4)   # rémiges
	m.region = FAUNA_COAT if flamingo else FAUNA_ACCENT
	for sx in [-1.0, 1.0]:
		m.prism(Vector3(sx * 0.04, leg_h, 0.0), Vector3(sx * 0.04, 0.0, 0.0), Vector2(0.012, 0.012), Vector2(0.01, 0.01), 4)   # pattes
		m.prism(Vector3(sx * 0.04, 0.004, -0.03), Vector3(sx * 0.04, 0.004, 0.1), Vector2(0.004, 0.012), Vector2(0.004, 0.012), 4)   # doigts
	# Cou en S : vers l'avant, en arrière, puis la tête en avant (UV.y de 0 au corps à 1 à la tête)
	m.region = FAUNA_COAT
	var base := Vector3(0.0, leg_h + 0.12, 0.16)
	var mid := Vector3(0.0, leg_h + neck_h * 0.5, 0.18)
	var top := Vector3(0.0, leg_h + neck_h, 0.2)
	m.prism(base, mid, Vector2(0.04, 0.04), Vector2(0.025, 0.025), 6, 0.5)
	m.uv = Vector2(0.0, 0.5)
	m.prism(mid, top, Vector2(0.025, 0.025), Vector2(0.025, 0.025), 6, 1.0)
	m.uv = Vector2(0.0, 1.0)
	m.ellipsoid(top + Vector3(0.0, 0.02, 0.03), Vector3(0.035, 0.035, 0.05))   # tête
	m.region = FAUNA_ACCENT
	if flamingo:
		m.prism(top + Vector3(0.0, 0.01, 0.07), top + Vector3(0.0, -0.03, 0.15), Vector2(0.018, 0.014), Vector2(0.012, 0.01), 4)   # bec
		m.region = FAUNA_DARK
		m.prism(top + Vector3(0.0, -0.03, 0.15), top + Vector3(0.0, -0.08, 0.17), Vector2(0.012, 0.01), Vector2(0.004, 0.004), 4)   # pointe noire
	else:
		m.prism(top + Vector3(0.0, 0.02, 0.07), top + Vector3(0.0, 0.0, 0.2), Vector2(0.012, 0.01), Vector2(0.002, 0.002), 4)   # bec jaune
		m.region = FAUNA_DARK
		m.prism(top + Vector3(0.0, 0.04, -0.01), top + Vector3(0.0, 0.03, -0.12), Vector2(0.008, 0.004), Vector2(0.002, 0.002), 4)   # aigrette
	m.region = FAUNA_DARK
	for sx in [-1.0, 1.0]:
		m.ellipsoid(top + Vector3(sx * 0.025, 0.03, 0.05), Vector3(0.008, 0.008, 0.008), -90.0, 3)   # yeux
	m.uv = Vector2.ZERO
	return m.commit()

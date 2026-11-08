extends Node3D

## Affichage des cyclistes du décor de road_cyclists_model.gd (lots P28 et AS7) : chacun est le même cycliste
## que l'avatar du joueur et les bots (avatar_view.gd, lot Y18 : corps effilé, casque, vélo de route, roues et
## pédalier qui tournent), habillé dans la garde-robe du décor (road_cyclist_look.gd : maillots unis ou de club
## aux couleurs que ne portent ni les bots ni le fantôme, sans dossard), d'après son maillot et sa tenue.
## Pas de class_name : charger par preload("res://scripts/road_cyclists_renderer.gd").
##
## - Niveau de détail comme les bots (quality_presets.gd bot_lod ; ombre au niveau 0 seulement) selon la distance à la
##   caméra (sans caméra : l'écart le long de la route). Un avatar par niveau déjà vu ; un niveau neuf se
##   construit dans un fil de travail (avatar_view.gd request_parts), le cycliste garde en attendant le niveau
##   prêt le plus proche. Les maillages du niveau 2 des VARIANTS apparences sont demandés dès `setup`.
## - Préchauffage au chargement (`warm_up(camera)`, après la route, comme les portiques ; banc PC du 5/11 :
##   pointes d'images à l'entrée des avatars dans le champ) : tous les niveaux du préréglage des VARIANTS
##   apparences construits, une racine de réserve par apparence, montrée minuscule devant la caméra pendant
##   WARM_FRAMES images pour que pipelines, textures et ombres se préparent au chargement et non en roulant.
## - Au plus MAX_CYCLISTS cyclistes affichés. Un cycliste qui quitte la route laisse son avatar caché, repris
##   par le prochain cycliste de même apparence (SPARE_PER_VARIANT avatars de réserve par apparence) : après le
##   préchauffage, un avatar n'est créé que si plusieurs cyclistes de même apparence roulent ensemble. Toute
##   création en roulant est notée dans la sonde (perf_probe.gd, saccades.csv, étape « cyclistes »).
## - Pédalier : l'angle est cumulé ici d'après la cadence du modèle (braquet de 50 × 17), pour qu'un changement
##   de vitesse ne fasse pas sauter les jambes ; roues calées sur la distance parcourue ; en danseuse au-delà
##   de la pente de l'avatar (8 %). Au niveau 2 (loin), la pose n'est recalculée qu'une image sur LOD2_POSE_EVERY.
## - Un groupe qui double dit « Salut ! » (`voice_salut` de sound_player.gd) sur un lecteur 3D.
## - `setup(model, sound_player)` ; `set_quality(nom)` ; `update(dt_s, paused, cam_s)` une fois par image, après
##   `model.update`.

const RoadCyclistsModel := preload("res://scripts/road_cyclists_model.gd")
const RoadCyclistLook := preload("res://scripts/road_cyclist_look.gd")
const AvatarView := preload("res://scripts/avatar_view.gd")
const AvatarMesh := preload("res://scripts/avatar_mesh.gd")
const AvatarModel := preload("res://scripts/avatar_model.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const AudioMix := preload("res://scripts/audio_mix.gd")
const PerfProbe := preload("res://scripts/perf_probe.gd")

const MAX_CYCLISTS := 16
const SPARE_PER_VARIANT := 3
## Ombre portée au niveau 0 seulement (les bots aussi au niveau 1) : jusqu'à 16 cyclistes du décor, et la médiane
## GPU de medium au-dessus de son budget au banc PC du 5/11.
const SHADOW_MAX_LOD := 0
const WARM_FRAMES := 3
const WARM_SCALE := 0.0005          # un cycliste de 1,8 m tient dans 1 mm : rien de visible à l'écran
const WARM_DIST_M := 2.0
const LOD2_POSE_EVERY := 3
const SALUT_VOLUME_DB := -6.0
const STANDING_GRADE_PCT: float = AvatarModel.DEFAULTS["standing_grade_pct"]
## Avatar (face vers −z local, comme bots_view.gd) tourné d'un demi-tour sous la transformée du modèle (face vers +z).
const FACE_AVATAR := Basis(Vector3.UP, PI)

var model = null
var quality := QualityPresets.DEFAULT_PRESET
var _sound = null
var _audio: AudioStreamPlayer3D
var _by_id := {}                 # id du cycliste → racine (Node3D) de son avatar
var _spare := {}                 # apparence → racines cachées, prêtes à resservir
var _warm_left := 0              # images de préchauffage restantes
var _warm_cam: Node3D = null
var _frame := 0
var _shown := 0
var _xforms: Array = []          # transformée de chaque cycliste affiché (tests)
var _cadences: Array = []        # cadence (tr/min) de chaque cycliste affiché (tests)
var _variants: Array = []        # apparence de chaque cycliste affiché (tests)
var _created := 0                # racines créées depuis le démarrage (tests)


func _init() -> void:
	_audio = AudioStreamPlayer3D.new()
	_audio.name = "CyclistVoice"
	_audio.unit_size = 6.0
	_audio.max_distance = 60.0
	_audio.volume_db = SALUT_VOLUME_DB
	_audio.bus = AudioMix.bus(AudioMix.AMBIENCE)
	add_child(_audio)


## Constructions en cours attendues avant la libération (comme bots_view.gd).
func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE:
		AvatarView.wait_parts()


func setup(cyclists_model, sound_player = null) -> void:
	model = cyclists_model
	_sound = sound_player
	for v in range(RoadCyclistLook.VARIANTS):
		AvatarView.request_parts(2, RoadCyclistLook.settings_for(v), RoadCyclistLook.looks_for(v))


## Préréglage de qualité (low, medium, high) : distances des niveaux de détail, comme les bots.
func set_quality(name_: String) -> void:
	quality = QualityPresets.applied_name(name_)
	for id in _by_id:
		_by_id[id].set_meta("lod", -1)


func visible_count() -> int:
	return _shown


func shown_transform(i: int) -> Transform3D:
	return _xforms[i] if i < _xforms.size() else Transform3D()


func shown_cadence(i: int) -> float:
	return _cadences[i] if i < _cadences.size() else 0.0


## Apparence (road_cyclist_look.gd) du cycliste affiché `i` (tests).
func shown_variant(i: int) -> int:
	return _variants[i] if i < _variants.size() else -1


## Racines d'avatar créées depuis le démarrage (tests : les avatars resservent).
func created_count() -> int:
	return _created


## Avatar affiché du cycliste d'`id` donné (tests, vitrine) ; null s'il ne l'est pas.
func avatar_of(id: String) -> Variant:
	var root: Node3D = _by_id.get(id)
	if root == null:
		return null
	return root.get_node_or_null("Lod%d" % int(root.get_meta("shown_lod", 2)))


## Lecteur 3D de la voix (tests).
func audio() -> AudioStreamPlayer3D:
	return _audio


func _take_root(variant: int) -> Node3D:
	var pool: Array = _spare.get(variant, [])
	if not pool.is_empty():
		var again: Node3D = pool.pop_back()
		again.set_meta("lod", -1)
		again.set_meta("shown_lod", -1)
		return again
	var t0 := Time.get_ticks_usec()
	var root := _new_root(variant)
	PerfProbe.mark_since("cyclistes", "avatar %d" % variant, t0)
	return root


func _new_root(variant: int) -> Node3D:
	var root := Node3D.new()
	root.name = "Cyclist%d" % _created
	root.visible = false
	root.set_meta("variant", variant)
	root.set_meta("settings", RoadCyclistLook.settings_for(variant))
	root.set_meta("looks", RoadCyclistLook.looks_for(variant))
	root.set_meta("lod", -1)
	add_child(root)
	_created += 1
	return root


func _release(root: Node3D) -> void:
	root.visible = false
	var v := int(root.get_meta("variant"))
	if not _spare.has(v):
		_spare[v] = []
	if (_spare[v] as Array).size() >= SPARE_PER_VARIANT:
		remove_child(root)
		root.queue_free()
		return
	_spare[v].append(root)


## Niveaux de détail que le préréglage montre (le niveau 0 seulement si bot_lod peut le donner).
func _levels() -> Array:
	return [1, 2] if float(QualityPresets.BOT_LOD_M[quality][0]) <= 0.0 else [0, 1, 2]


## Avatar du niveau `n` de `root`, construit s'il manque (caché).
func _ensure_level(root: Node3D, n: int) -> AvatarView:
	var name_ := "Lod%d" % n
	if root.has_node(name_):
		return root.get_node(name_)
	var av := AvatarView.new()
	av.name = name_
	av.shadow_max_lod = SHADOW_MAX_LOD
	av.looks = (root.get_meta("looks") as Dictionary).duplicate()
	av.configure(root.get_meta("settings"), n)
	av.set_visible_for_view("follow")
	av.visible = false
	root.add_child(av)
	return av


## Préchauffage (après la route, au chargement) : niveaux du préréglage des VARIANTS apparences construits
## (dans les fils de travail, attendus ici), une racine de réserve par apparence, et sans `camera` rien de
## plus ; avec `camera`, ces racines minuscules devant elle pendant WARM_FRAMES images. Retourne le nombre
## d'avatars prêts.
func warm_up(camera: Node3D = null) -> int:
	var t0 := Time.get_ticks_usec()
	var levels := _levels()
	for v in range(RoadCyclistLook.VARIANTS):
		for n in levels:
			AvatarView.request_parts(n, RoadCyclistLook.settings_for(v), RoadCyclistLook.looks_for(v))
	AvatarView.wait_parts()
	var count := 0
	for v in range(RoadCyclistLook.VARIANTS):
		if (_spare.get(v, []) as Array).is_empty():
			_release(_new_root(v))
		for root in _spare[v]:
			for n in levels:
				_ensure_level(root, n)
				count += 1
	_warm_cam = camera
	_warm_left = WARM_FRAMES if camera != null else 0
	_place_warm()
	PerfProbe.mark_since("cyclistes", "préchauffage", t0)
	return count


## Racines de réserve devant la caméra, tous niveaux visibles (préchauffage), ou rangées et cachées à la fin.
func _place_warm() -> void:
	var on := _warm_left > 0 and is_instance_valid(_warm_cam) and _warm_cam.is_inside_tree()
	var i := 0
	for v in _spare:
		for root in _spare[v]:
			root.visible = on
			root.set_meta("shown_lod", -1)
			for child in root.get_children():
				if child is AvatarView:
					child.visible = on
			if on:
				var at := Vector3((i % 8 - 3.5) * 0.002, floorf(i / 8.0) * 0.002, -WARM_DIST_M)
				root.global_transform = _warm_cam.global_transform * Transform3D(Basis().scaled(Vector3.ONE * WARM_SCALE), at)
			i += 1


## Cyclistes affichés par niveau de détail montré [0, 1, 2] (tests, banc visuel).
func lod_counts() -> Array:
	var out := [0, 0, 0]
	for id in _by_id:
		var root: Node3D = _by_id[id]
		if root.visible:
			out[clampi(int(root.get_meta("shown_lod", 2)), 0, 2)] += 1
	return out


## Avatars de réserve prêts (tests).
func spare_count() -> int:
	var n := 0
	for v in _spare:
		n += (_spare[v] as Array).size()
	return n


## Avatar du niveau `lod`, les autres niveaux cachés ; un niveau pas encore construit l'est dans un fil de
## travail, le niveau prêt le plus proche (ou le niveau 2) affiché en attendant (comme bots_view.gd).
func _avatar(root: Node3D, lod: int) -> AvatarView:
	var st: Dictionary = root.get_meta("settings")
	var lk: Dictionary = root.get_meta("looks")
	var shown := lod
	if not root.has_node("Lod%d" % lod) and lod < 2 and not AvatarView.parts_ready(lod, st, lk):
		AvatarView.request_parts(lod, st, lk)
		shown = 2
		for n in [lod + 1, lod - 1, 2]:
			if n >= 0 and n <= 2 and root.has_node("Lod%d" % n):
				shown = n
				break
	var name_ := "Lod%d" % shown
	if not root.has_node(name_):
		var t0 := Time.get_ticks_usec()
		_ensure_level(root, shown)
		PerfProbe.mark_since("cyclistes", "niveau %d" % shown, t0)
	if int(root.get_meta("shown_lod", -1)) != shown:
		for child in root.get_children():
			if child is AvatarView:
				child.visible = child.name == name_
		root.set_meta("shown_lod", shown)
	return root.get_node(name_)


func _distance(pos: Vector3, s: float, cam_s: float) -> float:
	var cam := get_viewport().get_camera_3d() if is_inside_tree() else null
	if cam != null:
		return cam.global_position.distance_to(pos)
	return absf(s - cam_s) if is_finite(cam_s) else 0.0


func update(dt_s: float, paused: bool = false, cam_s: float = NAN) -> void:
	_xforms.clear()
	_cadences.clear()
	_variants.clear()
	_shown = 0
	_frame += 1
	if _warm_left > 0:
		_warm_left -= 1
		_place_warm()
	var seen := {}
	if model != null:
		for r in model.riders():
			if _shown >= MAX_CYCLISTS:
				break
			var g: Dictionary = r["group"]
			var m: Dictionary = r["member"]
			var id := str(r.get("id", "%s-%d" % [str(g.get("id", "")), _shown]))
			var rpm := RoadCyclistsModel.cadence_rpm(float(g["speed_mps"]))
			if not paused:
				m["crank"] = fposmod(float(m.get("crank", float(m["phase"]) * TAU)) + rpm / 60.0 * TAU * dt_s, TAU)
			var angle := float(m.get("crank", float(m["phase"]) * TAU))
			var s := float(r["s"])
			var xf: Transform3D = model.world_transform(s, float(r["lateral"]), int(r["dir"]), float(r.get("yaw", 0.0)))
			var variant := RoadCyclistLook.variant_of(int(m["jersey"]), int(m["look"]))
			var root: Node3D = _by_id.get(id)
			if root != null and int(root.get_meta("variant")) != variant:
				_release(root)
				root = null
			if root == null:
				root = _take_root(variant)
				_by_id[id] = root
			seen[id] = true
			root.transform = Transform3D(xf.basis * FACE_AVATAR, xf.origin)
			root.visible = true
			var lod := QualityPresets.bot_lod(quality, _distance(xf.origin, s, cam_s), int(root.get_meta("lod")))
			root.set_meta("lod", lod)
			var av := _avatar(root, lod)
			if int(root.get_meta("shown_lod")) < 2 or (_frame + _shown) % LOD2_POSE_EVERY == 0 or not root.has_meta("posed"):
				var smp: Dictionary = model.route.sample(clampf(s, 0.0, model.route.length_m))
				var standing := float(smp.get("grade_pct", 0.0)) * float(r["dir"]) >= STANDING_GRADE_PCT
				av.apply_pose(angle, standing)
				av.set_wheel_angle(fposmod(s * float(r["dir"]) / AvatarMesh.WHEEL_R, TAU))
				root.set_meta("posed", true)
			_xforms.append(xf)
			_cadences.append(rpm)
			_variants.append(variant)
			_shown += 1
	for id in _by_id.keys():
		if not seen.has(id):
			_release(_by_id[id])
			_by_id.erase(id)
	if model == null:
		return
	var ev: Dictionary = model.last_event
	if not ev.is_empty() and _sound != null:
		var st: Resource = _sound.stream(str(ev["kind"]))
		if st != null:
			_audio.stream = st
			_audio.position = ev["pos"]
			if is_inside_tree():
				_audio.play()

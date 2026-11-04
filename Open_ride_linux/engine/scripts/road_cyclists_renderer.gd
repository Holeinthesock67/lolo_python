extends Node3D

## Affichage des cyclistes du décor de road_cyclists_model.gd (lots P28 et AS7) : chacun est le même cycliste
## que l'avatar du joueur et les bots (avatar_view.gd, lot Y18 : corps effilé, casque, vélo de route, roues et
## pédalier qui tournent), habillé dans la garde-robe du décor (road_cyclist_look.gd : maillots unis ou de club
## aux couleurs que ne portent ni les bots ni le fantôme, sans dossard), d'après son maillot et sa tenue.
## Pas de class_name : charger par preload("res://scripts/road_cyclists_renderer.gd").
##
## - Niveau de détail comme les bots (quality_presets.gd bot_lod, BOT_SHADOW_MAX_LOD) selon la distance à la
##   caméra (sans caméra : l'écart le long de la route). Un avatar par niveau déjà vu ; un niveau neuf se
##   construit dans un fil de travail (avatar_view.gd request_parts), le cycliste garde en attendant le niveau
##   prêt le plus proche. Les maillages du niveau 2 des VARIANTS apparences sont demandés dès `setup`.
## - Au plus MAX_CYCLISTS cyclistes affichés. Un cycliste qui quitte la route laisse son avatar caché, repris
##   par le prochain cycliste de même apparence (au plus SPARE_MAX avatars de réserve, le plus ancien part le
##   premier) : peu de nœuds créés.
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

const MAX_CYCLISTS := 16
const SPARE_MAX := 8
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
var _spare_order: Array = []     # les mêmes, de la plus ancienne à la plus récente
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
		_spare_order.erase(again)
		again.set_meta("lod", -1)
		return again
	var root := Node3D.new()
	root.name = "Cyclist%d" % _created
	root.set_meta("variant", variant)
	root.set_meta("settings", RoadCyclistLook.settings_for(variant))
	root.set_meta("looks", RoadCyclistLook.looks_for(variant))
	root.set_meta("lod", -1)
	add_child(root)
	_created += 1
	return root


func _release(root: Node3D) -> void:
	root.visible = false
	if _spare_order.size() >= SPARE_MAX:   # réserve pleine : le plus ancien avatar caché s'en va
		var old: Node3D = _spare_order.pop_front()
		(_spare[int(old.get_meta("variant"))] as Array).erase(old)
		remove_child(old)
		old.queue_free()
	var v := int(root.get_meta("variant"))
	if not _spare.has(v):
		_spare[v] = []
	_spare[v].append(root)
	_spare_order.append(root)


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
		var av := AvatarView.new()
		av.name = name_
		av.shadow_max_lod = QualityPresets.BOT_SHADOW_MAX_LOD
		av.looks = lk.duplicate()
		av.configure(st, shown)
		av.set_visible_for_view("follow")
		root.add_child(av)
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
			var xf: Transform3D = model.world_transform(s, float(r["lateral"]), int(r["dir"]))
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

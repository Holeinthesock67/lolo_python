extends Node3D

## Bots sur la route (lots O7 et Y18) : chaque bot est le même cycliste que l'avatar du joueur
## (avatar_view.gd : corps effilé, maillot à motif, casque à aérations, vélo de route, roues et pédalier qui
## tournent), habillé d'après le bot (bot_look.gd : maillot à la couleur du bot, maillot vert ou à pois de la
## séance, corps et équipement variés) ; le fantôme est le même cycliste translucide, sans ombre. Posé à `s`
## avec le cap et la pente de route_data.gd (relief exagéré comme la caméra), décalé de sa place en travers
## `lateral` (bots_view_model.gd : à droite du cycliste vers le bord, côte à côte en peloton ; lot P32) ; nom
## au-dessus à moins de NAME_M.
##
## - Niveau de détail selon la distance à la caméra et le préréglage (quality_presets.gd bot_lod) : niveau 0
##   (celui du joueur) de près en medium et high, 1 à moyenne distance, 2 (allégé) au-delà. Un avatar par
##   niveau déjà vu, gardé caché quand il ne sert pas : changer de niveau ne reconstruit rien. Les maillages
##   d'un niveau neuf se construisent dans un fil de travail (aucune image perdue) ; `wait_builds()` les
##   attend (tests, vitrine).
## - Pédalier : la phase suit la distance parcourue `s` (un tour par DEVELOPMENT_M), les roues aussi (un tour
##   par 2π × rayon) : jambes et roues tournent avec la vitesse du bot et s'arrêtent avec lui. En danseuse
##   au-delà de la pente `standing_grade_pct` de l'avatar (8 %), comme le joueur par défaut.
## - Une silhouette par bot visible (moins de 300 m) ; sans bot, aucun nœud. Ne décide rien : affiche la
##   sortie de bots_view_model.view().
## Pas de class_name : charger par preload("res://scripts/bots_view.gd").

const BotsViewModel := preload("res://scripts/bots_view_model.gd")
const BotLook := preload("res://scripts/bot_look.gd")
const AvatarView := preload("res://scripts/avatar_view.gd")
const AvatarMesh := preload("res://scripts/avatar_mesh.gd")
const AvatarModel := preload("res://scripts/avatar_model.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const RoadCyclistsModel := preload("res://scripts/road_cyclists_model.gd")

const NAME_HEIGHT_M := 2.1
const GHOST_ALPHA := 0.55
const SLOPE_PROBE_M := 1.5          # pente du vélo : points de la route à ± cette distance
const STANDING_GRADE_PCT: float = AvatarModel.DEFAULTS["standing_grade_pct"]

var quality := QualityPresets.DEFAULT_PRESET
var _nodes := {}        # id:kind → Node3D (racine du bot)
var _poses := {}        # id:kind → {phase, color, lod, standing} (tests)


func _init() -> void:
	name = "BotsView"


## Préréglage de qualité (low, medium, high) : niveaux de détail des bots (quality_presets.gd BOT_LOD_M).
func set_quality(name_: String) -> void:
	quality = QualityPresets.applied_name(name_)
	for key in _nodes:
		_nodes[key].set_meta("lod", -1)


func _make_node(b: Dictionary, index: int) -> Node3D:
	var root := Node3D.new()
	var kind := str(b["kind"])
	root.set_meta("settings", BotLook.settings_for(index, BotLook.role_of(b), b.get("jersey")))
	root.set_meta("looks", BotLook.looks_for(index, b.get("jersey")))
	root.set_meta("jersey", _jersey(b))
	root.set_meta("ghost", kind == "ghost")
	root.set_meta("lod", -1)
	var label := Label3D.new()
	label.name = "Name"
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.position = Vector3(0.0, NAME_HEIGHT_M, 0.0)
	label.font_size = 48
	label.pixel_size = 0.006
	label.outline_size = 10
	label.modulate = BotsViewModel.color_of(kind).lightened(0.3)
	root.add_child(label)
	add_child(root)
	return root


## Avatar du niveau `lod` du bot, les autres niveaux cachés. Un niveau pas encore construit l'est dans un fil
## de travail (AvatarView.request_parts : jusqu'à 20 ms pour le niveau 0, une image perdue sinon) ; en
## attendant, le bot garde le niveau déjà construit le plus proche, ou prend le niveau 2 (moins de 2 ms).
func _avatar(root: Node3D, lod: int) -> AvatarView:
	var st: Dictionary = root.get_meta("settings")
	var lk: Dictionary = root.get_meta("looks")
	var shown := lod
	if not root.has_node("Lod%d" % lod) and lod < 2 and not AvatarView.parts_ready(lod, st, lk):
		AvatarView.request_parts(lod, st, lk)
		shown = 2
		for n in [lod + 1, lod - 1, 2]:   # le plus proche déjà là
			if n >= 0 and n <= 2 and root.has_node("Lod%d" % n):
				shown = n
				break
	var name_ := "Lod%d" % shown
	if not root.has_node(name_):
		var av := AvatarView.new()
		av.name = name_
		av.shadow_max_lod = QualityPresets.BOT_SHADOW_MAX_LOD
		if root.get_meta("ghost"):
			av.ghost_alpha = GHOST_ALPHA
		av.looks = lk.duplicate()
		av.configure(st, shown)
		av.set_visible_for_view("follow")
		root.add_child(av)
	for child in root.get_children():
		if child is AvatarView:
			child.visible = child.name == name_
	root.set_meta("shown_lod", shown)
	return root.get_node(name_)


## Maillot vert ou à pois gagné (ou perdu) pendant la séance : l'apparence suit, les avatars sont refaits.
func _refresh_jersey(root: Node3D, b: Dictionary, index: int) -> void:
	if _jersey(b) == str(root.get_meta("jersey")):
		return
	var kind := str(b["kind"])
	root.set_meta("jersey", _jersey(b))
	root.set_meta("settings", BotLook.settings_for(index, BotLook.role_of(b), b.get("jersey")))
	root.set_meta("looks", BotLook.looks_for(index, b.get("jersey")))
	for child in root.get_children():
		if child is AvatarView:
			root.remove_child(child)
			child.queue_free()
	root.set_meta("lod", -1)


## Maillot de la séance porté par le bot (`sprint`, `kom`), "" sans maillot.
static func _jersey(b: Dictionary) -> String:
	var j = b.get("jersey")
	return str(j) if j != null else ""


## Distance du bot à la caméra ; sans caméra (tests, hors arbre), l'écart le long de la route.
func _distance(b: Dictionary, pos: Vector3) -> float:
	var cam := get_viewport().get_camera_3d() if is_inside_tree() else null
	if cam != null:
		return cam.global_position.distance_to(pos)
	return absf(float(b.get("gap_m", 0.0)))


## `view` : sortie de bots_view_model.view() ; `route` : route_data.gd (hauteur affichée, relief exagéré comme la
## caméra).
func update_view(view: Array, route) -> void:
	var seen := {}
	for b in view:
		var id: String = b["id"]
		if not b["visible"] or route == null:
			continue
		seen[id] = true
		var key := id + ":" + str(b["kind"])
		if not _nodes.has(key):
			_nodes[key] = _make_node(b, _nodes.size())
			_nodes[key].set_meta("index", _nodes.size() - 1)
		var node: Node3D = _nodes[key]
		_refresh_jersey(node, b, int(node.get_meta("index")))
		var s := float(b["s"])
		var smp: Dictionary = route.sample(route.wrap_s(s))
		var pos := Vector3(smp["x"], smp["y"], smp["z"])
		var h := deg_to_rad(float(smp["heading_deg"]))
		var right := Vector3(cos(h), 0.0, sin(h))
		var a: Dictionary = route.sample(route.wrap_s(s - SLOPE_PROBE_M))
		var c: Dictionary = route.sample(route.wrap_s(s + SLOPE_PROBE_M))
		var run := Vector2(float(c["x"]) - float(a["x"]), float(c["z"]) - float(a["z"])).length()
		var pitch := atan2(float(c["y"]) - float(a["y"]), run) if run > 0.01 else 0.0
		node.position = pos + right * float(b["lateral"])
		node.rotation = Vector3(pitch, -h, 0.0)
		var lod := QualityPresets.bot_lod(quality, _distance(b, node.position), int(node.get_meta("lod")))
		node.set_meta("lod", lod)
		var av := _avatar(node, lod)
		var phase := fposmod(s / RoadCyclistsModel.DEVELOPMENT_M, 1.0)
		var standing := float(smp.get("grade_pct", 0.0)) >= STANDING_GRADE_PCT
		av.apply_pose(phase * TAU, standing)
		av.set_wheel_angle(fposmod(s / AvatarMesh.WHEEL_R, TAU))
		_poses[key] = {"phase": phase, "color": b.get("color", BotsViewModel.color_of(str(b["kind"]))), "lod": lod,
			"shown_lod": int(node.get_meta("shown_lod")), "standing": standing, "settings": node.get_meta("settings"), "looks": node.get_meta("looks")}
		var label: Label3D = node.get_node("Name")
		label.text = str(b["name"])
		label.visible = bool(b["show_name"])
		node.visible = true
	for key in _nodes.keys():
		if not seen.has(str(key).get_slice(":", 0)):
			remove_child(_nodes[key])
			_nodes[key].queue_free()
			_nodes.erase(key)
			_poses.erase(key)


## Attend les maillages en construction ; la prochaine update_view montre alors le niveau voulu.
func wait_builds() -> void:
	AvatarView.wait_parts()


## Pédalier (phase de 0 à 1), couleur, niveau de détail, danseuse et apparence du bot `id` affiché ; {} s'il
## ne l'est pas.
func pose_of(id: String) -> Dictionary:
	for key in _poses:
		if str(key).get_slice(":", 0) == id:
			return _poses[key]
	return {}


## Avatar affiché du bot `id` (tests, vitrine) ; null s'il ne l'est pas.
func avatar_of(id: String) -> Variant:
	for key in _nodes:
		if str(key).get_slice(":", 0) == id:
			var node: Node3D = _nodes[key]
			return node.get_node("Lod%d" % int(node.get_meta("shown_lod")))
	return null


## Position dans le monde de la silhouette du bot `id` (jauge d'abri, draft_gauge.gd) ; null s'il n'est pas affiché.
func anchor_of(id: String) -> Variant:
	for key in _nodes:
		if str(key).get_slice(":", 0) == id and _nodes[key].visible:
			return _nodes[key].global_position
	return null


## Pour les tests graphiques : silhouettes affichées, celles dans le champ de la caméra, et nombre par niveau
## de détail affiché.
func test_info(camera: Camera3D) -> Dictionary:
	var shown := 0
	var in_view := 0
	var lods := [0, 0, 0]
	for key in _nodes:
		var n: Node3D = _nodes[key]
		if n.visible:
			shown += 1
			lods[int(n.get_meta("shown_lod"))] += 1
			if camera != null and _on_screen(camera, n.global_position + Vector3(0.0, 1.0, 0.0)):
				in_view += 1
	return {"shown": shown, "in_view": in_view, "lods": lods}


## Devant la caméra et dans l'image (comme les panneaux de col de living_decor.gd).
static func _on_screen(camera: Camera3D, point: Vector3) -> bool:
	if camera.is_position_behind(point):
		return false
	return camera.get_viewport().get_visible_rect().has_point(camera.unproject_position(point))

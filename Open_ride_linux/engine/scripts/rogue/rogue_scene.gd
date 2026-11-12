extends Node3D

## Scène du mode Cyber-Rogue (lot R10) : ruban suspendu construit depuis le message `room`, repères de la salle,
## Firewall, vélo du joueur, grille au sol et caméra de suivi. La scène ne contient aucune règle de jeu : elle
## affiche `state.rogue` (s_room, pente, fenêtres, Firewall). Instanciée par `rogue_host.gd` quand
## `state.mode` vaut « ROGUE » ; les salles viennent du `room_store.gd` du hôte.

const Palette := preload("res://scripts/rogue/neon_palette.gd")
const Materials := preload("res://scripts/rogue/neon_materials.gd")
const RibbonBuilder := preload("res://scripts/rogue/ribbon_builder.gd")
const RibbonColors := preload("res://scripts/rogue/ribbon_colors.gd")
const MarkerViews := preload("res://scripts/rogue/marker_views.gd")
const FirewallView := preload("res://scripts/rogue/firewall_view.gd")
const HudModel := preload("res://scripts/rogue/rogue_hud_model.gd")
const HudView := preload("res://scripts/rogue/rogue_hud_view.gd")
const EnemyModel := preload("res://scripts/rogue/enemy_model.gd")
const EnemyViews := preload("res://scripts/rogue/enemy_views.gd")
const CorridorView := preload("res://scripts/rogue/rogue_corridor_view.gd")
const RogueAudio := preload("res://scripts/rogue/rogue_audio.gd")
const CameraFx := preload("res://scripts/rogue/rogue_camera_fx.gd")
const SheetScript := preload("res://scripts/rogue/rogue_style_sheet.gd")
const RIBBON_SHADER := preload("res://scripts/rogue/ribbon.gdshader")
const MarkerGuides := preload("res://scripts/rogue/marker_guides.gd")
const SideDecor := preload("res://scripts/rogue/rogue_side_decor.gd")

## Phases où le ruban est affiché (hors échauffement, retour au calme et bilan : vide et grille).
const RIBBON_PHASES := ["ROOM", "CORRIDOR", "BOSS", "RECOVERY"]
## Vues de la caméra (lot R22, choix du propriétaire du 12 novembre : 3 vues sur les flèches haut et bas) :
## [recul, hauteur, visée devant] en mètres. 0 : derrière (vue d'origine), 1 : haute, 2 : proche.
const VIEWS := [[6.0, 2.4, 14.0], [12.0, 6.5, 26.0], [3.2, 1.5, 10.0]]
const VIEW_NAMES := ["derrière", "haute", "proche"]
const CAMERA_BACK_M := 6.0
const CAMERA_UP_M := 2.4
const CAMERA_LOOK_AHEAD_M := 14.0
const WARM_GLYPHS := "0123456789 %·.:'/-\nW FW Ennemi rpm\nABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz"   # glyphes du HUD préchauffés (lot Y20)
const SMOOTH_PER_S := 12.0       # lissage de la position affichée entre deux états

signal resync_wanted

## Mis à vrai par on_state quand une salle inconnue demande une resynchronisation (lu et remis à faux par l'hôte).
var resync_requested := false

var store                         # room_store.gd (fourni par l'hôte)
var preset := "low"
var adapted := false
var exaggeration := RibbonBuilder.DEFAULT_EXAGGERATION
var camera: Camera3D
var ribbon: MeshInstance3D
var firewall: Node3D
var bike: MeshInstance3D
var grid: MeshInstance3D
var markers_root: Node3D
var shown_room_id := -1
var ribbon_visible := false
var markers: Array = []           # {node, kind, s, len, guides}
var view_index := 0               # vue de la caméra (VIEWS)
var side_decor: Node3D            # rogue_side_decor.gd (lot R22)
var _v_mps := 0.0                 # vitesse du joueur (state.v) : longueur des zones Z et anneau des arches
var _decor_mode := ""             # "room:<id>" ou "strip"
var _stations: Array = []
var _s_target := 0.0
var _s_disp := 0.0
var _gap_m := 150.0
var _ribbon_mat: ShaderMaterial
var hud_model = HudModel.new()
var hud_view: Node3D              # rogue_hud_view.gd
var camera_fx = CameraFx.new()
var enemy_model = EnemyModel.new()
var corridor_view: CanvasLayer    # rogue_corridor_view.gd
var audio: Node                   # rogue_audio.gd
var enemy_view: Node3D            # enemy_views.gd
var _grade_pct := 0.0
var _enemy_seq := -1
var _enemy_rogue = null
var effects_ok := true            # faux si le préréglage `low` ne tient pas son budget d'images
var _hud_events: Array = []
var _warm_markers: Array = []     # repères et ennemis du préchauffage (lot Y20), retirés au premier état du mode


func _ready() -> void:
	camera = Camera3D.new()
	camera.name = "RogueCamera"
	camera.far = 1500.0
	add_child(camera)
	ribbon = MeshInstance3D.new()
	ribbon.name = "Ribbon"
	add_child(ribbon)
	markers_root = Node3D.new()
	markers_root.name = "Markers"
	add_child(markers_root)
	firewall = FirewallView.new()
	firewall.name = "Firewall"
	add_child(firewall)
	bike = MeshInstance3D.new()
	bike.name = "Bike"
	var wheel := CylinderMesh.new()
	wheel.top_radius = 0.35
	wheel.bottom_radius = 0.35
	wheel.height = 0.12
	bike.mesh = wheel
	bike.rotation.z = PI * 0.5
	add_child(bike)
	grid = MeshInstance3D.new()
	grid.name = "Grid"
	var plane := PlaneMesh.new()
	plane.size = Vector2(3000.0, 3000.0)
	grid.mesh = plane
	add_child(grid)
	_ribbon_mat = ShaderMaterial.new()
	_ribbon_mat.shader = RIBBON_SHADER
	ribbon.material_override = _ribbon_mat
	side_decor = SideDecor.new()
	side_decor.name = "SideDecor"
	side_decor.preset = preset
	side_decor.adapted = adapted
	add_child(side_decor)
	enemy_view = EnemyViews.new()
	enemy_view.name = "Enemy"
	enemy_view.preset = preset
	enemy_view.adapted = adapted
	add_child(enemy_view)
	audio = RogueAudio.new()
	audio.name = "Audio"
	add_child(audio)
	corridor_view = CorridorView.new()
	corridor_view.name = "Corridor"
	add_child(corridor_view)
	hud_view = HudView.new()
	hud_view.name = "Hud"
	hud_view.preset = preset
	hud_view.adapted = adapted
	add_child(hud_view)
	set_style(preset, adapted)
	_place_camera()
	camera.make_current()


func set_style(new_preset: String, new_adapted: bool) -> void:
	preset = new_preset
	adapted = new_adapted
	if grid == null:
		return
	grid.material_override = Materials.grid(preset, adapted)
	bike.material_override = Materials.edge("player", 2.0, preset, adapted)
	firewall.set_style(preset, adapted)
	if side_decor != null:
		side_decor.set_style(preset, adapted)
		_decor_mode = ""
	if hud_view != null:
		hud_view.set_style(preset, adapted)
	if enemy_view != null:
		enemy_view.set_style(preset, adapted)
	_ribbon_mat.set_shader_parameter("body_color", Palette.body_color())
	_ribbon_mat.set_shader_parameter("intensity", Palette.INTENSITY.get(preset, 1.6))
	_ribbon_mat.set_shader_parameter("ahead_m", RibbonColors.AHEAD_M)
	_ribbon_mat.set_shader_parameter("far_dim", RibbonColors.FAR_DIM)
	if shown_room_id >= 0 and store != null and store.has_room(shown_room_id):
		_build_room(shown_room_id)


## Altitude du ruban à la distance `s` de la salle affichée (0 sans salle).
func ribbon_y(s: float) -> float:
	return RibbonBuilder.y_at(_stations, s) if ribbon_visible else 0.0


func _build_room(room_id: int) -> void:
	var r: Dictionary = store.room(room_id)
	shown_room_id = room_id
	var length_m := float(r["length_m"])
	_stations = RibbonBuilder.stations(r["profile"], length_m, exaggeration)
	ribbon.mesh = RibbonBuilder.mesh(r["profile"], length_m, exaggeration, adapted)
	for m in markers:
		m["node"].queue_free()
	markers.clear()
	for mk in r["markers"]:
		var kind := str(mk["kind"])
		var node: Node3D = MarkerViews.make(kind, float(mk["len_m"]), preset, adapted)
		var s_mid := float(mk["s_m"]) + float(mk["len_m"]) * 0.5
		node.position = Vector3(0.0, RibbonBuilder.y_at(_stations, s_mid), -s_mid)
		markers_root.add_child(node)
		# Lot R22 : étiquette, zone où Z est accepté, portique et anneau d'approche des arches.
		var guides: Dictionary = MarkerGuides.decorate(node, kind, mk.get("param", null), float(mk["len_m"]), preset, adapted)
		markers.append({"node": node, "kind": kind, "s": float(mk["s_m"]), "len": float(mk["len_m"]), "guides": guides})
	hud_model.guide.set_room(room_id, r["markers"])


## Préchauffage (lot Y20), pendant l'écran d'attente du départ : un bout de ruban plat et un repère de chaque
## sorte devant la caméra, pour compiler leurs matériaux avant RUNNING. Renvoie le nombre de repères posés.
func warm_up() -> int:
	ribbon.mesh = RibbonBuilder.mesh([[0.0, 0.0]], 40.0, exaggeration, adapted)
	ribbon.visible = true
	var i := 0
	for kind in MarkerViews.CATALOG_OF:
		var node: Node3D = MarkerViews.make(kind, 20.0, preset, adapted)
		node.position = Vector3(0.0, 0.0, -10.0 - 4.0 * i)
		markers_root.add_child(node)
		# Guides du lot R22 (étiquette, zone Z, portique et anneau des arches) : leurs matériaux et la police de
		# l'étiquette se compilaient à la première salle (images de 137 ms aux transitions de salle, galerie PC).
		MarkerGuides.decorate(node, kind, null, 20.0, preset, adapted)
		_warm_markers.append(node)
		i += 1
	markers_root.visible = true
	# Ennemis (un par archétype, flash et éclat compris), hologramme, jauges et bandeau du HUD : leurs matériaux
	# et les glyphes des Label3D étaient encore compilés à la première image de RUNNING (1 image de 150-190 ms).
	for arch in EnemyViews.OBJECT_OF:
		var ev: Node3D = EnemyViews.new()
		ev.preset = preset
		ev.adapted = adapted
		ev.position = Vector3(3.0 * (i % 3 - 1), 1.4, -12.0 - 4.0 * i)
		add_child(ev)
		ev.set_archetype(arch)
		ev.flash.visible = true
		ev.impact(true, 0.1)
		_warm_markers.append(ev)
		i += 1
	hud_view.visible = true
	hud_view.position = bike.position
	hud_view.holo.text = WARM_GLYPHS
	hud_view.gauges.text = WARM_GLYPHS
	hud_view.banner.visible = true
	return _warm_markers.size()


func warm_count() -> int:
	return _warm_markers.size()


## Trame `state.rogue` : salle à afficher, position, fenêtres actives et Firewall. `now_s` : horloge de
## l'appelant (pour limiter les demandes de resynchronisation). `run_s` : distance depuis le début de la run
## (`state.s`) ; hors salle (échauffement, retour au calme), le vélo avance sur la grille de cette distance
## (recette R14 du 8 novembre : sans elle, l'échauffement de 6 min restait figé et passait pour un blocage).
func on_state(rogue: Dictionary, now_s: float, run_s: float = 0.0) -> void:
	if not _warm_markers.is_empty():
		hud_view.banner.visible = false
	for n in _warm_markers:
		n.queue_free()
	_warm_markers.clear()
	var phase := str(rogue.get("phase", ""))
	var rid := int(rogue.get("room_id", -1))
	ribbon_visible = phase in RIBBON_PHASES
	if ribbon_visible and rid != shown_room_id:
		if store != null and store.has_room(rid):
			_build_room(rid)
			_s_disp = float(rogue.get("s_room", 0.0))      # nouvelle salle : pas de glissement
		elif store != null and store.should_resync(rid, now_s):
			resync_requested = true
			resync_wanted.emit()
	ribbon.visible = ribbon_visible and shown_room_id == rid and store != null and store.has_room(rid)
	markers_root.visible = ribbon.visible
	firewall.visible = ribbon.visible
	_s_target = float(rogue.get("s_room", 0.0)) if ribbon.visible else maxf(run_s, 0.0)
	_place_decor(rid)
	_gap_m = float(rogue.get("firewall_gap_m", 150.0))
	if ribbon.visible:
		var windows: Array = rogue.get("windows", [])
		for m in markers:
			var active := false
			for w in windows:
				if str(w.get("kind", "")) == m["kind"] and float(w.get("s_start", 0.0)) < m["s"] + m["len"] \
						and float(w.get("s_end", 0.0)) > m["s"]:
					active = true
			MarkerViews.set_active(m["node"], active)
	_update_pose()


## Trame `state` entière (vitesse, watts, cadence) pour le HUD diégétique et les effets de caméra (lot R11).
func on_hud(state: Dictionary, now_s: float) -> void:
	hud_model.update(state, now_s)
	var events: Array = hud_model.take_events()
	_hud_events.append_array(events)
	hud_view.show_events(events)
	hud_view.push_feedback(hud_model.guide.take_toasts(), hud_model.guide.take_legend())
	var summary = state.get("summary", null)
	var result := "victory"
	if typeof(summary) == TYPE_DICTIONARY and typeof(summary.get("rogue", null)) == TYPE_DICTIONARY:
		result = str(summary["rogue"].get("result", result))
	audio.on_state(state.get("rogue", null), int(state.get("gear", 1)), int(state.get("seq", -1)), now_s, result)
	_enemy_rogue = state.get("rogue", null)
	_enemy_seq = int(state.get("seq", -1))
	_grade_pct = float(state.get("grade", 0.0))
	_v_mps = maxf(float(state.get("v", 0.0)), 0.0)


## Décor latéral (lot R22) : le long du ruban en salle, sinon la bande plate qui suit le joueur.
func _place_decor(rid: int) -> void:
	if side_decor == null:
		return
	var want := ("room:%d" % rid) if ribbon.visible else "strip"
	if want != _decor_mode:
		_decor_mode = want
		if ribbon.visible:
			side_decor.build_room(_stations, float(store.room(rid)["length_m"]), rid)
		else:
			side_decor.build_strip()
	if not ribbon.visible:
		side_decor.follow_strip(_s_target)


## Vue suivante (`step` = 1, flèche haut) ou précédente (−1, flèche bas), en boucle. Renvoie le nom de la vue.
func cycle_view(step: int) -> String:
	view_index = posmod(view_index + step, VIEWS.size())
	_place_camera()
	return VIEW_NAMES[view_index]


func _process(delta: float) -> void:
	_s_disp = lerpf(_s_disp, _s_target, clampf(delta * SMOOTH_PER_S, 0.0, 1.0))
	if absf(_s_disp - _s_target) > 50.0:
		_s_disp = _s_target       # saut de salle : pas de glissement
	_update_pose()
	_tick_guides()
	_tick_hud(delta)
	_tick_enemy(delta)


func _update_pose() -> void:
	var y := ribbon_y(_s_disp)
	bike.position = Vector3(0.0, y + 0.45, -_s_disp)
	grid.position = Vector3(0.0, y - 12.0, -_s_disp)
	if ribbon.visible:
		firewall.place(_s_disp - _gap_m, ribbon_y(_s_disp - _gap_m), _gap_m)
	_ribbon_mat.set_shader_parameter("player_s", _s_disp)
	_place_camera()


## Point du ruban (ou de la grille) sous le joueur, où l'engine pose l'avatar du cycliste.
func rider_point() -> Vector3:
	return Vector3(0.0, ribbon_y(_s_disp), -_s_disp)


## Pente du ruban sous le joueur, en degrés (positive en montée), pour incliner l'avatar.
func rider_pitch_deg() -> float:
	if not ribbon_visible:
		return 0.0
	return rad_to_deg(atan((ribbon_y(_s_disp + 1.0) - ribbon_y(_s_disp - 1.0)) * 0.5))


func _tick_guides() -> void:
	if not ribbon.visible:
		return
	for m in markers:
		MarkerGuides.update(m.get("guides", {}), m["kind"], m["s"], m["len"], _s_disp, _v_mps)


func _tick_enemy(delta: float) -> void:
	# Le modèle tourne à chaque image sur la dernière trame ; une trame déjà vue (même seq) ne rejoue pas ses événements.
	enemy_model.update(_enemy_rogue, _enemy_seq, _grade_pct, delta, effects_ok)
	for imp in enemy_model.take_impacts():
		enemy_view.impact(bool(imp["crit"]), float(imp["flash_s"]))
	var pose: Dictionary = enemy_model.pose()
	if ribbon.visible and bool(pose.get("visible", false)):
		var s_e := _s_disp + float(pose["distance_m"])
		enemy_view.position = Vector3(0.0, ribbon_y(s_e) + 1.4, -s_e)
	enemy_view.apply(pose, delta)


func _tick_hud(delta: float) -> void:
	var v: Dictionary = hud_model.values()
	camera_fx.update(delta, float(v.get("power_pct", 0.0)), _hud_events)
	_hud_events = []
	hud_view.apply(v, bike.position, delta)
	corridor_view.apply(v.get("corridor", {}))


func _place_camera() -> void:
	if camera == null:
		return
	var y := ribbon_y(_s_disp)
	var view: Array = VIEWS[view_index]
	var eye := Vector3(0.0, y + float(view[1]), -(_s_disp - float(view[0])))
	var ahead := float(view[2])
	var target := Vector3(0.0, ribbon_y(_s_disp + ahead) + 0.5, -(_s_disp + ahead))
	camera.fov = camera_fx.fov_deg()
	camera.look_at_from_position(eye + camera_fx.shake_offset(), target)


## Ce que la scène affiche, pour les tests (banc visuel du mode, lot X41) : salle construite, ruban, repères,
## Firewall, ennemi, écran de couloir, hologramme du HUD et bandeau « Salle manquée ».
func test_info() -> Dictionary:
	return {"room_shown": shown_room_id, "ribbon": ribbon.visible, "markers": markers.size() if ribbon.visible else 0,
		"firewall": firewall.visible, "enemy": enemy_view.visible and ribbon.visible,
		"enemy_archetype": str(enemy_view.archetype) if enemy_view.visible else "",
		"corridor": corridor_view.visible, "hud": hud_view.visible,
		"holo": hud_view.holo.text if hud_view.visible and hud_view.holo.visible else "",
		"gauges": hud_view.gauges.text if hud_view.visible and hud_view.gauges.visible else "",
		"banner": hud_view.banner.visible,
		# lot R22
		"view": VIEW_NAMES[view_index], "decor": side_decor.instance_total() if side_decor != null else 0,
		"hint": hud_view.hint_label.text if hud_view.hint_panel.visible else "",
		"side": hud_view.side_big.text if hud_view.side_panel.visible else ""}

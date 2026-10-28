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
const CameraFx := preload("res://scripts/rogue/rogue_camera_fx.gd")
const SheetScript := preload("res://scripts/rogue/rogue_style_sheet.gd")
const RIBBON_SHADER := preload("res://scripts/rogue/ribbon.gdshader")

## Phases où le ruban est affiché (hors échauffement, retour au calme et bilan : vide et grille).
const RIBBON_PHASES := ["ROOM", "CORRIDOR", "BOSS", "RECOVERY"]
const CAMERA_BACK_M := 6.0
const CAMERA_UP_M := 2.4
const CAMERA_LOOK_AHEAD_M := 14.0
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
var markers: Array = []           # {node, kind, s, len}
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
var enemy_view: Node3D            # enemy_views.gd
var _grade_pct := 0.0
var _enemy_seq := -1
var _enemy_rogue = null
var effects_ok := true            # faux si le préréglage `low` ne tient pas son budget d'images
var _hud_events: Array = []


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
	enemy_view = EnemyViews.new()
	enemy_view.name = "Enemy"
	enemy_view.preset = preset
	enemy_view.adapted = adapted
	add_child(enemy_view)
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
		markers.append({"node": node, "kind": kind, "s": float(mk["s_m"]), "len": float(mk["len_m"])})


## Trame `state.rogue` : salle à afficher, position, fenêtres actives et Firewall. `now_s` : horloge de
## l'appelant (pour limiter les demandes de resynchronisation).
func on_state(rogue: Dictionary, now_s: float) -> void:
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
	_s_target = float(rogue.get("s_room", 0.0)) if ribbon.visible else 0.0
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
	else:
		_s_disp = 0.0
	_update_pose()


## Trame `state` entière (vitesse, watts, cadence) pour le HUD diégétique et les effets de caméra (lot R11).
func on_hud(state: Dictionary, now_s: float) -> void:
	hud_model.update(state, now_s)
	var events: Array = hud_model.take_events()
	_hud_events.append_array(events)
	hud_view.show_events(events)
	_enemy_rogue = state.get("rogue", null)
	_enemy_seq = int(state.get("seq", -1))
	_grade_pct = float(state.get("grade", 0.0))


func _process(delta: float) -> void:
	_s_disp = lerpf(_s_disp, _s_target, clampf(delta * SMOOTH_PER_S, 0.0, 1.0))
	if absf(_s_disp - _s_target) > 50.0:
		_s_disp = _s_target       # saut de salle : pas de glissement
	_update_pose()
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
	var eye := Vector3(0.0, y + CAMERA_UP_M, -(_s_disp - CAMERA_BACK_M))
	var target := Vector3(0.0, ribbon_y(_s_disp + CAMERA_LOOK_AHEAD_M) + 0.5, -(_s_disp + CAMERA_LOOK_AHEAD_M))
	camera.fov = camera_fx.fov_deg()
	camera.look_at_from_position(eye + camera_fx.shake_offset(), target)

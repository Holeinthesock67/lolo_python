extends SceneTree

## Tests sans écran du modèle des bots à l'écran `bots_view_model.gd` (Lot O7) et de leur affichage.
## Lancement : godot --headless --path engine --script res://tests/unit/test_bots_view_model.gd

const BotsViewModel := preload("res://scripts/bots_view_model.gd")
const BotsView := preload("res://scripts/bots_view.gd")
const RoadCyclistsModel := preload("res://scripts/road_cyclists_model.gd")
const HudView := preload("res://scripts/hud_view.gd")
const ClimbTest := preload("res://tests/unit/test_climb_detector.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")

const US := 1000000

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _bots() -> Array:
	return [
		{"id": "bot1", "name": "Bot 200 W", "s": 1000.0, "v": 5.0, "kind": "constant"},
		{"id": "ghost", "name": "Fantôme du 26/10", "s": 880.0, "v": 6.0, "kind": "ghost"},
		{"id": "bot2", "name": "Bot 300 W", "s": 1500.0, "v": 8.0, "kind": "constant"},
	]


func _test_gaps() -> void:
	_check(BotsViewModel.gap_m(1000.0, 1100.0) == 100.0 and BotsViewModel.gap_m(1000.0, 900.0) == -100.0, "écart signé en mètres")
	_check(is_equal_approx(BotsViewModel.gap_m(50.0, 3950.0, 4000.0), -100.0), "boucle : le plus court sens, derrière (%s)" % str(BotsViewModel.gap_m(50.0, 3950.0, 4000.0)))
	_check(is_equal_approx(BotsViewModel.gap_m(3950.0, 50.0, 4000.0), 100.0), "boucle : le plus court sens, devant")
	_check(is_equal_approx(BotsViewModel.gap_seconds(60.0, 8.0, 4.0), 10.0), "écart en secondes : 60 m à 6 m/s de moyenne")
	_check(is_equal_approx(BotsViewModel.gap_seconds(10.0, 0.0, 0.0), 10.0), "arrêtés : vitesse plancher de 1 m/s")


func _test_view() -> void:
	var m = BotsViewModel.new()
	m.push(_bots(), 0)
	var v: Array = m.view(1000.0, 7.0, 0)
	_check(v.map(func(b): return b["id"]) == ["bot2", "bot1", "ghost"], "ordre : du plus loin devant au plus loin derrière (%s)" % str(v.map(func(b): return b["id"])))
	_check(v[0]["gap_m"] == 500.0 and not v[0]["visible"], "bot à 500 m : trop loin pour la route")
	_check(v[1]["gap_m"] == 0.0 and v[1]["visible"] and v[1]["show_name"], "bot à 0 m : visible, avec son nom")
	_check(v[2]["gap_m"] == -120.0 and v[2]["visible"] and not v[2]["show_name"], "fantôme à 120 m derrière : visible, sans nom")
	_check(is_equal_approx(v[2]["gap_s"], -120.0 / 6.5), "fantôme : écart en secondes (%s)" % str(v[2]["gap_s"]))
	# Extrapolation entre deux trames, bornée à 1 s.
	var later: Array = m.view(1000.0, 7.0, US)
	_check(is_equal_approx(later[1]["s"], 1005.0), "extrapolé de 1 s : 1005 m")
	later = m.view(1000.0, 7.0, 5 * US)
	_check(is_equal_approx(later[1]["s"], 1005.0), "extrapolation bornée à 1 s")
	# gap_s du core (révision 1.4) prioritaire.
	m.push([{"id": "b", "name": "Grimpeur", "s": 1100.0, "v": 5.0, "kind": "constant", "gap_s": 8.4}], 0)
	_check(is_equal_approx(m.view(1000.0, 7.0, 0)[0]["gap_s"], 8.4), "gap_s du core utilisé")
	# Boucle.
	m.loop_length_m = 4000.0
	m.push([{"id": "b", "name": "B", "s": 3990.0, "v": 10.0, "kind": "constant"}], 0)
	var loop: Array = m.view(20.0, 5.0, US)
	_check(absf(loop[0]["s"]) < 0.01, "boucle : s ramené dans la longueur (%s)" % str(loop[0]["s"]))
	_check(absf(loop[0]["gap_m"] + 20.0) < 0.01, "boucle : bot derrière malgré le passage de la ligne (%s)" % str(loop[0]["gap_m"]))
	# Sans bot.
	m.push(null, 0)
	_check(m.count() == 0 and m.view(0.0, 0.0, 0).is_empty(), "trame sans bots : liste vide")
	m.push([{"id": "", "s": 1.0}, {"id": "x"}, 5], 0)
	_check(m.count() == 0, "éléments mal formés ignorés")
	var six: Array = []
	for i in range(8):
		six.append({"id": "b%d" % i, "name": "B", "s": float(i), "v": 1.0, "kind": "constant"})
	m.push(six, 0)
	_check(m.count() == 5, "au plus cinq bots")


func _test_hud() -> void:
	var m = BotsViewModel.new()
	m.push(_bots(), 0)
	var v: Array = m.view(1000.0, 7.0, 0)
	var marks: Array = BotsViewModel.profile_marks(v, -500.0, 4500.0)
	_check(marks.size() == 3 and BotsViewModel.profile_marks(v, -50.0, 200.0).size() == 1, "repères du profil dans la fenêtre")
	_check(BotsViewModel.color_of("ghost") != BotsViewModel.color_of("constant"), "couleur par kind")
	var hud = HudView.new()
	hud.update_bots(v)
	_check(hud.panel_bots.visible and hud.bots_lines[0].text == "Bot 300 W" and hud.bots_gaps[0].text == "+66,7 s"
		and hud.bots_lines[2].visible and not hud.bots_lines[3].visible, "HUD : encart affiché, trois lignes (lignes du lot T15)")
	hud.update_bots([])
	_check(not hud.panel_bots.visible, "HUD : encart caché sans bot")
	hud.free()


func _test_nodes() -> void:
	var route = ClimbTest.make_route(2000.0, func(_s): return 0.0)
	var m = BotsViewModel.new()
	m.push(_bots(), 0)
	var bv = BotsView.new()
	bv.update_view(m.view(1000.0, 7.0, 0), route)
	_check(bv.get_child_count() == 2, "une silhouette par bot visible (%d)" % bv.get_child_count())
	var node: Node3D = bv.get_child(0)
	var label: Label3D = node.get_node("Name")
	_check(absf(node.position.x - 1000.0) < 1.0 and absf(node.position.z - RoadBuilder.BOT_LATERAL_M) < 0.1 and RoadBuilder.BOT_LATERAL_M > RoadBuilder.RIDER_LATERAL_M, "posée sur la route, à droite du cycliste (lot P32) (%s)" % str(node.position))
	_check(label.visible, "nom affiché à moins de 50 m")
	# Lot Y14 : coureur et vélo de people_mesh.gd, pédalier qui suit la distance, fantôme translucide
	var rider: MultiMeshInstance3D = node.get_node("Rider")
	var bike: MultiMeshInstance3D = node.get_node("Bike")
	_check(rider.multimesh.mesh.get_faces().size() > 1000 and bike.multimesh.mesh.get_faces().size() > 1000,
		"coureur et vélo de people_mesh.gd")
	var pose: Dictionary = bv.pose_of("bot1")
	var phase := fposmod(1000.0 / RoadCyclistsModel.DEVELOPMENT_M, 1.0)
	_check(is_equal_approx(float(pose.get("phase", -1.0)), phase), "pédalier calé sur la distance parcourue (%s)" % str(pose.get("phase")))
	var shown: Dictionary = m.view(1000.0, 7.0, 0).filter(func(b): return b["id"] == "bot1")[0]
	_check(Color(pose.get("color", Color.BLACK)).is_equal_approx(shown["color"]), "maillot à la couleur du bot")
	var ghost: Node3D = bv.get_child(1)
	var g_mat: ShaderMaterial = (ghost.get_node("Rider") as MultiMeshInstance3D).material_override
	_check(g_mat.shader.resource_path.ends_with("bot_ghost.gdshader") and float(g_mat.get_shader_parameter("ghost_alpha")) < 1.0,
		"fantôme translucide (bot_ghost.gdshader)")
	bv.update_view([], route)
	_check(bv.get_child_count() == 0, "sans bot : aucune silhouette")
	bv.free()


## Lot Z2 (suite de P32) : quatre bots partis avec le cycliste se rangent côte à côte, sans se superposer ni
## toucher le cycliste ; un bot seul garde sa place vers le bord ; un bot écarté y revient en glissant.
func _test_laterals() -> void:
	var m = BotsViewModel.new()
	var pack := []
	for i in range(4):
		pack.append({"id": "b%d" % i, "name": "Bot %d" % i, "s": 0.5 * i, "v": 0.0, "kind": "constant", "profile": "rouleur"})
	m.push(pack, 0)
	var v: Array = []
	for k in range(60):   # 3 s à 20 images/s
		v = m.view(0.0, 0.0, k * 50000)
	var slots := {}
	var touching := 0
	for a in v:
		slots[snappedf(float(a["lateral"]), 0.01)] = true
		if absf(float(a["lateral"]) - RoadBuilder.RIDER_LATERAL_M) < 0.6 and absf(float(a["gap_m"])) < BotsViewModel.SLOT_CLEAR_M:
			touching += 1
		for b in v:
			if a != b and absf(float(a["lateral"]) - float(b["lateral"])) < 0.6 and absf(float(a["gap_m"]) - float(b["gap_m"])) < BotsViewModel.SLOT_CLEAR_M:
				touching += 1
	_check(slots.size() == 4 and touching == 0, "peloton au départ : quatre places différentes, aucun contact (%s)" % str(slots.keys()))
	_check(m.places().size() == 4 and m.places()[0].has("lateral"), "places() : une place par bot pour le décor")
	var first: Dictionary = v[0]
	_check(is_equal_approx(float(first["lateral"]), RoadBuilder.BOT_LATERAL_M), "le premier garde sa place vers le bord")
	# Le peloton s'étire et le cycliste est lâché : chacun revient vers le bord, en glissant (au plus
	# LATERAL_SPEED_MPS) ; près du cycliste, celui qui roule de l'autre côté ne se rabat pas sur lui
	var spread := []
	for i in range(4):
		spread.append({"id": "b%d" % i, "name": "Bot %d" % i, "s": 30.0 * i, "v": 0.0, "kind": "constant"})
	m.push(spread, 3000000)
	var before: Dictionary = {}
	for a in v:
		before[a["id"]] = float(a["lateral"])
	var near_rider: Array = m.view(0.0, 0.0, 3000000)   # 50 ms après la dernière vue
	var crossing := 0
	for k in range(100):
		near_rider = m.view(0.0, 0.0, 3050000 + k * 50000)
		for a in near_rider:
			if absf(float(a["gap_m"])) < BotsViewModel.RIDER_CLEAR_M and absf(float(a["lateral"]) - RoadBuilder.RIDER_LATERAL_M) < BotsViewModel.TOUCH_LATERAL_M:
				crossing += 1
	_check(crossing == 0, "près du cycliste, aucun bot ne se rabat sur lui (%d)" % crossing)
	m.push(spread, 3000000)
	for a in near_rider:
		before[a["id"]] = float(a["lateral"])
	var step: Array = m.view(-200.0, 0.0, 8050000)   # cycliste lâché, 50 ms après la dernière vue
	var jump := 0.0
	for a in step:
		jump = maxf(jump, absf(float(a["lateral"]) - float(before[a["id"]])))
	_check(jump <= BotsViewModel.LATERAL_SPEED_MPS * 0.05 + 1e-4, "glisse vers sa place, sans saut (%.3f m en 50 ms)" % jump)
	for k in range(100):
		step = m.view(-200.0, 0.0, 8100000 + k * 50000)
	var all_edge := true
	for a in step:
		all_edge = all_edge and is_equal_approx(float(a["lateral"]), RoadBuilder.BOT_LATERAL_M)
	_check(all_edge, "peloton étiré : tous revenus à leur place vers le bord")
	m.push([], 14000000)
	_check(m.view(0.0, 0.0, 14000000).is_empty() and m.places().is_empty(), "sans bot : aucune place")


func _init() -> void:
	_test_gaps()
	_test_view()
	_test_hud()
	_test_nodes()
	_test_laterals()
	print("test_bots_view_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

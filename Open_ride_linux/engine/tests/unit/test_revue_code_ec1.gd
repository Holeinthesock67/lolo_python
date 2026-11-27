extends SceneTree

## Lot EC1, retour au menu après une séance (revue de code, vague 3, E2-01 à E2-05), sans écran :
## balade du monde ouvert qui ne devient plus le parcours du menu, run Cyber-Rogue quittée avant le départ,
## filtre par étiquette de la liste affichée, attente de la run sans réponse du core, séance finie en erreur.
## Lancement : godot --headless --path engine --script res://tests/unit/test_revue_code_ec1.gd

const MenuFlow := preload("res://scripts/menu_flow.gd")
const RogueMenuModel := preload("res://scripts/rogue/rogue_menu_model.gd")
const FeedbackModel := preload("res://scripts/feedback_model.gd")

const ROGUE_CONFIG := {"w_prime_j": 20000.0, "w_prime_estimate_j": 18400.0, "cp_w": 220.0,
	"objectives": ["endurance", "threshold", "vo2max"], "durations_min": [30, 45, 60, 90]}

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _init() -> void:
	call_deferred("_run")


func _ids(f) -> Array:
	return f.state()["items"].map(func(it): return it["id"])


func _flow() -> Variant:
	var f = MenuFlow.new()
	f.connect_done = true
	f.menu.set_modes(["ride", "erg", "rogue"])
	f.rogue.configure(ROGUE_CONFIG)
	f.on_state({"session_state": "IDLE"})
	f.menu.set_world("vosges", "Vosges")
	return f


## Actions d'un retour de `handle` (seule ou en séquence), à plat.
func _parts(act: Dictionary) -> Array:
	if act.is_empty():
		return []
	return act.get("list", []) if act.get("action", "") == "sequence" else [act]


func _has_route(act: Dictionary, route_id: String) -> bool:
	for a in _parts(act):
		if a.get("action", "") == "select_route" and a.get("route_id", "") == route_id:
			return true
	return false


## Action « list » d'un retour au menu (avec `route_id` quand un parcours est rechargé), {} sinon.
func _list_of(act: Dictionary) -> Dictionary:
	for a in _parts(act):
		if a.get("action", "") == "list":
			return a
	return {}


## Lance une run depuis l'accueil jusqu'à l'écran Prêt du Cyber-Rogue (premier lancement : avertissement).
func _prepare_run(f) -> void:
	f.menu.focus_item("rogue")
	f.handle("A_LONG")
	f.menu.focus_item("launch")
	var act: Dictionary = f.handle("A_LONG")
	if f.state()["screen"] == "confirm":
		f.handle("PLUS_SHORT")
		act = f.handle("A_LONG")
	_check(act.get("action", "") == "start_run", "run lancée (%s)" % str(act))
	f.on_command_acked("start_run")
	f.on_state({"session_state": "READY", "mode": "ROGUE", "route_id": null})


func _run() -> void:
	_test_open_world_is_not_menu_route()
	_test_run_left_before_start()
	_test_run_without_answer()
	_test_tag_filter_of_shown_list()
	_test_ride_ended_by_error()
	_test_end_hint_cleared_by_error()
	print("test_revue_code_ec1 : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


## E2-01 : la balade `ow:<id>` ne remplace pas le parcours du menu ; « Menu principal » recharge celui-ci.
func _test_open_world_is_not_menu_route() -> void:
	var f = _flow()
	f.note_launch("start_open_world")
	f.on_state({"session_state": "RUNNING", "route_id": "ow:abc"})
	_check(f.menu.world_id == "vosges" and f.menu.free_world_id == "vosges",
		"monde ouvert : le parcours du menu reste celui du catalogue (%s)" % f.menu.world_id)
	f.on_state({"session_state": "FINISHED", "route_id": "ow:abc", "summary": {}})
	f.menu.focus_item("new_session")
	var act: Dictionary = f.handle("A_LONG")
	_check(_list_of(act) == {"action": "list", "route_id": "vosges"}, "Menu principal : le parcours du catalogue est rechargé (%s)" % str(act))
	# sans parcours connu du menu : aucune demande d'un parcours `ow:`
	var g = MenuFlow.new()
	g.connect_done = true
	g.on_state({"session_state": "IDLE"})
	g.on_state({"session_state": "RUNNING", "route_id": "ow:abc"})
	g.on_state({"session_state": "FINISHED", "route_id": "ow:abc", "summary": {}})
	g.menu.focus_item("new_session")
	act = g.handle("A_LONG")
	_check(g.menu.world_id == "" and _list_of(act) == {"action": "list"}, "sans parcours du menu : listes seules (%s)" % str(act))
	# un parcours du catalogue annoncé par la trame reste suivi
	g.on_state({"session_state": "READY", "route_id": "demo"})
	_check(g.menu.world_id == "demo", "parcours du catalogue de la trame : suivi comme avant")


## E2-02 : run préparée puis quittée par Y, puis « Session libre » : le parcours du menu est renvoyé au core.
func _test_run_left_before_start() -> void:
	var f = _flow()
	_prepare_run(f)
	_check(f.state()["screen"] == "ready" and f.menu.mode == "rogue", "écran Prêt du Cyber-Rogue")
	_check(not _has_route(f.handle("PLUS_SHORT"), "vosges"), "sur l'écran Prêt du Rogue : rien n'est renvoyé")
	f.handle("Y_SHORT")
	_check(f.state()["screen"] == "home", "Y : accueil")
	f.menu.focus_item("ride")
	var act: Dictionary = f.handle("A_LONG")
	var names: Array = _parts(act).map(func(a): return a.get("action", ""))
	_check(names == ["select_workout", "select_route"] and _has_route(act, "vosges"),
		"Session libre après une run quittée : select_workout puis select_route du parcours du menu (%s)" % str(act))
	_check(f.handle("PLUS_SHORT").is_empty(), "renvoyé une seule fois")
	# run courue : le retour au menu recharge déjà le parcours, rien de plus ensuite
	var g = _flow()
	_prepare_run(g)
	g.on_state({"session_state": "RUNNING", "mode": "ROGUE"})
	g.on_state({"session_state": "FINISHED", "summary": {}})
	g.menu.focus_item("new_session")
	g.handle("A_LONG")
	g.on_state({"session_state": "READY", "route_id": "vosges"})
	g.menu.focus_item("ride")
	var after: Dictionary = g.handle("A_LONG")
	_check(after == {"action": "select_workout", "workout_id": null}, "après une run courue : session libre comme avant (%s)" % str(after))
	# pendant la composition, un appui ne fait pas abandonner la run par le core
	var h = _flow()
	h.menu.focus_item("rogue")
	h.handle("A_LONG")
	h.menu.focus_item("launch")
	h.handle("A_LONG")
	if h.state()["screen"] == "confirm":
		h.handle("PLUS_SHORT")
		h.handle("A_LONG")
	_check(h.state()["screen"] == RogueMenuModel.LOADING and h.handle("PLUS_SHORT").is_empty(),
		"pendant la composition : aucun select_route")


## E2-04 : `start_run` sans accusé du core : retour à l'écran de départ avec un message ; Y sort de l'attente.
func _test_run_without_answer() -> void:
	var f = _flow()
	f.menu.focus_item("rogue")
	f.handle("A_LONG")
	f.menu.focus_item("launch")
	f.handle("A_LONG")
	if f.state()["screen"] == "confirm":
		f.handle("PLUS_SHORT")
		f.handle("A_LONG")
	_check(f.state()["screen"] == RogueMenuModel.LOADING, "attente de la run")
	f.on_command_failed("list_routes")
	_check(f.state()["screen"] == RogueMenuModel.LOADING, "autre commande sans réponse : l'attente reste")
	f.on_command_failed("start_run")
	_check(f.state()["screen"] == RogueMenuModel.SCREEN, "start_run sans réponse : retour à l'écran de départ")
	var launch: Dictionary = f.state()["items"].filter(func(it): return it["id"] == "launch")[0]
	_check(str(launch.get("detail", "")).begins_with("Échec"), "message d'échec affiché (%s)" % str(launch.get("detail", "")))
	f.menu.focus_item("launch")
	var act: Dictionary = f.handle("A_LONG")
	_check(act.get("action", "") == "start_run" and f.state()["screen"] == RogueMenuModel.LOADING, "relance possible")
	f.handle("Y_SHORT")
	_check(f.state()["screen"] == RogueMenuModel.SCREEN, "Y pendant l'attente : retour à l'écran de départ")
	f.on_command_acked("start_run")
	f.on_state({"session_state": "READY", "mode": "ROGUE"})
	_check(f.state()["screen"] == RogueMenuModel.SCREEN, "accusé tardif après Y : l'écran ne change pas tout seul")
	_check(_has_route(f.handle("Y_SHORT"), "vosges") and f.state()["screen"] == "home",
		"run peut-être composée derrière l'attente quittée : parcours renvoyé au core dès le retour à l'accueil")


## E2-03 : le filtre fait défiler les étiquettes de la liste affichée, pas celles des parcours d'un mode.
func _test_tag_filter_of_shown_list() -> void:
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "IDLE"})
	f.menu.mode_routes = {"track": "velodrome"}
	var routes: Array = []
	for r in [["col_a", "col"], ["piste", "velodrome"], ["cratere", "volcan"]]:
		routes.append({"id": r[0], "name": r[0], "length_m": 5000.0, "status": "ready", "library": {"tags": [r[1]]}})
	f.set_routes(routes)
	f.menu.focus_item("world")
	f.handle("A_LONG")
	_check("_filter" in _ids(f) and not "piste" in _ids(f), "liste générale sans la piste (%s)" % str(_ids(f)))
	f.menu.focus_item("_filter")
	var seen: Array = []
	for i in 3:
		f.handle("A_LONG")
		seen.append(f.route_tag)
	_check(seen == ["col", "volcan", ""], "étiquettes parcourues : col, volcan, toutes (%s)" % str(seen))
	f.handle("A_LONG")
	f.handle("A_LONG")
	_check(_ids(f).slice(0, 1) == ["cratere"] and not "col_a" in _ids(f), "filtre « volcan » atteint (%s)" % str(_ids(f)))


## E2-05 : séance arrêtée par une erreur : le bilan de la trame s'ouvre, sinon retour à l'accueil.
func _test_ride_ended_by_error() -> void:
	var f = _flow()
	f.on_state({"session_state": "RUNNING"})
	f.on_state({"session_state": "PAUSED"})
	f.on_state({"session_state": "RUNNING"})
	f.on_state({"session_state": "ERROR", "summary": {"duration_s": 600.0}})
	_check(f.state()["screen"] == "summary" and f.summary.get("duration_s", 0.0) == 600.0,
		"erreur en séance avec bilan : le bilan s'ouvre (%s)" % f.state()["screen"])
	f.on_state({"session_state": "ERROR", "summary": {"duration_s": 600.0, "distance_m": 4000.0}})
	_check(f.summary.get("distance_m", 0.0) == 4000.0 and f.state()["screen"] == "summary", "bilan tenu à jour, écran gardé")
	f.menu.focus_item("new_session")
	var act: Dictionary = f.handle("A_LONG")
	_check(_list_of(act) == {"action": "list", "route_id": "vosges"} and f.state()["screen"] == "home",
		"Menu principal depuis ce bilan : accueil et parcours rechargé (%s)" % str(act))
	var g = _flow()
	g.on_state({"session_state": "RUNNING"})
	g.on_state({"session_state": "PAUSED"})
	g.on_state({"session_state": "ERROR"})
	_check(g.state()["screen"] == "home", "erreur en pause sans bilan : accueil, plus l'écran Pause (%s)" % g.state()["screen"])
	var h = _flow()
	h.on_state({"session_state": "ERROR", "summary": {"duration_s": 1.0}})
	_check(h.state()["screen"] == "home" and h.summary.is_empty(), "erreur hors séance : rien ne change")


## E4-02 : la consigne de fin d'une séance arrêtée par une erreur ne reste pas pour la séance suivante.
func _test_end_hint_cleared_by_error() -> void:
	var fb = FeedbackModel.new()
	fb.on_state({"session_state": "READY"}, 0.0)
	fb.on_state({"session_state": "RUNNING"}, 1.0)
	fb.result("place", "2e sur 8", "Bien joué", 2.0, "COURSE FINIE")
	_check(fb.is_done(), "issue annoncée : consigne de fin posée")
	fb.on_state({"session_state": "ERROR"}, 3.0)
	_check(not fb.is_done(), "fin en erreur : consigne de fin effacée")
	fb.on_state({"session_state": "READY"}, 4.0)
	fb.on_state({"session_state": "RUNNING"}, 5.0)
	_check(not fb.is_done(), "séance suivante : pas de « COURSE FINIE » de la séance d'avant")

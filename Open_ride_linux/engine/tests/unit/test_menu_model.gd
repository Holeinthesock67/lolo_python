extends SceneTree

## Tests sans écran de la navigation des menus `menu_model.gd` (Lot K5).
## Lancement : godot --headless --path engine --script res://tests/unit/test_menu_model.gd
## Chaque scénario est une suite d'événements avec, après chacun, l'écran, l'élément qui a le focus
## et l'action attendue (null : aucune action).

const MenuModel := preload("res://scripts/menu_model.gd")

const ROUTES_4 := [
	{"id": "galibier", "label": "Col du Galibier"},
	{"id": "alpe", "label": "Alpe d'Huez"},
	{"id": "vercors", "label": "Vercors"},
	{"id": "demo", "label": "Démo"},
]
const ROUTES_WITH_DISABLED := [
	{"id": "galibier", "label": "Col du Galibier"},
	{"id": "nouveau", "label": "Nouveau GPX", "enabled": false, "detail": "à compiler"},
	{"id": "vercors", "label": "Vercors"},
]
const WORKOUTS_2 := [
	{"id": "sweet_spot", "label": "Sweet spot 3 × 10"},
	{"id": "casse", "label": "Fichier cassé", "enabled": false, "detail": "bloc 3 : durée manquante"},
	{"id": "vo2", "label": "VO2 5 × 3"},
]

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _focus_id(st: Dictionary) -> String:
	var f: int = st["focus"]
	return "" if f < 0 else str(st["items"][f]["id"])


func _same_action(got: Dictionary, expected: Variant) -> bool:
	if expected == null:
		return got.is_empty()
	return got == expected


## Joue un scénario ; vérifie après chaque événement l'écran, le focus et l'action, et qu'aucune
## action ne sort d'une validation sur un élément désactivé.
func _scenario(name: String, setup: Callable, steps: Array) -> void:
	var m = MenuModel.new()
	setup.call(m)
	var ok := true
	var detail := ""
	for k in range(steps.size()):
		var step: Array = steps[k]
		var before: Dictionary = m.state()
		var on_disabled: bool = before["focus"] < 0 or not before["items"][before["focus"]]["enabled"]
		var st: Dictionary = m.handle(step[0])
		var good: bool = st["screen"] == step[1] and _focus_id(st) == step[2] and _same_action(st["action"], step[3])
		if step[0] == "PLUS_LONG" and on_disabled and not st["action"].is_empty():
			good = false
		if not good and ok:
			detail = " ; étape %d (%s) : écran %s, focus « %s », action %s" % [
				k + 1, step[0], st["screen"], _focus_id(st), str(st["action"])]
		ok = ok and good
	_check(ok, "scénario « %s » (%d événements)%s" % [name, steps.size(), detail])


func _routes(items: Array) -> Callable:
	return func(m): m.set_items("routes", items); m.set_items("workouts", WORKOUTS_2)


func _test_scenarios() -> void:
	_scenario("choisir le 3e parcours et démarrer", _routes(ROUTES_4), [
		["PLUS_LONG", "routes", "galibier", null],
		["PLUS_SHORT", "routes", "alpe", null],
		["PLUS_SHORT", "routes", "vercors", null],
		["PLUS_LONG", "ready", "start", {"action": "select_route", "route_id": "vercors"}],
		["PLUS_LONG", "ready", "start", {"action": "start"}],
	])
	_scenario("passer un parcours désactivé (à compiler)", _routes(ROUTES_WITH_DISABLED), [
		["PLUS_LONG", "routes", "galibier", null],
		["PLUS_SHORT", "routes", "vercors", null],
		["MINUS_SHORT", "routes", "galibier", null],
	])
	_scenario("boucler en fin et en début de liste", _routes(ROUTES_4), [
		["PLUS_LONG", "routes", "galibier", null],
		["MINUS_SHORT", "routes", "demo", null],
		["PLUS_SHORT", "routes", "galibier", null],
		["PLUS_SHORT", "routes", "alpe", null],
		["PLUS_SHORT", "routes", "vercors", null],
		["PLUS_SHORT", "routes", "demo", null],
		["PLUS_SHORT", "routes", "galibier", null],
	])
	_scenario("accueil : boucle sur les quatre entrées", _routes(ROUTES_4), [
		["MINUS_SHORT", "home", "quit", null],
		["PLUS_SHORT", "home", "ride", null],
		["MINUS_LONG", "home", "ride", null],
	])
	_scenario("retour depuis les parcours, l'écran prêt et les réglages", _routes(ROUTES_4), [
		["PLUS_LONG", "routes", "galibier", null],
		["PLUS_SHORT", "routes", "alpe", null],
		["PLUS_LONG", "ready", "start", {"action": "select_route", "route_id": "alpe"}],
		["MINUS_LONG", "routes", "alpe", null],
		["MINUS_LONG", "home", "ride", null],
		["PLUS_SHORT", "home", "workouts", null],
		["PLUS_SHORT", "home", "settings", null],
		["PLUS_LONG", "settings", "devices", null],
		["PLUS_SHORT", "settings", "devices", null],
		["PLUS_LONG", "settings", "devices", {"action": "item", "screen": "settings", "id": "devices"}],
		["MINUS_LONG", "home", "settings", null],
	])
	_scenario("entraînement depuis l'accueil (invalide sauté), puis parcours", _routes(ROUTES_4), [
		["PLUS_SHORT", "home", "workouts", null],
		["PLUS_LONG", "workouts", "_sim", null],
		["PLUS_SHORT", "workouts", "sweet_spot", null],
		["PLUS_SHORT", "workouts", "vo2", null],
		["PLUS_LONG", "routes", "galibier", {"action": "select_workout", "workout_id": "vo2"}],
		["MINUS_LONG", "workouts", "vo2", null],
		["MINUS_LONG", "home", "workouts", null],
	])
	_scenario("entraînement depuis l'écran prêt, retour à l'écran prêt", _routes(ROUTES_4), [
		["PLUS_LONG", "routes", "galibier", null],
		["PLUS_LONG", "ready", "start", {"action": "select_route", "route_id": "galibier"}],
		["PLUS_SHORT", "ready", "workout", null],
		["PLUS_LONG", "workouts", "_sim", null],
		["MINUS_LONG", "ready", "workout", null],
		["PLUS_LONG", "workouts", "_sim", null],
		["PLUS_LONG", "ready", "workout", {"action": "select_workout", "workout_id": null}],
		["PLUS_SHORT", "ready", "change_route", null],
		["PLUS_LONG", "routes", "galibier", null],
	])
	_scenario("quitter : annulé puis confirmé", _routes(ROUTES_4), [
		["MINUS_SHORT", "home", "quit", null],
		["PLUS_LONG", "confirm", "no", null],
		["PLUS_LONG", "home", "quit", null],
		["PLUS_LONG", "confirm", "no", null],
		["MINUS_LONG", "home", "quit", null],
		["PLUS_LONG", "confirm", "no", null],
		["PLUS_SHORT", "confirm", "yes", null],
		["PLUS_LONG", "home", "quit", {"action": "quit"}],
	])
	var paused := func(m): _routes(ROUTES_4).call(m); m.open_pause()
	_scenario("pause : abandon annulé puis confirmé", paused, [
		["PLUS_SHORT", "pause", "end_save", null],
		["PLUS_SHORT", "pause", "abandon", null],
		["PLUS_LONG", "confirm", "no", null],
		["PLUS_LONG", "pause", "abandon", null],
		["PLUS_LONG", "confirm", "no", null],
		["MINUS_LONG", "pause", "abandon", null],
		["PLUS_LONG", "confirm", "no", null],
		["MINUS_SHORT", "confirm", "yes", null],
		["PLUS_LONG", "home", "ride", {"action": "end_session", "save": false}],
	])
	_scenario("pause : reprendre, retour et terminer en enregistrant", paused, [
		["PLUS_LONG", "pause", "resume", {"action": "resume"}],
		["MINUS_LONG", "pause", "resume", {"action": "resume"}],
		["PLUS_SHORT", "pause", "end_save", null],
		["PLUS_LONG", "home", "ride", {"action": "end_session", "save": true}],
	])
	_scenario("liste de parcours vide", _routes([]), [
		["PLUS_LONG", "routes", "", null],
		["PLUS_SHORT", "routes", "", null],
		["MINUS_SHORT", "routes", "", null],
		["PLUS_LONG", "routes", "", null],
		["MINUS_LONG", "home", "ride", null],
	])
	var all_off := [{"id": "a", "label": "A", "enabled": false, "detail": "à compiler"},
		{"id": "b", "label": "B", "enabled": false, "detail": "à compiler"}]
	_scenario("tous les parcours désactivés", _routes(all_off), [
		["PLUS_LONG", "routes", "", null],
		["PLUS_LONG", "routes", "", null],
		["MINUS_LONG", "home", "ride", null],
	])


func _test_lists_and_events() -> void:
	var m = MenuModel.new()
	m.set_items("routes", [])
	m.handle("PLUS_LONG")
	var st: Dictionary = m.state()
	_check(st["items"].size() == 1 and st["items"][0]["label"] == "Aucun parcours" and not st["items"][0]["enabled"],
		"liste vide : un élément désactivé « Aucun parcours »")
	m.set_items("routes", ROUTES_WITH_DISABLED)
	var st2: Dictionary = m.state()
	_check(_focus_id(st2) == "galibier" and st2["items"][1]["detail"] == "à compiler",
		"liste injectée pendant l'affichage : focus sur le premier actif, détail gardé")
	m.handle("PLUS_SHORT")
	m.set_items("routes", ROUTES_4)
	_check(_focus_id(m.state()) == "vercors", "liste remplacée : le focus reste sur le même parcours")
	var before: Dictionary = m.state()
	var unknown_ok := true
	for ev in ["", "PLUS", "plus_short", "DOUBLE_TAP", "PLUS_SHORT "]:
		var after: Dictionary = m.handle(ev)
		unknown_ok = unknown_ok and after["action"].is_empty() and after["screen"] == before["screen"] \
			and after["focus"] == before["focus"] and after["items"] == before["items"]
	_check(unknown_ok, "événements inconnus : ignorés, état inchangé")
	var keys_ok: bool = MenuModel.key_to_event(KEY_DOWN) == "PLUS_SHORT" and MenuModel.key_to_event(KEY_UP) == "MINUS_SHORT" \
		and MenuModel.key_to_event(KEY_ENTER) == "PLUS_LONG" and MenuModel.key_to_event(KEY_ESCAPE) == "MINUS_LONG" \
		and MenuModel.key_to_event(KEY_A) == ""
	_check(keys_ok, "clavier ramené aux quatre événements, flèche bas = suivant")
	var w = MenuModel.new()
	w.set_items("workouts", [])
	w.handle("PLUS_SHORT")
	var ws: Dictionary = w.handle("PLUS_LONG")
	_check(ws["items"].size() == 2 and ws["items"][1]["label"] == "Aucun entraînement" and _focus_id(ws) == "_sim",
		"aucun entraînement : « Sans entraînement (SIM) » reste choisissable")


func _test_no_nodes() -> void:
	var before := int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT))
	var m = MenuModel.new()
	m.set_items("routes", ROUTES_4)
	for ev in ["PLUS_LONG", "PLUS_SHORT", "PLUS_LONG", "PLUS_SHORT", "PLUS_LONG", "MINUS_LONG", "MINUS_LONG"]:
		m.handle(ev)
	m.open_pause()
	m.handle("PLUS_SHORT")
	var after := int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT))
	_check(after == before, "aucun nœud créé (%d avant, %d après)" % [before, after])


func _init() -> void:
	_test_scenarios()
	_test_lists_and_events()
	_test_no_nodes()
	print("test_menu_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

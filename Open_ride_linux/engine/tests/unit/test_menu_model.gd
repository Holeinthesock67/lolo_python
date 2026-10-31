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
		if step[0] == "A_LONG" and on_disabled and not st["action"].is_empty():
			good = false
		if not good and ok:
			detail = " ; étape %d (%s) : écran %s, focus « %s », action %s" % [
				k + 1, step[0], st["screen"], _focus_id(st), str(st["action"])]
		ok = ok and good
	_check(ok, "scénario « %s » (%d événements)%s" % [name, steps.size(), detail])


func _routes(items: Array) -> Callable:
	return func(m): m.set_items("routes", items); m.set_items("workouts", WORKOUTS_2)


func _test_scenarios() -> void:
	_scenario("session libre sans monde : parcours puis Prêt, démarrer", _routes(ROUTES_4), [
		["PLUS_SHORT", "home", "ride", null],
		["A_LONG", "routes", "galibier", {"action": "select_workout", "workout_id": null}],
		["PLUS_SHORT", "routes", "alpe", null],
		["PLUS_SHORT", "routes", "vercors", null],
		["A_LONG", "ready", "start", {"action": "select_route", "route_id": "vercors"}],
		["A_LONG", "ready", "start", {"action": "start"}],
		["Y_SHORT", "home", "ride", null],
	])
	_scenario("passer un parcours désactivé (à compiler)", _routes(ROUTES_WITH_DISABLED), [
		["A_LONG", "routes", "galibier", null],
		["PLUS_SHORT", "routes", "vercors", null],
		["MINUS_SHORT", "routes", "galibier", null],
	])
	_scenario("boucler en fin et en début de liste", _routes(ROUTES_4), [
		["A_LONG", "routes", "galibier", null],
		["MINUS_SHORT", "routes", "_route_help", null],
		["MINUS_SHORT", "routes", "_add_route", null],
		["MINUS_SHORT", "routes", "demo", null],
		["PLUS_SHORT", "routes", "_add_route", null],
		["PLUS_SHORT", "routes", "_route_help", null],
		["PLUS_SHORT", "routes", "galibier", null],
		["PLUS_SHORT", "routes", "alpe", null],
		["PLUS_SHORT", "routes", "vercors", null],
	])
	_scenario("accueil : boucle sur les huit entrées", _routes(ROUTES_4), [
		["MINUS_SHORT", "home", "quit", null],
		["PLUS_SHORT", "home", "world", null],
		["PLUS_SHORT", "home", "ride", null],
		["PLUS_SHORT", "home", "erg", null],
		["PLUS_SHORT", "home", "plan", null],
		["A_LONG", "home", "plan", {"action": "item", "screen": "home", "id": "plan"}],
		["PLUS_SHORT", "home", "ftp", null],
		["A_LONG", "home", "ftp", {"action": "item", "screen": "home", "id": "ftp"}],
		["PLUS_SHORT", "home", "sim", null],
		["PLUS_SHORT", "home", "settings", null],
		["Y_SHORT", "home", "settings", null],
	])
	_scenario("choisir le monde depuis l'accueil : retour à l'accueil", _routes(ROUTES_4), [
		["A_LONG", "routes", "galibier", null],
		["PLUS_SHORT", "routes", "alpe", null],
		["A_LONG", "home", "world", {"action": "select_route", "route_id": "alpe"}],
		["PLUS_SHORT", "home", "ride", null],
		["A_LONG", "ready", "start", {"action": "select_workout", "workout_id": null}],
		["PLUS_SHORT", "ready", "workout", null],
		["PLUS_SHORT", "ready", "change_route", null],
		["A_LONG", "routes", "alpe", null],   # lot O32 : liste ouverte sur le parcours en cours
		["MINUS_SHORT", "routes", "galibier", null],
		["A_LONG", "ready", "start", {"action": "select_route", "route_id": "galibier"}],
		["Y_SHORT", "home", "ride", null],
	])
	_scenario("retour depuis les parcours et les réglages", _routes(ROUTES_4), [
		["A_LONG", "routes", "galibier", null],
		["Y_SHORT", "home", "world", null],
		["MINUS_SHORT", "home", "quit", null],
		["MINUS_SHORT", "home", "settings", null],
		["A_LONG", "settings", "devices", null],
		["A_LONG", "settings", "devices", {"action": "item", "screen": "settings", "id": "devices"}],
		["Y_SHORT", "home", "settings", null],
	])
	_scenario("session ERG sans monde : entraînement (invalide sauté), parcours, Prêt", _routes(ROUTES_4), [
		["PLUS_SHORT", "home", "ride", null],
		["PLUS_SHORT", "home", "erg", null],
		["A_LONG", "workouts", "_sim", null],
		["PLUS_SHORT", "workouts", "sweet_spot", null],
		["PLUS_SHORT", "workouts", "vo2", null],
		["A_LONG", "routes", "galibier", {"action": "select_workout", "workout_id": "vo2"}],
		["A_LONG", "ready", "start", {"action": "select_route", "route_id": "galibier"}],
		["PLUS_SHORT", "ready", "workout", null],
		["A_LONG", "workouts", "vo2", null],   # lot O32 : liste ouverte sur le dernier entraînement
		["Y_SHORT", "ready", "workout", null],
		["A_LONG", "workouts", "vo2", null],
		["MINUS_SHORT", "workouts", "sweet_spot", null],
		["MINUS_SHORT", "workouts", "_sim", null],
		["A_LONG", "ready", "workout", {"action": "select_workout", "workout_id": null}],
		["Y_SHORT", "home", "erg", null],
	])
	_scenario("session simulée : confirmation puis relance", _routes(ROUTES_4), [
		["MINUS_SHORT", "home", "quit", null],
		["MINUS_SHORT", "home", "settings", null],
		["MINUS_SHORT", "home", "sim", null],
		["A_LONG", "confirm", "no", null],
		["PLUS_SHORT", "confirm", "yes", null],
		["A_LONG", "home", "sim", {"action": "relaunch_sim"}],
	])
	var in_sim := func(m): _routes(ROUTES_4).call(m); m.set_sim_session(true)
	_scenario("en session simulée : revenir au matériel réel", in_sim, [
		["MINUS_SHORT", "home", "quit", null],
		["MINUS_SHORT", "home", "settings", null],
		["MINUS_SHORT", "home", "sim", null],
		["A_LONG", "confirm", "no", null],
		["PLUS_SHORT", "confirm", "yes", null],
		["A_LONG", "home", "sim", {"action": "relaunch"}],
	])
	_scenario("quitter : annulé puis confirmé", _routes(ROUTES_4), [
		["MINUS_SHORT", "home", "quit", null],
		["A_LONG", "confirm", "no", null],
		["A_LONG", "home", "quit", null],
		["A_LONG", "confirm", "no", null],
		["Y_SHORT", "home", "quit", null],
		["A_LONG", "confirm", "no", null],
		["PLUS_SHORT", "confirm", "yes", null],
		["A_LONG", "home", "quit", {"action": "quit"}],
	])
	var paused := func(m): _routes(ROUTES_4).call(m); m.open_pause()
	_scenario("pause : abandon annulé puis confirmé", paused, [
		["PLUS_SHORT", "pause", "end_save", null],
		["PLUS_SHORT", "pause", "abandon", null],
		["A_LONG", "confirm", "no", null],
		["A_LONG", "pause", "abandon", null],
		["A_LONG", "confirm", "no", null],
		["Y_SHORT", "pause", "abandon", null],
		["A_LONG", "confirm", "no", null],
		["MINUS_SHORT", "confirm", "yes", null],
		["A_LONG", "home", "world", {"action": "end_session", "save": false}],
	])
	_scenario("pause : reprendre, retour et terminer en enregistrant", paused, [
		["A_LONG", "pause", "resume", {"action": "resume"}],
		["Y_SHORT", "pause", "resume", {"action": "resume"}],
		["PLUS_SHORT", "pause", "end_save", null],
		["A_LONG", "home", "world", {"action": "end_session", "save": true}],
	])
	_scenario("liste de parcours vide : seules les lignes d'aide (lot O22)", _routes([]), [
		["A_LONG", "routes", "_add_route", null],
		["PLUS_SHORT", "routes", "_route_help", null],
		["MINUS_SHORT", "routes", "_add_route", null],
		["A_LONG", "routes", "_add_route", {"action": "item", "screen": "routes", "id": "_add_route"}],
		["Y_SHORT", "home", "world", null],
	])
	var all_off := [{"id": "a", "label": "A", "enabled": false, "detail": "à compiler"},
		{"id": "b", "label": "B", "enabled": false, "detail": "à compiler"}]
	_scenario("tous les parcours désactivés", _routes(all_off), [
		["A_LONG", "routes", "_add_route", null],
		["PLUS_SHORT", "routes", "_route_help", null],
		["Y_SHORT", "home", "world", null],
	])


func _test_lists_and_events() -> void:
	var m = MenuModel.new()
	m.set_items("routes", [])
	m.handle("A_LONG")
	var st: Dictionary = m.state()
	_check(st["items"].size() == 3 and st["items"][0]["label"] == "Aucun parcours" and not st["items"][0]["enabled"]
		and str(st["items"][0]["detail"]).contains("~/OpenRide/GPX/")
		and st["items"].slice(1).map(func(it): return it["id"]) == ["_add_route", "_route_help"],
		"liste vide : « Aucun parcours » désactivé, dit où déposer la trace, puis les lignes d'aide")
	m.set_items("routes", ROUTES_WITH_DISABLED)
	var st2: Dictionary = m.state()
	_check(_focus_id(st2) == "galibier" and st2["items"][1]["detail"] == "à compiler",
		"liste injectée pendant l'affichage : focus sur le premier actif, détail gardé")
	m.handle("PLUS_SHORT")
	m.set_items("routes", ROUTES_4)
	_check(_focus_id(m.state()) == "vercors", "liste remplacée : le focus reste sur le même parcours")
	var h = MenuModel.new()
	h.set_world("vosges", "Vosges")
	_check(h.state()["items"][0]["label"] == "Parcours : Vosges", "parcours affiché à l'accueil")
	_check(MenuModel._short_name("Vosges (32,0 km, boucle)") == "Vosges", "nom du monde sans la longueur")
	var before: Dictionary = m.state()
	var unknown_ok := true
	for ev in ["", "PLUS", "plus_short", "DOUBLE_TAP", "PLUS_SHORT "]:
		var after: Dictionary = m.handle(ev)
		unknown_ok = unknown_ok and after["action"].is_empty() and after["screen"] == before["screen"] \
			and after["focus"] == before["focus"] and after["items"] == before["items"]
	_check(unknown_ok, "événements inconnus : ignorés, état inchangé")
	var w = MenuModel.new()
	w.set_items("workouts", [])
	w.handle("PLUS_SHORT")
	w.handle("PLUS_SHORT")
	var ws: Dictionary = w.handle("A_LONG")
	_check(ws["items"].size() == 5 and ws["items"][1]["label"] == "Aucun entraînement" and _focus_id(ws) == "_sim",
		"aucun entraînement : « Sans entraînement (SIM) » reste choisissable")
	_check(ws["items"][2]["id"] == "_create" and ws["items"][3]["id"] == "_import",
		"sous-menu ERG (N16) : Créer et Importer en fin de liste")
	w.handle("PLUS_SHORT")
	var wc: Dictionary = w.handle("A_LONG")
	_check(wc["action"] == {"action": "item", "screen": "workouts", "id": "_create"} and wc["screen"] == "workouts",
		"Créer : action item laissée à menu_flow.gd")


func _test_no_nodes() -> void:
	var before := int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT))
	var m = MenuModel.new()
	m.set_items("routes", ROUTES_4)
	for ev in ["A_LONG", "PLUS_SHORT", "A_LONG", "PLUS_SHORT", "A_LONG", "Y_SHORT", "Y_SHORT"]:
		m.handle(ev)
	m.open_pause()
	m.handle("PLUS_SHORT")
	var after := int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT))
	_check(after == before, "aucun nœud créé (%d avant, %d après)" % [before, after])


## Séance préparée avec des arguments de `start` (lot O12) : Prêt, start avec args, annulée par un choix.
func _test_prepare_start() -> void:
	var m = MenuModel.new()
	m.set_items("routes", ROUTES_4)
	m.set_plan_home("Séance du jour : Seuil", "60 min, TSS 75")
	var home: Dictionary = m.state()["items"][3]
	_check(home["id"] == "plan" and home["label"] == "Séance du jour : Seuil" and home["detail"] == "60 min, TSS 75",
		"accueil : séance du jour avec durée et TSS")
	var st: Dictionary = m.prepare_start("test de FTP (rampe)", {"ftp_test": "ramp"})
	_check(st["screen"] == "routes", "sans monde choisi : parcours d'abord")
	st = m.handle("A_LONG")
	_check(st["screen"] == "ready" and st["title"] == "Prêt : test de FTP (rampe) — Col du Galibier",
		"puis écran Prêt (%s)" % st["title"])
	st = m.handle("A_LONG")
	_check(st["action"] == {"action": "start", "args": {"ftp_test": "ramp"}}, "start avec ftp_test (%s)" % str(st["action"]))
	m.handle("PLUS_SHORT")
	m.handle("A_LONG")   # Changer d'entraînement
	m.set_items("workouts", WORKOUTS_2)
	m.handle("PLUS_SHORT")
	st = m.handle("A_LONG")
	_check(st["screen"] == "ready" and st["title"].begins_with("Prêt : session ERG") and m.start_args.is_empty(),
		"entraînement choisi : séance préparée annulée (%s)" % st["title"])
	m.handle("MINUS_SHORT")
	_check(m.handle("A_LONG")["action"] == {"action": "start"}, "start sans arguments")
	m.prepare_start("séance du jour", {"plan_day": true})
	m.reset()
	_check(m.start_args.is_empty() and m.start_name == "", "remise à zéro (nouvelle séance) : annulée aussi")
	m.set_items("routes", ROUTES_4 + [{"id": "_sort", "label": "Trier par : nom"}])
	m.handle("A_LONG")
	m.handle("MINUS_SHORT")
	m.handle("MINUS_SHORT")
	m.handle("MINUS_SHORT")
	_check(m.handle("A_LONG")["action"] == {"action": "item", "screen": "routes", "id": "_sort"},
		"tri des parcours : action pour menu_flow, pas de parcours choisi")


func _test_modes() -> void:
	var m = MenuModel.new()
	var ids: Array = m.state()["items"].map(func(it): return it["id"])
	_check(ids == ["world", "ride", "erg", "plan", "ftp", "sim", "settings", "quit"],
		"modes par défaut : ride et erg, puis plans et test de FTP (lot O12) (%s)" % str(ids))
	m.set_modes(["erg", "cyber_rogue"])
	ids = m.state()["items"].map(func(it): return it["id"])
	_check(ids == ["world", "erg", "plan", "ftp", "sim", "settings", "quit"], "modes annoncés filtrés, inconnu ignoré (%s)" % str(ids))
	m.set_modes(null)
	_check(m.state()["items"].size() == 8, "modes absents : retour aux modes par défaut")


## Plan des boutons sans exception (spécification générale §7.1, 27 octobre).
func _test_button_plan() -> void:
	var m = MenuModel.new()
	var routes := []
	for i in range(12):
		routes.append({"id": "r%d" % i, "label": "Parcours %d" % i, "enabled": i != 3})
	m.set_items("routes", routes)
	m.handle("A_LONG")   # Parcours
	_check(m.state()["screen"] == "routes" and _focus_id(m.state()) == "r0", "A long valide (accueil → Parcours)")
	_check(_focus_id(m.handle("PLUS_LONG")) == "r6", "+ long : cinq éléments actifs plus loin (r3 désactivé sauté)")
	_check(_focus_id(m.handle("PLUS_LONG")) == "r11", "+ long : borné au dernier élément, sans boucler")
	_check(_focus_id(m.handle("MINUS_LONG")) == "r6", "− long : cinq éléments plus haut")
	_check(_focus_id(m.handle("MINUS_LONG")) == "r0", "− long : borné au premier élément")
	_check(_focus_id(m.handle("A_SHORT")) == "r1" and _focus_id(m.handle("RIGHT_SHORT")) == "r2",
		"A court et flèche droite : élément suivant")
	_check(_focus_id(m.handle("LEFT_SHORT")) == "r1", "flèche gauche : élément précédent")
	var before: Dictionary = m.state()
	var idle := true
	for ev in ["Z_SHORT", "Z_LONG", "UP_SHORT", "DOWN_SHORT", "PLUS_UNCLEAR"]:
		var st: Dictionary = m.handle(ev)
		idle = idle and st["action"].is_empty() and st["focus"] == before["focus"] and st["screen"] == "routes"
	_check(idle, "Z, flèches haut et bas, appui ambigu : rien dans un menu")
	_check(m.handle("Y_SHORT")["screen"] == "home", "Y : écran précédent")
	m.open_pause()
	_check(m.handle("Y_SHORT")["action"].get("action", "") == "resume", "Y sur l'écran de pause : reprendre")


## Derniers choix du profil (lot O32) : bot et fantôme remis à chaque accueil, listes ouvertes sur le dernier choix.
func _test_last_choices() -> void:
	var m = MenuModel.new()
	m.set_items("routes", ROUTES_4)
	m.set_items("workouts", WORKOUTS_2)
	m.set_last_choices({"workout_id": "vo2", "bots": [{"kind": "profile", "profile": "rouleur", "level_pct": 100.0},
		{"kind": "ghost"}]})
	_check(m.bot_choices == [MenuModel.bot_index({"kind": "profile", "profile": "rouleur", "level_pct": 100})] and m.ghost,
		"derniers choix : bot à profil (nombre du JSON en flottant) et fantôme repris")
	m.focus_item("erg")
	_check(_focus_id(m.handle("A_LONG")) == "vo2", "Session ERG : la liste s'ouvre sur le dernier entraînement")
	m.set_world("alpe", "Alpe d'Huez")
	m.reset()
	m.focus_item("world")
	_check(_focus_id(m.handle("A_LONG")) == "alpe", "Parcours : la liste s'ouvre sur le parcours en cours")
	m.reset()
	m.focus_item("ride")
	m.handle("A_LONG")   # écran Prêt
	m.focus_item("bot1")
	m.handle("A_LONG")   # bot suivant
	m.focus_item("ghost")
	m.handle("A_LONG")   # fantôme : non
	m.focus_item("start")
	var act: Dictionary = m.handle("A_LONG")["action"]
	var bots_after: Array[int] = m.bot_choices.duplicate()
	m.reset()
	_check(act.get("action", "") == "start" and m.bot_choices == bots_after and bots_after.size() == 1 and not m.ghost,
		"nouvel accueil : le bot et le fantôme de la séance lancée restent choisis")
	m.set_last_choices({"bots": [{"kind": "constant", "power_w": 999}]})
	_check(m.bot_choices.is_empty() and not m.ghost and m.last_workout == "", "bot inconnu et choix absents : valeurs par défaut")
	m.set_last_choices(null)
	_check(m.bot_choices.is_empty(), "aucun choix gardé (core sans last_choices)")
	# Lot O35 : jusqu'à quatre bots repris dans l'ordre, un bot inconnu sauté, le cinquième ignoré.
	var w := {"kind": "constant", "power_w": 200}
	m.set_last_choices({"bots": [w, {"kind": "constant", "power_w": 999}, {"kind": "constant", "power_w": 300}, w, w, w]})
	_check(m.bot_choices == [1, 3, 1, 1], "quatre bots repris au plus, bot inconnu sauté (%s)" % str(m.bot_choices))


func _init() -> void:
	_test_button_plan()
	_test_modes()
	_test_prepare_start()
	_test_scenarios()
	_test_lists_and_events()
	_test_no_nodes()
	_test_last_choices()
	print("test_menu_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

extends SceneTree

## Tests sans écran de « Plans d'entraînement › Créer un plan » (lot O30) : modèle (plan_builder.gd) et
## déroulé (menu_flow.gd : jours, entraînements numérotés, durée, create_plan, plan créé ouvert).
## Lancement : godot --headless --path engine --script res://tests/unit/test_plan_builder.gd

const PlanBuilder := preload("res://scripts/plan_builder.gd")
const MenuFlow := preload("res://scripts/menu_flow.gd")
const MenuModel := preload("res://scripts/menu_model.gd")

const WORKOUTS := [
	{"id": "ss", "name": "Sweet spot", "duration_s": 2700, "selectable": true},
	{"id": "vo2", "name": "VO2max", "duration_s": 3600, "selectable": true},
	{"id": "casse", "name": "casse", "duration_s": 0, "selectable": false, "error": "fichier illisible"},
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


func _ids(items: Array) -> Array:
	return items.map(func(it): return it["id"])


func _test_model() -> void:
	var b = PlanBuilder.new()
	_check(b.days == ["mardi", "jeudi", "samedi"] and b.workouts.is_empty(), "départ : mardi, jeudi, samedi")
	_check(not b.menu_items()[3]["enabled"], "« Créer le plan » grisé sans entraînement")
	_check(not b.menu_items()[2]["enabled"], "durée grisée sans entraînement")
	b.toggle_day("mardi")
	b.toggle_day("lundi")
	_check(b.days == ["lundi", "jeudi", "samedi"], "jours remis dans l'ordre de la semaine")
	_check(b.days_text() == "lun, jeu, sam", "jours abrégés sur la ligne")
	for id in ["vo2", "ss", "ftp_test:ramp", "vo2"]:
		b.toggle_workout(id)
	_check(b.workouts == ["ss", "ftp_test:ramp"], "un second choix retire l'entraînement, les suivants remontent")
	b.toggle_workout("vo2")
	b.toggle_workout("ss")
	b.toggle_workout("ss")
	_check(b.workouts == ["ftp_test:ramp", "vo2", "ss"], "rang = ordre du choix")
	var items: Array = b.workout_items(WORKOUTS)
	_check(_ids(items) == ["workout:ftp_test:ramp", "workout:ss", "workout:vo2", "workout:casse"],
		"test de FTP puis la bibliothèque")
	_check(items[0]["detail"] == "n° 1" and items[2]["detail"] == "n° 2" and items[1]["detail"] == "n° 3",
		"rang affiché à droite")
	_check(not items[3]["enabled"], "entraînement invalide grisé")
	_check(b.needed_weeks() == 1 and b.session_count() == 3, "trois séances sur trois jours : une semaine")
	_check(b.menu_items()[3]["detail"] == "3 séances", "résumé sur « Créer le plan »")
	b.toggle_workout("casse")
	b.toggle_day("jeudi")
	_check(b.needed_weeks() == 2 and b.schedule() == [[["lundi", "ftp_test:ramp"], ["samedi", "vo2"]],
		[["lundi", "ss"], ["samedi", "casse"]]], "quatre séances sur deux jours : deux semaines")
	var weeks: Array = b.week_items()
	_check(weeks[0]["label"] == "Automatique" and weeks[0]["detail"] == "2 semaines, choisi", "durée automatique")
	_check(weeks[1]["id"] == "weeks:2" and weeks[-1]["id"] == "weeks:12", "durées de 2 à 12 semaines")
	_check(weeks[2]["detail"] == "6 séances, la suite recommence", "au-delà : la suite recommence")
	_check(b.handle(PlanBuilder.WEEKS_SCREEN, "weeks:3") == {"back": true} and b.weeks == 3, "3 semaines choisies")
	_check(b.session_count() == 6 and b.schedule()[2] == [["lundi", "ftp_test:ramp"], ["samedi", "vo2"]],
		"troisième semaine : la suite recommence")
	b.toggle_day("samedi")
	b.toggle_day("lundi")
	b.toggle_day("dimanche")
	_check(b.weeks == 0, "un seul jour : 3 semaines trop court, retour à l'automatique")
	b.set_weeks(13)
	_check(b.weeks == 0, "au-delà de 12 semaines : refusé")
	_check(b.action() == {"action": "create_plan", "workouts": ["ftp_test:ramp", "vo2", "ss", "casse"],
		"days": ["dimanche"], "weeks": null}, "action create_plan, weeks null en automatique")
	var card: Dictionary = b.sheet(PlanBuilder.names_of(WORKOUTS), "Mon plan 2")
	_check(card["name"] == "Mon plan 2" and card["lines"][0] == "S1 : dim Test de FTP (rampe)", "aperçu par semaine")
	_check(card["lines"][4] == "Le plan se démarre ensuite depuis sa page", "rappel : démarrage depuis la page du plan")
	_check(PlanBuilder.plan_name(["mon-plan", "reprise"]) == "Mon plan 2" and PlanBuilder.plan_name([]) == "Mon plan",
		"nom donné par le core : Mon plan, Mon plan 2")
	var full = PlanBuilder.new()
	for i in range(PlanBuilder.MAX_WORKOUTS):
		full.workouts.append("w%d" % i)
	_check(not full.toggle_workout("ss"), "au plus 42 entraînements")


func _plans_msg(items: Array, created = null) -> Dictionary:
	var msg := {"type": "plans", "v": 1, "request_cmd_id": 1, "items": items, "truncated": false, "active": null}
	if created != null:
		msg["created"] = created
	return msg


func _test_flow() -> void:
	var f = MenuFlow.new()
	f.on_state({"session_state": "IDLE"})
	f.connect_done = true
	f.set_workouts(WORKOUTS)
	f.menu.open_screen(MenuModel.HOME)
	f.menu.push_screen(f.PLANS)
	f.on_plans(_plans_msg([{"id": "mon-plan", "name": "Mon plan", "weeks": 1, "sessions": 2, "active": false,
		"error": null}]))
	var items: Array = f.menu.state()["items"]
	_check(items[-1]["id"] == "create" and items[-1]["label"] == "Créer un plan", "« Créer un plan » en fin de liste")
	_check(f.menu.focus_item("create"), "focus sur « Créer un plan »")
	f.handle("A_LONG")
	_check(f.menu.current_screen() == PlanBuilder.SCREEN, "écran « Créer un plan »")
	_check(f.card(f.state())["name"] == "Mon plan 2", "aperçu : nom que le core donnera")
	f.menu.focus_item("workouts")
	f.handle("A_LONG")
	_check(f.menu.current_screen() == PlanBuilder.WORKOUTS_SCREEN, "écran des entraînements")
	f.menu.focus_item("workout:vo2")
	f.handle("A_LONG")
	f.menu.focus_item("workout:ss")
	f.handle("A_LONG")
	_check(f.menu.state()["items"][2]["detail"] == "n° 1" and f.menu.state()["items"][1]["detail"] == "n° 2",
		"rangs mis à jour à l'écran")
	f.handle("Y_SHORT")
	_check(f.menu.current_screen() == PlanBuilder.SCREEN and f.menu.state()["items"][1]["detail"] == "2 choisis",
		"Y : retour, deux entraînements")
	f.menu.focus_item("weeks")
	f.handle("A_LONG")
	f.menu.focus_item("weeks:4")
	f.handle("A_LONG")
	_check(f.menu.current_screen() == PlanBuilder.SCREEN and f.menu.state()["items"][2]["detail"] == "4 semaines",
		"durée choisie : retour à « Créer un plan »")
	f.menu.focus_item("create")
	var act: Dictionary = f.handle("A_LONG")
	_check(act == {"action": "create_plan", "workouts": ["vo2", "ss"], "days": ["mardi", "jeudi", "samedi"],
		"weeks": 4}, "A maintenu : create_plan")
	_check(f.state()["status"] == "Création du plan…", "ligne d'état en attendant le core")
	f.on_error("plan_invalid", "Plan refusé : le plan « mon-plan-2 » existe déjà")
	_check(f.state()["status"] == "Échec : Plan refusé : le plan « mon-plan-2 » existe déjà", "refus sur la ligne d'état")
	f.handle("A_LONG")
	f.on_plans(_plans_msg([{"id": "mon-plan", "name": "Mon plan", "weeks": 1, "sessions": 2, "active": false,
		"error": null}, {"id": "mon-plan-2", "name": "Mon plan 2", "weeks": 4, "sessions": 12, "active": false,
		"error": null}], {"id": "mon-plan-2", "name": "Mon plan 2"}))
	_check(f.menu.current_screen() == f.PLAN and f.menu.state()["title"] == "Mon plan 2", "plan créé : sa page s'ouvre")
	_check(f.state()["status"] == "Plan créé : Mon plan 2", "ligne d'état : plan créé")
	_check(f.menu.state()["items"][1]["id"] == "start", "prêt à démarrer")
	f.handle("Y_SHORT")
	_check(f.menu.current_screen() == f.PLANS, "Y : retour à la liste des plans")


func _init() -> void:
	_test_model()
	_test_flow()
	print("test_plan_builder : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

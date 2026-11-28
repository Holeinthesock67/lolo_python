extends SceneTree

## Objectif de la semaine à l'accueil (lot OS1, objet `week_goal` du message `coach`) : ligne « Semaine : 1 séance
## sur 2 » sous la ligue, état en mots (« il reste 4 jours », « dernier jour », « objectif atteint »), pas de ligne
## sans objectif, la ligne ouvre l'Historique. Valeurs fictives.
## Lancement : godot --headless --path engine --script res://tests/unit/test_week_goal_home.gd

const CoachViewModel := preload("res://scripts/coach_view_model.gd")
const MenuModel := preload("res://scripts/menu_model.gd")
const MenuFlow := preload("res://scripts/menu_flow.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if not cond:
		_failures += 1
		printerr("ÉCHEC : " + msg)


func _coach(goal) -> Dictionary:
	return {"type": "coach", "v": 1, "date": "2026-11-19", "need": "light", "need_label": "Aérobie léger",
		"rule": "R6", "reason": "r", "duration_s": 2700, "notes": [], "alternatives": [], "workout": null,
		"other_workouts": [], "route": null, "details": {}, "week_goal": goal}


func _ids(items: Array) -> Array:
	return items.map(func(it): return str(it["id"]))


func _init() -> void:
	var c = CoachViewModel.new()
	_check(c.week_label() == "" and c.week_detail() == "", "avant le conseil : pas de ligne")
	c.on_coach(_coach({"target": 2, "done": 1, "days_left": 4, "reached": false}))
	_check(c.week_label() == "Semaine : 1 séance sur 2" and c.week_detail() == "il reste 4 jours",
		"en cours (%s · %s)" % [c.week_label(), c.week_detail()])
	c.on_coach(_coach({"target": 2, "done": 0, "days_left": 1, "reached": false}))
	_check(c.week_label() == "Semaine : 0 séance sur 2" and c.week_detail() == "dernier jour", "dimanche, rien encore")
	c.on_coach(_coach({"target": 2, "done": 3, "days_left": 2, "reached": true}))
	_check(c.week_label() == "Semaine : 3 séances sur 2" and c.week_detail() == "objectif atteint",
		"atteint, écrit en mots")
	c.on_coach(_coach(null))
	_check(c.week_label() == "", "réglage à 0 : pas de ligne")
	var old := _coach(null)
	old.erase("week_goal")
	c.on_coach(old)
	_check(c.week_label() == "", "core plus ancien : pas de ligne")

	var m = MenuModel.new()
	m.set_league_home(true, "manche 3 · 5e")
	m.set_week_home("Semaine : 1 séance sur 2", "il reste 4 jours")
	m.reset()
	var items: Array = m.state()["items"]
	var ids := _ids(items)
	_check(ids.find("week") == ids.find("league") + 1 and ids.find("week") < ids.find("world"),
		"ligne sous la ligue, avant le parcours (%s)" % str(ids))
	var it: Dictionary = items[ids.find("week")]
	_check(it["label"] == "Semaine : 1 séance sur 2" and it["detail"] == "il reste 4 jours", "libellé et détail")
	m.set_week_home("", "")
	_check(not ("week" in _ids(m.state()["items"])), "ligne retirée sans objectif")

	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "IDLE"})
	f.on_coach(_coach({"target": 2, "done": 1, "days_left": 4, "reached": false}))
	f.menu.reset()
	_check("week" in _ids(f.state()["items"]), "menu_flow : ligne posée par le message coach")
	f.menu.focus_item("week")
	var act = f.handle("A_LONG")
	_check(act == {"action": "list_history"} and f.menu.current_screen() == "history",
		"la ligne ouvre l'Historique")
	print("test_week_goal_home : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

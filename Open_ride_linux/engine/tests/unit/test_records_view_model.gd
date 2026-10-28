extends SceneTree

## Tests sans écran de l'écran « Records » (lot T10) : modèle records_view_model.gd (deux tables, fichier
## absent, version inconnue, segment sans record), écrans « Records » de menu_flow.gd depuis l'écran
## Prêt (A court : bascule de table, Y : retour) et texte « oui » / « non » de l'option « Bonus ».
## Lancement : godot --headless --path engine --script res://tests/unit/test_records_view_model.gd

const Model := preload("res://scripts/records_view_model.gd")
const MenuFlow := preload("res://scripts/menu_flow.gd")
const SettingsViewModel := preload("res://scripts/settings_view_model.gd")

const SEGMENTS := [
	{"id": "climb1", "name": "Montée 1", "type": "climb", "category": "4"},
	{"id": "sprint1", "name": "Sprint 1", "type": "sprint", "category": null},
]
const ROUTES := [{"id": "demo", "name": "Démo", "length_m": 5000.0, "is_loop": false, "status": "ready"}]
const TMP_PATH := "user://test_records_t10.json"

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


static func _doc() -> Dictionary:
	return {"version": 1, "routes": {"demo": {"climb1": {
		"no_bonus": [
			{"time_s": 251.5, "date": "2026-10-26 18:00", "avg_power_w": 240.0, "avg_wkg": 3.2},
			{"time_s": 248.07, "date": "2026-10-27 18:05", "avg_power_w": 251.0, "avg_wkg": 3.38}],
		"bonus": [{"time_s": 239.9, "date": "2026-10-27 18:05", "avg_power_w": 251.0, "avg_wkg": null}]}}}}


func _run() -> void:
	_model()
	_flow()
	var it := {"key": "powerups.mode", "type": "choice", "choices": ["on", "off"]}
	_check(SettingsViewModel.format_value(it, "on") == "oui" and SettingsViewModel.format_value(it, "off") == "non", "option « Bonus » : oui / non")
	print("test_records_view_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _model() -> void:
	var m = Model.new()
	m.set_segments(SEGMENTS)
	_check(m.load_file("user://absent_records_t10.json") and m.load_error == "", "fichier absent : aucun temps, sans erreur")
	var items: Array = m.segment_items("demo")
	_check(items.size() == 2 and not items[0]["enabled"] and items[0]["detail"] == "aucun temps",
		"fichier absent : segments listés, désactivés (%s)" % str(items))
	_check(not m.load_text(JSON.stringify({"version": 2, "routes": {}})) and m.load_error == Model.UNREADABLE,
		"version inconnue : « Aucun record lisible »")
	items = m.segment_items("demo")
	_check(items.size() == 1 and items[0]["label"] == "Aucun record lisible" and not items[0]["enabled"],
		"version inconnue : un seul élément désactivé")
	_check(not m.load_text("{pas du json") and m.load_error == Model.UNREADABLE, "fichier illisible : « Aucun record lisible »")
	_check(m.load_text(JSON.stringify(_doc())), "records lus")
	items = m.segment_items("demo")
	_check(items[0]["id"] == "seg:climb1" and items[0]["label"] == "Montée 1 · 4:08,1" and items[0]["enabled"]
		and items[0]["detail"] == "2 temps sans bonus, avec bonus 3:59,9", "montée : meilleur temps (%s)" % str(items[0]))
	_check(items[1]["id"] == "seg:sprint1" and not items[1]["enabled"] and items[1]["detail"] == "aucun temps",
		"segment sans record : désactivé")
	var rows: Array = m.table_items("demo", "climb1", false)
	_check(rows.size() == 3 and rows[0]["id"] == "toggle" and rows[0]["label"] == "A : voir les temps avec bonus",
		"table sans bonus : bascule puis deux temps")
	_check(rows[1]["label"] == "1. 4:08,1 · 27/10/2026 18:05" and rows[1]["detail"] == "251 W, 3,4 W/kg"
		and rows[2]["label"].begins_with("2. 4:11,5"), "temps triés au dixième, date, W et W/kg (%s)" % str(rows[1]))
	rows = m.table_items("demo", "climb1", true)
	_check(rows.size() == 2 and rows[1]["label"] == "1. 3:59,9 · 27/10/2026 18:05" and rows[1]["detail"] == "251 W",
		"table avec bonus séparée, W/kg absent (%s)" % str(rows))
	var sh: Dictionary = m.sheet_segment("demo", "climb1")
	_check(sh["title"] == "Montée · cat. 4" and sh["name"] == "Montée 1", "fiche : montée avec sa catégorie (%s)" % str(sh["title"]))
	_check(sh["tiles"][0]["value"] == "4:08,1" and sh["tiles"][0].get("gold", false), "fiche : record en or")
	_check(sh["tiles"][1]["value"] == "+3,4" and sh["tiles"][1]["unit"] == "s" and sh["tiles"][2]["value"] == "2",
		"fiche : écart au deuxième temps et nombre de temps (%s)" % str(sh["tiles"]))
	_check(sh["lines"] == ["27/10/2026 18:05", "251 W, 3,4 W/kg", "avec bonus : 3:59,9"], "fiche : date, puissance, bonus (%s)" % str(sh["lines"]))
	sh = m.sheet_segment("demo", "sprint1")
	_check(not sh.has("tiles") and sh["lines"] == ["pas encore de temps"] and sh["title"] == "Sprint", "fiche : segment sans temps, sans zéro")
	sh = m.sheet_row("demo", "climb1", false, 1)
	_check(sh["tiles"][0]["value"] == "2" and not sh["tiles"][1].get("gold", false) and sh["tiles"][2]["value"] == "+3,4",
		"fiche d'une ligne : place, temps ordinaire, écart au record (%s)" % str(sh["tiles"]))
	_check(m.sheet_row("demo", "climb1", false, 0)["tiles"][1].get("gold", false) and m.sheet_row("demo", "climb1", false, 0)["tiles"][2]["value"] == "—"
		and m.sheet_row("demo", "climb1", false, 9).is_empty(), "fiche d'une ligne : le record en or, hors table vide")
	rows = m.table_items("demo", "sprint1", true)
	_check(rows.size() == 2 and rows[1]["label"] == "Aucun temps avec bonus" and not rows[1]["enabled"],
		"segment sans record : table vide")
	_check(m.table_title("climb1", true) == "Montée 1 : avec bonus", "titre de la table")
	var none = Model.new()
	_check(none.segment_items("demo")[0]["label"] == "Ce parcours n'a ni sprint ni montée", "parcours sans segment")


func _flow() -> void:
	var f = FileAccess.open(TMP_PATH, FileAccess.WRITE)
	f.store_string(JSON.stringify(_doc()))
	f.close()
	var flow = MenuFlow.new()
	flow.connect_done = true
	flow.records_path = TMP_PATH
	flow.records.set_segments(SEGMENTS)
	flow.on_state({"session_state": "IDLE"})
	flow.set_routes(ROUTES)
	flow.handle("A_LONG")                      # Parcours
	flow.handle("A_LONG")                      # Démo
	flow.on_state({"session_state": "READY", "route_id": "demo"})
	flow.handle("PLUS_SHORT")                  # Rouler
	flow.handle("A_LONG")
	_check(flow.state()["screen"] == "ready", "écran Prêt (%s)" % flow.state()["screen"])
	_check(flow.menu.focus_item("records"), "écran Prêt : entrée « Records du parcours »")
	_check(flow.handle("A_LONG").is_empty() and flow.state()["screen"] == MenuFlow.RECORDS
		and flow.state()["items"][0]["id"] == "seg:climb1", "A long : liste des segments du parcours")
	var rc: Dictionary = flow.card(flow.state())
	_check(rc.get("name", "") == "Montée 1" and rc["tiles"][0]["gold"], "liste des segments : carte du record du segment sous le focus")
	flow.handle("A_LONG")
	_check(flow.state()["screen"] == MenuFlow.RECORD_TABLE and flow.state()["title"] == "Montée 1 : sans bonus",
		"A long sur la montée : table sans bonus (%s)" % flow.state()["title"])
	flow.handle("A_SHORT")
	_check(flow.state()["title"] == "Montée 1 : avec bonus" and flow.state()["items"].size() == 2,
		"A court : table avec bonus")
	flow.handle("A_SHORT")
	_check(flow.state()["title"] == "Montée 1 : sans bonus", "A court : retour à la table sans bonus")
	flow.handle("Y_SHORT")
	_check(flow.state()["screen"] == MenuFlow.RECORDS, "Y : retour à la liste")
	flow.handle("Y_SHORT")
	_check(flow.state()["screen"] == "ready", "Y : retour à l'écran Prêt")
	DirAccess.remove_absolute(ProjectSettings.globalize_path(TMP_PATH))

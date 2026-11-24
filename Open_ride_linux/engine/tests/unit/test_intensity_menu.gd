extends SceneTree

## Tests sans écran de la ligne « Intensité du jour » (lot R1) hors des modes à réglages (Dernier survivant et
## Grand Prix : test_survivor_menu.gd, test_grandprix_menu.gd) : session libre avec un peloton (ligne sous
## « Démarrer », absente sans peloton), vélodrome (dose fixée par l'épreuve, ligne grisée), course conseillée du
## Dernier survivant (dose de la course seulement, pas de `set_setting`).
## Lancement : godot --headless --path engine --script res://tests/unit/test_intensity_menu.gd

const MenuFlow := preload("res://scripts/menu_flow.gd")
const MenuModel := preload("res://scripts/menu_model.gd")

const SETTINGS := {"type": "settings", "v": 1, "items": [
	{"key": "bots.level_pct", "label": "Niveau des bots", "type": "int", "value": 100, "min": 50, "max": 150, "step": 5, "unit": "%", "group": "ride", "applies": "next_session"},
	{"key": "bots.objective", "label": "Objectif des bots", "type": "choice", "value": "endurance", "choices": ["recovery", "endurance", "tempo", "threshold", "max"], "group": "ride", "applies": "next_session"}]}
const TRACK := {"events": {
	"free": {"opponents": [5, [0, 1, 2, 3, 4, 5]]},
	"pursuit": {"opponents": [1, [0, 1]], "distance_m": [4000, [3000, 4000]]}}}

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


func _item(f, id: String) -> Dictionary:
	for it in f.state()["items"]:
		if it["id"] == id:
			return it
	return {}


func _run() -> void:
	# Session libre : pas de peloton, pas de ligne ; un peloton : ligne sous « Démarrer »
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_settings(SETTINGS.duplicate(true))
	f.on_state({"session_state": "IDLE"})
	f.menu.set_world("demo", "Démo")
	f.menu.mode = "free"
	f.menu.open_screen(MenuModel.READY)
	_check(f.wanted_bots_preview().is_empty() and not "intensity" in _ids(f), "session libre sans peloton : pas de ligne")
	f.menu.focus_item("peloton")
	f.handle("A_LONG")
	_check(f.wanted_bots_preview() == {"mode": "ride"}, "peloton de 4 : bots_preview de la session libre")
	_check(_ids(f).slice(0, 2) == ["start", "intensity"] and _item(f, "intensity")["label"] == "Intensité : facile",
		"ligne sous Démarrer, mot du réglage commun (%s)" % str(_ids(f)))
	_check(str(_ids(f)[f.state()["focus"]]) == "peloton", "focus gardé sur le peloton quand la ligne arrive")
	f.on_bots_preview({"type": "bots_preview", "v": 1, "request_cmd_id": 3, "mode": "ride", "objective": "endurance",
		"ftp_pct": 60.0, "power_w": 150, "duration_s": 1500, "elo": null})
	_check(_item(f, "intensity")["label"] == "Intensité : facile" and _item(f, "intensity")["detail"] == "bots ≈ 150 W",
		"watts, sans cote hors des courses à classement (%s)" % str(_item(f, "intensity")))
	f.menu.focus_item("intensity")
	_check(f.handle("A_LONG") == {"action": "set_setting", "key": "bots.objective", "value": "tempo"}, "facile → moyen")

	# Vélodrome : la dose suit l'épreuve (décision du 15/11), ligne grisée
	var t = MenuFlow.new()
	t.connect_done = true
	t.on_settings(SETTINGS.duplicate(true))
	t.on_state({"session_state": "IDLE"})
	t.menu.set_track_events(TRACK)
	t.menu.set_track_ids(["velodrome-250"])
	t.menu.set_world("velodrome-250", "Vélodrome 250 m")
	t.menu.prepare_track()
	t.menu.open_screen(MenuModel.READY)
	_check(not t.wanted_bots_preview().is_empty() and not "intensity" in _ids(t), "vélodrome : demande, ligne à la réponse")
	t.on_bots_preview({"type": "bots_preview", "v": 1, "request_cmd_id": 4, "mode": "track", "objective": "max",
		"ftp_pct": 120.0, "power_w": 300, "duration_s": 280, "elo": {"rating": 1500, "races": 0}})
	var row := _item(t, "intensity")
	_check(row.get("label", "") == "Intensité fixée : dur" and not row["enabled"]
		and row["detail"] == "bots ≈ 300 W", "épreuve à fond : « dur », grisée (%s)" % str(row))

	# Course conseillée au Dernier survivant : la dose ne vaut que pour cette course
	var c = MenuFlow.new()
	c.connect_done = true
	c.on_settings(SETTINGS.duplicate(true))
	c.on_state({"session_state": "IDLE"})
	c.menu.set_world("demo", "Démo")
	c.menu.prepare_settings_mode("survivor")
	c.menu.coach_objective = "threshold"
	_check(c.wanted_bots_preview() == {"mode": "survivor", "objective": "threshold"}, "objectif du besoin du jour envoyé")
	_check(_item(c, "intensity")["label"] == "Intensité : seuil", "seuil affiché tel quel")
	c.menu.focus_item("intensity")
	_check(c.handle("A_LONG").is_empty() and c.menu.coach_objective == "max"
		and c.settings.item("bots.objective")["value"] == "endurance", "seuil → dur pour cette course, réglage commun intact")
	_check(c.wanted_bots_preview() == {"mode": "survivor", "objective": "max"}, "nouvelle demande avec la dose choisie")

	print("test_intensity_menu : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

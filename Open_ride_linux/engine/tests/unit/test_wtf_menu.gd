extends SceneTree

## Tests sans écran des menus du mode « What the fuck » (série WTF, lot WTF3) : entrée de l'accueil selon
## `modes`, écran des treize règles, bascule d'une règle (set_wtf_rules), « Tout allumer », réponse
## `wtf_rules` du core, lancement (écran Prêt sans entraînement ERG, `start` avec `mode` « wtf »).
## Lancement : godot --headless --path engine --script res://tests/unit/test_wtf_menu.gd

const MenuFlow := preload("res://scripts/menu_flow.gd")
const WtfRulesModel := preload("res://scripts/wtf/wtf_rules_model.gd")

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


func _rules_msg(off: Array) -> Dictionary:
	var rules: Array = []
	for r in WtfRulesModel.DEFAULT_RULES:
		rules.append({"id": r[0], "label": r[1], "family": "event", "pitch": "…", "on": not r[0] in off})
	return {"type": "wtf_rules", "v": 1, "rules": rules}


func _run() -> void:
	_model()
	var old = MenuFlow.new()
	old.connect_done = true
	old.menu.set_modes(["ride", "erg"])
	old.on_state({"session_state": "IDLE"})
	_check(not "wtf" in _ids(old), "core sans « wtf » dans modes : pas d'entrée")

	var f = MenuFlow.new()
	f.connect_done = true
	f.menu.set_modes(["ride", "erg", "wtf"])
	f.on_state({"session_state": "IDLE"})
	_check("wtf" in _ids(f), "modes avec « wtf » : entrée Mode WTF")
	_check(f.menu.focus_item("wtf"), "entrée active")
	var act: Dictionary = f.handle("A_LONG")
	_check(act.get("action", "") == "list_wtf_rules", "ouverture : liste des règles demandée au core")
	_check(f.state()["screen"] == WtfRulesModel.SCREEN, "écran des règles")
	_check(_ids(f).size() == 15, "13 règles, Tout allumer et Lancer")
	_check(str(f.state()["title"]).begins_with("Mode WTF : 13 règles sur 13"), "titre : nombre de règles actives")

	f.on_wtf_rules(_rules_msg(["camera", "storm"]))
	_check(str(f.state()["title"]).begins_with("Mode WTF : 11 règles sur 13"), "réponse du core : deux règles coupées")
	f.menu.focus_item("rule:camera")
	act = f.handle("A_LONG")
	_check(act.get("action", "") == "set_wtf_rules" and act["list"] == [{"id": "camera", "on": true}],
		"règle coupée validée : rallumée")
	_check(str(f.state()["items"][f.state()["focus"]]["label"]).ends_with(": oui"), "libellé mis à jour tout de suite")
	f.menu.focus_item(WtfRulesModel.ALL_ON_ID)
	act = f.handle("A_LONG")
	_check(act.get("action", "") == "set_wtf_rules" and act["list"] == [{"id": "storm", "on": true}],
		"Tout allumer : seulement les règles coupées")

	f.menu.focus_item(WtfRulesModel.LAUNCH_ID)
	act = f.handle("A_LONG")
	_check(act == {"action": "select_workout", "workout_id": null}, "Lancer : séance sans entraînement")
	_check(f.state()["screen"] == "routes", "sans parcours choisi : la liste des parcours d'abord")
	f.menu.set_world("demo", "Démo")
	f.menu.prepare_wtf()
	_check(f.state()["screen"] == "ready", "parcours connu : écran Prêt")
	_check(str(f.state()["title"]).begins_with("Prêt : mode WTF"), "titre du mode WTF")
	_check(not "workout" in _ids(f), "pas de passage en ERG depuis l'écran Prêt du mode WTF")
	_check("wtf_rules" in _ids(f), "Changer les règles")
	f.menu.focus_item("start")
	act = f.handle("A_LONG")
	_check(act.get("action", "") == "start" and act.get("args", {}).get("mode", "") == "wtf", "start avec mode « wtf »")
	f.menu.focus_item("wtf_rules")
	act = f.handle("A_LONG")
	_check(act.get("action", "") == "list_wtf_rules" and f.state()["screen"] == WtfRulesModel.SCREEN,
		"Changer les règles rouvre l'écran des règles")
	f.menu.reset()
	_check(f.menu.mode == "free", "retour à l'accueil : le mode WTF ne reste pas collé")
	print("%d vérifications, %d échec(s)" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _model() -> void:
	var m = WtfRulesModel.new()
	_check(m.active_count() == 13 and not m.received, "avant la réponse du core : 13 règles allumées")
	m.on_rules({"rules": "pas une liste"})
	_check(m.rules.size() == 13 and not m.received, "message mal formé ignoré")
	m.on_rules({"rules": []})
	_check(m.rules.size() == 13, "liste vide ignorée")
	_check(m.handle("inconnu").is_empty() and m.handle("rule:inconnue").is_empty(), "élément inconnu : rien")
	_check(m.handle(WtfRulesModel.ALL_ON_ID).is_empty(), "Tout allumer sans règle coupée : rien")
	var it: Array = m.items()
	_check(not it[13]["enabled"], "Tout allumer grisé quand tout est allumé")
	_check(it[14]["detail"].contains("SIM"), "Lancer rappelle que le mode est en SIM")

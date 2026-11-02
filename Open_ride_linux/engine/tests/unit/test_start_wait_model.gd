extends SceneTree

## Tests unitaires sans écran du départ au pédalage côté engine (lot O36, `start_wait_model.gd`, menu masqué
## pendant l'attente dans `menu_flow.gd`, réglage `depart.mode`).
## Vérifie : décor prêt après 10 images rapides sans tuile en attente, pas avant ; une image lente ou une tuile
## en attente remet le compte à zéro ; changement de parcours : décor à refaire ; `scene_ready` envoyé une fois
## par parcours, puis chaque seconde tant que le core attend le décor ; textes du bandeau ; choix du réglage.
## Lancement : godot --headless --path engine --script res://tests/unit/test_start_wait_model.gd

const StartWaitModel := preload("res://scripts/start_wait_model.gd")
const MenuFlow := preload("res://scripts/menu_flow.gd")
const SettingsViewModel := preload("res://scripts/settings_view_model.gd")
const StartScreen := preload("res://scripts/start_screen.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _frames(m, route: String, pending: int, ms: float, n: int) -> bool:
	var became := false
	for i in n:
		became = m.frame(route, pending, ms) or became
	return became


func _test_scene_ready() -> void:
	var m = StartWaitModel.new()
	_check(not _frames(m, "", 0, 10.0, 20) and m.route_id == "", "sans parcours : jamais prêt")
	_check(not _frames(m, "demo", 3, 10.0, 20), "tuiles en attente : pas prêt")
	_check(not _frames(m, "demo", 0, 10.0, 9), "9 images rapides : pas encore")
	_check(not m.frame("demo", 0, 50.0), "une image lente remet le compte à zéro")
	_check(not _frames(m, "demo", 0, 10.0, 9) and m.route_id == "", "9 images après l'image lente : pas encore")
	_check(m.frame("demo", 0, 10.0) and m.route_id == "demo", "10e image rapide : décor prêt")
	_check(not m.frame("demo", 4, 60.0) and m.route_id == "demo", "prêt une fois pour toutes sur ce parcours")
	var slow = StartWaitModel.new()
	_check(not _frames(slow, "demo", 0, 150.0, 13), "machine lente : pas prêt avant SETTLE_S")
	_check(_frames(slow, "demo", 0, 150.0, 1) and slow.route_id == "demo", "machine lente : prêt après SETTLE_S de vue complète")
	_check(m.should_send(0.0, "") and not m.should_send(0.5, ""), "scene_ready envoyé une fois")
	_check(not m.should_send(0.9, "decor") and m.should_send(1.1, "decor"), "renvoyé chaque seconde si le core attend le décor")
	_check(not m.should_send(5.0, "pedalage"), "pas de renvoi après l'étape du décor")
	_check(not m.frame("autre", 0, 10.0) and m.route_id == "", "autre parcours : décor à refaire")
	_frames(m, "autre", 0, 10.0, 10)
	_check(m.route_id == "autre" and m.should_send(6.0, ""), "nouveau parcours prêt : nouvel envoi")


func _test_texts() -> void:
	_check(StartWaitModel.text(null) == "", "hors attente : pas de bandeau")
	_check(StartWaitModel.text({"phase": "decor"}).begins_with("Départ : chargement du décor"), "étape décor")
	_check(StartWaitModel.text({"phase": "trainer"}).begins_with("Départ : connexion du trainer"), "étape trainer")
	var t := StartWaitModel.text({"phase": "pedalage", "cadence_rpm": 30, "hold_s": 3.0, "held_s": 1.2})
	_check(t.begins_with("Pédale pour partir : 30 tr/min, 1,2 s sur 3 s") and t.contains("Y : annuler"), "étape pédalage (%s)" % t)


func _test_lights() -> void:
	_check(StartWaitModel.lights(null) == 0, "hors attente : feux éteints")
	_check(StartWaitModel.lights({"phase": "decor"}) == 1 and StartWaitModel.lights({"phase": "trainer"}) == 2,
		"décor : 1 feu, trainer : 2 feux")
	var w := {"phase": "pedalage", "hold_s": 3.0, "held_s": 0.0}
	_check(StartWaitModel.lights(w) == 3 and StartWaitModel.progress(w) == 0.0, "pédalage commencé : 3 feux")
	w["held_s"] = 1.5
	_check(StartWaitModel.lights(w) == 4 and is_equal_approx(StartWaitModel.progress(w), 0.5), "mi-chemin : 4 feux")
	w["held_s"] = 3.0
	_check(StartWaitModel.lights(w) == 5, "compte atteint : 5 feux")


func _test_screen() -> void:
	var sc = StartScreen.new()
	root.add_child(sc)
	sc.show_wait({"phase": "decor"}, 0.0)
	var info: Dictionary = sc.test_info()
	_check(info["visible"] and info["lights"] == 1 and not info["go"], "écran affiché pendant le chargement (%s)" % str(info))
	sc.show_go()
	_check(sc.test_info()["go"] and sc.visible, "ouverture : feux verts « GO ! »")
	sc._process(StartWaitModel.GO_S + 0.1)
	_check(not sc.visible, "écran caché après GO_S")
	sc.show_wait({"phase": "pedalage", "hold_s": 3.0, "held_s": 1.0}, 55.0)
	sc.show_wait(null, 0.0)
	_check(not sc.visible, "départ annulé : écran caché")
	sc.queue_free()


func _test_menu_hidden() -> void:
	var flow = MenuFlow.new()
	flow.connect_done = true
	flow.on_state({"session_state": "READY", "route_id": "demo"}, -1.0)
	_check(flow.is_visible(), "READY sans attente : menu affiché")
	flow.on_state({"session_state": "READY", "route_id": "demo", "start_wait": {"phase": "pedalage"}}, -1.0)
	_check(not flow.is_visible(), "attente du départ : menu masqué")
	flow.on_state({"session_state": "READY", "route_id": "demo"}, -1.0)
	_check(flow.is_visible(), "départ annulé : menu de retour")


func _test_setting_text() -> void:
	_check(SettingsViewModel.CHOICE_TEXTS["depart.mode"]["pedalage"] == "au pédalage"
		and SettingsViewModel.CHOICE_TEXTS["depart.mode"]["immediat"] == "immédiat", "réglage « Départ » affiché en français")


func _run() -> void:
	_test_scene_ready()
	_test_texts()
	_test_lights()
	_test_screen()
	_test_menu_hidden()
	_test_setting_text()
	print("test_start_wait_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _init() -> void:
	call_deferred("_run")

extends SceneTree

## Tests sans écran de l'ERG d'une session libre (lot O18) : lignes de l'écran de pause (mode SIM / ERG /
## ERG cadence, puissance et cadence cibles, commande set_ride_mode), bandeau ERG et rappel des commandes.
## Lancement : godot --headless --path engine --script res://tests/unit/test_free_erg_menu.gd

const MenuFlow := preload("res://scripts/menu_flow.gd")
const SettingsViewModel := preload("res://scripts/settings_view_model.gd")
const ErgViewModel := preload("res://scripts/erg_view_model.gd")
const ErgView := preload("res://scripts/erg_view.gd")
const HudViewModel := preload("res://scripts/hud_view_model.gd")

const FREE := {"kind": "free", "workout_name": "ERG libre", "block_index": 1, "block_count": 1,
	"block_type": "steady", "block_remaining_s": 0.0, "block_total_s": 0.0, "target_w": 204,
	"next_target_w": null, "bias_pct": 102, "paused": true}
const CADENCE := {"kind": "cadence", "workout_name": "ERG cadence", "block_index": 1, "block_count": 1,
	"block_type": "steady", "block_remaining_s": 0.0, "block_total_s": 0.0, "target_w": 215,
	"next_target_w": null, "bias_pct": 100, "paused": false, "cadence_target_rpm": 90,
	"cadence_low_rpm": 81.0, "cadence_high_rpm": 99.0, "cadence_zone": "high"}
const WORKOUT := {"workout_name": "Seuil", "block_index": 2, "block_count": 5, "block_type": "steady",
	"block_remaining_s": 120.0, "block_total_s": 300.0, "target_w": 250, "next_target_w": 150,
	"bias_pct": 100, "paused": true}

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _ids(f) -> Array:
	return f.state()["items"].map(func(it): return it["id"])


func _row(f, id: String) -> Dictionary:
	for it in f.state()["items"]:
		if it["id"] == id:
			return it
	return {}


func _focus(f, id: String) -> void:
	for i in range(12):
		var st: Dictionary = f.state()
		if st["focus"] >= 0 and str(st["items"][st["focus"]]["id"]) == id:
			return
		f.handle("PLUS_SHORT")


func _paused(erg: Variant, mode := "SIM"):
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "RUNNING", "mode": mode, "erg": erg, "difficulty_pct": 50})
	f.on_state({"session_state": "PAUSED", "mode": mode, "erg": erg, "difficulty_pct": 50})
	return f


func _test_ride_mode_of() -> void:
	_check(MenuFlow.ride_mode_of({"mode": "SIM", "erg": null}) == "sim", "SIM sans objet erg : session libre")
	_check(MenuFlow.ride_mode_of({"mode": "ERG", "erg": FREE}) == "erg", "kind free : ERG")
	_check(MenuFlow.ride_mode_of({"mode": "ERG", "erg": CADENCE}) == "cadence", "kind cadence : ERG cadence")
	_check(MenuFlow.ride_mode_of({"mode": "ERG", "erg": WORKOUT}) == "", "entraînement (kind absent) : pas de bascule")
	_check(MenuFlow.ride_mode_of({"mode": "ROGUE", "erg": null}) == "", "run Cyber-Rogue : pas de bascule")


func _test_pause_rows_and_commands() -> void:
	var f = _paused(null)
	_check(_ids(f) == ["resume", "end_save", "abandon", "difficulty", "ride_mode"],
		"pause d'une session libre : ligne du mode (%s)" % str(_ids(f)))
	_check(_row(f, "ride_mode")["label"] == "Mode" and _row(f, "ride_mode")["detail"] == "SIM", "mode affiché : SIM")
	_focus(f, "ride_mode")
	_check(f.handle("A_LONG").is_empty() and _row(f, "ride_mode")["editing"], "A long : modification en place")
	f.handle("PLUS_SHORT")
	_check(_row(f, "ride_mode")["detail"] == "◀ ERG ▶", "choix suivant : ERG")
	var act: Dictionary = f.handle("A_LONG")
	_check(act == {"action": "set_ride_mode", "args": {"mode": "erg"}}, "A long : set_ride_mode erg (%s)" % str(act))
	f.on_state({"session_state": "PAUSED", "mode": "ERG", "erg": FREE, "difficulty_pct": 50})
	_check(_ids(f) == ["resume", "end_save", "abandon", "difficulty", "ride_mode", "target_w"],
		"ERG : ligne de la puissance cible (%s)" % str(_ids(f)))
	_check(_row(f, "target_w")["detail"] == "204 W" and _row(f, "ride_mode")["detail"] == "ERG",
		"puissance cible affichée (%s)" % _row(f, "target_w")["detail"])
	_focus(f, "target_w")
	f.handle("A_LONG")
	f.handle("PLUS_LONG")   # cinq pas de 5 W
	act = f.handle("A_LONG")
	_check(act == {"action": "set_ride_mode", "args": {"mode": "erg", "target_w": 229}},
		"puissance cible + 25 W (%s)" % str(act))
	_focus(f, "ride_mode")
	f.handle("A_LONG")
	f.handle("PLUS_SHORT")
	act = f.handle("A_LONG")
	_check(act == {"action": "set_ride_mode", "args": {"mode": "cadence"}}, "choix ERG cadence (%s)" % str(act))
	f.on_state({"session_state": "PAUSED", "mode": "ERG", "erg": CADENCE, "difficulty_pct": 50})
	_check(_ids(f).back() == "cadence_rpm" and _row(f, "cadence_rpm")["detail"] == "90 tr/min",
		"ERG cadence : cadence cible (%s)" % str(_ids(f)))
	_focus(f, "cadence_rpm")
	f.handle("A_LONG")
	f.handle("MINUS_SHORT")
	act = f.handle("A_LONG")
	_check(act == {"action": "set_ride_mode", "args": {"mode": "cadence", "cadence_rpm": 89}},
		"cadence cible − 1 (%s)" % str(act))
	_focus(f, "ride_mode")
	f.handle("A_LONG")
	f.handle("PLUS_SHORT")   # cadence → SIM (le choix boucle)
	_check(f.handle("Y_SHORT").is_empty() and _row(f, "ride_mode")["detail"] == "ERG cadence"
		and not _row(f, "ride_mode")["editing"], "Y annule le changement de mode")
	# Entraînement : pas de ligne de mode.
	var g = _paused(WORKOUT, "ERG")
	_check(_ids(g) == ["resume", "end_save", "abandon", "difficulty"], "entraînement : pas de bascule (%s)" % str(_ids(g)))
	_check(SettingsViewModel.pause_item("pause.inconnu", 1).is_empty(), "clé de pause inconnue : rien")


func _test_banner() -> void:
	var vm = ErgViewModel.new()
	var ev: Dictionary = vm.update(FREE, 0.0)
	_check(ev["title"] == "ERG libre" and ev["target_text"] == "204 W (102 %)" and ev["remaining_text"] == ""
		and ev["next_text"] == "" and not ev["beep"], "bandeau ERG libre (%s)" % str(ev))
	var lines: Dictionary = ErgView.banner_lines(FREE, ev)
	_check(lines["title"] == "ERG libre" and lines["next"] == "En pause" and lines["remaining"] == "",
		"lignes du bandeau ERG libre, sans type de bloc (%s)" % str(lines))
	ev = vm.update(CADENCE, 1.0)
	_check(ev["title"] == "ERG cadence 90 tr/min (77–104)" and ev["target_text"] == "215 W"
		and ev["next_text"] == "Trop vite : la puissance monte", "bandeau ERG cadence (%s)" % str(ev))
	var low: Dictionary = CADENCE.duplicate()
	low["cadence_zone"] = "low"
	ev = vm.update(low, 2.0)
	_check(ev["next_text"] == "Trop lent : la puissance baisse", "zone mise à jour d'une trame à l'autre")
	_check(ErgView.is_free(CADENCE) and not ErgView.is_free(WORKOUT), "pas de blocs en session libre")
	var hud: Dictionary = HudViewModel.session_lines({"mode": "ERG", "erg": CADENCE, "power": 210}, ev)
	_check(hud["erg"] == "ERG: ERG cadence 90 tr/min (77–104)  |  Trop lent : la puissance baisse",
		"ligne ERG du HUD sans temps restant (%s)" % hud["erg"])
	_check("cadence cible ± 2 %" in HudViewModel.controls_text(true, "cadence")
		and "Z = bloc suivant" not in HudViewModel.controls_text(true, "free")
		and "Z = bloc suivant" in HudViewModel.controls_text(true), "rappel des commandes selon le mode")


func _init() -> void:
	_test_ride_mode_of()
	_test_pause_rows_and_commands()
	_test_banner()
	print("test_free_erg_menu : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

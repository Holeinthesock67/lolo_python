extends SceneTree

## Tests sans écran du parcours de lancement du Cyber-Rogue dans les menus (lot R13) : entrée de l'accueil
## selon `modes`, écran de départ, avertissement du premier lancement, `start_run`, écran Prêt, erreur de
## composition, pause et bilan de run.
## Lancement : godot --headless --path engine --script res://tests/unit/test_rogue_menu_flow.gd

const MenuFlow := preload("res://scripts/menu_flow.gd")
const SummaryViewModel := preload("res://scripts/summary_view_model.gd")

const CONFIG := {"w_prime_j": 20000.0, "w_prime_estimate_j": 18400.0, "cp_w": 220.0,
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


func _run() -> void:
	var old = MenuFlow.new()
	old.connect_done = true
	old.menu.set_modes(null)
	old.on_state({"session_state": "IDLE"})
	_check(not "rogue" in _ids(old), "hello_ack sans modes : accueil de la 1.0 inchangé")

	var f = MenuFlow.new()
	f.connect_done = true
	f.menu.set_modes(["ride", "erg", "rogue"])
	f.rogue.configure(CONFIG)
	f.on_state({"session_state": "IDLE"})
	_check("rogue" in _ids(f), "modes avec « rogue » : entrée Cyber-Rogue")
	_check(f.menu.focus_item("rogue"), "entrée active")
	f.handle("A_LONG")
	_check(f.state()["screen"] == "rogue_start", "écran de départ")
	_check(_ids(f) == ["objective", "duration", "wprime", "launch"], "objectif, durée, W' et Lancer")
	f.handle("A_LONG")   # objectif suivant
	_check(f.rogue.objective() == "threshold", "A long fait défiler l'objectif")
	f.menu.focus_item("duration")
	f.handle("A_LONG")
	_check(f.rogue.duration_min() == 45, "durée suivante")
	f.menu.focus_item("launch")
	var act: Dictionary = f.handle("A_LONG")
	_check(act.is_empty() and f.state()["screen"] == "confirm", "premier lancement : avertissement avant l'envoi")
	_check(f.state()["items"][f.state()["focus"]]["id"] == "no", "focus sur « Non » par défaut")
	f.handle("PLUS_SHORT")
	act = f.handle("A_LONG")
	_check(act.get("action") == "start_run", "« Oui » envoie start_run")
	_check(act["args"] == {"objective": "threshold", "duration_min": 45, "seed": null, "w_prime_j": null}, "arguments de start_run")
	_check(f.state()["screen"] == "rogue_loading", "écran « Composition de la run… »")
	f.on_state({"session_state": "LOADING"})
	_check(f.state()["screen"] == "rogue_loading", "LOADING : on attend")
	f.on_command_acked("start_run")
	f.on_state({"session_state": "READY", "mode": "ROGUE"})
	_check(f.state()["screen"] == "ready" and f.state()["title"] == "Prêt : Cyber-Rogue", "READY : écran Prêt du Cyber-Rogue")
	_check(_ids(f) == ["start", "rogue_change"], "Démarrer ou changer les choix")
	_check(f.state()["items"][0]["detail"] == "Seuil · 45 min · W' 20,0 kJ (estimé 18,4 kJ)", "rappel des choix")
	act = f.handle("A_LONG")
	_check(act.get("action") == "start", "Démarrer envoie start")
	f.menu.focus_item("rogue_change")
	f.handle("A_LONG")
	_check(f.state()["screen"] == "rogue_start", "Changer les choix : retour au départ")

	# Run recomposée depuis Prêt : le core reste en READY (READY, LOADING, READY dans la même commande)
	f.menu.focus_item("duration")
	f.handle("A_LONG")
	f.menu.focus_item("launch")
	act = f.handle("A_LONG")
	_check(act.get("action") == "start_run" and act["args"]["duration_min"] == 60, "run recomposée : start_run sans avertissement")
	f.on_state({"session_state": "READY", "mode": "ROGUE"})
	_check(f.state()["screen"] == "rogue_loading", "trame READY d'avant l'accusé : on attend encore")
	f.on_command_acked("start_run")
	f.on_state({"session_state": "READY", "mode": "ROGUE"})
	_check(f.state()["screen"] == "ready" and f.state()["items"][0]["detail"].begins_with("Seuil · 60 min"),
		"accusé de start_run : écran Prêt de la nouvelle run")
	f.menu.focus_item("rogue_change")
	f.handle("A_LONG")

	# Deuxième lancement : plus d'avertissement ; erreur de composition
	f.menu.focus_item("launch")
	act = f.handle("A_LONG")
	_check(act.get("action") == "start_run" and f.state()["screen"] == "rogue_loading", "deuxième lancement sans avertissement")
	f.on_error("run_invalid", "objectif inconnu")
	_check(f.state()["screen"] == "rogue_start", "erreur : retour à l'écran de départ")
	_check(f.state()["items"][3]["detail"].begins_with("Échec"), "message d'échec affiché")

	# Pause et abandon
	f.on_state({"session_state": "RUNNING", "mode": "ROGUE"})
	f.on_state({"session_state": "PAUSED", "mode": "ROGUE"})
	_check(f.state()["screen"] == "pause" and f.state()["items"][0]["id"] == "resume", "pause : Reprendre en premier")
	f.menu.focus_item("abandon")
	f.handle("A_LONG")
	_check(f.state()["screen"] == "confirm", "abandon : confirmation")
	f.handle("PLUS_SHORT")
	act = f.handle("A_LONG")
	_check(act == {"action": "end_session", "save": false}, "abandon confirmé : end_session sans enregistrer")

	# Bilan de run
	var sv = SummaryViewModel.new()
	var lines: Array = sv.lines({"duration_s": 1800.0, "rogue": {"result": "victory", "objective": "threshold", "duration_min": 45,
		"seed": 12, "rooms_won": 6, "rooms_fled": 1, "rooms_skipped": 0, "rooms_total": 8, "defeats": 0, "boss": "won",
		"gold": 120, "cards": ["a", "b", "c"], "perfect_shifts": 14, "unlocks": ["grimpeur"]}})
	var labels: Array = lines.map(func(l): return l["label"])
	_check("Résultat" in labels and "Boss" in labels and "Déblocages" in labels, "bilan : lignes du Cyber-Rogue")
	var by_label := {}
	for l in lines:
		by_label[l["label"]] = l["value"]
	_check(by_label["Résultat"] == "Victoire" and by_label["Salles gagnées"] == "6 / 8" and by_label["Boss"] == "vaincu"
		and by_label["Cartes"] == "3" and by_label["Or"] == "120", "bilan : valeurs")
	_check(sv.lines({"duration_s": 60.0}).size() == 1, "bilan sans rogue inchangé")

	print("test_rogue_menu_flow : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

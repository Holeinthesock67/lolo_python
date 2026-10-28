extends SceneTree

## Tests sans écran du menu de départ du Cyber-Rogue (lot R13) : valeurs par défaut, configuration depuis
## hello_ack, défilement des choix, arguments de start_run, avertissement du premier lancement.
## Lancement : godot --headless --path engine --script res://tests/unit/test_rogue_menu_model.gd

const RogueMenu := preload("res://scripts/rogue/rogue_menu_model.gd")

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


func _ids(items: Array) -> Array:
	var out: Array = []
	for it in items:
		out.append(it["id"])
	return out


func _run() -> void:
	var m = RogueMenu.new()
	m.configure(null)
	_check(_ids(m.items()) == ["objective", "duration", "wprime", "launch"], "sans configuration : quatre éléments, pas de châssis")
	_check(m.start_args() == {"objective": "endurance", "duration_min": 30, "seed": null, "w_prime_j": null}, "arguments par défaut")

	m.configure({"w_prime_j": 20000.0, "w_prime_estimate_j": 18400.0, "cp_w": 220.0,
		"objectives": ["endurance", "threshold"], "durations_min": [45, 60],
		"chassis": {"unlocked": ["standard", "grimpeur"], "selected": "standard"}})
	var items: Array = m.items()
	_check(_ids(items) == ["objective", "duration", "wprime", "chassis", "launch"], "avec châssis : cinq éléments")
	_check(items[0]["label"] == "Objectif : Endurance" and items[1]["label"] == "Durée : 45 min", "objectif et durée affichés")
	_check(items[2]["label"] == "W' : 20,0 kJ (estimé 18,4 kJ)" and items[2]["enabled"], "W' avec estimation proposée")
	_check(items[3]["label"] == "Châssis : Standard", "châssis choisi par défaut")
	m.cycle("objective")
	m.cycle("duration")
	m.cycle("wprime")
	m.cycle("chassis")
	_check(m.objective() == "threshold" and m.duration_min() == 60, "objectif et durée défilent")
	_check(m.items()[2]["label"] == "W' : estimé 18,4 kJ", "estimation choisie")
	var args: Dictionary = m.start_args()
	_check(args == {"objective": "threshold", "duration_min": 60, "seed": null, "w_prime_j": 18400.0, "chassis": "grimpeur"}, "start_run : arguments choisis")
	m.cycle("objective")
	_check(m.objective() == "endurance", "défilement circulaire")
	_check(m.ready_text() == "Endurance · 60 min · W' estimé 18,4 kJ · Grimpeur", "texte de l'écran Prêt")

	m.configure({"w_prime_j": 20000.0, "w_prime_estimate_j": null, "cp_w": 220.0, "objectives": ["vo2max"], "durations_min": [30]})
	_check(not m.use_estimate and not m.items()[0]["enabled"] and not m.items()[2]["enabled"], "un seul choix ou pas d'estimation : éléments inactifs")
	_check(m.start_args()["w_prime_j"] == null and not m.start_args().has("chassis"), "sans estimation ni châssis")

	_check(m.needs_warning(), "avertissement au premier lancement")
	m.mark_warned()
	_check(not m.needs_warning(), "une seule fois")

	print("test_rogue_menu_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

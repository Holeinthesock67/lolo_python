extends SceneTree

## Tests sans écran du sous-menu ERG (Lot N16) : paramètres d'intervalles `workout_builder.gd`
## (bornes, libellés, nom et identifiant ; le fichier .zwo est écrit par le core, décision D4).
## Lancement : godot --headless --path engine --script res://tests/unit/test_workout_builder.gd

const WorkoutBuilder := preload("res://scripts/workout_builder.gd")

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
	_test_builder()
	print("test_workout_builder : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)


func _test_builder() -> void:
	var b = WorkoutBuilder.new()
	_check(b.duration_s() == 10 * 60 + 5 * (240 + 180) + 10 * 60, "durée par défaut : 10 + 5 × 7 + 10 min")
	_check(b.workout_name() == "Intervalles 5 × 4 min à 105 %", "nom : " + b.workout_name())
	_check(b.workout_id() == "intervalles_5x240s_105", "identifiant : " + b.workout_id())
	var items: Array = b.menu_items()
	_check(items.size() == 8 and items[-1]["id"] == "save", "sept paramètres puis « Enregistrer et choisir »")
	_check(items[0]["label"] == "Échauffement" and items[0]["detail"] == "10 min", "libellé : %s — %s" % [items[0]["label"], items[0]["detail"]])
	_check(items[3]["label"] == "Puissance de l'effort" and items[3]["detail"] == "105 % de la FTP",
		"libellé : %s — %s" % [items[3]["label"], items[3]["detail"]])
	_check(str(items[-1]["detail"]).ends_with("55 min"), "détail : " + str(items[-1]["detail"]))
	_check(WorkoutBuilder.format_duration(270) == "4 min 30 s" and WorkoutBuilder.format_duration(45) == "45 s",
		"durées lisibles")
	# Bornes.
	_check(b.set_value("reps", 99) and b.values["reps"] == 20, "répétitions bornées à 20")
	_check(b.set_value("on_pct", 10) and b.values["on_pct"] == 50, "puissance bornée à 50 %")
	_check(not b.set_value("inconnu", 3), "clé inconnue refusée")
	b.reset()
	# Paramètre pour l'écran de modification (clé préfixée, format gardé).
	var e: Dictionary = b.edit_item("on_s")
	_check(e["key"] == "workout.on_s" and e["step"] == 15 and e["format"] == "s", "paramètre à modifier : workout.on_s")

extends SceneTree

## Tests unitaires sans écran des consignes d'essai (cue_model.gd).
## Lancement : godot --headless --path engine --script res://tests/unit/test_cue_model.gd

const CueModel := preload("res://scripts/cue_model.gd")

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
	var nodes_before := Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
	var m = CueModel.new()

	var text := JSON.stringify({"cues": [
		{"at_m": 3500, "text": "Bosses : un braquet à chaque sommet", "duration_s": 25},
		{"at_m": 0, "text": "Échauffement", "beep": false},
		{"at_m": 6000, "text": "   "},
		{"text": "sans distance"},
		{"at_m": 9500, "text": "Rampe à 10 %", "duration_s": -3},
	]})
	_check(m.from_text(text), "fichier valide lu")
	_check(m.cues.size() == 3, "consignes sans texte ou sans distance ignorées (3 gardées)")
	_check(m.cues[0]["text"] == "Échauffement" and m.cues[2]["at_m"] == 9500.0, "consignes triées par distance")
	_check(m.cues[0]["duration_s"] == 20.0 and m.cues[2]["duration_s"] == 20.0, "durée absente ou négative : 20 s")
	_check(m.cues[0]["beep"] == false and m.cues[1]["beep"] == true, "bip par défaut, désactivable")

	var first: Array = m.update(0.0)
	_check(first.size() == 1 and first[0]["index"] == 1 and first[0]["count"] == 3, "départ : consigne 1/3 donnée")
	_check(m.update(5.0).is_empty(), "même consigne pas répétée")
	_check(absf(m.distance_to_next(1000.0) - 2500.0) < 0.01, "distance jusqu'à la prochaine consigne")
	_check(m.update(3499.0).is_empty(), "avant 3 500 m : rien")
	var second: Array = m.update(3500.5)
	_check(second.size() == 1 and second[0]["text"].begins_with("Bosses"), "à 3 500 m : consigne 2")
	var jump: Array = m.update(20000.0)
	_check(jump.size() == 1 and jump[0]["index"] == 3, "plusieurs consignes franchies d'un coup : seule la dernière")
	_check(m.distance_to_next(20000.0) == -1.0, "plus de consigne : -1")

	var again: Array = m.update(0.0)
	_check(again.size() == 1 and again[0]["index"] == 1, "retour au départ (nouveau départ) : consignes réarmées")
	_check(m.update(30.0).is_empty(), "petit recul ou avance après réarmement : pas de doublon")

	_check(not m.from_text("[1, 2]") and m.load_error != "" and m.cues.is_empty(), "format invalide refusé avec un message")
	_check(not m.from_text("pas du json"), "texte non JSON refusé")
	_check(m.update(100.0).is_empty(), "sans consigne : rien à afficher")
	_check(CueModel.path_for("essai-69").ends_with("OpenRide/Essais/essai-69.consignes.json"), "chemin du fichier de consignes")

	# Consignes au temps de séance et préavis (essais guidés sur le HomeTrainer).
	var timed := JSON.stringify({"cues": [
		{"at_s": 660, "text": "Retire la ceinture 30 s", "prepare": "la ceinture", "warn_s": 60},
		{"at_s": 0, "text": "Échauffement 5 min"},
		{"at_s": 300, "text": "10 appuis sur +", "prepare": "rien", "warn_s": 0},
		{"at_m": 2000, "text": "Bosse", "prepare": "un petit braquet"},
		{"at_s": 30, "at_m": 9999, "text": "les deux : la distance gagne"},
	]})
	_check(m.from_text(timed), "consignes au temps lues")
	_check(m.cues.size() == 5 and m.cues[0]["at_m"] == 2000.0 and m.cues[2]["at_s"] == 0.0,
			"consignes à la distance d'abord, puis au temps, chacune triée")
	_check(m.cues[1]["at_m"] == 9999.0 and not m.cues[1].has("at_s"), "distance et temps : la distance gagne")
	var t0: Array = m.update(0.0, 0.0)
	_check(t0.size() == 1 and t0[0]["text"].begins_with("Échauffement") and not t0[0]["warn"],
			"t = 0 : consigne au temps donnée")
	_check(m.update(10.0, 299.0).is_empty(), "t = 299 s : rien (préavis désactivé par warn_s = 0)")
	_check(m.update(20.0, 300.0).size() == 1, "t = 300 s : consigne au temps")
	var warn: Array = m.update(30.0, 600.0)
	_check(warn.size() == 1 and warn[0]["warn"] and warn[0]["warn_text"] == "Dans 1 min, prépare la ceinture"
			and warn[0]["duration_s"] == CueModel.WARN_DURATION_S, "t = 600 s : préavis d'une minute")
	_check(m.update(40.0, 650.0).is_empty(), "préavis pas répété")
	var main_cue: Array = m.update(50.0, 660.0)
	_check(main_cue.size() == 1 and not main_cue[0]["warn"] and main_cue[0]["index"] == 5,
			"t = 660 s : la consigne elle-même")
	_check(m.update(60.0, 700.0).is_empty(), "après : rien")
	var warn_m: Array = m.update(1500.0, 710.0)
	_check(warn_m.size() == 1 and warn_m[0]["warn"] and warn_m[0]["warn_text"] == "Dans 500 m, prépare un petit braquet",
			"préavis à 500 m d'une consigne à la distance")
	_check(absf(m.distance_to_next(1500.0) - 500.0) < 0.01, "distance jusqu'à la consigne, préavis exclus")
	_check(m.update(1600.0).size() == 0, "sans temps (t négatif) : axe du temps ignoré")
	var restart: Array = m.update(0.0, 0.0)
	_check(restart.size() == 1 and restart[0]["text"].begins_with("Échauffement"),
			"t revenu à 0 (nouvelle séance) : consignes au temps réarmées")

	var nodes_after := Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
	_check(nodes_after == nodes_before, "aucun nœud créé")

	print("test_cue_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)

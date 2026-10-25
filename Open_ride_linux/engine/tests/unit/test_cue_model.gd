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

	var nodes_after := Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
	_check(nodes_after == nodes_before, "aucun nœud créé")

	print("test_cue_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)

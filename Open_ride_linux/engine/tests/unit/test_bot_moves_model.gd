extends SceneTree

## Tests sans écran des gestes des bots voisins (lot BA1, essai du 22 novembre en mode Course : « rien n'indique
## quand un bot utilise un boost ») : bot_moves_model.gd (texte en mots, son, début de geste seulement, bots
## loin et fantôme ignorés, attaque avant réponse, pas de rafale, nom gardé d'une trame à l'autre, hors séance).
## Lancement : godot --headless --path engine --script res://tests/unit/test_bot_moves_model.gd

const Model := preload("res://scripts/bot_moves_model.gd")
const EventSounds := preload("res://scripts/event_sounds_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


static func _frame(bots: Array, s := 1000.0, state := "RUNNING") -> Dictionary:
	return {"session_state": state, "mode": "SIM", "s": s, "bots": bots}


func _init() -> void:
	var m = Model.new()
	var climber := {"id": "b1", "name": "Grimpeur", "kind": "constant", "s": 1040.0}
	var rouleur := {"id": "b2", "name": "Rouleur", "kind": "constant", "s": 990.0}
	_check(m.on_state(_frame([climber, rouleur]), 0.0).is_empty(), "aucun geste : rien")
	var att := climber.duplicate()
	att["move"] = "attack"
	var out: Dictionary = m.on_state(_frame([att, rouleur]), 1.0)
	_check(out.get("text", "") == "Grimpeur attaque, 40 m devant" and out.get("jingle", "") == "bot_attack",
		"attaque : texte en mots et son (%s)" % str(out))
	_check(EventSounds.JINGLES.has("bot_attack"), "son bot_attack dans la palette des jingles")
	_check(m.on_state(_frame([att, rouleur]), 10.0).is_empty(), "même attaque à la trame suivante : rien de plus")
	# Réponse et attaque dans la même trame : l'attaque d'abord ; puis pas de rafale (4 s au moins)
	var att2 := rouleur.duplicate()
	att2["move"] = "respond"
	var c2 := climber.duplicate()
	var m2 = Model.new()
	c2["move"] = "attack"
	out = m2.on_state(_frame([att2, c2]), 0.0)
	_check(str(out.get("text", "")).begins_with("Grimpeur attaque"), "attaque avant réponse (%s)" % str(out))
	var spr := {"id": "b3", "name": "Sprinteur", "kind": "constant", "s": 1000.0, "move": "sprint"}
	_check(m2.on_state(_frame([att2, c2, spr]), 2.0).is_empty(), "moins de 4 s après une ligne : pas de rafale")
	spr["id"] = "b4"
	out = m2.on_state(_frame([att2, c2, spr]), 6.0)
	_check(out.get("text", "") == "Sprinteur lance le sprint, à ta hauteur", "sprint à ta hauteur (%s)" % str(out))
	_check(Model.text_of("Rouleur", "respond", -12.0) == "Rouleur suit l'attaque, 12 m derrière", "réponse derrière")
	# Bots loin, fantôme, nom absent (peloton allégé), hors séance
	var m3 = Model.new()
	m3.on_state(_frame([{"id": "b5", "name": "Diesel", "kind": "constant", "s": 1000.0}]), 0.0)
	var far := {"id": "b6", "name": "Loin", "kind": "constant", "s": 2000.0, "move": "attack"}
	var ghost := {"id": "ghost", "kind": "ghost", "s": 1010.0, "move": "attack"}
	_check(m3.on_state(_frame([far, ghost]), 1.0).is_empty(), "bot à plus de 250 m et fantôme : rien")
	out = m3.on_state(_frame([{"id": "b5", "kind": "constant", "s": 1000.0, "move": "attack"}]), 2.0)
	_check(str(out.get("text", "")).begins_with("Diesel attaque"), "nom gardé d'une trame précédente (%s)" % str(out))
	var m4 = Model.new()
	_check(m4.on_state(_frame([att], 1000.0, "PAUSED"), 0.0).is_empty(), "hors séance en cours : rien")
	print("test_bot_moves_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

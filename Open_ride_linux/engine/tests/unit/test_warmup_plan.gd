extends SceneTree

## Tests unitaires sans écran du préchauffage unique (warmup_plan.gd, lot PI2).
## Lancement : godot --headless --path engine --script res://tests/unit/test_warmup_plan.gd

const WarmupPlan := preload("res://scripts/warmup_plan.gd")

var _failures := 0
var _checked := 0
var _calls: Array = []


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _note(what: String) -> void:
	_calls.append(what)


func _init() -> void:
	var plan = WarmupPlan.new()
	_check(plan.pending() == 0 and plan.step() == "", "plan vide : rien à jouer")

	plan.start([["portiques", _note.bind("p")], ["spectateurs", _note.bind("s")], ["forets", _note.bind("f")]])
	_check(plan.pending() == 3 and _calls.is_empty(), "start ne joue rien : 3 étapes en attente")
	_check(plan.step() == "portiques" and _calls == ["p"] and plan.pending() == 2, "une étape par image, dans l'ordre")
	plan.add("wtf", _note.bind("w"))
	_check(plan.pending() == 3, "étape ajoutée en fin de plan (mode choisi après le chargement)")
	plan.step()
	plan.step()
	_check(plan.step() == "wtf" and _calls == ["p", "s", "f", "w"], "l'étape ajoutée passe en dernier")
	_check(plan.pending() == 0 and plan.step() == "", "plan fini : le départ n'attend plus")
	_check(plan.summary().begins_with("portiques ") and plan.done.size() == 4, "résumé : une entrée par étape jouée")

	# Nouveau parcours : les étapes non jouées de l'ancien plan sont abandonnées.
	_calls.clear()
	plan.start([["a", _note.bind("a")], ["b", _note.bind("b")]])
	plan.step()
	plan.start([["c", _note.bind("c")]])
	_check(plan.done.is_empty() and plan.pending() == 1, "nouveau plan : ancien abandonné, résumé vidé")
	plan.step()
	_check(_calls == ["a", "c"], "l'étape « b » de l'ancien plan n'est pas jouée")

	# Nœud libéré entre-temps : son étape est sautée sans erreur, la suivante joue dans la même image.
	var gone := Node.new()
	plan.start([["libéré", Callable(gone, "queue_free")], ["suite", _note.bind("x")]])
	gone.free()
	_check(plan.step() == "suite" and plan.pending() == 0, "étape d'un nœud libéré sautée")

	print("test_warmup_plan : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

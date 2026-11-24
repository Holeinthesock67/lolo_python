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

	# Lot AC4 : étape d'attente, rejouée à chaque image tant que ce qu'elle attend n'est pas prêt.
	_calls.clear()
	var tries := [0]
	plan.start([["demande", _note.bind("d")]])
	plan.add_wait("attente", func() -> bool:
		tries[0] += 1
		return tries[0] >= 3)
	plan.add("suite", _note.bind("s"))
	_check(plan.step() == "demande" and plan.pending() == 2, "attente : l'étape avant elle joue d'abord")
	_check(plan.step() == "attente" and plan.pending() == 2 and plan.step() == "attente" and plan.pending() == 2,
		"pas encore prêt : l'étape d'attente reste en tête, une fois par image")
	_check(plan.step() == "attente" and plan.pending() == 1 and _calls == ["d"], "prêt à la 3e image : l'attente est finie")
	_check(plan.step() == "suite" and plan.pending() == 0 and _calls == ["d", "s"], "l'étape suivante joue ensuite")
	_check(plan.done.size() == 3, "résumé : l'attente compte une fois")
	plan.start([["normale", func() -> bool: return false]])
	_check(plan.step() == "normale" and plan.pending() == 0, "une étape normale qui renvoie faux n'est pas rejouée")

	# Lot AC5 : pas d'étape dans une image qui a déjà beaucoup travaillé (menu affiché), sans jamais bloquer le plan.
	plan.start([["x", _note.bind("x")]])
	_check(plan.may_step(0.0), "image légère : l'étape peut jouer")
	var skipped := 0
	while not plan.may_step(plan.BUSY_MS + 30.0):
		skipped += 1
		if skipped > 100:
			break
	_check(skipped == plan.MAX_SKIPS, "image chargée : étape remise au plus %d images de suite (%d)" % [plan.MAX_SKIPS, skipped])
	_check(not plan.may_step(plan.BUSY_MS + 30.0) and plan.may_step(1.0), "après une étape jouée, le compte des remises repart")
	plan.start([])
	_check(not plan.may_step(0.0), "plan vide : rien à jouer")
	# Plan du chargement : même règle, étapes notées sous un autre type dans la sonde.
	var load_plan = WarmupPlan.new()
	load_plan.kind = "chargement"
	load_plan.start([["vidage", _note.bind("v")], ["streamer", _note.bind("t")]])
	_check(load_plan.step() == "vidage" and load_plan.pending() == 1 and plan.kind == "préchauffage",
		"plan du chargement : une étape par image, type propre à chaque plan")

	print("test_warmup_plan : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

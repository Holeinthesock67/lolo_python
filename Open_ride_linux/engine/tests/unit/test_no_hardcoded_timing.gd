extends SceneTree

## Tests unitaires sans écran : aucun seuil de temps écrit en dur dans les tests de l'engine (lot X34).
## Un seuil de temps dépend de la machine (PC cible, cloud, CI) : il passe par `PerfBudget.check` avec une
## entrée dans `tests/perf_budgets.json` (lot X2), qui ne fait échouer qu'en mode `OPENRIDE_PERF=strict`.
## Repère, dans chaque `tests/unit/*.gd` et `tests/render/*.gd`, un `_check(` qui compare à un nombre une
## variable de temps (`…_ms`, `ms`, `us`, `usec`, `…_usec`) ou une lecture de `Time.get_ticks_*`.
## Lancement : godot --headless --path engine --script res://tests/unit/test_no_hardcoded_timing.gd

const DIRS := ["res://tests/unit", "res://tests/render"]

var _failures := 0
var _checked := 0
var _re := RegEx.new()


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Vrai si la ligne de test compare une durée à un seuil écrit en dur.
func hardcoded(line: String) -> bool:
	return line.contains("_check(") and _re.search(line) != null


func _run() -> void:
	_re.compile("(\\b\\w*_(ms|us|usec)\\b|\\b(ms|us|usec)\\b|get_ticks_\\w+\\(\\)[^,]*?)\\s*[<>]=?\\s*[0-9]")
	# Le repérage lui-même, sur des lignes fabriquées.
	_check(hardcoded("\t_check(per_frame_ms < 0.2, \"coût\")"), "seuil en dur repéré (per_frame_ms < 0.2)")
	_check(hardcoded("\t_check(us < 20.0, \"µs\")"), "seuil en dur repéré (us < 20.0)")
	_check(hardcoded("\t_check((Time.get_ticks_usec() - t1) / 1000.0 < 0.5, \"cache\")"), "seuil en dur repéré (get_ticks)")
	_check(not hardcoded("\t_check(PerfBudget.check(\"wind_evaluate\", per_call_ms), \"evaluate\")"), "PerfBudget.check accepté")
	_check(not hardcoded("\t_check(count < 20, \"nombre d'arbres\")"), "comparaison qui n'est pas un temps acceptée")
	_check(not hardcoded("\tvar ms := (Time.get_ticks_usec() - t0) / 1000.0"), "mesure sans seuil acceptée")
	# Les tests de l'engine.
	var found := []
	var files := 0
	for dir in DIRS:
		for f in DirAccess.get_files_at(dir):
			if not f.ends_with(".gd") or f == "test_no_hardcoded_timing.gd":
				continue
			files += 1
			var lines := FileAccess.get_file_as_string(dir.path_join(f)).split("\n")
			for i in range(lines.size()):
				if hardcoded(lines[i]):
					found.append("%s:%d : %s" % [f, i + 1, lines[i].strip_edges()])
	_check(files > 50, "%d fichiers de test lus" % files)
	_check(found.is_empty(), "aucun seuil de temps en dur (passer par PerfBudget.check et perf_budgets.json)%s"
		% ("" if found.is_empty() else " : " + " | ".join(found)))
	print("test_no_hardcoded_timing : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _init() -> void:
	call_deferred("_run")

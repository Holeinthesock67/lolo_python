extends SceneTree

## Tests unitaires sans écran des budgets de l'engine (perf_budget.gd, lots X2 et X19) : coût par image
## sur une fonction de coût connu, mémoire, budgets lus par machine.
## Lancement : godot --headless --path engine --script res://tests/unit/test_perf_budget.gd

const PerfBudget := preload("res://tests/perf_budget.gd")

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
	var saved_mode := OS.get_environment("OPENRIDE_PERF")
	var saved_ci := OS.get_environment("CI")
	var saved_local := OS.get_environment("OPENRIDE_PERF_BUDGETS")
	OS.set_environment("OPENRIDE_PERF", "report")

	# Coût connu : 1 ms d'attente par image, plus une image sur dix à 3 ms (le p95 doit la voir).
	var st := {"i": 0}
	var cost := PerfBudget.frame_cost(func():
		OS.delay_usec(3000 if st["i"] % 10 == 9 else 1000)
		st["i"] += 1, 40, 5)
	_check(cost["frames"] == 40 and st["i"] == 45, "40 images mesurées après 5 de chauffe (%d appels)" % st["i"])
	_check(cost["median_ms"] >= 1.0 and cost["median_ms"] < 2.5, "médiane d'une image de 1 ms : %.2f ms" % cost["median_ms"])
	_check(cost["p95_ms"] >= 3.0 and cost["p95_ms"] < 6.0, "p95 voit l'image de 3 ms : %.2f ms" % cost["p95_ms"])

	var keep: Array = []
	var kb := PerfBudget.memory_kb(func():
		for i in range(64):
			var b := PackedByteArray()
			b.resize(16384)
			keep.append(b))
	_check(kb >= 0.0, "mémoire statique mesurée sans erreur (%.0f Ko)" % kb)

	# Budgets par machine : PC cible, CI, puis remplacement local.
	OS.set_environment("CI", "")
	OS.set_environment("OPENRIDE_PERF_BUDGETS", "/nonexistent/perf_budgets.json")
	_check(PerfBudget.budget_ms("passersby_frame") == 0.2, "budget du PC cible (%.2f ms)" % PerfBudget.budget_ms("passersby_frame"))
	_check(PerfBudget.budget_kb("sound_synthesis_rogue_memory") == 8192.0, "budget mémoire des sons R18 : 8 Mo")
	_check(PerfBudget.budget_ms("sound_synthesis_rogue") == 300.0, "budget de synthèse des sons R18 : 300 ms")
	_check(is_inf(PerfBudget.budget_ms("inconnu")), "budget inconnu : infini")
	OS.set_environment("CI", "true")
	_check(PerfBudget.budget_ms("passersby_frame") == 0.6, "budget de la CI (%.2f ms)" % PerfBudget.budget_ms("passersby_frame"))
	_check(PerfBudget.budget_kb("sound_synthesis_rogue_memory") == 16384.0, "budget mémoire de la CI : 16 Mo")
	var local := OS.get_cache_dir().path_join("openride_perf_budgets_test.json")
	var f := FileAccess.open(local, FileAccess.WRITE)
	f.store_string(JSON.stringify({"passersby_frame": 0.35}))
	f.close()
	OS.set_environment("OPENRIDE_PERF_BUDGETS", local)
	_check(PerfBudget.budget_ms("passersby_frame") == 0.35, "remplacement par machine (%.2f ms)" % PerfBudget.budget_ms("passersby_frame"))
	DirAccess.remove_absolute(local)

	# Verdicts (sans ligne [PERF], qui fausserait le rapport du passage) : report ne fait jamais
	# échouer, strict fait échouer un dépassement.
	_check(PerfBudget.passes(1e9, 0.2), "report : un dépassement ne fait pas échouer")
	OS.set_environment("OPENRIDE_PERF", "strict")
	_check(not PerfBudget.passes(0.5, 0.2), "strict : 0,5 ms pour 0,2 ms échoue")
	_check(PerfBudget.passes(0.1, 0.2), "strict : 0,1 ms pour 0,2 ms passe")
	_check(PerfBudget.passes(1e9, INF), "strict : sans budget, rien n'échoue")

	OS.set_environment("OPENRIDE_PERF", saved_mode)
	OS.set_environment("CI", saved_ci)
	OS.set_environment("OPENRIDE_PERF_BUDGETS", saved_local)
	print("test_perf_budget : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

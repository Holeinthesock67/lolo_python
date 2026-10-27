extends RefCounted
## Budgets de temps des tests de l'engine (lot X2).
##
## Un test unitaire vérifie le résultat ; le temps est mesuré à part et comparé à un budget
## lu dans `perf_budgets.json`. Le budget dépend de la machine : celui du cahier vaut pour le PC
## cible, `ci_ms` pour les machines partagées de GitHub (variable `CI`), et un fichier
## `~/OpenRide/perf_budgets.json` (ou `OPENRIDE_PERF_BUDGETS`) peut le remplacer sur un PC.
##
## Mode (`OPENRIDE_PERF`) : `report` (défaut) écrit une ligne `[PERF]` et ne fait jamais échouer
## le test ; `strict` fait échouer un dépassement (passage dédié aux performances) ; `off` ne
## mesure qu'une fois.
##
## Exemple :
##   var ms := PerfBudget.measure_ms(func(): placer.place(...))
##   _check(PerfBudget.check("vegetation_tile_max", ms), "…")   # vrai sauf dépassement en strict

const DEFAULTS_PATH := "res://tests/perf_budgets.json"


static func mode() -> String:
	var m := OS.get_environment("OPENRIDE_PERF").strip_edges().to_lower()
	return m if m in ["report", "strict", "off"] else "report"


## Médiane en millisecondes de `runs` appels de `fn`, après `warmup` appels hors mesure.
static func measure_ms(fn: Callable, runs: int = 5, warmup: int = 1) -> float:
	if mode() == "off":
		runs = 1
		warmup = 0
	for i in range(warmup):
		fn.call()
	var samples: Array[float] = []
	for i in range(maxi(runs, 1)):
		var t0 := Time.get_ticks_usec()
		fn.call()
		samples.append((Time.get_ticks_usec() - t0) / 1000.0)
	samples.sort()
	var n := samples.size()
	return samples[n / 2] if n % 2 == 1 else (samples[n / 2 - 1] + samples[n / 2]) / 2.0


static func _read_json(path: String) -> Dictionary:
	if path == "" or not FileAccess.file_exists(path):
		return {}
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed if parsed is Dictionary else {}


## Budget en ms pour `name` sur cette machine (INF si inconnu).
static func budget_ms(name: String) -> float:
	var entry: Dictionary = _read_json(DEFAULTS_PATH).get(name, {})
	var limit := float(entry.get("budget_ms", INF))
	if OS.get_environment("CI") != "" and entry.has("ci_ms"):
		limit = float(entry["ci_ms"])
	var local_path := OS.get_environment("OPENRIDE_PERF_BUDGETS")
	if local_path == "":
		local_path = OS.get_environment("HOME").path_join("OpenRide/perf_budgets.json")
	var local := _read_json(local_path)
	if local.has(name):
		limit = float(local[name])
	return limit


## Écrit la ligne `[PERF]` et rend faux seulement en mode strict quand le budget est dépassé.
static func check(name: String, value_ms: float) -> bool:
	var limit := budget_ms(name)
	var over := value_ms > limit
	print("[PERF] %s : %.2f ms, budget %.2f ms%s" % [name, value_ms, limit, " (DÉPASSÉ)" if over else ""])
	return not (over and mode() == "strict")

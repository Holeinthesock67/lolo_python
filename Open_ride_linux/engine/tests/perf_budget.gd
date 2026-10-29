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
##
## Coût par image (lot X19) : `frame_cost(fn, images, chauffe)` appelle `fn` une fois par image simulée
## (l'état du modèle avance d'un appel à l'autre) et rend la médiane et le p95 ; mémoire :
## `memory_kb(fn)` (mémoire statique avant et après), comparée par `check_memory` à `budget_kb`.

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


## Coût d'une mise à jour par image : `fn` appelée `warmup` fois hors mesure, puis `frames` fois ;
## rend {"median_ms", "p95_ms", "frames"}.
static func frame_cost(fn: Callable, frames: int = 120, warmup: int = 10) -> Dictionary:
	if mode() == "off":
		frames = 1
		warmup = 0
	for i in range(warmup):
		fn.call()
	var samples: Array[float] = []
	for i in range(maxi(frames, 1)):
		var t0 := Time.get_ticks_usec()
		fn.call()
		samples.append((Time.get_ticks_usec() - t0) / 1000.0)
	samples.sort()
	var n := samples.size()
	var med := samples[n / 2] if n % 2 == 1 else (samples[n / 2 - 1] + samples[n / 2]) / 2.0
	return {"median_ms": med, "p95_ms": samples[mini(int(0.95 * n), n - 1)], "frames": n}


## Mémoire statique prise par `fn` (Ko) : différence de `Performance.MEMORY_STATIC` avant et après.
static func memory_kb(fn: Callable) -> float:
	var before := Performance.get_monitor(Performance.MEMORY_STATIC)
	fn.call()
	return (Performance.get_monitor(Performance.MEMORY_STATIC) - before) / 1024.0


static func _read_json(path: String) -> Dictionary:
	if path == "" or not FileAccess.file_exists(path):
		return {}
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed if parsed is Dictionary else {}


## Budget en ms pour `name` sur cette machine (INF si inconnu).
static func budget_ms(name: String) -> float:
	return _budget(name, "budget_ms", "ci_ms")


## Budget de mémoire en Ko pour `name` sur cette machine (INF si inconnu).
static func budget_kb(name: String) -> float:
	return _budget(name, "budget_kb", "ci_kb")


static func _budget(name: String, key: String, ci_key: String) -> float:
	var entry: Dictionary = _read_json(DEFAULTS_PATH).get(name, {})
	var limit := float(entry.get(key, INF))
	if OS.get_environment("CI") != "" and entry.has(ci_key):
		limit = float(entry[ci_key])
	var local_path := OS.get_environment("OPENRIDE_PERF_BUDGETS")
	if local_path == "":
		local_path = OS.get_environment("HOME").path_join("OpenRide/perf_budgets.json")
	var local := _read_json(local_path)
	if local.has(name):
		limit = float(local[name])
	return limit


## Écrit la ligne `[PERF]` et rend faux seulement en mode strict quand le budget est dépassé.
## `unit` : unité de la mesure et du budget (« ms » par défaut ; « % » pour un surcoût relatif, lot X34).
static func check(name: String, value_ms: float, unit: String = "ms") -> bool:
	return _report(name, value_ms, budget_ms(name), unit)


## Même chose pour une mémoire en Ko (`budget_kb`, `ci_kb`).
static func check_memory(name: String, value_kb: float) -> bool:
	return _report(name, value_kb, budget_kb(name), "Ko")


## Verdict d'une mesure face à sa limite : faux seulement en mode strict au-delà de la limite.
static func passes(value: float, limit: float) -> bool:
	return not (value > limit and mode() == "strict")


static func _report(name: String, value: float, limit: float, unit: String) -> bool:
	print("[PERF] %s : %.4f %s, budget %.4f %s%s" % [name, value, unit, limit, unit, " (DÉPASSÉ)" if value > limit else ""])
	return passes(value, limit)

extends RefCounted

## Préchauffage unique du chargement (lot PI2, fil « pire image » du 17 novembre).
##
## Avant ce lot, chaque module préchauffait seul, et le plus souvent tous dans la même image, à la fin du
## chargement du parcours : portiques, spectateurs, passants, cyclistes du décor, forêts lointaines. Le WTF le
## faisait sous l'écran d'attente, et le Grand Prix à sa première trame. Le banc rPI1 (19 novembre) a mesuré
## une image de 14 s à ce moment-là, en low, medium et high.
##
## Ici, une seule voie : `main.gd` met dans le plan toutes les étapes de préchauffage dès que le parcours est
## chargé, donc dans le menu, avant même que le joueur lance la séance. Le plan joue une étape par image :
## chaque compilation de shaders tombe dans sa propre image, et le menu ou l'écran d'attente reste animé entre
## deux. Le départ attend la fin du plan, car `pending()` s'ajoute aux tuiles en attente
## (start_wait_model.gd), et la séance ne part pas avec des shaders encore à compiler.
## Chaque étape est notée dans la sonde (étape « préchauffage » et son nom).
## Pas de class_name : charger par preload("res://scripts/warmup_plan.gd").

const PerfProbe := preload("res://scripts/perf_probe.gd")

## Étapes restantes : [nom, Callable] ; jouées dans l'ordre, une par image.
var _steps: Array = []
## Étapes jouées depuis le dernier `start` : [nom, ms].
var done: Array = []


## Nouveau plan (parcours chargé) : les étapes d'un plan précédent pas encore jouées sont abandonnées.
func start(steps: Array) -> void:
	_steps = steps.duplicate()
	done.clear()


## Étape ajoutée à la fin du plan en cours (mode choisi après le chargement, par exemple).
func add(step_name: String, call: Callable) -> void:
	_steps.append([step_name, call])


## Étapes encore à jouer.
func pending() -> int:
	return _steps.size()


## Une image : joue l'étape suivante. Renvoie son nom, ou "" s'il n'y avait rien à jouer.
func step() -> String:
	while not _steps.is_empty():
		var st: Array = _steps.pop_front()
		var call: Callable = st[1]
		if not call.is_valid():   # nœud libéré entre-temps (parcours changé, mode quitté)
			continue
		var t0 := Time.get_ticks_usec()
		call.call()
		var ms := (Time.get_ticks_usec() - t0) / 1000.0
		PerfProbe.mark("préchauffage", str(st[0]), ms)
		done.append([str(st[0]), ms])
		return str(st[0])
	return ""


## Ligne du journal : « portiques 3, spectateurs 12… » (ms).
func summary() -> String:
	var parts := PackedStringArray()
	for d in done:
		parts.append("%s %.0f" % [d[0], float(d[1])])
	return ", ".join(parts)

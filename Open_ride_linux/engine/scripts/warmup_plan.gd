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

## Étapes restantes : [nom, Callable] ou [nom, Callable, ATTENTE] ; jouées dans l'ordre, une par image.
## Une étape d'attente (lot AC4) appelle son Callable, qui renvoie vrai quand ce qu'elle attend est prêt (travail des
## fils de fond, par exemple) : tant qu'il renvoie faux, elle reste en tête du plan et repasse à l'image suivante,
## sans bloquer le fil principal. Les étapes suivantes attendent leur tour, et le départ la fin du plan.
const ATTENTE := "attente"
## Image déjà chargée (lot AC5) : au-delà de BUSY_MS de travail du fil principal avant l'étape (affichage d'un menu,
## par exemple l'écran de fin d'une run), l'étape attend l'image suivante, une fois au plus (MAX_SKIPS) : l'image
## lente isolée (bilan) est évitée, sans ralentir le plan quand toutes les images sont lentes (Xvfb, low).
const BUSY_MS := 12.0
const MAX_SKIPS := 1
## Type de l'étape notée dans la sonde : « préchauffage », ou « chargement » pour le plan du chargement (lot AC5).
var kind := "préchauffage"
var _skips := 0
var _steps: Array = []
## Étapes jouées depuis le dernier `start` : [nom, ms].
var done: Array = []


## Nouveau plan (parcours chargé) : les étapes d'un plan précédent pas encore jouées sont abandonnées.
func start(steps: Array) -> void:
	_steps = steps.duplicate()
	done.clear()
	_skips = 0


## Étape ajoutée à la fin du plan en cours (mode choisi après le chargement, par exemple).
func add(step_name: String, call: Callable) -> void:
	_steps.append([step_name, call])


## Étape d'attente ajoutée à la fin du plan : `ready` renvoie vrai quand c'est prêt (voir ATTENTE).
func add_wait(step_name: String, ready: Callable) -> void:
	_steps.append([step_name, ready, ATTENTE])


## Une image dont le fil principal a déjà travaillé `busy_ms` : vrai si une étape peut y être jouée (BUSY_MS),
## sinon l'étape est remise à l'image suivante, sauf après MAX_SKIPS remises de suite (le plan avance toujours).
func may_step(busy_ms: float) -> bool:
	if _steps.is_empty():
		return false
	if busy_ms > BUSY_MS and _skips < MAX_SKIPS:
		_skips += 1
		return false
	_skips = 0
	return true


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
		var ready = call.call()
		var ms := (Time.get_ticks_usec() - t0) / 1000.0
		PerfProbe.mark(kind, str(st[0]), ms)
		if st.size() > 2 and str(st[2]) == ATTENTE and not bool(ready):
			_steps.push_front(st)   # pas encore prêt : la même étape à l'image suivante
			return str(st[0])
		done.append([str(st[0]), ms])
		return str(st[0])
	return ""


## Ligne du journal : « portiques 3, spectateurs 12… » (ms).
func summary() -> String:
	var parts := PackedStringArray()
	for d in done:
		parts.append("%s %.0f" % [d[0], float(d[1])])
	return ", ".join(parts)

extends RefCounted

## Détecteur de gel du fil principal (lot GL2, gels du monde ouvert, essai du 22 novembre).
##
## Constat : pendant l'essai de Biarritz en high, l'engine a noté des écarts de 9,1 s, 10,4 s et 9,5 s entre deux
## trames `state`, alors que le core envoyait normalement. Un tel écart ne peut être noté que si `_process` n'a pas
## tourné pendant tout ce temps (sinon le délai d'une seconde du contrat §6 coupe d'abord la liaison) : c'est donc le
## fil principal de l'engine qui était bloqué, et les trames perdues sont celles que le tampon du noyau n'a pas pu
## garder. Le journal ne le montrait pas : `[perf-rendu]` et `[diag] gel de l'engine` lisent le `delta` de Godot,
## borné à 8 pas de physique (133 à 150 ms) quand il prend du retard. Banc rOWpile (medium) : une image de 4 286 ms
## (temps réel) avec un `delta` de 137 ms, un écart de 4 301 ms entre trames et 37 seq sautés à la même seconde.
##
## Ce module tourne dans son propre fil et regarde le battement que le fil principal pose à chaque image (`beat`).
## Sans battement depuis `STALL_MS`, il écrit une ligne `[gel]` avec l'étape en cours (`step`, posée par main.gd
## à chaque grande étape de l'image, par bg_tasks.gd pendant l'attente d'une tâche de fond, et aux signaux du
## rendu), puis une ligne de fin avec la durée du blocage et les étapes vues pendant ce temps. Aucun changement de
## comportement : mesure seule, active en séance réelle comme au banc, sans sonde.
## Pas de class_name : chargé par preload.

const CHECK_MS := 100          # le fil de surveillance regarde le battement 10 fois par seconde
const STALL_MS := 1000         # blocage signalé au-delà d'une seconde sans image (délai du contrat §6)
const REPEAT_MS := 5000        # rappel toutes les 5 s pendant un long blocage

static var _mutex := Mutex.new()
static var _beat_us := 0       # dernier battement du fil principal (Time.get_ticks_usec), 0 : pas encore
static var _step := ""         # étape en cours du fil principal
static var _step_us := 0       # début de cette étape

var _thread: Thread = null
var _stop := false
var stalls := 0                # blocages signalés depuis le lancement
var last_report := ""          # dernière ligne de fin écrite (tests)

# État du blocage en cours, tenu par le fil de surveillance (ou par `check` dans les tests).
var _in_stall := false
var _stall_from_us := 0
var _next_repeat_us := 0
var _seen: Dictionary = {}     # étape -> nombre de relevés pendant le blocage
var _seen_order: Array = []


## Battement du fil principal, au début de chaque image ; l'étape repart de « début d'image ».
static func beat(label: String = "début d'image") -> void:
	var now := Time.get_ticks_usec()
	_mutex.lock()
	_beat_us = now
	_step = label
	_step_us = now
	_mutex.unlock()


## Étape en cours du fil principal ; sans effet depuis un autre fil (tâches de fond). Renvoie l'étape d'avant,
## à reposer avec `step` après une attente (bg_tasks.gd).
static func step(label: String) -> String:
	if OS.get_thread_caller_id() != OS.get_main_thread_id():
		return ""
	var now := Time.get_ticks_usec()
	_mutex.lock()
	var before := _step
	_step = label
	_step_us = now
	_mutex.unlock()
	return before


## Relevé de l'état partagé : [battement, étape, début de l'étape].
static func snapshot() -> Array:
	_mutex.lock()
	var out := [_beat_us, _step, _step_us]
	_mutex.unlock()
	return out


## Remise à zéro de l'état partagé (tests).
static func reset_for_tests() -> void:
	_mutex.lock()
	_beat_us = 0
	_step = ""
	_step_us = 0
	_mutex.unlock()


func start() -> void:
	if _thread != null:
		return
	_stop = false
	_thread = Thread.new()
	_thread.start(_loop)


func stop() -> void:
	if _thread == null:
		return
	_stop = true
	_thread.wait_to_finish()
	_thread = null


func _loop() -> void:
	while not _stop:
		OS.delay_msec(CHECK_MS)
		var line := check(Time.get_ticks_usec())
		if line != "":
			print(line)


## Un relevé : rend la ligne à écrire (début, rappel ou fin d'un blocage) ou "". Appelé par le fil de
## surveillance ; les tests l'appellent directement avec une heure choisie.
func check(now_us: int) -> String:
	var snap := snapshot()
	var beat_us: int = snap[0]
	var label: String = snap[1]
	var step_us: int = snap[2]
	if beat_us == 0:
		return ""
	var silent_ms := (now_us - beat_us) / 1000.0
	if silent_ms >= STALL_MS:
		if not _in_stall or beat_us != _stall_from_us:
			var before := ""
			if _in_stall:   # une image est passée entre deux relevés : le blocage d'avant est fini
				before = _finish(beat_us) + "\n"
			_in_stall = true
			_stall_from_us = beat_us
			_seen = {}
			_seen_order = []
			_next_repeat_us = now_us + REPEAT_MS * 1000
			_note(label)
			return before + "[gel] fil principal bloqué depuis %d ms : étape « %s » (depuis %d ms)" % [
				int(silent_ms), label, int((now_us - step_us) / 1000.0)]
		_note(label)
		if now_us >= _next_repeat_us:
			_next_repeat_us = now_us + REPEAT_MS * 1000
			return "[gel] toujours bloqué depuis %d ms : étape « %s » (depuis %d ms)" % [
				int(silent_ms), label, int((now_us - step_us) / 1000.0)]
		return ""
	if _in_stall:
		return _finish(beat_us)
	return ""


func _note(label: String) -> void:
	if not _seen.has(label):
		_seen[label] = 0
		_seen_order.append(label)
	_seen[label] += 1


## Fin du blocage : durée exacte (du battement d'avant au suivant) et part de chaque étape vue.
func _finish(next_beat_us: int) -> String:
	_in_stall = false
	stalls += 1
	var total := 0
	for k in _seen_order:
		total += int(_seen[k])
	var parts := PackedStringArray()
	for k in _seen_order:
		parts.append("%s %d %%" % [k, roundi(100.0 * int(_seen[k]) / maxi(total, 1))])
	last_report = "[gel] fin du blocage : %d ms sans image ; étapes vues : %s" % [
		int((next_beat_us - _stall_from_us) / 1000.0), ", ".join(parts)]
	return last_report

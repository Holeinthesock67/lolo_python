extends RefCounted

## Jingles des événements du parcours (lot T17, série T) : sommet d'une montée, fin d'un sprint, passage sous
## une arche de bonus, fin de séance ; sans aucun nœud. Pas de class_name : charger par
## preload("res://scripts/event_sounds_model.gd").
##
## Aucun champ IPC nouveau : tout vient de ce que l'engine reçoit déjà (contrat 1.4).
## - `on_segment_result(msg)` : message `segment_result` déjà dédoublonné (segment_hud_model.on_result) ;
##   `kind` « climb » → `jingle_summit` (la fin d'une montée est son sommet), « sprint » →
##   `jingle_sprint` ; avec `pr` vrai, variante `_pr` (dernière note une octave plus haut).
## - `on_state(state)` une fois par trame `state`, rend la liste des jingles à jouer :
##   - `jingle_arch` quand `s` (cumulé) franchit une arche, même règle que `ArchSchedule.crossed` du
##     core (lot T6, positions de segment_markers_model.arch_positions), seulement en `RUNNING` avec le
##     champ `powerup` (arches affichées, lot T8) ; un saut de plus de `MAX_STEP_M` (reprise après
##     coupure, nouvelle séance) ne compte pas ; plusieurs arches dans une trame : un seul jingle ;
##   - `jingle_finish` au passage de `RUNNING` ou `PAUSED` à `FINISHED` (SIM comme ERG).
## - `JINGLES` : notes `[début s, fréquence Hz, durée s, niveau 0 à 1, timbre]`, timbre `tone` (note
##   douce, deux harmoniques) ou `bell` (cloche, partiels inharmoniques amortis). Palette commune aux
##   bruitages du mode Rogue (lot R18) : gamme de do majeur, notes de 523 à 2 093 Hz, au-dessus du vent
##   et de la roue libre. Synthèse : sound_player.gd ; remplaçables par ~/OpenRide/Sounds/<nom>.ogg.

const SegmentMarkersModel := preload("res://scripts/segment_markers_model.gd")

const MAX_STEP_M := 100.0
const C5 := 523.25
const E5 := 659.25
const G5 := 783.99
const C6 := 1046.5
const E6 := 1318.5
const G6 := 1568.0
const C7 := 2093.0

const JINGLES := {
	"jingle_summit": [[0.0, C5, 0.16, 0.55, "tone"], [0.15, E5, 0.16, 0.55, "tone"], [0.30, G5, 0.45, 0.6, "tone"],
		[0.30, C6, 1.2, 0.45, "bell"]],
	"jingle_summit_pr": [[0.0, C5, 0.16, 0.55, "tone"], [0.15, E5, 0.16, 0.55, "tone"], [0.30, G5, 0.16, 0.6, "tone"],
		[0.45, C6, 0.5, 0.6, "tone"], [0.45, C7, 1.2, 0.4, "bell"]],
	"jingle_sprint": [[0.0, G5, 0.09, 0.6, "tone"], [0.10, C6, 0.30, 0.6, "tone"]],
	"jingle_sprint_pr": [[0.0, G5, 0.09, 0.6, "tone"], [0.10, C6, 0.12, 0.6, "tone"], [0.22, C7, 0.35, 0.5, "tone"]],
	"jingle_arch": [[0.0, C6, 0.07, 0.4, "bell"], [0.05, E6, 0.07, 0.4, "bell"], [0.10, G6, 0.07, 0.4, "bell"],
		[0.15, C7, 0.5, 0.4, "bell"]],
	"jingle_finish": [[0.0, G5, 0.14, 0.55, "tone"], [0.15, G5, 0.14, 0.55, "tone"], [0.30, G5, 0.14, 0.55, "tone"],
		[0.45, C6, 0.9, 0.6, "tone"], [0.45, E5, 0.9, 0.35, "tone"], [0.45, C7, 1.4, 0.3, "bell"]],
}

var _arches := PackedFloat64Array()
var _length_m := 0.0
var _loop := false
var _prev_s := NAN
var _prev_session := ""


## Arches du parcours courant : `every_m` (powerups.toml, 0 : aucune), longueur d'un tour, boucle.
func set_route(every_m: float, length_m: float, loop: bool) -> void:
	_arches = SegmentMarkersModel.arch_positions(every_m, length_m)
	_length_m = length_m
	_loop = loop
	_prev_s = NAN


func on_segment_result(msg: Dictionary) -> String:
	var kind := str(msg.get("kind", ""))
	if not kind in ["climb", "sprint"]:
		return ""
	var jingle := "jingle_summit" if kind == "climb" else "jingle_sprint"
	return jingle + "_pr" if bool(msg.get("pr", false)) else jingle


func on_state(state: Dictionary) -> Array:
	var out := []
	var session := str(state.get("session_state", ""))
	var s := float(state.get("s", 0.0))
	if session == "RUNNING" and state.has("powerup") and not is_nan(_prev_s) and s - _prev_s <= MAX_STEP_M \
			and crossed(_prev_s, s) > 0:
		out.append("jingle_arch")
	_prev_s = s if session in ["RUNNING", "PAUSED"] else NAN
	if session == "FINISHED" and _prev_session in ["RUNNING", "PAUSED"]:
		out.append("jingle_finish")
	_prev_session = session
	return out


## Arches franchies entre deux positions cumulées (`s_prev` exclu, `s` inclus), comme le core.
func crossed(s_prev: float, s: float) -> int:
	if s <= s_prev or _arches.is_empty():
		return 0
	var count := 0
	for p in _arches:
		if not _loop:
			count += 1 if s_prev < p and p <= s else 0
		else:
			count += int(floor((s - p) / _length_m) - floor((s_prev - p) / _length_m))
	return count


## Durée d'un jingle en secondes (fin de la dernière note).
static func duration_s(jingle: String) -> float:
	var d := 0.0
	for note in JINGLES.get(jingle, []):
		d = maxf(d, float(note[0]) + float(note[2]))
	return d

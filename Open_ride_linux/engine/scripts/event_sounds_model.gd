extends RefCounted

## Jingles des événements du parcours (lot T17, série T) : sommet d'une montée, fin d'un sprint, passage sous
## une arche de bonus, fin de séance ; depuis le 29/10, départ (début de séance, portique de départ d'un
## sprint ou d'une montée) et ligne d'une boucle ; sans aucun nœud. Pas de class_name : charger par
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
##   - `jingle_finish` au passage de `RUNNING` ou `PAUSED` à `FINISHED` (SIM comme ERG) : l'arrivée du
##     parcours ouvert, la fin d'un entraînement ;
##   - `jingle_start` au passage de `READY` à `RUNNING` (départ du parcours) quand le parcours a ses
##     portiques (pas le monde ouvert), et au franchissement d'un portique de `gates` (positions et jingles
##     de segment_markers_model.gate_jingles : départ d'un sprint ou d'une montée `jingle_start`, ligne d'une
##     boucle `jingle_lap`), mêmes règles que les arches mais sans le champ `powerup` ; jamais en mode Rogue
##     (`mode` ROGUE, ses propres bruitages) ; un seul jingle par trame, l'arche passe après le portique.
## - `JINGLES` : notes `[début s, fréquence Hz, durée s, niveau 0 à 1, timbre]`, timbre `tone` (note
##   douce, deux harmoniques) ou `bell` (cloche, partiels inharmoniques amortis). Palette commune aux
##   bruitages du mode Rogue (lot R18) : gamme de do majeur, notes de 523 à 2 093 Hz, au-dessus du vent
##   et de la roue libre. Timbres ajoutés pour les gags du mode WTF (lot WTF7) : `slide` (glissando de la
##   fréquence de la note jusqu'au 6e champ, en ratio constant : sifflet, « boing », trombone triste) et
##   `noise` (bruit passé au filtre de la fréquence de la note : craquement, éclaboussure, rafale) ; les
##   `wtf_*` sont choisis par wtf/wtf_sound_model.gd. `jingle_elim` et `jingle_winner` (lot DS5) : rendus par survivor_hud_model.gd à chaque
##   message `elimination` nouveau. `track_bell`, `track_gun` et `track_crowd` (lot VD9) : vélodrome. `gp_*` (lot GP7) : choisis par grandprix/gp_sound_model.gd. Synthèse : sound_player.gd ; remplaçables par ~/OpenRide/Sounds/<nom>.ogg.

const SegmentMarkersModel := preload("res://scripts/segment_markers_model.gd")

const MAX_STEP_M := 100.0
const C5 := 523.25
const E5 := 659.25
const G5 := 783.99
const C6 := 1046.5
const E6 := 1318.5
const G6 := 1568.0
const C7 := 2093.0
const D5 := 587.33
const F5 := 698.46
const FS5 := 739.99

const JINGLES := {
	# départ : appel bref et clair, deux notes répétées puis la quinte (plus aigu et plus court que le sprint)
	"jingle_start": [[0.0, C6, 0.06, 0.5, "tone"], [0.09, C6, 0.06, 0.5, "tone"], [0.18, G6, 0.32, 0.55, "tone"],
		[0.18, C6, 0.32, 0.25, "tone"]],
	# ligne d'une boucle : « ding-dong » de deux cloches descendantes (l'arche monte en arpège)
	"jingle_lap": [[0.0, E6, 0.6, 0.45, "bell"], [0.16, C6, 0.8, 0.45, "bell"]],
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
	# Dernier survivant (lot DS5) : élimination, deux notes qui descendent ; victoire, arpège et cloche
	"jingle_elim": [[0.0, G5, 0.14, 0.6, "tone"], [0.16, C5, 0.45, 0.6, "tone"]],
	"jingle_winner": [[0.0, C6, 0.1, 0.55, "tone"], [0.11, E6, 0.1, 0.55, "tone"], [0.22, G6, 0.1, 0.55, "tone"],
		[0.33, C7, 1.2, 0.45, "bell"], [0.33, C6, 0.9, 0.4, "tone"]],
	# Vélodrome (lot VD9) : cloche du dernier tour (coups rapides répétés), pistolet du départ (claquement de
	# bruit), public qui monte au sprint (rumeur de bruit en vagues qui se chevauchent) ; rendus par
	# track/track_hud_model.gd sounds().
	"track_bell": [[0.0, E6, 0.35, 0.55, "bell"], [0.18, E6, 0.35, 0.55, "bell"], [0.36, E6, 0.35, 0.55, "bell"],
		[0.54, E6, 0.35, 0.55, "bell"], [0.72, E6, 0.7, 0.55, "bell"]],
	"track_gun": [[0.0, C7, 0.05, 0.8, "noise"], [0.0, C6, 0.35, 0.6, "noise"], [0.03, C5, 0.6, 0.35, "noise"]],
	"track_crowd": [[0.0, G5, 0.9, 0.35, "noise"], [0.25, C6, 1.0, 0.45, "noise"], [0.55, E6, 1.1, 0.5, "noise"],
		[0.9, C6, 1.2, 0.5, "noise"]],
	# Mode WTF (lot WTF7) : un son par début de gag, puis les à-côtés (craquement d'un œuf, éclaboussure du
	# fromage, cloche du chef, manches des micro-défis), la fin d'un gag (gagné : arpège ; raté : trombone
	# triste) et les règles permanentes (Katamari « pop » et « boing », klaxon de la mamie, poissons).
	"wtf_moon": [[0.0, C5, 0.7, 0.55, "slide", C7], [0.6, C7, 0.8, 0.35, "bell"]],
	"wtf_jupiter": [[0.0, G5, 0.5, 0.6, "slide", C5], [0.48, C5, 0.45, 0.6, "tone"]],
	"wtf_flip": [[0.0, C6, 0.2, 0.55, "slide", C7], [0.2, C7, 0.25, 0.55, "slide", C6]],
	"wtf_collapse": [[0.0, C6, 0.8, 0.5, "noise"], [0.0, G5, 0.8, 0.45, "slide", C5]],
	"wtf_cheese": [[0.0, C5, 0.12, 0.6, "tone"], [0.14, E5, 0.12, 0.6, "tone"], [0.28, C5, 0.12, 0.6, "tone"],
		[0.42, E5, 0.12, 0.6, "tone"], [0.56, G5, 0.6, 0.4, "bell"]],
	"wtf_micro": [[0.0, E6, 0.08, 0.5, "tone"], [0.12, E6, 0.08, 0.5, "tone"], [0.24, C7, 0.22, 0.5, "tone"]],
	"wtf_eggs": [[0.0, E6, 0.3, 0.45, "bell"], [0.1, G6, 0.4, 0.4, "bell"]],
	"wtf_tiny": [[0.0, C7, 0.5, 0.5, "slide", C6], [0.5, C6, 0.3, 0.35, "bell"]],
	"wtf_storm": [[0.0, G5, 1.3, 0.55, "noise"], [0.0, C5, 1.3, 0.35, "slide", G5]],
	"wtf_camera": [[0.0, C7, 0.04, 0.6, "noise"], [0.09, C7, 0.05, 0.6, "noise"], [0.16, G6, 0.2, 0.3, "bell"]],
	"wtf_chef": [[0.0, C6, 0.1, 0.5, "tone"], [0.1, E6, 0.1, 0.5, "tone"], [0.2, G6, 0.1, 0.5, "tone"],
		[0.3, E6, 0.1, 0.5, "tone"], [0.4, C6, 0.25, 0.5, "tone"]],
	"wtf_cloche": [[0.0, G6, 1.0, 0.5, "bell"], [0.12, C7, 1.0, 0.4, "bell"]],
	"wtf_crack": [[0.0, C7, 0.09, 0.7, "noise"], [0.02, G6, 0.12, 0.3, "slide", C6]],
	"wtf_splat": [[0.0, C6, 0.3, 0.6, "noise"], [0.0, C6, 0.3, 0.45, "slide", C5]],
	"wtf_round_ok": [[0.0, G6, 0.1, 0.5, "tone"], [0.11, C7, 0.25, 0.5, "tone"]],
	"wtf_round_fail": [[0.0, E5, 0.12, 0.55, "tone"], [0.14, C5, 0.3, 0.55, "tone"]],
	"wtf_win": [[0.0, C6, 0.09, 0.55, "tone"], [0.1, E6, 0.09, 0.55, "tone"], [0.2, G6, 0.09, 0.55, "tone"],
		[0.3, C7, 0.7, 0.45, "bell"], [0.3, C6, 0.5, 0.35, "tone"]],
	"wtf_fail": [[0.0, G5, 0.28, 0.55, "slide", FS5], [0.3, FS5, 0.28, 0.55, "slide", F5],
		[0.6, F5, 0.7, 0.55, "slide", D5]],
	"wtf_pop": [[0.0, C6, 0.08, 0.5, "slide", C7]],
	"wtf_boing": [[0.0, C5, 0.12, 0.55, "slide", C6], [0.12, C6, 0.3, 0.55, "slide", C5]],
	"wtf_horn": [[0.0, E5, 0.14, 0.5, "tone"], [0.0, G5, 0.14, 0.4, "tone"], [0.2, E5, 0.22, 0.5, "tone"],
		[0.2, G5, 0.22, 0.4, "tone"]],
	"wtf_fish": [[0.0, C6, 0.06, 0.45, "slide", E6], [0.1, E6, 0.06, 0.45, "slide", G6],
		[0.2, G6, 0.08, 0.45, "slide", C7]],
	# Grand Prix des objets (lot GP7, grandprix/gp_sound_model.gd) : roulette du tirage (tics qui montent),
	# lancer (souffle qui monte), glissade (bruit et glissando qui descend), averse (pluie), dring de la
	# sonnette, klaxon de la voiture d'équipe (deux tons, plus grave que celui de la mamie WTF)
	"gp_roulette": [[0.0, C6, 0.04, 0.4, "tone"], [0.15, D5 * 2.0, 0.04, 0.4, "tone"], [0.3, E6, 0.04, 0.4, "tone"],
		[0.45, F5 * 2.0, 0.04, 0.4, "tone"], [0.6, G6, 0.04, 0.4, "tone"], [0.8, G6, 0.04, 0.4, "tone"],
		[1.0, C7, 0.04, 0.4, "tone"], [1.3, C7, 0.04, 0.4, "tone"], [1.7, C7, 0.3, 0.45, "bell"]],
	"gp_lancer": [[0.0, C6, 0.18, 0.5, "noise"], [0.0, G5, 0.18, 0.4, "slide", C7]],
	"gp_glissade": [[0.0, G6, 0.5, 0.45, "noise"], [0.0, C7, 0.5, 0.5, "slide", C6]],
	"gp_averse": [[0.0, C7, 1.4, 0.5, "noise"], [0.0, G6, 1.4, 0.3, "noise"]],
	"gp_sonnette": [[0.0, C7, 0.35, 0.5, "bell"], [0.12, C7, 0.5, 0.5, "bell"]],
	"gp_klaxon": [[0.0, C5, 0.18, 0.5, "tone"], [0.0, E5, 0.18, 0.4, "tone"], [0.26, C5, 0.18, 0.5, "tone"],
		[0.26, E5, 0.18, 0.4, "tone"]],
}

var _arches := PackedFloat64Array()
var _gates: Array = []             # [{s, jingle}] des portiques sonores
var _start_gate := false
var _length_m := 0.0
var _loop := false
var _prev_s := NAN
var _prev_session := ""


## Arches du parcours courant : `every_m` (powerups.toml, 0 : aucune), longueur d'un tour, boucle ; portiques
## sonores `gates` (segment_markers_model.gate_jingles) ; `start_gate` : départ du parcours (faux en monde ouvert).
func set_route(every_m: float, length_m: float, loop: bool, gates: Array = [], start_gate: bool = false) -> void:
	_arches = SegmentMarkersModel.arch_positions(every_m, length_m)
	_gates = gates
	_start_gate = start_gate
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
	var rogue := str(state.get("mode", "")) == "ROGUE"
	var moving := session == "RUNNING" and not is_nan(_prev_s) and s - _prev_s <= MAX_STEP_M
	if session == "RUNNING" and _prev_session == "READY" and _start_gate and not rogue:
		out.append("jingle_start")
	elif moving and not rogue:
		var gate := crossed_gate(_prev_s, s)
		if not gate.is_empty():
			out.append(gate)
	if moving and state.has("powerup") and out.is_empty() and crossed(_prev_s, s) > 0:
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


## Jingle du dernier portique franchi entre deux positions cumulées (`s_prev` exclu, `s` inclus) ; "" sinon.
func crossed_gate(s_prev: float, s: float) -> String:
	var best := ""
	var best_at := -INF
	if s <= s_prev:
		return best
	for g in _gates:
		var p := float(g["s"])
		var at := -INF
		if not _loop:
			if s_prev < p and p <= s:
				at = p
		elif floor((s - p) / _length_m) > floor((s_prev - p) / _length_m):
			at = p + floor((s - p) / _length_m) * _length_m
		if at > best_at:
			best_at = at
			best = str(g["jingle"])
	return best


## Durée d'un jingle en secondes (fin de la dernière note).
static func duration_s(jingle: String) -> float:
	var d := 0.0
	for note in JINGLES.get(jingle, []):
		d = maxf(d, float(note[0]) + float(note[2]))
	return d

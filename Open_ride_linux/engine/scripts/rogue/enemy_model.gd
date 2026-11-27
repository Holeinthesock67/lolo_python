extends RefCounted

## Modèle de pose de l'ennemi du Cyber-Rogue (lot R12), sans affichage : position devant le joueur, état
## (tient, s'enfuit, éteint), phase du boss, drapeaux d'animation par archétype et impacts à jouer.
## enemy_views.gd ne fait que dessiner ce que renvoie pose(). Pas de class_name :
## preload("res://scripts/rogue/enemy_model.gd").
##
## Position : 30 m devant le joueur à pleins PV, 60 m à zéro (l'ennemi recule quand ses PV baissent).
## Fin de salle : `room_fled` et `room_skipped` le font fuir (il s'éloigne à 40 m/s et s'éteint en 2 s),
## `room_won` l'éteint sur place en 0,5 s, avec le dernier archétype vu (la trame de fin n'en porte plus). Le tout
## reste figé jusqu'à la salle suivante (`room_id` change).

const MIN_DIST_M := 30.0
const MAX_DIST_M := 60.0
const APPROACH_MPS := 20.0           # vitesse du déplacement vers la distance voulue
const FLEE_MPS := 40.0
const FLEE_FADE_S := 2.0
const DEATH_FADE_S := 0.5
const CLOAK_GAP_M := 30.0            # Sprinteur invisible quand le Firewall est à moins de 30 m
const LIFT_PER_PCT_M := 0.5
const LIFT_MAX_PCT := 12.0
const LIFT_SMOOTH_PER_S := 2.0
const FLASH_S := 0.1
const SWARM_SIZE := 24
const IMPACT_EVENTS := {"hit": false, "crit": true, "parry": false}
const BOSS_EFFECTS := {1: "locks", 2: "shockwaves", 3: "scarlet"}
const ENEMY_PHASES := ["ROOM", "BOSS"]

var _room_id: int = -1
var _state: String = "hold"          # hold | fleeing | dead
var _distance: float = MIN_DIST_M
var _alpha: float = 1.0
var _lift: float = 0.0
var _last_seq: int = -1
var _pose: Dictionary = {"visible": false}
var _impacts: Array = []
var _seen_events: Array = []
## Dernier archétype vu dans la salle (revue de code E10-09) : la trame qui porte `room_won` ou `room_fled` a déjà
## quitté la salle (`archetype` nul, phase suivante) ; sans lui, l'extinction et la fuite n'étaient jamais vues.
var _last_arch = null


func pose() -> Dictionary:
	return _pose


## Impacts à jouer depuis le dernier appel : {"crit": bool, "flash_s": 0.1}, au plus une fois chacun.
func take_impacts() -> Array:
	var out := _impacts
	_impacts = []
	return out


## `rogue` : objet state.rogue ou null ; `seq` : numéro de la trame (une trame renvoyée ne rejoue pas ses
## événements) ; `grade_pct` : pente sous le joueur ; `effects_ok` : faux quand le préréglage `low` ne tient
## pas son budget d'images (plus de particules ni de flash).
func update(rogue: Variant, seq: int, grade_pct: float, dt: float, effects_ok: bool = true) -> void:
	if typeof(rogue) != TYPE_DICTIONARY:
		_pose = {"visible": false}
		_room_id = -1
		_last_seq = -1
		return
	var arch = rogue.get("archetype", null)
	var rid := int(rogue.get("room_id", -1))
	var hp_max := float(rogue.get("enemy_hp_max", 0.0))
	var hp_frac := 1.0 if hp_max <= 0.0 else clampf(float(rogue.get("enemy_hp", 0.0)) / hp_max, 0.0, 1.0)
	var want := MIN_DIST_M + (MAX_DIST_M - MIN_DIST_M) * (1.0 - hp_frac)
	# Les événements d'une trame sont ceux des pas du core depuis la trame précédente : une fin de salle
	# (`room_won`…) peut arriver dans la trame qui porte déjà la salle suivante (passage d'une phase du boss à
	# l'autre). Elle appartient alors à la salle d'avant et ne touche pas l'ennemi neuf.
	var room_changed := rid != _room_id and _room_id != -1
	if rid != _room_id:
		_room_id = rid
		_state = "hold"
		_alpha = 1.0
		_distance = want
		_last_arch = null
	if arch != null:
		_last_arch = arch
	var fresh := seq < 0 or seq != _last_seq
	_last_seq = seq
	var events: Array = rogue.get("events", []) if fresh else []
	for ev in events:
		var e := String(ev)
		if _state == "hold" and not room_changed and (e == "room_fled" or e == "room_skipped"):
			_state = "fleeing"
		elif _state == "hold" and not room_changed and e == "room_won":
			_state = "dead"
		if effects_ok and IMPACT_EVENTS.has(e):
			_impacts.append({"crit": IMPACT_EVENTS[e], "flash_s": FLASH_S})
	dt = clampf(dt, 0.0, 1.0)

	match _state:
		"hold":
			_distance = move_toward(_distance, want, APPROACH_MPS * dt)
		"fleeing":
			_distance += FLEE_MPS * dt
			_alpha = maxf(_alpha - dt / FLEE_FADE_S, 0.0)
		"dead":
			_alpha = maxf(_alpha - dt / DEATH_FADE_S, 0.0)
	var phase := String(rogue.get("phase", ""))
	var in_fight := phase in ENEMY_PHASES
	var ending := _state != "hold" and _alpha > 0.0     # animation de fin de salle en cours
	var shown := (arch != null and in_fight) or (ending and _last_arch != null)
	if arch == null and ending:
		arch = _last_arch
	var lift_target := clampf(grade_pct, 0.0, LIFT_MAX_PCT) * LIFT_PER_PCT_M
	_lift = lerpf(_lift, lift_target, clampf(dt * LIFT_SMOOTH_PER_S, 0.0, 1.0))

	var boss_phase = rogue.get("boss_phase", null)
	var kinds := {}
	for w in rogue.get("windows", []):
		kinds[String(w.get("kind", ""))] = true
	var hack = rogue.get("hack", null)
	_pose = {
		"visible": shown,
		"archetype": "" if arch == null else String(arch),
		"state": _state,
		"distance_m": _distance,
		"alpha": _alpha,
		"hp_frac": hp_frac,
		"boss_phase": 0 if boss_phase == null else int(boss_phase),
		"boss_effect": BOSS_EFFECTS.get(0 if boss_phase == null else int(boss_phase), ""),
		"lift_m": _lift,
		"charge": kinds.has("tunnel"),                              # Diesel : éclairs de charge
		"prelight": kinds.has("parry_zone"),                        # Puncheur : zone allumée
		# Sprinteur ; en salle seulement : hors salle l'écart nul du core le cachait pendant sa fin (revue E10-09)
		"cloaked": in_fight and float(rogue.get("firewall_gap_m", 1000.0)) < CLOAK_GAP_M,
		"glitch": typeof(hack) == TYPE_DICTIONARY,                  # Saboteur : grésille pendant un piratage
		"scatter": kinds.has("purge"),                              # Saboteur : essaim dispersé
		"swarm": SWARM_SIZE,
		"effects": effects_ok,
	}

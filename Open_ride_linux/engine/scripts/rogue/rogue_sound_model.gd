extends RefCounted

## Modèle sonore du Cyber-Rogue (lot R18), sans nœud : de la trame `state.rogue` et du message `loot`, il tire
## la liste des sons de jeu à jouer (budget de 8 voix, priorités, 60 ms entre deux sons identiques), le volume
## des deux boucles (surchauffe, ronflement du Firewall) et les niveaux des trois couches de musique. Ne dépend
## que des événements du core : testable sans écran. Pas de class_name :
## preload("res://scripts/rogue/rogue_sound_model.gd").
##
## Sons dérivés d'un changement d'état (le core n'envoie pas d'événement dédié) : changement de vitesse,
## bouclier touché (le bouclier baisse), début de piratage, changement de phase du boss, or gagné, porte
## choisie (le couloir se referme), fin de la récupération, bilan. La balise de purge réussie et le coffre
## de fin n'ont pas de signal : leurs sons existent (rogue_sound_synth.gd) mais ne sont pas déclenchés.

const Synth := preload("res://scripts/rogue/rogue_sound_synth.gd")

const MAX_VOICES := 8
const RETRIGGER_S := 0.06
const SLEW_DB_PER_S := 12.0
const SILENCE_DB := -60.0
const HUM_FROM_M := 30.0
const BEAT_GAP_M := 2.0              # battement de l'alarme : contact ou Firewall à moins de 2 m
const HUM_MAX_DB := -6.0
const HUM_MIN_DB := -30.0
const OVERHEAT_DB := -12.0
const MUSIC_FADE_S := 2.0
## Niveau de tout le mode (R18 « doux d'abord ») : avec les bus par défaut, bruitages à −18 dB du plein niveau
## (−12 dB et RogueSfx à 70 %) et musique à −28 dB (RogueMusic à 40 %), tous sous le vent à 60 km/h (lot X51).
const MODE_DB := -12.0

## Événement du core -> son.
const EVENT_SOUNDS := {
	"perfect_shift": "rogue_perfect_shift", "hit": "rogue_hit", "crit": "rogue_crit", "parry": "rogue_parry",
	"parry_miss": "rogue_parry_miss", "room_won": "rogue_room_won", "room_fled": "rogue_room_fled",
	"room_skipped": "rogue_room_skipped", "defeat": "rogue_defeat", "card_taken": "rogue_card_pick",
}
## Priorité des sons (le plus haut garde sa voix à saturation) : défaite > boss > salle > Perfect Shift > parade
## > impact > le reste.
const PRIORITY := {
	"rogue_defeat": 100, "rogue_boss_won": 90, "rogue_boss_phase": 90, "rogue_room_won": 80,
	"rogue_room_fled": 80, "rogue_room_skipped": 80, "rogue_result": 80, "rogue_result_lost": 80,
	"rogue_perfect_shift": 70, "rogue_parry": 60, "rogue_parry_miss": 60, "rogue_crit": 55, "rogue_hit": 50,
}
const DEFAULT_PRIORITY := 10
## Couches de musique par phase : basse partout, pulsation en salle, arpège au boss et à la fin.
const MUSIC_BY_PHASE := {
	"WARMUP": {"bass": 1.0, "pulse": 0.0, "arp": 0.0},
	"ROOM": {"bass": 1.0, "pulse": 1.0, "arp": 0.0},
	"CORRIDOR": {"bass": 1.0, "pulse": 0.0, "arp": 0.0},
	"BOSS": {"bass": 1.0, "pulse": 1.0, "arp": 1.0},
	"RECOVERY": {"bass": 1.0, "pulse": 0.0, "arp": 0.0},
	"COOLDOWN": {"bass": 1.0, "pulse": 0.0, "arp": 0.0},
	"RESULTS": {"bass": 0.0, "pulse": 0.0, "arp": 1.0},
}

var _active: Array = []            # [{sound, priority, end_s}]
var _last_played: Dictionary = {}  # son -> instant du dernier déclenchement
var _plays: Array = []
var _prev: Dictionary = {}         # valeurs de la trame précédente
var _last_seq: int = -1
var _last_time_s: float = NAN
var _loops := {"overheat_db": SILENCE_DB, "hum_db": SILENCE_DB, "beat": false}
var _music := {"bass": 0.0, "pulse": 0.0, "arp": 0.0}
var _corridor_id: int = -1
var _corridor_cards: String = ""
var in_run := false


func reset() -> void:
	_active = []
	_last_played = {}
	_plays = []
	_prev = {}
	_last_seq = -1
	_last_time_s = NAN
	_loops = {"overheat_db": SILENCE_DB, "hum_db": SILENCE_DB, "beat": false}
	_music = {"bass": 0.0, "pulse": 0.0, "arp": 0.0}
	_corridor_id = -1
	_corridor_cards = ""
	in_run = false


## Sons à jouer depuis le dernier appel : liste de noms (déjà filtrés par le budget).
func take_plays() -> Array:
	var out := _plays
	_plays = []
	return out


## Volume des boucles en dB (silence = SILENCE_DB) et battement de l'alarme de contact.
func loops() -> Dictionary:
	return _loops


## Niveau (0 à 1) de chaque couche de musique.
func music() -> Dictionary:
	return _music


func voices(now_s: float) -> int:
	_expire(now_s)
	return _active.size()


## Message `loot` : une relance garde le même couloir avec d'autres cartes.
func on_loot(msg: Dictionary, now_s: float) -> void:
	var cid := int(msg.get("corridor_id", -1))
	var ids := PackedStringArray()
	for c in msg.get("cards", []):
		ids.append(str(c.get("id", "")))
	var key := ",".join(ids)
	if cid == _corridor_id and _corridor_cards != "" and key != _corridor_cards:
		_request("rogue_reroll", now_s)
	_corridor_id = cid
	_corridor_cards = key


## Trame `state` : `rogue` (objet ou null), `gear`, `seq`, `now_s` (secondes). `result` : « victory » ou autre,
## pour le son du bilan.
func update(rogue: Variant, gear: int, seq: int, now_s: float, result: String = "") -> void:
	var dt := 0.0 if not is_finite(_last_time_s) else clampf(now_s - _last_time_s, 0.0, 1.0)
	_last_time_s = now_s
	if typeof(rogue) != TYPE_DICTIONARY:
		if in_run:
			reset()
		_fade(dt, {"overheat": false, "gap": 1000.0}, {})
		return
	in_run = true
	var fresh := seq < 0 or seq != _last_seq
	_last_seq = seq
	var phase := String(rogue.get("phase", ""))
	if fresh:
		for ev in rogue.get("events", []):
			var e := String(ev)
			# Trame de la victoire : le core a déjà quitté la salle (`archetype` nul, phase suivante) ;
			# c'est la phase de la trame précédente qui dit si c'était le boss.
			if e == "room_won" and String(_prev.get("phase", "")) == "BOSS":
				_request("rogue_boss_won", now_s)
			elif EVENT_SOUNDS.has(e):
				_request(EVENT_SOUNDS[e], now_s)
		if _prev.has("gear") and gear != int(_prev["gear"]):
			_request("rogue_shift_tick", now_s)
		if _prev.has("shield") and float(rogue.get("shield", 0.0)) < float(_prev["shield"]) - 0.01:
			_request("rogue_shield_hit", now_s)
		if _prev.has("hack") and not _prev["hack"] and typeof(rogue.get("hack", null)) == TYPE_DICTIONARY:
			_request("rogue_hack", now_s)
		var bp = rogue.get("boss_phase", null)
		if _prev.has("boss_phase") and bp != null and _prev["boss_phase"] != null and int(bp) != int(_prev["boss_phase"]):
			_request("rogue_boss_phase", now_s)
		if _prev.has("gold") and int(rogue.get("gold", 0)) > int(_prev["gold"]):
			_request("rogue_gold", now_s)
		if _prev.has("phase"):
			var before := String(_prev["phase"])
			if before == "CORRIDOR" and phase in ["ROOM", "BOSS"]:
				_request("rogue_door", now_s)
			elif before == "RECOVERY" and phase != "RECOVERY":
				_request("rogue_recovery_end", now_s)
			elif phase == "RESULTS" and before != "RESULTS":
				_request("rogue_result" if result == "victory" else "rogue_result_lost", now_s)
		_prev = {"gear": gear, "shield": float(rogue.get("shield", 0.0)), "hack": typeof(rogue.get("hack", null)) == TYPE_DICTIONARY,
			"boss_phase": rogue.get("boss_phase", null), "gold": int(rogue.get("gold", 0)), "phase": phase}
	var contact := false
	for ev in rogue.get("events", []):
		if String(ev) == "firewall_contact":
			contact = true
	_fade(dt, {"overheat": bool(rogue.get("overheat", false)), "gap": float(rogue.get("firewall_gap_m", 1000.0)),
		"contact": contact}, MUSIC_BY_PHASE.get(phase, MUSIC_BY_PHASE["WARMUP"]))


func _request(sound: String, now_s: float) -> void:
	_expire(now_s)
	if _last_played.has(sound) and now_s - float(_last_played[sound]) < RETRIGGER_S:
		return
	var prio: int = PRIORITY.get(sound, DEFAULT_PRIORITY)
	if _active.size() >= MAX_VOICES:
		var lowest := 0
		for i in _active.size():
			if int(_active[i]["priority"]) < int(_active[lowest]["priority"]):
				lowest = i
		if int(_active[lowest]["priority"]) >= prio:
			return                    # saturation : le nouveau son est le moins prioritaire
		_active.remove_at(lowest)
	_active.append({"sound": sound, "priority": prio, "end_s": now_s + Synth.duration_s(sound)})
	_last_played[sound] = now_s
	_plays.append(sound)


func _expire(now_s: float) -> void:
	_active = _active.filter(func(v): return float(v["end_s"]) > now_s)


func _slew(current: float, target: float, dt: float) -> float:
	return move_toward(current, target, SLEW_DB_PER_S * dt)


## Lisse les boucles à 12 dB/s et les couches de musique sur 2 s.
func _fade(dt: float, flags: Dictionary, layers: Dictionary) -> void:
	var over_target := OVERHEAT_DB if bool(flags.get("overheat", false)) else SILENCE_DB
	var gap := float(flags.get("gap", 1000.0))
	var hum_target := SILENCE_DB
	if gap < HUM_FROM_M:
		hum_target = lerpf(HUM_MAX_DB, HUM_MIN_DB, clampf(gap / HUM_FROM_M, 0.0, 1.0))
	_loops = {"overheat_db": _slew(float(_loops["overheat_db"]), over_target, dt),
		"hum_db": _slew(float(_loops["hum_db"]), hum_target, dt), "beat": bool(flags.get("contact", false)) or gap < BEAT_GAP_M}
	for k in _music.keys():
		_music[k] = move_toward(float(_music[k]), float(layers.get(k, 0.0)), dt / MUSIC_FADE_S)

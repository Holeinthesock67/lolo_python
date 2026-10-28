extends RefCounted

## Modèle du HUD diégétique du Cyber-Rogue (lot R11) : calcule les valeurs à afficher à partir de la trame
## `state` (objet `rogue` compris) et du message `loot`, sans aucun nœud Godot. La vue (rogue_hud_view.gd)
## ne fait que dessiner ce que renvoie values(). Pas de class_name : preload("res://scripts/rogue/rogue_hud_model.gd").
##
## Lissage : les valeurs affichées rejoignent la valeur reçue en 0,3 s, sauf la vitesse engagée (immédiate).
## Trame sans objet `rogue` : modèle vide (active = false), jamais d'erreur.
## Événements : ceux d'une trame ne sont rendus qu'une fois, même si la trame est renvoyée (même `seq`).

const SMOOTH_S := 0.3
const ADRENALINE_MAX := 100.0
const ADRENALINE_Z := 50.0          # seuil de l'attaque Z
const WBAL_LOW_PCT := 25.0          # rouge sous ce seuil
const FIREWALL_DANGER_M := 30.0     # rouge sous ce seuil
const MAX_POWER_PCT := 999.0

# Posture -> jeton de couleur de la charte R17.
const POSTURE_TOKEN := {"ROC": "gold", "FLUIDE": "neutral", "VELOCE": "glitch", "ARRET": "grid"}

var _ftp_w: float = 0.0
var _active: bool = false
var _last_seq: int = -1
var _last_time_s: float = NAN
var _smooth: Dictionary = {}
var _values: Dictionary = {}
var _pending_events: Array = []
var _loot: Dictionary = {}


## FTP du coureur, tirée de hello_ack.config.ftp_w.
func set_ftp(ftp_w: float) -> void:
	_ftp_w = ftp_w if is_finite(ftp_w) and ftp_w > 0.0 else 0.0


## Dernier message `loot` (cartes, portes, coût de relance) ; vide hors couloir.
func set_loot(msg: Dictionary) -> void:
	_loot = msg


func is_active() -> bool:
	return _active


func values() -> Dictionary:
	return _values


## Événements à jouer depuis le dernier appel (chacun une seule fois).
func take_events() -> Array:
	var out := _pending_events
	_pending_events = []
	return out


## Met à jour le modèle avec une trame et l'instant courant (secondes).
func update(state: Dictionary, now_s: float) -> void:
	var rogue = state.get("rogue", null)
	if typeof(rogue) != TYPE_DICTIONARY:
		_active = false
		_values = {}
		_smooth = {}
		_last_seq = -1
		_last_time_s = NAN
		return
	var dt := 0.0
	if is_finite(_last_time_s):
		dt = maxf(now_s - _last_time_s, 0.0)
	_last_time_s = now_s
	var alpha := 1.0 if _smooth.is_empty() else clampf(dt / SMOOTH_S, 0.0, 1.0)
	var seq := int(state.get("seq", -1))
	var fresh := seq < 0 or seq != _last_seq
	_last_seq = seq
	if not _active:
		_pending_events = []
	_active = true
	if fresh:
		for ev in rogue.get("events", []):
			_pending_events.append(String(ev))

	var power_pct := 0.0
	if _ftp_w > 0.0:
		power_pct = clampf(roundf(float(state.get("power_3s", 0.0)) / _ftp_w * 100.0), 0.0, MAX_POWER_PCT)
	var shield_max := float(rogue.get("shield_max", 0.0))
	var shield_frac := 0.0 if shield_max <= 0.0 else clampf(float(rogue.get("shield", 0.0)) / shield_max, 0.0, 1.0)
	var adr_frac := clampf(float(rogue.get("adrenaline", 0.0)) / ADRENALINE_MAX, 0.0, 1.0)
	var w_prime := float(rogue.get("w_prime_j", 0.0))
	var wbal_pct := 0.0 if w_prime <= 0.0 else clampf(float(rogue.get("w_bal_j", 0.0)) / w_prime * 100.0, 0.0, 100.0)
	var enemy_max := float(rogue.get("enemy_hp_max", 0.0))
	var enemy_pct := 0.0 if enemy_max <= 0.0 else clampf(float(rogue.get("enemy_hp", 0.0)) / enemy_max * 100.0, 0.0, 100.0)

	_blend("power_pct", power_pct, alpha)
	_blend("cadence_rpm", maxf(float(state.get("cadence", 0.0)), 0.0), alpha)
	_blend("shield_frac", shield_frac, alpha)
	_blend("adrenaline_frac", adr_frac, alpha)
	_blend("wbal_pct", wbal_pct, alpha)
	_blend("enemy_pct", enemy_pct, alpha)
	_blend("firewall_gap_m", float(rogue.get("firewall_gap_m", 0.0)), alpha)

	var posture := String(rogue.get("posture", "ARRET"))
	var hack = rogue.get("hack", null)
	var phase := String(rogue.get("phase", ""))
	_values = {
		"active": true,
		"phase": phase,
		"gear_text": "%02d" % maxi(int(state.get("gear", 1)), 1),
		"power_pct": _smooth["power_pct"],
		"power_pct_text": "%d %%" % int(roundf(_smooth["power_pct"])),
		"cadence_text": "%d" % int(roundf(_smooth["cadence_rpm"])),
		"posture": posture,
		"posture_token": POSTURE_TOKEN.get(posture, "neutral"),
		"shield_frac": _smooth["shield_frac"],
		"adrenaline_frac": _smooth["adrenaline_frac"],
		"adrenaline_z_mark": ADRENALINE_Z / ADRENALINE_MAX,
		"z_ready": float(rogue.get("adrenaline", 0.0)) >= ADRENALINE_Z,
		"wbal_pct": _smooth["wbal_pct"],
		"wbal_low": _smooth["wbal_pct"] < WBAL_LOW_PCT,
		"enemy_pct": _smooth["enemy_pct"],
		"has_enemy": enemy_max > 0.0,
		"firewall_gap_m": _smooth["firewall_gap_m"],
		"firewall_danger": _smooth["firewall_gap_m"] < FIREWALL_DANGER_M,
		"overheat": bool(rogue.get("overheat", false)),
		"gold": int(rogue.get("gold", 0)),
		"room_text": "%d/%d" % [int(rogue.get("room_index", 1)), int(rogue.get("rooms_total", 1))],
		"corridor": _corridor(phase, rogue),
		"hack": _hack(hack),
	}


func _blend(key: String, target: float, alpha: float) -> void:
	if not is_finite(target):
		target = 0.0
	var cur: float = _smooth.get(key, target)
	_smooth[key] = lerpf(cur, target, alpha)


func _corridor(phase: String, rogue: Dictionary) -> Dictionary:
	if phase != "CORRIDOR" or _loot.is_empty():
		return {}
	var focus = rogue.get("loot_focus", null)
	return {
		"cards": _loot.get("cards", []),
		"doors": _loot.get("doors", []),
		"focus": -1 if focus == null else int(focus),
		"reroll_cost": int(_loot.get("reroll_cost", 0)),
		"can_reroll": int(rogue.get("gold", 0)) >= int(_loot.get("reroll_cost", 0)),
	}


func _hack(hack: Variant) -> Dictionary:
	if typeof(hack) != TYPE_DICTIONARY:
		return {}
	var gear = hack.get("forced_gear", null)
	return {
		"locked": bool(hack.get("locked", false)),
		"forced_gear": -1 if gear == null else int(gear),
		"until_s": float(hack.get("until_s", 0.0)),
	}

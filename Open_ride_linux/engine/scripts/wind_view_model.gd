extends RefCounted

## Modèle de vue de l'indicateur du vent et de l'abri du HUD, sans aucun nœud (Lot P4, Contrat IPC v1
## révision 1.3 §3 : `wind`, `draft`). Pas de class_name : preload("res://scripts/wind_view_model.gd").
## Le dessin vient avec P16 (vent) et P17 (abri).
##
## `view(state, heading_deg, now_s)` rend `{visible, arrow_deg, speed_text, label, verdict, verdict_text,
## tone, level, level_text, draft_text}` :
## - `arrow_deg` : direction d'où vient le vent par rapport au cap de la route, de 0 à 360 (0 = de face,
##   flèche vers le bas ; 90 = de droite ; 180 = de dos ; 270 = de gauche) ;
## - `label` : « face », « dos », « travers gauche », « travers droit » (secteurs de 45° autour de l'axe,
##   hystérésis de `LABEL_HYSTERESIS_DEG`) ;
## - verdict d'après `head_mps` lissé (`HEAD_TAU_S`) : « défavorable » au-dessus de + 1 m/s, « favorable »
##   sous − 1 m/s, « neutre » entre les deux, hystérésis de 0,3 m/s (entrée à 1,15, sortie à 0,85 m/s) ;
## - intensité `level` de 0 à 4 (calme sous 5 km/h, faible 5 à 15, modéré 15 à 25, fort 25 à 40, très
##   fort au-delà), hystérésis de 2 km/h, et un niveau ne change qu'après `LEVEL_DWELL_S` (une rafale
##   isolée de moins d'une seconde ne compte pas) ; `speed_text` est la vitesse lissée sur 2 s ;
## - `draft_text` : « Abri 30 % » (`draft / 0,55` arrondi à 5 %, lot AS4), vide sous 5 % ;
## - `visible` faux sans vent (pas de `wind` depuis 2 s) ni abri.

const WIRE_TIMEOUT_S := 2.0
const SPEED_TAU_S := 2.0
const HEAD_TAU_S := 1.0
const LABEL_HYSTERESIS_DEG := 5.0
const VERDICT_THRESHOLD_MPS := 1.0
const VERDICT_HYSTERESIS_MPS := 0.3
const LEVEL_THRESHOLDS_KMH := [5.0, 15.0, 25.0, 40.0]
const LEVEL_HYSTERESIS_KMH := 2.0
const LEVEL_DWELL_S := 1.0
const LEVEL_TEXTS := ["calme", "faible", "modéré", "fort", "très fort"]
const DRAFT_MAX := 0.55   # plafond de l'abri au cœur d'un groupe (lot AS4, choix du propriétaire du 31 octobre)
const VERDICTS := {
	"favorable": ["Vent favorable", "good"],
	"defavorable": ["Vent défavorable", "bad"],
	"neutre": ["Vent neutre", "neutral"],
}

var _wire_at_s: float = -INF
var _speed_kmh_raw: float = 0.0
var _from_deg: float = 0.0
var _head_raw: float = 0.0

var _last_s: float = NAN
var _speed_kmh: float = 0.0     # lissé
var _head_mps: float = 0.0      # lissé
var _label: String = ""
var _verdict: String = "neutre"
var _level: int = 0
var _level_candidate: int = 0
var _candidate_since_s: float = NAN


static func _is_number(v: Variant) -> bool:
	return (typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT) and is_finite(float(v))


## Angle signé (−180 à 180) d'où vient le vent par rapport au cap ; négatif = vent de gauche.
static func _rel_deg(from_deg: float, heading_deg: float) -> float:
	return fposmod(from_deg - heading_deg + 180.0, 360.0) - 180.0


## Secteur sans hystérésis d'un angle relatif signé (−180 à 180, négatif = vent de gauche).
static func _sector(rel_deg: float) -> String:
	var a := absf(rel_deg)
	if a <= 45.0:
		return "face"
	if a >= 135.0:
		return "dos"
	return "travers gauche" if rel_deg < 0.0 else "travers droit"


## Garde le secteur courant tant que l'angle n'a pas franchi la limite de plus de `LABEL_HYSTERESIS_DEG`.
static func _sector_with_hysteresis(rel_deg: float, current: String) -> String:
	var raw := _sector(rel_deg)
	if current == "" or raw == current:
		return raw
	for shift in [-LABEL_HYSTERESIS_DEG, LABEL_HYSTERESIS_DEG]:
		if _sector(rel_deg + shift) == current:
			return current
	return raw


static func _raw_level(kmh: float) -> int:
	var lvl := 0
	for thr in LEVEL_THRESHOLDS_KMH:
		if kmh >= thr:
			lvl += 1
	return lvl


## Niveau avec hystérésis : on ne quitte `current` qu'à 1 km/h au-delà de ses bornes (bande de 2 km/h).
static func _level_with_hysteresis(kmh: float, current: int) -> int:
	var half := LEVEL_HYSTERESIS_KMH * 0.5
	var lo: float = -INF if current == 0 else LEVEL_THRESHOLDS_KMH[current - 1] - half
	var hi: float = INF if current == LEVEL_THRESHOLDS_KMH.size() else LEVEL_THRESHOLDS_KMH[current] + half
	if kmh >= lo and kmh < hi:
		return current
	return _raw_level(kmh)


func reset() -> void:
	_wire_at_s = -INF
	_last_s = NAN
	_speed_kmh = 0.0
	_head_mps = 0.0
	_label = ""
	_verdict = "neutre"
	_level = 0
	_level_candidate = 0
	_candidate_since_s = NAN


func view(state: Dictionary, heading_deg: float, now_s: float) -> Dictionary:
	var w: Variant = state.get("wind", null)
	if typeof(w) == TYPE_DICTIONARY and _is_number(w.get("speed_mps")) and _is_number(w.get("from_deg")):
		var first := now_s - _wire_at_s > WIRE_TIMEOUT_S
		_wire_at_s = now_s
		_speed_kmh_raw = maxf(float(w["speed_mps"]), 0.0) * 3.6
		_from_deg = float(w["from_deg"])
		_head_raw = float(w.get("head_mps", 0.0)) if _is_number(w.get("head_mps", 0.0)) else 0.0
		if first:   # premier vent reçu : pas de montée progressive depuis zéro
			_speed_kmh = _speed_kmh_raw
			_head_mps = _head_raw
			_level = _raw_level(_speed_kmh_raw)
			_level_candidate = _level
			_last_s = now_s
	var has_wind := now_s - _wire_at_s <= WIRE_TIMEOUT_S

	var dt := 0.0 if is_nan(_last_s) else clampf(now_s - _last_s, 0.0, 1.0)
	_last_s = now_s
	if has_wind:
		_speed_kmh += (_speed_kmh_raw - _speed_kmh) * (1.0 - exp(-dt / SPEED_TAU_S))
		_head_mps += (_head_raw - _head_mps) * (1.0 - exp(-dt / HEAD_TAU_S))
		var candidate := _level_with_hysteresis(_speed_kmh_raw, _level)
		if candidate == _level:
			_candidate_since_s = NAN
		elif candidate != _level_candidate or is_nan(_candidate_since_s):
			_level_candidate = candidate
			_candidate_since_s = now_s
		elif now_s - _candidate_since_s >= LEVEL_DWELL_S:
			_level = candidate
			_candidate_since_s = NAN
	else:
		_speed_kmh = 0.0
		_head_mps = 0.0
		_level = 0
		_label = ""

	var rel := _rel_deg(_from_deg, heading_deg)
	if has_wind:
		_label = _sector_with_hysteresis(rel, _label)
		var enter := VERDICT_THRESHOLD_MPS + VERDICT_HYSTERESIS_MPS * 0.5
		var leave := VERDICT_THRESHOLD_MPS - VERDICT_HYSTERESIS_MPS * 0.5
		match _verdict:
			"defavorable":
				if _head_mps < leave:
					_verdict = "favorable" if _head_mps < -enter else "neutre"
			"favorable":
				if _head_mps > -leave:
					_verdict = "defavorable" if _head_mps > enter else "neutre"
			_:
				if _head_mps > enter:
					_verdict = "defavorable"
				elif _head_mps < -enter:
					_verdict = "favorable"
	else:
		_verdict = "neutre"

	var draft_text := ""
	var d: Variant = state.get("draft", null)
	if _is_number(d):
		var pct := roundi(clampf(float(d) / DRAFT_MAX, 0.0, 1.0) * 20.0) * 5
		if pct >= 5:
			draft_text = "Abri %d %%" % pct

	var v: Array = VERDICTS[_verdict]
	return {
		"visible": has_wind or draft_text != "",
		"arrow_deg": fposmod(rel, 360.0) if has_wind else 0.0,
		"speed_text": ("%d km/h" % roundi(_speed_kmh)) if has_wind else "",
		"label": _label,
		"verdict": _verdict,
		"verdict_text": v[0],
		"tone": v[1],
		"level": _level,
		"level_text": LEVEL_TEXTS[_level],
		"draft_text": draft_text,
	}


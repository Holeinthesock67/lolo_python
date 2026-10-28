extends RefCounted

## Effets de caméra du Cyber-Rogue (lot R11) : champ de vision (75° au repos, jusqu'à 95° pendant un sprint,
## retour en 1 s) et tremblement léger aux impacts et aux Perfect Shifts. Calcul pur, sans nœud : la scène
## applique fov_deg() à la caméra et shake_offset() à sa position. Sans effet hors du mode ROGUE (la caméra
## du mode classique n'utilise pas cette classe). Pas de class_name :
## preload("res://scripts/rogue/rogue_camera_fx.gd").
##
## Sprint : puissance ≥ 1,40 FTP. L'attaque Z n'a pas de drapeau dans la trame state (contrat 1.4) : seul le
## sprint ouvre le champ de vision.

const FOV_REST_DEG := 75.0
const FOV_SPRINT_DEG := 95.0
const FOV_RETURN_S := 1.0            # retour de 95° à 75°
const FOV_OPEN_S := 0.4              # ouverture de 75° à 95°
const SPRINT_FROM_PCT := 140.0
const SHAKE_AMPLITUDE_M := 0.05
const SHAKE_DURATION_S := 0.2
const SHAKE_HZ := 28.0
const SHAKE_EVENTS := ["perfect_shift", "hit", "crit", "parry"]

## Réglage « réduire les mouvements » (O4) : coupe le tremblement et garde le champ de vision au repos.
var reduce_motion := false

var _fov := FOV_REST_DEG
var _shake_left_s := 0.0
var _shake_t := 0.0


func reset() -> void:
	_fov = FOV_REST_DEG
	_shake_left_s = 0.0
	_shake_t = 0.0


## Avance de `dt_s` secondes. `power_pct` : puissance en % de FTP ; `events` : événements à jouer.
func update(dt_s: float, power_pct: float, events: Array) -> void:
	dt_s = clampf(dt_s, 0.0, 1.0)
	var target := FOV_SPRINT_DEG if power_pct >= SPRINT_FROM_PCT and not reduce_motion else FOV_REST_DEG
	var span := FOV_SPRINT_DEG - FOV_REST_DEG
	if target > _fov:
		_fov = minf(_fov + span / FOV_OPEN_S * dt_s, target)
	else:
		_fov = maxf(_fov - span / FOV_RETURN_S * dt_s, target)
	if not reduce_motion:
		for ev in events:
			if ev in SHAKE_EVENTS:
				_shake_left_s = SHAKE_DURATION_S
	else:
		_shake_left_s = 0.0
	_shake_t += dt_s
	_shake_left_s = maxf(_shake_left_s - dt_s, 0.0)


func fov_deg() -> float:
	return _fov


## Décalage de la caméra en mètres (nul hors secousse), amplitude décroissante jusqu'à 0 en 0,2 s.
func shake_offset() -> Vector3:
	if _shake_left_s <= 0.0:
		return Vector3.ZERO
	var k := _shake_left_s / SHAKE_DURATION_S
	var a := SHAKE_AMPLITUDE_M * k
	return Vector3(sin(_shake_t * SHAKE_HZ * TAU) * a, cos(_shake_t * SHAKE_HZ * 1.3 * TAU) * a, 0.0)

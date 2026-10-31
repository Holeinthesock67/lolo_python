extends RefCounted

## Vues de caméra sans affichage (lot V12, spécification générale §7.2, exigences 2.0-CAM-1 à 2.0-CAM-5).
##
## - Quatre vues, dans l'ordre : `subjective` (yeux du cycliste, 1,4 m, avatar masqué, celle de la 1.0), `follow_near`
##   (4 m derrière, 1,8 m de haut, regard 10 m devant), `follow_far` (12 m derrière, 6 m de haut) et `side`
##   (de côté, à 8 m de la route, façon retransmission).
## - `next_view()` et `previous_view()` passent d'une vue à l'autre en boucle, `reset_default()` revient à la vue par
##   défaut (suivi proche). Sans avatar (core sans progression), la vue affichée reste la subjective et les
##   changements de vue ne font rien (`effective()`).
## - `goal(pos, heading_rad, pitch_deg)` : pose visée de la vue courante d'après le point de la route, son cap et
##   l'inclinaison de la route (lot Q2) : les vues de suivi se placent le long de la pente, donc l'exagération du
##   relief et le tangage s'appliquent à toutes les vues (2.0-CAM-4).
## - `step(dt, goal)` : pose affichée ; au changement de vue, interpolation (position et orientation) en
##   TRANSITION_S secondes. `snap()` oublie la pose affichée (reprise après un menu : pas de glissement).
## - Tangage partiel (lot Y15) : les caméras ne suivent que CAMERA_PITCH_FOLLOW de l'inclinaison de la route
##   (`camera_pitch_deg`). La rampe reste visible à l'écran (elle monte dans l'image en montée, plonge en descente)
##   et l'horizon bouge quand même ; avec une caméra qui suit toute la pente, la route paraît plate dans l'image.
##   Les vues de suivi restent posées le long de la route (pente entière), seul le regard est moins incliné.
## - `fov_deg(base_fov, pitch_deg)` (lot Y15) : champ de vision qui respire avec la pente, pour toutes les vues ; resserré
##   en montée (effet de téléobjectif : la rampe paraît plus raide et plus proche), élargi en descente (vitesse).
##   `pitch_deg` vient de camera_follow.gd, déjà lissé (0,5 s) : pas de saut d'une image à l'autre.
## - `remember_due(now_s)` : vrai une fois, REMEMBER_DELAY_S après le dernier changement, pour écrire la vue dans
##   `[render] camera` sans écrire le fichier à chaque appui.
## - `log_line()` : ligne de journal « Vue de caméra : <vue affichée> (<origine>) » quand la vue affichée a changé
##   depuis l'appel précédent, quelle qu'en soit l'origine (Click ou clavier, réglage, message de test, arrivée ou
##   perte de l'avatar), sinon "". main.gd l'écrit à chaque image : chaque changement de vue est vérifiable au journal.
## Pas de class_name : charger par preload("res://scripts/camera_views.gd").

const VIEWS := ["subjective", "follow_near", "follow_far", "side"]
const DEFAULT_VIEW := "follow_near"
const TRANSITION_S := 0.4
const REMEMBER_DELAY_S := 2.0

const EYE_HEIGHT_M := 1.4
const NEAR_BACK_M := 4.0
const NEAR_HEIGHT_M := 1.8
const NEAR_AHEAD_M := 10.0
const FAR_BACK_M := 12.0
const FAR_HEIGHT_M := 6.0
const FAR_AHEAD_M := 8.0
const SIDE_OFFSET_M := 8.0
const SIDE_HEIGHT_M := 1.6
const SIDE_AHEAD_M := 2.0
## Champ de vision selon la pente affichée (lot Y15) : écart maximal atteint à FOV_FULL_PITCH_DEG d'inclinaison.
## Part de l'inclinaison de la route suivie par la caméra (lot Y15) ; 1,0 jusque-là.
const CAMERA_PITCH_FOLLOW := 0.5
const FOV_CLIMB_DEG := 5.0
const FOV_DESCENT_DEG := 6.0
const FOV_FULL_PITCH_DEG := 10.0
## Hauteur visée sur le cycliste en vue de suivi ou latérale.
const TARGET_HEIGHT_M := 1.0

var current := DEFAULT_VIEW
## Vrai quand l'avatar existe (message `progression` du core) : sinon seule la vue subjective s'affiche.
var has_avatar := true
## Origine du dernier changement de vue, pour le journal (`log_line`).
var cause := "départ"
var _logged := ""

var _from := Transform3D.IDENTITY
var _last := Transform3D.IDENTITY
var _has_last := false
var _t := 1.0
var _changed_s := -1.0


static func is_valid(view: String) -> bool:
	return view in VIEWS


## Vue réellement affichée : la subjective tant que l'avatar n'existe pas (2.0-CAM-3).
func effective() -> String:
	return current if has_avatar else "subjective"


## Choisit une vue (réglage ou configuration) ; faux si elle est inconnue ou déjà courante.
func set_view(view: String, now_s := -1.0, origin := "réglage") -> bool:
	if not is_valid(view) or view == current:
		return false
	_begin_change(view, now_s, origin)
	return true


func next_view(now_s := -1.0, origin := "vue suivante") -> bool:
	return _cycle(1, now_s, origin)


func previous_view(now_s := -1.0, origin := "vue précédente") -> bool:
	return _cycle(-1, now_s, origin)


## A long : retour à la vue par défaut ; faux sans avatar ou si c'est déjà elle.
func reset_default(now_s := -1.0, origin := "vue par défaut") -> bool:
	if not has_avatar:
		return false
	return set_view(DEFAULT_VIEW, now_s, origin)


func _cycle(direction: int, now_s: float, origin: String) -> bool:
	if not has_avatar:
		return false
	var i := VIEWS.find(current)
	_begin_change(VIEWS[posmod(i + direction, VIEWS.size())], now_s, origin)
	return true


## Ligne de journal si la vue affichée a changé depuis l'appel précédent (toutes origines), sinon "".
func log_line() -> String:
	var view := effective()
	if view == _logged:
		return ""
	_logged = view
	var origin := cause if has_avatar else "sans avatar"
	return "Vue de caméra : %s (%s)" % [view, origin]


func _begin_change(view: String, now_s: float, origin: String) -> void:
	cause = origin
	current = view
	_from = _last
	_t = 0.0 if _has_last else 1.0
	_changed_s = now_s


## Vrai une seule fois, REMEMBER_DELAY_S après le dernier changement de vue.
func remember_due(now_s: float) -> bool:
	if _changed_s >= 0.0 and now_s - _changed_s >= REMEMBER_DELAY_S:
		_changed_s = -1.0
		return true
	return false


func in_transition() -> bool:
	return _t < 1.0


## Oublie la pose affichée : la prochaine image se place directement (reprise après un menu).
func snap() -> void:
	_has_last = false
	_t = 1.0


## Pose visée de la vue affichée. `pos` : point de la route sous le cycliste, `heading_rad` : cap horaire,
## `pitch_deg` : inclinaison de la route (positive en montée).
func goal(pos: Vector3, heading_rad: float, pitch_deg: float) -> Transform3D:
	var view := effective()
	var p_cam := deg_to_rad(camera_pitch_deg(pitch_deg))
	if view == "subjective":
		# Même orientation que la caméra de la 1.0 : cap sur Y, tangage sur X.
		return Transform3D(Basis.from_euler(Vector3(p_cam, -heading_rad, 0.0)), pos + Vector3(0.0, EYE_HEIGHT_M, 0.0))
	var p := deg_to_rad(pitch_deg)
	var fwd := Vector3(sin(heading_rad) * cos(p), sin(p), -cos(heading_rad) * cos(p))
	# Regard : même cap, tangage partiel (CAMERA_PITCH_FOLLOW).
	var look := Vector3(sin(heading_rad) * cos(p_cam), sin(p_cam), -cos(heading_rad) * cos(p_cam))
	var right := Vector3(cos(heading_rad), 0.0, sin(heading_rad))
	var target_base := pos + Vector3(0.0, TARGET_HEIGHT_M, 0.0)
	var eye: Vector3
	var target: Vector3
	match view:
		"follow_far":
			eye = pos - fwd * FAR_BACK_M + Vector3(0.0, FAR_HEIGHT_M, 0.0)
			target = target_base + look * FAR_AHEAD_M
		"side":
			eye = pos + right * SIDE_OFFSET_M + Vector3(0.0, SIDE_HEIGHT_M, 0.0)
			target = target_base + look * SIDE_AHEAD_M
		_:
			eye = pos - fwd * NEAR_BACK_M + Vector3(0.0, NEAR_HEIGHT_M, 0.0)
			target = target_base + look * NEAR_AHEAD_M
	return Transform3D(Basis.looking_at(target - eye, Vector3.UP), eye)


## Tangage de la caméra (degrés) pour une inclinaison de route `pitch_deg` : CAMERA_PITCH_FOLLOW de celle-ci.
static func camera_pitch_deg(pitch_deg: float) -> float:
	return pitch_deg * CAMERA_PITCH_FOLLOW


## Champ de vision vertical (degrés) pour une inclinaison de route `pitch_deg` (positive en montée).
static func fov_deg(base_fov: float, pitch_deg: float) -> float:
	var t := clampf(pitch_deg / FOV_FULL_PITCH_DEG, -1.0, 1.0)
	return base_fov - FOV_CLIMB_DEG * t if t > 0.0 else base_fov - FOV_DESCENT_DEG * t


## Pose affichée à cette image : la pose visée, ou son mélange avec la pose d'avant le changement de vue.
func step(dt: float, goal_pose: Transform3D) -> Transform3D:
	var pose := goal_pose
	if _t < 1.0 and _has_last:
		_t = minf(_t + dt / TRANSITION_S, 1.0)
		var k := _t * _t * (3.0 - 2.0 * _t)
		var q := Quaternion(_from.basis).slerp(Quaternion(goal_pose.basis), k)
		pose = Transform3D(Basis(q), _from.origin.lerp(goal_pose.origin, k))
	_last = pose
	_has_last = true
	return pose

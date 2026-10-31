extends RefCounted

## Départ au pédalage (lot O36, contrat IPC révision 1.5), sans nœud.
##
## Côté engine, deux rôles :
## - dire au core que le décor du départ est prêt : le parcours demandé est chargé, plus aucune tuile
##   voulue autour de la caméra n'est en attente (world_streamer.gd `pending_count`) et PLAYABLE_FRAMES
##   images de suite passent sous SLOW_FRAME_MS, ou, sur une machine lente (rendu logiciel de la CI), la
##   vue est restée complète SETTLE_S secondes ; commande `scene_ready {route_id}` envoyée une fois par
##   parcours, puis de nouveau chaque seconde tant que le core attend le décor (trame `state` avec
##   `start_wait.phase` = `decor` : core relancé, datagramme perdu) ;
## - décrire l'écran d'attente « Start your engines » (start_screen.gd) : texte de l'étape (`text`), feux
##   de départ allumés (`lights`, LIGHTS feux : un par étape franchie, puis le pédalage allume les
##   derniers), avancée du pédalage (`progress`) ; feux verts « GO ! » pendant GO_S à l'ouverture.
## Le core décide seul du départ (start_gate.py) ; le menu est masqué pendant l'attente (menu_flow.gd)
## et Y l'annule (le core reçoit la touche comme un appui du Click).
## Pas de class_name : charger par preload("res://scripts/start_wait_model.gd").

const PLAYABLE_FRAMES := 10
const SLOW_FRAME_MS := 33.0
const RESEND_S := 1.0
const SETTLE_S := 2.0
const LIGHTS := 5
const GO_S := 1.2
const TITLE := "START YOUR ENGINES"

## Parcours dont le décor du départ est prêt ; vide tant qu'il ne l'est pas.
var route_id := ""
var _candidate := ""
var _good := 0
var _settled_s := 0.0
var _sent_route := ""
var _last_sent_s := -1.0e9


## Une image affichée : `loaded_id` parcours chargé ("" sans parcours), `pending` tuiles voulues pas encore
## affichées, `frame_ms` durée de l'image. Renvoie vrai à l'image où le décor devient prêt.
func frame(loaded_id: String, pending: int, frame_ms: float) -> bool:
	if loaded_id != _candidate:
		_candidate = loaded_id
		route_id = ""
		_good = 0
		_settled_s = 0.0
	if loaded_id == "" or route_id == loaded_id:
		return false
	if pending > 0:
		_good = 0
		_settled_s = 0.0
		return false
	_settled_s += frame_ms / 1000.0
	_good = 0 if frame_ms > SLOW_FRAME_MS else _good + 1
	if _good < PLAYABLE_FRAMES and _settled_s < SETTLE_S:
		return false
	route_id = loaded_id
	return true


## Vrai s'il faut envoyer `scene_ready` maintenant ; `phase` : `start_wait.phase` de la dernière trame
## (vide hors attente). Note l'envoi.
func should_send(now_s: float, phase: String) -> bool:
	if route_id == "":
		return false
	if route_id != _sent_route or (phase == "decor" and now_s - _last_sent_s >= RESEND_S):
		_sent_route = route_id
		_last_sent_s = now_s
		return true
	return false


## Texte du bandeau pendant l'attente du départ ; vide hors attente.
static func text(wait) -> String:
	if not (wait is Dictionary):
		return ""
	match str(wait.get("phase", "")):
		"decor":
			return "Départ : chargement du décor…  (Y : annuler)"
		"trainer":
			return "Départ : connexion du trainer…  (Y : annuler)"
		"pedalage":
			return "Pédale pour partir : %d tr/min, %s s sur %.0f s  (Y : annuler)" % [int(wait.get("cadence_rpm", 0)),
				("%.1f" % float(wait.get("held_s", 0.0))).replace(".", ","), float(wait.get("hold_s", 0.0))]
	return ""


## Feux rouges allumés (0 à LIGHTS) : décor 1, trainer 2, pédalage 3 puis jusqu'à 5 avec le compte.
static func lights(wait) -> int:
	if not (wait is Dictionary):
		return 0
	match str(wait.get("phase", "")):
		"decor":
			return 1
		"trainer":
			return 2
		"pedalage":
			return mini(LIGHTS, 3 + int(floor(progress(wait) * 2.0 + 1.0e-6)))
	return 0


## Avancée du pédalage, de 0 à 1 (0 avant l'étape du pédalage).
static func progress(wait) -> float:
	if not (wait is Dictionary) or str(wait.get("phase", "")) != "pedalage":
		return 0.0
	var hold := float(wait.get("hold_s", 0.0))
	return 1.0 if hold <= 0.0 else clampf(float(wait.get("held_s", 0.0)) / hold, 0.0, 1.0)

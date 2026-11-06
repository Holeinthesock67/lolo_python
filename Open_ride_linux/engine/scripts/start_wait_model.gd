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
##   derniers), avancée du pédalage (`progress`), pastilles des trois étapes (`steps`), carte du parcours
##   qui va être roulé (`route_card` : nom, distance, dénivelé, profil) ; feux verts « GO ! » pendant GO_S.
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
const TAG := "OPENRIDE · DÉPART"
## Étapes de l'attente, dans l'ordre des pastilles de l'écran : (phase, libellé).
const STEPS := [["decor", "Décor"], ["trainer", "Trainer"], ["pedalage", "Pédalage"]]
const PROFILE_POINTS := 60

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


## Pastilles des étapes : [{label, state}] dans l'ordre de STEPS, `state` = `done` (franchie), `current`
## (en cours) ou `todo` (à venir) ; vide hors attente.
static func steps(wait) -> Array:
	if not (wait is Dictionary):
		return []
	var phase := str(wait.get("phase", ""))
	var at := -1
	for i in STEPS.size():
		if STEPS[i][0] == phase:
			at = i
	var out: Array = []
	for i in STEPS.size():
		out.append({"label": STEPS[i][1], "state": "done" if i < at else ("current" if i == at else "todo")})
	return out


## Ligne de valeurs sous le nom du parcours : « 24,6 km · 410 m D+ » (le dénivelé seulement s'il est connu).
static func route_line(length_m: float, gain_m) -> String:
	var line := "%s km" % ("%.1f" % (length_m / 1000.0)).replace(".", ",")
	if gain_m != null:
		line += " · %d m D+" % int(round(float(gain_m)))
	return line


## Carte du parcours de l'écran d'attente : `item` = entrée de la liste `routes` du core (id, name, length_m,
## stats), `profile` = profil d'altitude du parcours entier (hud_view_model.profile, champ `points`).
## Renvoie {name, line, heights} avec `heights` = PROFILE_POINTS hauteurs de 0 à 1 (vide sans profil),
## ou {} sans parcours (run Cyber-Rogue, liste pas encore reçue).
static func route_card(item: Dictionary, profile: Dictionary) -> Dictionary:
	if item.is_empty():
		return {}
	var st = item.get("stats", null)
	var length = st.get("distance_m", item.get("length_m", null)) if st is Dictionary else item.get("length_m", null)
	var gain = st.get("gain_m", null) if st is Dictionary else null
	var card := {"name": str(item.get("name", item.get("id", ""))), "line": "",
		"heights": _heights(profile.get("points", PackedVector2Array()))}
	if length != null:
		card["line"] = route_line(float(length), gain)
	return card


## Hauteurs de 0 à 1 du profil, ré-échantillonnées sur PROFILE_POINTS points ; vide sous 2 points.
static func _heights(points) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	if not (points is PackedVector2Array) or points.size() < 2:
		return out
	var lo := INF
	var hi := -INF
	for p in points:
		lo = minf(lo, p.y)
		hi = maxf(hi, p.y)
	var span := maxf(hi - lo, 1.0)
	for i in PROFILE_POINTS:
		var f := float(i) / float(PROFILE_POINTS - 1) * float(points.size() - 1)
		var k := mini(int(floor(f)), points.size() - 2)
		var y := lerpf(points[k].y, points[k + 1].y, f - float(k))
		out.append(clampf((y - lo) / span, 0.0, 1.0))
	return out

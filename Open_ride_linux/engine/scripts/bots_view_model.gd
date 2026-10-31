extends RefCounted

## Bots à l'écran (Lot O7, contrat IPC v1 §3, liste `bots`), sans nœud : écarts au cycliste en mètres
## et en secondes, bots visibles, ordre d'affichage, repères du profil (encart du HUD : bot_hud_model.gd).
##
## - push() garde la dernière liste reçue (au plus 5 bots {id, name, s, v, kind}) avec son heure ;
##   un bot absent de la trame disparaît, une trame sans `bots` (ou `bots` à null) les retire tous.
## - Position affichée : s + v × (maintenant − réception), bornée à MAX_EXTRAPOLATION_S comme la caméra
##   (camera_follow.gd) ; sur une boucle (loop_length_m > 0), s est ramené dans [0, longueur[.
## - Écart en mètres : s du bot − s du cycliste, positif devant ; sur une boucle, le plus court des deux
##   sens (entre −L/2 et L/2). Écart en secondes : `gap_s` du core quand il le donne (révision 1.4),
##   sinon écart en mètres divisé par la vitesse moyenne des deux (au moins MIN_SPEED_MPS).
## - Visible à moins de VISIBLE_M ; nom affiché au-dessus de la silhouette à moins de NAME_M.
## - Ordre : du plus loin devant au plus loin derrière (comme un classement).
## - Lot T15 : les champs de profil de la révision 1.4 (`profile`, `cp_w`, `mass_kg`, `wbal_pct`,
##   `jersey`) passent tels quels dans view() (null s'ils manquent) ; set_race() garde `bot_ahead`,
##   `bot_behind` et `jerseys` de la même trame (race()) ; un bot à profil garde `kind` = `constant`
##   (contrat 1.4) et se reconnaît à `profile`. Lignes de l'encart : bot_hud_model.gd.
## - Place en travers (`lateral`, écart à l'axe, positif à droite ; lot Z2, suite de P32 « aucune collision ») :
##   chaque bot vise une des LATERAL_SLOTS, la première libre : aucun autre bot sur la même place à moins de
##   SLOT_CLEAR_M devant ou derrière, et personne sur le chemin entre la place affichée et la nouvelle (on ne se
##   rabat pas sur quelqu'un ; le cycliste, à RIDER_LATERAL_M, compte jusqu'à RIDER_CLEAR_M). Du premier au
##   dernier : BOT_LATERAL_M (sa place habituelle) si elle est libre, sinon la place qu'il tient déjà, sinon la
##   première libre, sinon il reste où il est ; un peloton au départ se range donc côte à côte au lieu de se
##   superposer. Le bot glisse vers sa place à LATERAL_SPEED_MPS au plus. bots_view.gd l'affiche ;
##   living_decor.gd la passe aux cyclistes du décor, aux véhicules et au compte des contacts (places()).
## Pas de class_name : charger par preload("res://scripts/bots_view_model.gd").

const UiTheme := preload("res://scripts/ui_theme.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const VISIBLE_M := 300.0
const NAME_M := 50.0
const MAX_LINES := 5
const MAX_EXTRAPOLATION_S := 1.0
const MIN_SPEED_MPS := 1.0
## Couleur par `kind` : bot à puissance constante orange, fantôme bleu pâle ; inconnu gris. Un bot à
## profil (T12, `kind` = `constant` avec `profile`, contrat 1.4) est jaune. Teintes claires : les noms de
## l'encart des bots gardent au moins 3:1 sur le panneau au-dessus d'un ciel clair (lot X22).
const COLORS := {"constant": UiTheme.BOT_CONSTANT, "ghost": UiTheme.BOT_GHOST}
const PROFILE_COLOR := UiTheme.BOT_PROFILE
## Champs de profil (révision 1.4) recopiés tels quels dans view().
const PROFILE_FIELDS := ["profile", "cp_w", "mass_kg", "wbal_pct", "jersey"]
const OTHER_COLOR := UiTheme.BOT_OTHER
## Places en travers des bots, par ordre de préférence : leur place du lot P32 vers le bord, puis, en sautant
## celle du cycliste (un bot qui le rattrape dans sa ligne le toucherait), vers l'axe et la voie d'en face
## (peloton au départ), écartées de 0,9 m : deux cyclistes côte à côte ne se touchent pas
## (2 × TrafficModel.RIDER_HALF_WIDTH_M = 0,6 m). Cinq places pour cinq bots au plus (MAX_LINES).
const LATERAL_SLOTS := [RoadBuilder.BOT_LATERAL_M, RoadBuilder.RIDER_LATERAL_M - 0.9, RoadBuilder.RIDER_LATERAL_M - 1.8,
	RoadBuilder.RIDER_LATERAL_M - 2.7, RoadBuilder.RIDER_LATERAL_M - 3.6]
## Écart le long de la route en dessous duquel deux cyclistes sur la même place se touchent (deux demi-longueurs
## de vélo, TrafficModel.CYCLIST_HALF_LENGTH_M, et 0,2 m de marge).
const SLOT_CLEAR_M := 2.0
## Écart autour du cycliste en dessous duquel un bot ne traverse pas sa ligne pour changer de place (il glisse
## de 1,8 m à LATERAL_SPEED_MPS, en 1,5 s, pendant lesquelles l'écart peut fondre).
const RIDER_CLEAR_M := 10.0
## Écart latéral en dessous duquel deux cyclistes se touchent (2 × TrafficModel.RIDER_HALF_WIDTH_M).
const TOUCH_LATERAL_M := 0.6
const LATERAL_SPEED_MPS := 1.2

## Longueur de la boucle (0 si le parcours n'est pas une boucle).
var loop_length_m := 0.0
var _bots: Array = []   # [{id, name, kind, s, v, gap_s, t_us, champs de profil}] dans l'ordre de la trame
var _race: Dictionary = {}
var _slot := {}          # id → place visée
var _lateral := {}       # id → place affichée (glisse vers la place visée)
var _last_view_us := -1
var _places: Array = []  # [{s, lateral}] de la dernière vue


## Champs `bot_ahead`, `bot_behind` et `jerseys` de la trame (absents : null) ; `null` ou trame hors
## séance : rien.
func set_race(state) -> void:
	_race = {}
	if state is Dictionary:
		for key in ["bot_ahead", "bot_behind", "jerseys"]:
			_race[key] = state.get(key, null)


func race() -> Dictionary:
	return _race


func clear() -> void:
	_bots.clear()
	_race = {}
	_slot.clear()
	_lateral.clear()
	_places = []


func count() -> int:
	return _bots.size()


## Liste `bots` d'une trame `state` reçue à t_us (horloge locale, Time.get_ticks_usec()).
func push(bots, t_us: int) -> void:
	_bots.clear()
	if not (bots is Array):
		return
	for b in bots:
		if not (b is Dictionary) or str(b.get("id", "")) == "" or not (b.get("s") is float or b.get("s") is int):
			continue
		var gap = b.get("gap_s", null)
		var item := {"id": str(b["id"]), "name": str(b.get("name", b["id"])), "kind": str(b.get("kind", "")),
			"s": float(b["s"]), "v": float(b.get("v", 0.0)) if (b.get("v") is float or b.get("v") is int) else 0.0,
			"gap_s": float(gap) if (gap is float or gap is int) else null, "t_us": t_us}
		for key in PROFILE_FIELDS:
			item[key] = b.get(key, null)
		_bots.append(item)
		if _bots.size() >= MAX_LINES:
			break


## Écart en mètres du bot au cycliste, positif devant ; le plus court sur une boucle.
static func gap_m(rider_s: float, bot_s: float, loop_m := 0.0) -> float:
	var d := bot_s - rider_s
	if loop_m > 0.0:
		d = fposmod(d + loop_m / 2.0, loop_m) - loop_m / 2.0
	return d


## Écart en secondes : mètres divisés par la vitesse moyenne des deux (au moins MIN_SPEED_MPS).
static func gap_seconds(gap: float, rider_v: float, bot_v: float) -> float:
	return gap / maxf((maxf(rider_v, 0.0) + maxf(bot_v, 0.0)) / 2.0, MIN_SPEED_MPS)


static func color_of(kind: String, profile = null) -> Color:
	if profile != null and str(profile) != "":
		return PROFILE_COLOR
	return COLORS.get(kind, OTHER_COLOR)


## Bots à l'instant now_us vus du cycliste (s et v affichés) : [{id, name, kind, s, lateral, gap_m, gap_s,
## visible, show_name, color, profile, cp_w, mass_kg, wbal_pct, jersey}], du plus loin devant au plus
## loin derrière.
func view(rider_s: float, rider_v: float, now_us: int) -> Array:
	var out: Array = []
	for b in _bots:
		var dt := clampf(float(now_us - int(b["t_us"])) / 1e6, 0.0, MAX_EXTRAPOLATION_S)
		var s: float = b["s"] + b["v"] * dt
		if loop_length_m > 0.0:
			s = fposmod(s, loop_length_m)
		var gm := gap_m(rider_s, s, loop_length_m)
		var gs: float = b["gap_s"] if b["gap_s"] != null else gap_seconds(gm, rider_v, b["v"])
		var item := {"id": b["id"], "name": b["name"], "kind": b["kind"], "s": s, "gap_m": gm, "gap_s": gs,
			"visible": absf(gm) < VISIBLE_M, "show_name": absf(gm) < NAME_M, "color": color_of(b["kind"], b["profile"])}
		for key in PROFILE_FIELDS:
			item[key] = b[key]
		out.append(item)
	out.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a["gap_m"] > b["gap_m"])
	var dt := 0.0 if _last_view_us < 0 else clampf(float(now_us - _last_view_us) / 1e6, 0.0, 1.0)
	_last_view_us = now_us
	_assign_laterals(out, dt)
	return out


## Places des bots de la dernière vue, pour le décor (living_decor.gd) : [{s, lateral}].
func places() -> Array:
	return _places


## Place visée de chaque bot de `view` (trié du premier au dernier), puis place affichée qui y glisse.
func _assign_laterals(view: Array, dt: float) -> void:
	var taken: Array = [[0.0, RoadBuilder.RIDER_LATERAL_M, RIDER_CLEAR_M]]   # [écart au cycliste, place, garde]
	var seen := {}
	_places = []
	for item in view:
		var id: String = item["id"]
		seen[id] = true
		var want: Array = [LATERAL_SLOTS[0]]
		if _slot.has(id):
			want.append(_slot[id])
		want.append_array(LATERAL_SLOTS)
		var lat: float = _lateral.get(id, NAN)
		var slot: float = _slot.get(id, LATERAL_SLOTS[0])
		for cand in want:
			if _slot_free(taken, float(item["gap_m"]), float(cand), lat):
				slot = float(cand)
				break
		_slot[id] = slot
		taken.append([float(item["gap_m"]), slot, SLOT_CLEAR_M])
		if is_nan(lat):
			lat = slot
		lat = move_toward(lat, slot, LATERAL_SPEED_MPS * dt)
		_lateral[id] = lat
		item["lateral"] = lat
		_places.append({"s": item["s"], "lateral": lat})
	for id in _slot.keys():
		if not seen.has(id):
			_slot.erase(id)
			_lateral.erase(id)


## Vrai si la place `lateral` est libre à l'écart `gap` et si le chemin depuis `from` (place affichée, NAN pour un
## bot qui apparaît) ne passe sur personne.
static func _slot_free(taken: Array, gap: float, lateral: float, from: float) -> bool:
	var lo := lateral if is_nan(from) else minf(from, lateral)
	var hi := lateral if is_nan(from) else maxf(from, lateral)
	for t in taken:
		if absf(float(t[0]) - gap) >= float(t[2]):
			continue
		var other := float(t[1])
		if absf(other - lateral) < 0.01:
			return false
		if other > lo - TOUCH_LATERAL_M and other < hi + TOUCH_LATERAL_M and not (absf(other - from) < TOUCH_LATERAL_M):
			return false
	return true


## Repères du profil d'altitude : [{rel_m, color}] des bots entre from_m et to_m (écarts au cycliste,
## fenêtre de hud_view_model.profile()).
static func profile_marks(bots_view: Array, from_m: float, to_m: float) -> Array:
	var out: Array = []
	for b in bots_view:
		var rel: float = b["gap_m"]
		if rel >= from_m and rel <= to_m:
			out.append({"rel_m": rel, "color": b["color"]})
	return out

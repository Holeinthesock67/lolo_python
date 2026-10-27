extends RefCounted

## Bots à l'écran (Lot O7, contrat IPC v1 §3, liste `bots`), sans nœud : écarts au cycliste en mètres
## et en secondes, bots visibles, ordre d'affichage, lignes de l'encart du HUD et repères du profil.
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
## Pas de class_name : charger par preload("res://scripts/bots_view_model.gd").

const VISIBLE_M := 300.0
const NAME_M := 50.0
const MAX_LINES := 5
const MAX_EXTRAPOLATION_S := 1.0
const MIN_SPEED_MPS := 1.0
## Couleur par `kind` : bot à puissance constante orange, fantôme bleu pâle ; inconnu gris.
const COLORS := {"constant": Color(0.95, 0.55, 0.15), "ghost": Color(0.60, 0.75, 1.00)}
const OTHER_COLOR := Color(0.75, 0.75, 0.75)

## Longueur de la boucle (0 si le parcours n'est pas une boucle).
var loop_length_m := 0.0
var _bots: Array = []   # [{id, name, kind, s, v, gap_s, t_us}] dans l'ordre de la trame


func clear() -> void:
	_bots.clear()


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
		_bots.append({"id": str(b["id"]), "name": str(b.get("name", b["id"])), "kind": str(b.get("kind", "")),
			"s": float(b["s"]), "v": float(b.get("v", 0.0)) if (b.get("v") is float or b.get("v") is int) else 0.0,
			"gap_s": float(gap) if (gap is float or gap is int) else null, "t_us": t_us})
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


static func color_of(kind: String) -> Color:
	return COLORS.get(kind, OTHER_COLOR)


## Bots à l'instant now_us vus du cycliste (s et v affichés) : [{id, name, kind, s, gap_m, gap_s,
## visible, show_name, color}], du plus loin devant au plus loin derrière.
func view(rider_s: float, rider_v: float, now_us: int) -> Array:
	var out: Array = []
	for b in _bots:
		var dt := clampf(float(now_us - int(b["t_us"])) / 1e6, 0.0, MAX_EXTRAPOLATION_S)
		var s: float = b["s"] + b["v"] * dt
		if loop_length_m > 0.0:
			s = fposmod(s, loop_length_m)
		var gm := gap_m(rider_s, s, loop_length_m)
		var gs: float = b["gap_s"] if b["gap_s"] != null else gap_seconds(gm, rider_v, b["v"])
		out.append({"id": b["id"], "name": b["name"], "kind": b["kind"], "s": s, "gap_m": gm, "gap_s": gs,
			"visible": absf(gm) < VISIBLE_M, "show_name": absf(gm) < NAME_M, "color": color_of(b["kind"])})
	out.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a["gap_m"] > b["gap_m"])
	return out


## Texte d'un écart : « +12 s » devant, « -5 s » derrière, « 0 s » à moins d'une demi-seconde.
static func gap_text(gap_s: float) -> String:
	var r := int(round(gap_s))
	if r == 0:
		return "0 s"
	return ("+%d s" % r) if r > 0 else ("-%d s" % -r)


## Lignes de l'encart du HUD (au plus `max_lines`) : [{text, color}], « Bot 200 W  +12 s ».
static func hud_lines(bots_view: Array, max_lines := MAX_LINES) -> Array:
	var out: Array = []
	for b in bots_view:
		if out.size() >= max_lines:
			break
		out.append({"text": "%s  %s" % [b["name"], gap_text(float(b["gap_s"]))], "color": b["color"]})
	return out


## Repères du profil d'altitude : [{rel_m, color}] des bots entre from_m et to_m (écarts au cycliste,
## fenêtre de hud_view_model.profile()).
static func profile_marks(bots_view: Array, from_m: float, to_m: float) -> Array:
	var out: Array = []
	for b in bots_view:
		var rel: float = b["gap_m"]
		if rel >= from_m and rel <= to_m:
			out.append({"rel_m": rel, "color": b["color"]})
	return out

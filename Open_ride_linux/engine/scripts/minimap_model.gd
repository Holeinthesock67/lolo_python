extends RefCounted

## Mini-carte du monde ouvert (lot W24) : modèle sans affichage, testé sans écran.
##
## La carte suit le cycliste, cap en haut : route engagée devant (trait plein épais), route déjà roulée
## (pointillés), amorces des branches des carrefours proches (traits fins), prochain carrefour (anneau),
## nord (lettre « N » au bord), échelle écrite (« 200 m ») et but de la balade (« Arrivée » en destination,
## « Départ » en boucle) avec sa distance à vol d'oiseau, épinglé au bord quand il est hors de la carte.
## Tout ce qui compte est écrit ou se lit à la forme du trait : jamais la couleur seule.
##
## Coordonnées rendues : repère de la carte, unité = demi-largeur de la carte (`radius_m`), x vers la droite,
## y vers le bas, cycliste en `RIDER` (un peu sous le centre, pour voir plus loin devant). Le dessin
## (`minimap_view.gd`) multiplie par la demi-taille en pixels.
## Pas de class_name (charger par preload).

const RADIUS_M := 600.0            # demi-largeur de la carte : 1 200 m d'un bord à l'autre
const RIDER := Vector2(0.0, 0.35)  # cycliste sous le centre : ~800 m visibles devant, ~400 m derrière
const RANGE_FACTOR := 1.7          # route lue de part et d'autre, en multiples de `radius_m`
const HEADING_PROBE_M := 15.0      # cap = corde entre s − 15 m et s + 15 m
const JUNCTION_MAX_M := 1500.0     # prochain carrefour écrit sous la carte jusqu'à 1 500 m
const EDGE := 0.92                 # but hors carte : épinglé à 92 % du bord
const SCALE_STEPS := [50, 100, 200, 500, 1000, 2000, 5000]
const SCALE_SHARE := 0.4           # barre d'échelle : au plus 40 % de la largeur
const MIN_FIT_M := 200.0           # sous 200 m de route connue, pas de correction du repère pour le but

## Zoom réglable (ligne « Zoom de la carte » de l'écran de pause, retour du propriétaire du 24 novembre) : largeur
## de la carte d'un bord à l'autre, écrite telle quelle (« 1,2 km »). Par défaut 1,2 km (`RADIUS_M`).
const ZOOM_WIDTHS_M := [600.0, 1200.0, 3000.0, 6000.0, 15000.0]
const ZOOM_TEXTS := ["0,6 km", "1,2 km", "3 km", "6 km", "15 km"]
const DEFAULT_ZOOM := 1


## Indice de zoom d'un texte de ZOOM_TEXTS (indice par défaut s'il est inconnu).
static func zoom_index(text: String) -> int:
	var i := ZOOM_TEXTS.find(text)
	return i if i >= 0 else DEFAULT_ZOOM


## Demi-largeur de la carte (m) au zoom `i` (borné).
static func zoom_radius_m(i: int) -> float:
	return float(ZOOM_WIDTHS_M[clampi(i, 0, ZOOM_WIDTHS_M.size() - 1)]) * 0.5


## Pas de lecture des points de la route : celui de la qualité, allongé quand la carte s'élargit (un point tous
## les 10 m à 1,2 km de large, tous les 120 m à 15 km) : le nombre de segments dessinés reste à peu près le même.
static func stride_for(quality_stride: int, radius_m: float) -> int:
	return maxi(quality_stride, int(radius_m / RADIUS_M))


## Réglages par qualité : pas de lecture des points de la route (1 = tous les 10 m) et intervalle entre deux
## dessins. Le dessin ne coûte que quelques centaines de segments 2D ; en low on lit un point sur trois et on
## redessine 4 fois par seconde.
const QUALITY := {
	"low": {"stride": 3, "redraw_ms": 250},
	"medium": {"stride": 1, "redraw_ms": 100},
	"high": {"stride": 1, "redraw_ms": 66},
}


static func quality(name: String) -> Dictionary:
	return QUALITY.get(name, QUALITY["medium"])


## Barre d'échelle : longueur ronde la plus grande sous `SCALE_SHARE` de la largeur ; {m, text, frac}
## (`frac` : longueur en unités de la carte).
static func scale_bar(radius_m: float) -> Dictionary:
	var best: int = SCALE_STEPS[0]
	for step in SCALE_STEPS:
		if float(step) <= SCALE_SHARE * 2.0 * radius_m:
			best = step
	return {"m": best, "text": distance_text(float(best)), "frac": float(best) / radius_m}


## « 240 m » sous 1 km, « 3,2 km » ensuite (virgule décimale), « 12 km » à partir de 10 km.
static func distance_text(d_m: float) -> String:
	var d := maxf(d_m, 0.0)
	if d < 1000.0:
		return "%d m" % int(roundf(d))
	if d < 10000.0:
		return ("%.1f km" % (d / 1000.0)).replace(".", ",")
	return "%d km" % int(roundf(d / 1000.0))


## Point du repère de la carte pour un point du monde `p` (x vers l'est, z vers le sud), le cycliste étant en
## `origin` et regardant vers `fwd` (vecteur unitaire du plan x, z).
static func project(p: Vector2, origin: Vector2, fwd: Vector2, radius_m: float) -> Vector2:
	var v := p - origin
	var right := Vector2(-fwd.y, fwd.x)   # quart de tour à droite, vu de dessus (z vers le bas de l'écran)
	return RIDER + Vector2(v.dot(right), -v.dot(fwd)) / radius_m


## Cap du cycliste : corde de la route autour de `s_pos`, retournée en marche arrière (`direction` < 0).
static func forward_of(route, s_pos: float, direction: int) -> Vector2:
	var a: Vector3 = route.sample_point(route.wrap_s(s_pos - HEADING_PROBE_M))
	var b: Vector3 = route.sample_point(route.wrap_s(s_pos + HEADING_PROBE_M))
	var f := Vector2(b.x - a.x, b.z - a.z)
	if f.length() < 0.01:
		return Vector2(0.0, -1.0)   # route trop courte : nord en haut
	f = f.normalized()
	return -f if direction < 0 else f


## Points bruts de la route entre s0 et s1 (croissants, bornés à la route), un sur `stride`, plus les deux bouts
## interpolés : PackedVector2Array du plan x, z.
static func route_points(route, s0: float, s1: float, stride: int) -> PackedVector2Array:
	var out := PackedVector2Array()
	var a := clampf(s0, 0.0, float(route.length_m))
	var b := clampf(s1, 0.0, float(route.length_m))
	if b - a < 0.5:
		return out
	var p0: Vector3 = route.sample_point(a)
	out.append(Vector2(p0.x, p0.z))
	var ds: float = float(route.ds_m) if float(route.ds_m) > 0.0 else 10.0
	var i := int(ceil(a / ds))
	var step := maxi(stride, 1)
	while i < route.n and float(route.s[i]) < b:
		if float(route.s[i]) > a:
			out.append(Vector2(route.x[i], route.z[i]))
		i += step
	var p1: Vector3 = route.sample_point(b)
	out.append(Vector2(p1.x, p1.z))
	return out


## Repère local (est, nord) en mètres d'un point géographique autour de (lat0, lon0) : projection
## équirectangulaire, juste à quelques dizaines de kilomètres près.
static func geo_local(lat: float, lon: float, lat0: float, lon0: float) -> Vector2:
	var k_lat := 111132.0
	var k_lon := 111320.0 * cos(deg_to_rad(lat0))
	return Vector2((lon - lon0) * k_lon, (lat - lat0) * k_lat)


## Position dans le repère du monde (x, z) d'un point géographique, d'après les colonnes lat et lon de la route :
## le premier point sert d'ancre ; le point le plus loin de la route corrige l'angle et l'échelle (écart entre le
## nord géographique et le nord de la grille UTM, jusqu'à 2 à 3°). Vector2(NAN, NAN) sans route.
static func geo_to_world(route, lat: float, lon: float) -> Vector2:
	if route == null or int(route.n) < 1 or route.lat.size() < 1:
		return Vector2(NAN, NAN)
	var lat0: float = route.lat[0]
	var lon0: float = route.lon[0]
	var x0: float = route.x[0]
	var z0: float = route.z[0]
	# Correction (rotation et échelle, nombre complexe k) : repère géographique local → repère du monde.
	var k := Vector2(1.0, 0.0)
	var far := -1
	var far_d := MIN_FIT_M
	for i in range(0, int(route.n), 10):
		var d := Vector2(float(route.x[i]) - x0, float(route.z[i]) - z0).length()
		if d > far_d:
			far_d = d
			far = i
	if far > 0:
		var g := geo_local(route.lat[far], route.lon[far], lat0, lon0)
		var w := Vector2(float(route.x[far]) - x0, -(float(route.z[far]) - z0))   # (est, nord)
		var den := g.length_squared()
		if den > 1.0:
			k = Vector2((w.x * g.x + w.y * g.y) / den, (w.y * g.x - w.x * g.y) / den)   # w / g
	var t := geo_local(lat, lon, lat0, lon0)
	var en := Vector2(k.x * t.x - k.y * t.y, k.x * t.y + k.y * t.x)
	return Vector2(x0 + en.x, z0 - en.y)


## But de la balade d'après les arguments du départ (`start_open_world` ou `last_choices.open_world`) :
## {kind, label, lat, lon} ou {} en balade libre. Destination : la cible ; boucle : le point de départ.
static func goal_from_start(args: Variant) -> Dictionary:
	if typeof(args) != TYPE_DICTIONARY:
		return {}
	var nav := str(args.get("nav", "ride"))
	if nav == "destination":
		var t = args.get("target")
		if typeof(t) == TYPE_DICTIONARY and t.has("lat") and t.has("lon"):
			return {"kind": "destination", "label": "Arrivée", "lat": float(t["lat"]), "lon": float(t["lon"])}
	elif nav == "loop" and args.has("lat") and args.has("lon"):
		return {"kind": "loop", "label": "Départ", "lat": float(args["lat"]), "lon": float(args["lon"])}
	return {}


## But épinglé dans la carte : {pos, inside, label, text}. `p` : position carte du but ; `aspect` : hauteur sur
## largeur de la carte (le bord haut et le bord bas sont à ± `aspect`).
static func pin_goal(p: Vector2, label: String, dist_m: float, aspect: float = 1.0) -> Dictionary:
	var ey := EDGE * aspect
	var inside := absf(p.x) <= EDGE and absf(p.y) <= ey
	var pos := p
	if not inside:
		# Sur le rayon cycliste → but, au point où il sort du carré [-EDGE, EDGE].
		var d := p - RIDER
		var t := INF
		if absf(d.x) > 1e-6:
			t = minf(t, ((EDGE if d.x > 0.0 else -EDGE) - RIDER.x) / d.x)
		if absf(d.y) > 1e-6:
			t = minf(t, ((ey if d.y > 0.0 else -ey) - RIDER.y) / d.y)
		pos = RIDER + d * clampf(t, 0.0, 1.0)
	return {"pos": pos, "inside": inside, "label": label, "text": "%s : %s à vol d'oiseau" % [label, distance_text(dist_m)]}


## Vue complète de la carte. `route` : route affichée (RouteData) ; `s_pos` : position lissée du cycliste ;
## `direction` : sens de la marche ; `opts` : `radius_m`, `stride`, `previews` (amorces de live_world.previews),
## `next` (champ `open_world.next` de la trame), `goal` ({kind, label, x, z} dans le repère du monde, ou {}),
## `aspect` (hauteur sur largeur de la carte dessinée, 1 par défaut).
static func build(route, s_pos: float, direction: int, opts: Dictionary = {}) -> Dictionary:
	if route == null or int(route.n) < 2 or float(route.length_m) <= 0.0:
		return {"visible": false}
	var radius: float = float(opts.get("radius_m", RADIUS_M))
	var stride: int = int(opts.get("stride", 1))
	var s := float(route.wrap_s(s_pos))
	var here: Vector3 = route.sample_point(s)
	var origin := Vector2(here.x, here.z)
	var fwd := forward_of(route, s, direction)
	var span := RANGE_FACTOR * radius
	var dir := -1 if direction < 0 else 1
	var ahead := route_points(route, s, s + span, stride) if dir > 0 else route_points(route, s - span, s, stride)
	var behind := route_points(route, s - span, s, stride) if dir > 0 else route_points(route, s, s + span, stride)
	var view := {
		"visible": true,
		"ahead": _project_all(ahead, origin, fwd, radius),
		"behind": _project_all(behind, origin, fwd, radius),
		"previews": [],
		"rider": RIDER,
		"north": _north_dir(fwd),
		"scale": scale_bar(radius),
		"junction": {},
		"goal": {},
		"lines": [],
	}
	for pv in opts.get("previews", []):
		if typeof(pv) != TYPE_DICTIONARY or typeof(pv.get("xs")) != TYPE_ARRAY:
			continue
		var xs: Array = pv["xs"]
		var zs: Array = pv.get("zs", [])
		var pts := PackedVector2Array()
		for i in mini(xs.size(), zs.size()):
			pts.append(project(Vector2(float(xs[i]), float(zs[i])), origin, fwd, radius))
		if pts.size() >= 2:
			view["previews"].append(pts)
	var nxt = opts.get("next")
	if typeof(nxt) == TYPE_DICTIONARY and typeof(nxt.get("d_m")) in [TYPE_INT, TYPE_FLOAT]:
		var d_m := float(nxt["d_m"])
		if d_m >= 0.0 and d_m <= JUNCTION_MAX_M:
			var p: Vector3 = route.sample_point(route.wrap_s(s + dir * d_m))
			view["junction"] = {"pos": project(Vector2(p.x, p.z), origin, fwd, radius),
				"text": "Carrefour dans %s" % distance_text(d_m)}
			view["lines"].append(view["junction"]["text"])
	var goal = opts.get("goal", {})
	if typeof(goal) == TYPE_DICTIONARY and goal.has("x") and goal.has("z") \
			and is_finite(float(goal["x"])) and is_finite(float(goal["z"])):
		var gw := Vector2(float(goal["x"]), float(goal["z"]))
		var pin := pin_goal(project(gw, origin, fwd, radius), str(goal.get("label", "Arrivée")), gw.distance_to(origin),
			float(opts.get("aspect", 1.0)))
		view["goal"] = pin
		view["lines"].append(pin["text"])
	return view


## Direction du nord dans le repère de la carte (vecteur unitaire).
static func _north_dir(fwd: Vector2) -> Vector2:
	return (project(Vector2(0.0, -1.0), Vector2.ZERO, fwd, 1.0) - RIDER).normalized()


static func _project_all(pts: PackedVector2Array, origin: Vector2, fwd: Vector2, radius: float) -> PackedVector2Array:
	var out := PackedVector2Array()
	out.resize(pts.size())
	for i in pts.size():
		out[i] = project(pts[i], origin, fwd, radius)
	return out

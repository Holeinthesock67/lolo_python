extends RefCounted

## Marques des segments et arches de bonus (lot T8, série T), sans aucun nœud. Pas de class_name :
## charger par preload("res://scripts/segment_markers_model.gd").
##
## `items(route, segments, arch_every_m)` rend `[{kind, s, side, type, segment_id, lines}]`, trié par `s` :
## - `start` et `finish` au départ et à l'arrivée de chaque segment (ligne au sol et portique, vert pour
##   un sprint, blanc à pois rouges pour une montée), avec le nom du segment ;
## - `panel` avant un sprint (« Sprint dans 1 km », « 500 m », « 200 m ») ; au pied d'une montée
##   (« Montée de 2e catégorie » et « 4,2 km à 6,1 % »), puis « Sommet dans 1 km » et « 500 m » ;
##   panneaux à gauche (`side` = -1), pour ne pas cacher ceux du bord droit (P14) ;
## - `arch` : arches de bonus tous les `arch_every_m`, même règle que `ArchSchedule` du core (lot T6) :
##   k × every pour k ≥ 1 tant que la position reste avant la fin du parcours, aucune avec 0 ; sur une
##   boucle, elles reviennent à chaque tour (positions données sur un tour). Vecteurs partagés avec le
##   core : `engine/tests/data/arch_schedule_vectors.json`.
## Un panneau qui tomberait avant le départ d'un parcours ouvert est omis (sur une boucle, il passe au
## tour précédent), sauf celui du pied d'une montée, posé alors juste après la ligne de départ.
## `arch_every_m_from_text(texte)` : valeur `[obtain] arch_every_m` de `~/OpenRide/powerups.toml`, lue
## comme le core (5 000 m sans fichier ou sans clé, valeur refusée par le core : 5 000 m).
## `climbs(route, segments)` : montées de la couche au format de climb_detector.gd, pour le décor (une
## seule source des montées quand la couche existe).
## `window(starts, cam_s, length_m, loop, ahead_m, behind_m)` : indices des marques à afficher autour de
## la caméra, par recherche dichotomique dans les positions triées.
## Textes en français, nombres au format français.

const RoadsideModel := preload("res://scripts/roadside_model.gd")

const DEFAULT_ARCH_EVERY_M := 5000.0
const ARCH_EVERY_MIN_M := 500.0
const ARCH_EVERY_MAX_M := 1e6
const SPRINT_PANELS_M := [1000.0, 500.0, 200.0]
const SUMMIT_PANELS_M := [1000.0, 500.0]
const FOOT_PANEL_BEFORE_M := 30.0     # panneau de pied de montée, juste avant la ligne
const FOOT_PANEL_AFTER_M := 15.0      # ou juste après, pour une montée dès le départ
const MAX_KM_STEP_M := 20.0
const AHEAD_M := 400.0
const BEHIND_M := 30.0
const EPS_M := 1e-6


static func powerups_path() -> String:
	return OS.get_environment("HOME").path_join("OpenRide/powerups.toml")


## `arch_every_m` de la section `[obtain]`, comme `powerups.load_table` du core ; 5 000 m par défaut.
static func arch_every_m_from_text(text: String) -> float:
	var section := ""
	for raw_line in text.split("\n"):
		var line := raw_line.strip_edges()
		var cut := line.find("#")
		if cut >= 0:
			line = line.left(cut).strip_edges()
		if line.is_empty():
			continue
		if line.begins_with("[") and line.ends_with("]"):
			section = line.substr(1, line.length() - 2).strip_edges()
			continue
		if section != "obtain" or line.find("=") < 0:
			continue
		var key := line.get_slice("=", 0).strip_edges()
		if key != "arch_every_m":
			continue
		var value := line.substr(line.find("=") + 1).strip_edges().replace("_", "")
		if not (value.is_valid_float() or value.is_valid_int()):
			return DEFAULT_ARCH_EVERY_M
		var every := value.to_float()
		if every < 0.0 or every > ARCH_EVERY_MAX_M or (every > 0.0 and every < ARCH_EVERY_MIN_M):
			return DEFAULT_ARCH_EVERY_M
		return every
	return DEFAULT_ARCH_EVERY_M


static func arch_every_m_from_file(path: String = "") -> float:
	var p := path if not path.is_empty() else powerups_path()
	if not FileAccess.file_exists(p):
		return DEFAULT_ARCH_EVERY_M
	return arch_every_m_from_text(FileAccess.get_file_as_string(p))


## Positions des arches sur un tour (règle d'`ArchSchedule`, lot T6).
static func arch_positions(every_m: float, length_m: float) -> PackedFloat64Array:
	var out := PackedFloat64Array()
	if every_m <= 0.0:
		return out
	var k := 1
	while k * every_m < length_m - EPS_M:
		out.append(k * every_m)
		k += 1
	return out


## « 2e catégorie », « 1re catégorie », « hors catégorie ».
static func category_text(category) -> String:
	if category == null:
		return ""
	var c := str(category)
	if c == "HC":
		return "hors catégorie"
	if c == "1":
		return "1re catégorie"
	return "%se catégorie" % c


static func _distance_text(d_m: float) -> String:
	return "1 km" if d_m >= 1000.0 else "%d m" % int(round(d_m))


## Position d'une marque placée `before_m` avant `s` ; -1 si elle tombe avant le départ d'un parcours ouvert.
static func _before(route, s: float, before_m: float) -> float:
	var p := s - before_m
	if p >= 0.0:
		return p
	if route.is_loop():
		return fposmod(p, route.length_m)
	return -1.0


static func items(route, segments: Array, arch_every_m: float = DEFAULT_ARCH_EVERY_M) -> Array:
	var out: Array = []
	for seg in segments:
		var kind: String = seg["type"]
		var sid: String = seg["id"]
		var s0 := float(seg["s_start"])
		var s1 := float(seg["s_end"])
		var seg_name: String = seg["name"]
		out.append({"kind": "start", "s": s0, "side": 0, "type": kind, "segment_id": sid, "lines": [seg_name, "Départ"]})
		out.append({"kind": "finish", "s": s1, "side": 0, "type": kind, "segment_id": sid, "lines": [seg_name, "Arrivée"]})
		if kind == "sprint":
			for d in SPRINT_PANELS_M:
				var at := _before(route, s0, d)
				if at >= 0.0:
					out.append({"kind": "panel", "s": at, "side": -1, "type": kind, "segment_id": sid,
						"lines": ["Sprint dans " + _distance_text(d)]})
		else:
			var foot := _before(route, s0, FOOT_PANEL_BEFORE_M)
			if foot < 0.0:   # montée dès le départ d'un parcours ouvert : panneau juste après la ligne
				foot = s0 + FOOT_PANEL_AFTER_M
			out.append({"kind": "panel", "s": foot, "side": -1, "type": kind, "segment_id": sid,
				"lines": ["Montée de " + category_text(seg.get("category")),
					"%s km à %s %%" % [RoadsideModel.format_dec(float(seg["length_m"]) / 1000.0, 1),
						RoadsideModel.format_dec(float(seg["avg_grade_pct"]), 1)]]})
			for d in SUMMIT_PANELS_M:
				if d < s1 - s0:
					out.append({"kind": "panel", "s": s1 - d, "side": -1, "type": kind, "segment_id": sid,
						"lines": ["Sommet dans " + _distance_text(d)]})
	for p in arch_positions(arch_every_m, float(route.length_m)):
		out.append({"kind": "arch", "s": p, "side": 0, "type": "", "segment_id": "", "lines": ["Bonus"]})
	out.sort_custom(func(a, b): return float(a["s"]) < float(b["s"]))
	return out


## Positions triées des marques (pour `window`).
static func starts(marks: Array) -> PackedFloat64Array:
	var out := PackedFloat64Array()
	for m in marks:
		out.append(float(m["s"]))
	return out


## Premier indice i tel que starts[i] >= s.
static func _lower_bound(starts_arr: PackedFloat64Array, s: float) -> int:
	var lo := 0
	var hi := starts_arr.size()
	while lo < hi:
		var mid := (lo + hi) >> 1
		if starts_arr[mid] < s:
			lo = mid + 1
		else:
			hi = mid
	return lo


static func _range(starts_arr: PackedFloat64Array, a: float, b: float, out: Array) -> void:
	var i := _lower_bound(starts_arr, a)
	while i < starts_arr.size() and starts_arr[i] <= b:
		if not out.has(i):
			out.append(i)
		i += 1


## Indices des marques entre `cam_s - behind_m` et `cam_s + ahead_m` (sur une boucle, à cheval sur la ligne).
static func window(starts_arr: PackedFloat64Array, cam_s: float, length_m: float, loop: bool,
		ahead_m: float = AHEAD_M, behind_m: float = BEHIND_M) -> Array:
	var out: Array = []
	var a := cam_s - behind_m
	var b := cam_s + ahead_m
	_range(starts_arr, maxf(a, 0.0), minf(b, length_m), out)
	if loop:
		if a < 0.0:
			_range(starts_arr, a + length_m, length_m, out)
		if b > length_m:
			_range(starts_arr, 0.0, b - length_m, out)
	return out


## Montées de la couche segments au format de climb_detector.gd (`start_s`, `summit_s`, `length_m`,
## `gain_m`, `avg_grade_pct`, `max_km_grade_pct`, `summit_alt_m`).
static func climbs(route, segments: Array) -> Array:
	var out: Array = []
	for seg in segments:
		if seg["type"] != "climb":
			continue
		var s0 := float(seg["s_start"])
		var s1 := float(seg["s_end"])
		var length := s1 - s0
		var avg := float(seg["avg_grade_pct"])
		var max_km := avg
		if length > 1000.0:
			max_km = -INF
			var s := s0
			while s + 1000.0 <= s1 + EPS_M:
				var a0 := float(route.sample(s)["alt_m"])
				var a1 := float(route.sample(s + 1000.0)["alt_m"])
				max_km = maxf(max_km, (a1 - a0) / 10.0)
				s += MAX_KM_STEP_M
		out.append({
			"start_s": s0, "summit_s": s1, "length_m": length, "gain_m": float(seg["gain_m"]),
			"avg_grade_pct": avg, "max_km_grade_pct": max_km,
			"summit_alt_m": float(route.sample(s1)["alt_m"]),
		})
	return out

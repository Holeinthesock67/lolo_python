extends RefCounted

## Objets du bord de route (Lot P14), sans aucun nœud : panneaux de col, panneaux d'approche, bornes
## kilométriques, et chiffres peints sur la chaussée. Pas de class_name : charger par
## preload("res://scripts/roadside_model.gd").
##
## `items(route, climbs, pois, water)` rend `[{kind, s, side, text, lines}]`, trié par `s` :
## - `summit` au sommet de chaque montée (climb_detector.gd) : nom du point d'intérêt nommé le plus
##   proche à moins de SUMMIT_NAME_M, sinon « Sommet », et l'altitude arrondie au mètre (« 1 234 m ») ;
## - `approach` à APPROACH_KM du sommet (si la montée est assez longue) : « Sommet à 3 km » et
##   « Pente moyenne 7 % » (pente moyenne du reste de la montée, arrondie à l'unité) ;
## - `km` tous les kilomètres de parcours (« km 12 »), sans doublon au point de départ d'une boucle.
## `side` vaut 1 (à droite). Un objet qui tomberait dans l'eau (surface d'eau ou cours d'eau, donc
## aussi sur un pont) est avancé par pas de NUDGE_M, au plus MAX_NUDGE_M, sinon abandonné.
## `paint_marks(climbs)` : chiffres des kilomètres restants peints sur la chaussée, de 5 à 1 km du
## sommet, `[{s, digit}]`, pour road_markings.gdshader.
## Textes en français, nombres au format français (espace des milliers, virgule décimale).

const RoadBuilder := preload("res://scripts/road_builder.gd")
const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")

const APPROACH_KM := [5, 3, 2, 1]
const PAINT_KM := [5, 4, 3, 2, 1]
const SUMMIT_NAME_M := 400.0
const SIDE_OFFSET_M := 1.5          # du bord de la chaussée
const NUDGE_M := 10.0
const MAX_NUDGE_M := 100.0
const WATER_MARGIN_M := 2.0


## Entier au format français : « 1 234 ».
static func format_int(v: int) -> String:
	var neg := v < 0
	var digits := str(absi(v))
	var out := ""
	var count := 0
	for i in range(digits.length() - 1, -1, -1):
		out = digits[i] + out
		count += 1
		if count % 3 == 0 and i > 0:
			out = " " + out
	return ("-" if neg else "") + out


## Nombre à `decimals` décimales au format français : « 7,5 ».
static func format_dec(v: float, decimals: int = 1) -> String:
	var txt := String.num(v, decimals)
	if decimals > 0 and txt.find(".") < 0:
		txt += "." + "0".repeat(decimals)
	return txt.replace(".", ",")


static func approach_texts(km: int, avg_pct: float) -> Array:
	return ["Sommet à %d km" % km, "Pente moyenne %d %%" % int(round(avg_pct))]


## Position d'un objet du bord de route (côté droit, à SIDE_OFFSET_M du bord de la chaussée).
static func prop_position(route, s: float, road_width_m: float = RoadBuilder.ROAD_WIDTH_M) -> Vector3:
	var smp: Dictionary = route.sample(s)
	var h := deg_to_rad(float(smp["heading_deg"]))
	var right := Vector3(cos(h), 0.0, sin(h))
	return Vector3(smp["x"], smp["y"], smp["z"]) + right * (road_width_m * 0.5 + SIDE_OFFSET_M)


static func _in_water(p: Vector3, water: Dictionary) -> bool:
	for a in water.get("areas", []):
		if typeof(a) == TYPE_DICTIONARY and typeof(a.get("outer")) == TYPE_ARRAY and a["outer"].size() >= 3:
			if VegetationPlacer.point_in_ring(p.x, p.z, a["outer"]):
				return true
	var q := Vector2(p.x, p.z)
	for l in water.get("lines", []):
		if typeof(l) != TYPE_DICTIONARY or typeof(l.get("points")) != TYPE_ARRAY:
			continue
		var pts: Array = l["points"]
		var half := float(l.get("width_m", 2.0)) * 0.5 + WATER_MARGIN_M
		for i in range(pts.size() - 1):
			var a2 := Vector2(float(pts[i][0]), float(pts[i][1]))
			var b2 := Vector2(float(pts[i + 1][0]), float(pts[i + 1][1]))
			var ab := b2 - a2
			var len2 := ab.length_squared()
			var t := 0.0 if len2 <= 0.0 else clampf((q - a2).dot(ab) / len2, 0.0, 1.0)
			if (a2 + ab * t).distance_to(q) < half:
				return true
	return false


## `s` hors de l'eau le plus proche en avançant (NAN si aucun à moins de MAX_NUDGE_M).
static func _dry_s(route, s: float, water: Dictionary, road_width_m: float) -> float:
	var t := 0.0
	while t <= MAX_NUDGE_M:
		var cand := s + t
		if cand > route.length_m:
			return NAN
		if not _in_water(prop_position(route, cand, road_width_m), water):
			return cand
		t += NUDGE_M
	return NAN


static func _summit_name(route, summit_s: float, pois: Array) -> String:
	var c: Vector3 = route.sample_point(summit_s)
	var best := ""
	var best_d := SUMMIT_NAME_M
	for p in pois:
		if typeof(p) != TYPE_DICTIONARY or typeof(p.get("name")) != TYPE_STRING or str(p["name"]).is_empty():
			continue
		var d := Vector2(float(p.get("x", 0.0)) - c.x, float(p.get("z", 0.0)) - c.z).length()
		if d <= best_d:
			best_d = d
			best = str(p["name"])
	return best if not best.is_empty() else "Sommet"


static func items(route, climbs: Array, pois: Array = [], water: Dictionary = {},
		road_width_m: float = RoadBuilder.ROAD_WIDTH_M) -> Array:
	var out := []
	if route == null:
		return out
	for c in climbs:
		var summit_s := float(c["summit_s"])
		var name := _summit_name(route, summit_s, pois)
		var alt_txt := "%s m" % format_int(int(round(float(c["summit_alt_m"]))))
		var ss := _dry_s(route, summit_s, water, road_width_m)
		if not is_nan(ss):
			out.append({"kind": "summit", "s": ss, "side": 1, "text": "%s\n%s" % [name, alt_txt], "lines": [name, alt_txt]})
		for km in APPROACH_KM:
			var s: float = summit_s - km * 1000.0
			if s < float(c["start_s"]) - 1.0:
				continue
			var alt_here := float(route.sample(s)["alt_m"])
			var avg: float = (float(c["summit_alt_m"]) - alt_here) / (km * 1000.0) * 100.0
			var lines := approach_texts(km, avg)
			var sa := _dry_s(route, s, water, road_width_m)
			if not is_nan(sa):
				out.append({"kind": "approach", "s": sa, "side": 1, "text": "\n".join(lines), "lines": lines})
	var n_km := int(floor(route.length_m / 1000.0 + 1e-6))
	for k in range(1, n_km + 1):
		var s := k * 1000.0
		if route.is_loop() and absf(s - route.length_m) < 1.0:
			continue   # boucle : le kilomètre final est le point de départ
		var sk := _dry_s(route, minf(s, route.length_m - 1.0), water, road_width_m)   # borne finale : dans le dernier tronçon
		if not is_nan(sk):
			out.append({"kind": "km", "s": sk, "side": 1, "text": "km %d" % k, "lines": ["km %d" % k]})
	out.sort_custom(func(a, b): return a["s"] < b["s"] or (a["s"] == b["s"] and a["kind"] < b["kind"]))
	return out


## Chiffres peints sur la chaussée : kilomètres restants, de 5 à 1 km du sommet de chaque montée.
static func paint_marks(climbs: Array) -> Array:
	var out := []
	for c in climbs:
		for km in PAINT_KM:
			var s: float = float(c["summit_s"]) - km * 1000.0
			if s >= float(c["start_s"]) - 1.0:
				out.append({"s": s, "digit": km})
	out.sort_custom(func(a, b): return a["s"] < b["s"])
	return out


## Objets du tronçon k (s de k × 1 000 à (k + 1) × 1 000).
static func for_chunk(all_items: Array, k: int) -> Array:
	var out := []
	for it in all_items:
		var s := float(it["s"])
		if s >= k * 1000.0 and s < (k + 1) * 1000.0:
			out.append(it)
	return out

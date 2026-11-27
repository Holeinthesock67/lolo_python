extends RefCounted

## Parcours en boucle pour les tests (revue E7-02 et E8-02) : cercle de `segments` segments de `ds` mètres
## autour de `center`, dernier point sur le premier (type `loop`). Longueur segments × ds, choisie par les tests
## pour ne pas tomber sur un multiple de la longueur des tronçons (dernier tronçon du tour plus court).
## Pas de class_name : charger par preload("res://tests/loop_route.gd").

const RouteDataScript := preload("res://scripts/route_data.gd")


static func circle(segments: int, ds: float = 10.0, center: Vector2 = Vector2.ZERO) -> Variant:
	var r := ds / (2.0 * sin(PI / segments))
	var d := {"version": "1.0", "ds_m": ds, "n": segments + 1, "length_m": ds * segments, "type": "loop",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(segments + 1):
		var a := TAU * float(i % segments) / segments
		var p := center + Vector2(r * cos(a), r * sin(a))
		var t := Vector2(-sin(a), cos(a))   # sens de la marche (a croissant)
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(500.0)
		d["x"].append(p.x)
		d["z"].append(p.y)
		d["grade_pct"].append(0.0)
		d["heading_deg"].append(fposmod(rad_to_deg(atan2(t.x, -t.y)), 360.0))
	var route = RouteDataScript.new()
	route.load_route_dict(d)
	return route

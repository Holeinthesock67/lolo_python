extends RefCounted

## Route d'essai et séance « véhicules et cyclistes du décor ensemble » des tests de la circulation, communes à
## test_traffic_model.gd et à test_traffic_mixed_a.gd / _b.gd (27 novembre : test_traffic_model seul tenait 95 s sur
## 120 s de délai en CI, dont 80 % pour les 16 graines de la séance mêlée ; partagées en deux fichiers de 8 graines).

const TrafficModel := preload("res://scripts/traffic_model.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const RoadCyclistsModel := preload("res://scripts/road_cyclists_model.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")

const LENGTH_M := 32000.0
const SNOW_FROM := 12000.0      # de 12 à 15 km : au-dessus de la limite de neige
const SNOW_TO := 15000.0
const STEEP_FROM := 20000.0     # de 20 à 22 km : pente de 10 %
const STEEP_TO := 22000.0


## Route droite vers l'est, avec un passage enneigé et une rampe raide.
static func route():
	var ds := 10.0
	var n := int(LENGTH_M / ds) + 1
	var cols := {"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		var s := i * ds
		cols["lat"].append(48.9)
		cols["lon"].append(7.1)
		cols["alt_m"].append(2500.0 if s >= SNOW_FROM and s < SNOW_TO else 400.0)
		cols["x"].append(s)
		cols["z"].append(0.0)
		cols["grade_pct"].append(10.0 if s >= STEEP_FROM and s < STEEP_TO else 2.0)
		cols["heading_deg"].append(90.0)
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": (n - 1) * ds, "type": "open"}
	d.merge(cols)
	var r = RouteDataScript.new()
	r.load_route_dict(d)
	return r


static func villages() -> Array:
	var out := []
	for x in [3000.0, 9000.0, 17000.0, 26000.0]:
		out.append({"id": "v%d" % int(x), "kind": "village", "x": x, "y": 400.0, "z": 300.0, "radius_m": 300, "name": null})
	return out


## Lot P32 : véhicules, cyclistes du décor et un bot ensemble, 30 km à 30 km/h ; collisions (carrosseries qui se
## touchent, entre véhicules ou avec un cycliste ou le bot) et écarts de carrosserie aux cyclistes dépassés.
static func ride_mixed(route, rng_seed: int) -> Dictionary:
	var tm = TrafficModel.new()
	tm.configure(route, {"terrain": {"snow_line_m": 2200.0}}, villages(), 5, rng_seed)
	var cy = RoadCyclistsModel.new()
	cy.configure(route, [], villages(), 12, rng_seed, RoadBuilder.ROAD_WIDTH_M, tm)
	var v_mps := 30.0 / 3.6
	var dt := 1.0 / 15.0     # 15 images/s : mêmes résultats qu’à 30 (vérifié), deux fois plus rapide
	var s := 300.0
	var bot := 150.0
	var hits := 0
	var hit_vehicles := 0
	var hit_cyclists := 0
	var close_pass := 0
	var met := 0
	var waited := 0
	while s < 30500.0:
		cy.update(s, v_mps, dt, false, [{"s": bot, "lateral": RoadBuilder.BOT_LATERAL_M}])
		var others: Array = cy.riders()
		others.append({"s": bot, "lateral": RoadBuilder.BOT_LATERAL_M, "dir": 1})
		tm.update(s, v_mps, dt, false, others)
		var vs: Array = tm.vehicles
		for v in vs:
			var k: Dictionary = TrafficModel.KINDS[v["kind"]]
			if int(v["dir"]) == 1 and not v.get("committed", false) and float(v["s"]) - s > -TrafficModel.FOLLOW_GAP_M - 2.0 \
					and float(v["s"]) < s:
				waited += 1
			for o in others:
				if absf(float(o["s"]) - float(v["s"])) < float(k["length"]) * 0.5 + TrafficModel.CYCLIST_HALF_LENGTH_M:
					met += 1
					var side := absf(float(o["lateral"]) - float(v["lateral"])) - float(k["half_width"]) - TrafficModel.RIDER_HALF_WIDTH_M
					if side < 0.0:
						hits += 1
					elif int(o["dir"]) == int(v["dir"]) and side < TrafficModel.LATERAL_CLEARANCE_M - 1e-3:
						close_pass += 1
		for i in range(vs.size()):
			for j in range(i + 1, vs.size()):
				var a: Dictionary = vs[i]
				var b: Dictionary = vs[j]
				var ka: Dictionary = TrafficModel.KINDS[a["kind"]]
				var kb: Dictionary = TrafficModel.KINDS[b["kind"]]
				if absf(float(a["s"]) - float(b["s"])) < (float(ka["length"]) + float(kb["length"])) * 0.5 \
						and absf(float(a["lateral"]) - float(b["lateral"])) < float(ka["half_width"]) + float(kb["half_width"]):
					hit_vehicles += 1
		# Cyclistes du décor entre eux (groupes différents), avec le cycliste et avec le bot
		var everyone: Array = others.duplicate()
		everyone.append({"s": s, "lateral": RoadBuilder.RIDER_LATERAL_M, "dir": 1})
		for i in range(everyone.size()):
			for j in range(i + 1, everyone.size()):
				var p: Dictionary = everyone[i]
				var q: Dictionary = everyone[j]
				if p.has("group") and q.has("group") and p["group"] == q["group"]:
					continue
				if absf(float(p["s"]) - float(q["s"])) < 2.0 * TrafficModel.CYCLIST_HALF_LENGTH_M \
						and absf(float(p["lateral"]) - float(q["lateral"])) < 2.0 * TrafficModel.RIDER_HALF_WIDTH_M:
					hit_cyclists += 1
		s += v_mps * dt
		bot += 31.0 / 3.6 * dt
	return {"hits": hits, "hit_vehicles": hit_vehicles, "hit_cyclists": hit_cyclists, "close_pass": close_pass, "met": met, "waited": waited,
		"spawned": tm.spawned_total, "groups": cy.spawned_total}

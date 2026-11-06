extends SceneTree

## Cyclistes du décor proches calculés par le core (lot AS7) : `road_cyclists_model.gd` reprend la liste `riders`
## (`sync_core`) : cyclistes reçus à la place de ceux de l'engine (même `id`, tenue gardée), extrapolés jusqu'à la
## liste suivante, une seule reprise par trame, décor lointain gardé, cyclistes que le core ne donne pas retirés
## (liste qui n'est pas pleine), cycliste sorti de la liste rendu au décor de l'engine (il double un groupe plus
## lent au lieu de le traverser), tenue tirée de `look` sinon.
## Lancement : godot --headless --path engine --script res://tests/unit/test_road_cyclists_core.gd

const Model := preload("res://scripts/road_cyclists_model.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route droite et plate de 10 km vers l'est.
func _route():
	var ds := 10.0
	var n := 1001
	var cols := {"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		cols["lat"].append(48.9)
		cols["lon"].append(7.1)
		cols["alt_m"].append(200.0)
		cols["x"].append(i * ds)
		cols["z"].append(0.0)
		cols["grade_pct"].append(0.0)
		cols["heading_deg"].append(90.0)
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": (n - 1) * ds, "type": "open"}
	d.merge(cols)
	var r = RouteDataScript.new()
	r.load_route_dict(d)
	return r


func _model(route):
	var m = Model.new()
	m.configure(route, [], [], 16, 7)
	m.update(1000.0, 7.0, 0.0)      # premier appel : cases à partir de la position, aucune tirée avant
	m._next_slot = 1 << 30            # aucune case tirée : seuls les groupes posés roulent
	return m


func _by_id(m) -> Dictionary:
	var out := {}
	for r in m.riders():
		out[str(r["id"])] = r
	return out


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var route = _route()
	var s := 1000.0
	var m = _model(route)
	m.place_for_test(s, 7.0, "ahead", 20.0, 3)
	m.place_for_test(s, 7.0, "ahead", 300.0, 1)
	var ids: Array = []
	for r in m.riders():
		ids.append(str(r["id"]))
	_check(ids == ["c1000000-0", "c1000000-1", "c1000000-2", "c1000001-0"], "identifiants « c<case>-<rang> » comme le core (%s)" % str(ids))
	var jersey0 := int(_by_id(m)["c1000000-0"]["member"]["jersey"])
	var list := [
		{"id": "c1000000-0", "s": s + 21.0, "dir": 1, "v": 6.0, "lane_m": 2.4, "look": 7},
		{"id": "c1000000-1", "s": s + 19.5, "dir": 1, "v": 6.0, "lane_m": 2.4, "look": 7},
		{"id": "c9-0", "s": s - 30.0, "dir": -1, "v": 8.0, "lane_m": -2.5, "look": (12 << 4) | 5},
		{"id": "c5-0", "s": s + 58.0, "dir": 1, "v": 6.0, "lane_m": 2.5, "look": 3},
	]
	m.sync_core(list, 3, s)
	var got := _by_id(m)
	_check(got.has("c1000000-0") and got.has("c1000000-1") and got.has("c9-0") and got.has("c5-0") and got.has("c1000001-0"),
		"cyclistes de la liste et décor lointain (300 m) gardés (%s)" % str(got.keys()))
	_check(not got.has("c1000000-2"), "cycliste de l'engine à 17 m que la liste ne donne pas : retiré")
	_check(got.size() == 5, "aucun doublon (%d cyclistes)" % got.size())
	_check(not got.is_empty() and is_same(got["c1000000-0"]["group"], got["c1000000-1"]["group"]),
		"cyclistes d'un même groupe reçus : un seul groupe (pas de contact compté entre eux)")
	var r0: Dictionary = got.get("c1000000-0", {})
	_check(not r0.is_empty() and absf(float(r0["s"]) - (s + 21.0)) < 1e-6 and absf(float(r0["lateral"]) - 2.4) < 1e-6
		and absf(float(got["c1000000-1"]["s"]) - (s + 19.5)) < 1e-6, "places et écarts à l'axe du core repris")
	_check(not r0.is_empty() and int(r0["member"]["jersey"]) == jersey0, "maillot du cycliste de l'engine gardé")
	var r9: Dictionary = got.get("c9-0", {})
	_check(not r9.is_empty() and int(r9["dir"]) == -1 and int(r9["member"]["jersey"]) == 5 and int(r9["member"]["look"]) == 12,
		"cycliste que l'engine n'a pas tiré : sens, maillot et tenue tirés de `look`")
	m.update(s, 7.0, 0.5)
	got = _by_id(m)
	_check(absf(float(got["c1000000-0"]["s"]) - (s + 24.0)) < 1e-6 and absf(float(got["c9-0"]["s"]) - (s - 34.0)) < 1e-6,
		"extrapolés entre deux listes, dans leur sens")
	m.sync_core([], 3, s)
	_check(_by_id(m).size() == 5, "même trame : liste reprise une seule fois")
	m.sync_core([list[0]], 6, s)
	got = _by_id(m)
	_check(got.has("c1000000-0") and not got.has("c1000000-1") and not got.has("c9-0"),
		"cyclistes absents de la liste à moins de 55 m : plus sur la route (%s)" % str(got.keys()))
	_check(got.has("c5-0") and not got["c5-0"]["group"].has("core") and str(got["c5-0"]["group"]["case"]) == "ahead",
		"cycliste à 61 m sorti de la liste : rendu au décor de l'engine (groupe « ahead »)")
	m.update(s, 7.0, 0.5)
	_check(absf(float(_by_id(m)["c5-0"]["s"]) - (s + 58.0 + 6.0)) < 1e-3, "... à sa dernière vitesse (6 m/s, deux pas de 0,5 s)")
	# Banc E1 du 5/11 : le groupe rendu au décor rattrape un groupe plus lent sur sa voie ; il le double au lieu
	# de rouler au travers
	m.sync_core([], 7, s)   # le core ne donne plus personne : les cyclistes du core proches quittent la route
	m.place_for_test(s, 7.0, "ahead", 75.0, 1)
	var overlap := 0
	var closest := INF
	for i in range(30 * 40):
		m.update(s, 0.0, 1.0 / 30.0)
		var rs: Array = m.riders()
		for a in rs:
			for b in rs:
				if a["group"] == b["group"] or int(a["dir"]) != int(b["dir"]):
					continue
				var ds := absf(float(a["s"]) - float(b["s"]))
				if ds < 2.0:
					closest = minf(closest, absf(float(a["lateral"]) - float(b["lateral"])))
					if absf(float(a["lateral"]) - float(b["lateral"])) < Model.MIN_CENTRE_M - 0.05:
						overlap += 1
	got = _by_id(m)
	_check(overlap == 0 and got.has("c5-0") and float(got["c5-0"]["s"]) > s + 75.0 + 40.0 * 5.0 + 5.0,
		"groupe rendu au décor : double le plus lent sans le traverser (%d images l'une dans l'autre, écart en travers %.2f m au plus près)" % [overlap, closest])

	# Liste pleine : les cyclistes proches qu'elle ne donne pas peuvent encore rouler
	var m2 = _model(route)
	m2.place_for_test(s, 7.0, "ahead", 10.0, 1)
	m2.place_for_test(s, 7.0, "ahead", 40.0, 1)
	var full := []
	for i in range(Model.CORE_LIST_MAX):
		full.append({"id": "c%d-0" % (50 + i), "s": s + 2.0 * i, "dir": -1, "v": 7.0, "lane_m": -2.5, "look": i})
	m2.sync_core(full, 1, s)
	got = _by_id(m2)
	_check(got.size() == Model.CORE_LIST_MAX + 2 and got.has("c1000000-0") and got.has("c1000001-0"),
		"liste pleine : cyclistes proches de l'engine gardés (%d)" % got.size())
	print("test_road_cyclists_core : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)

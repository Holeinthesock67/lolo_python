extends SceneTree

## Cyclistes du décor à la limite des 60 m de la liste `riders` (banc r879b du 14/11 sur le volcan, roulé à
## 50–65 km/h : contacts « overtake / core » à −61 m, écarts à l'axe 1,9 et 2,0 m ; « core / cycliste » à −1 m).
## 1. Un groupe dont une partie seulement est dans la liste (tête à moins de 60 m, queue au-delà) appartient tout
##    entier au core : les membres que la liste ne donne pas suivent la tête du core à leur place dans le groupe,
##    au lieu de rester dans la copie de l'engine, qui n'est pas au même endroit (contacts du même groupe).
## 2. Les places du core sont recalées sur le cycliste affiché (`core_s`, comme les véhicules, lot AS6) et ne
##    sont pas extrapolées une fois de plus à l'image de leur reprise.
## Lancement : godot --headless --path engine --script res://tests/unit/test_road_cyclists_limit.gd

const Model := preload("res://scripts/road_cyclists_model.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const CONTACT_LEN_M := 1.7      # living_decor.gd : 2 × CONTACT_BIKE_HALF_M
const CONTACT_WIDTH_M := 0.6    # 2 × RIDER_HALF_WIDTH_M

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


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


func _model(route, s: float, v: float):
	var m = Model.new()
	m.configure(route, [], [], 16, 7)
	m.update(s, v, 0.0)
	m._next_slot = 1 << 30
	return m


## Paires de cyclistes de groupes différents qui se touchent, comme living_decor._count_contacts.
func _contacts(m) -> Array:
	var out := []
	var rs: Array = m.riders()
	for i in range(rs.size()):
		for j in range(i + 1, rs.size()):
			var a: Dictionary = rs[i]
			var b: Dictionary = rs[j]
			if is_same(a["group"], b["group"]):
				continue
			if absf(float(a["s"]) - float(b["s"])) < CONTACT_LEN_M and absf(float(a["lateral"]) - float(b["lateral"])) < CONTACT_WIDTH_M:
				out.append("%s (%s) / %s (%s)" % [a["id"], a["group"]["case"], b["id"], b["group"]["case"]])
	return out


func _by_id(m) -> Dictionary:
	var out := {}
	for r in m.riders():
		out[str(r["id"])] = r
	return out


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var route = _route()
	var v := 55.0 / 3.6
	var s := 2000.0
	# 1. Groupe « overtake » de 3 en file, tête à −57,4 m dans l'engine ; le core, 2,1 m plus loin derrière, ne
	#    donne que sa tête (−59,5 m), les deux autres sont au-delà de 60 m
	var m = _model(route, s, v)
	m.place_for_test(s, v, "overtake", -57.4, 3)
	var g: Dictionary = m.groups[0]
	var gid := str(g["id"])
	var lane := float(g["members"][0]["lateral"])
	var list := [{"id": gid + "-0", "s": s - 59.5, "dir": 1, "v": v + 1.5, "lane_m": lane, "look": 1}]
	m.sync_core(list, 1, s, s)
	var got := _by_id(m)
	_check(got.size() == 3, "trois cyclistes, aucun doublon (%d)" % got.size())
	_check(got.has(gid + "-1") and got.has(gid + "-2") and is_same(got[gid + "-1"]["group"], got[gid + "-0"]["group"]),
		"membres hors liste d'un groupe donné par le core : dans le groupe du core")
	if got.has(gid + "-1") and got.has(gid + "-2"):
		_check(absf(float(got[gid + "-1"]["s"]) - (s - 59.5 - Model.FILE_GAP_M)) < 1e-3
			and absf(float(got[gid + "-2"]["s"]) - (s - 59.5 - 2.0 * Model.FILE_GAP_M)) < 1e-3,
			"... à leur place dans la file derrière la tête du core (%.2f, %.2f)" % [float(got[gid + "-1"]["s"]) - s, float(got[gid + "-2"]["s"]) - s])
	var hits := []
	for i in range(30 * 4):
		m.update(s, v, 1.0 / 60.0)
		s += v / 60.0
		if i % 6 == 5:
			list = [{"id": gid + "-0", "s": float(_by_id(m)[gid + "-0"]["s"]), "dir": 1, "v": v + 1.5, "lane_m": lane, "look": 1}]
			m.sync_core(list, 2 + i, s, s)
		hits.append_array(_contacts(m))
	_check(hits.is_empty(), "groupe à cheval sur la limite des 60 m : aucun contact en 2 s (%s)" % str(hits.slice(0, 3)))

	# 2. Groupe de tête à −60 m, sa queue revient dans la liste : la tête que la liste ne donne plus reste à sa place
	var m3 = _model(route, s, v)
	var list3 := [
		{"id": "c42-0", "s": s + 56.0, "dir": 1, "v": 7.0, "lane_m": 2.0, "look": 1},
		{"id": "c42-1", "s": s + 53.9, "dir": 1, "v": 7.0, "lane_m": 2.0, "look": 1},
	]
	m3.sync_core(list3, 1, s, s)
	m3.sync_core([list3[1]], 2, s, s)
	got = _by_id(m3)
	_check(got.size() == 2 and got.has("c42-0") and absf(float(got["c42-0"]["s"]) - (s + 56.0)) < 1e-3
		and absf(float(got["c42-1"]["s"]) - (s + 53.9)) < 1e-3,
		"tête sortie de la liste par l'avant : gardée à sa place, pas posée sur le suivant (%s)" % str(
			[float(got.get("c42-0", {}).get("s", NAN)) - s, float(got.get("c42-1", {}).get("s", NAN)) - s]))

	# 3. Recalage sur le cycliste affiché : le cycliste affiché a 0,8 m de retard sur la trame du core
	var m2 = _model(route, s, v)
	var core_s := s + 0.8
	m2.sync_core([{"id": "c77-0", "s": core_s - 2.1, "dir": 1, "v": v, "lane_m": 1.2, "look": 1}], 1, s, core_s)
	got = _by_id(m2)
	_check(absf(float(got["c77-0"]["s"]) - (s - 2.1)) < 1e-3, "place du core recalée sur le cycliste affiché (%.2f m, attendu −2,10)" % (float(got["c77-0"]["s"]) - s))
	m2.update(s, v, 1.0 / 60.0)
	got = _by_id(m2)
	_check(absf(float(got["c77-0"]["s"]) - (s - 2.1)) < 1e-3, "pas extrapolé une fois de plus à l'image de sa reprise (%.3f m)" % (float(got["c77-0"]["s"]) - s))
	m2.update(s + v / 60.0, v, 1.0 / 60.0)
	got = _by_id(m2)
	_check(absf(float(got["c77-0"]["s"]) - (s - 2.1 + v / 60.0)) < 1e-3, "extrapolé aux images suivantes")
	var m4 = _model(route, s, v)
	m4.sync_core([{"id": "c78-0", "s": s + 10.0, "dir": 1, "v": v, "lane_m": 2.0, "look": 1}], 1, s, s + 400.0)
	_check(absf(float(_by_id(m4)["c78-0"]["s"]) - (s + 10.0)) < 1e-3, "écart de plus de 50 m (saut, boucle) : pas de recalage")

	# 4. Lot AS10 : un groupe que le core a donné puis rendu au décor (au-delà des 60 m) garde sa vitesse, même doublé
	# par un groupe du core plus rapide sur sa ligne (le core le voit et le fait doubler) : il ne roule plus à côté de
	# lui à sa vitesse (contacts « core / ahead » vers −60 m à 65 km/h)
	var m5 = _model(route, s, v)
	var slow_list := [{"id": "c50-0", "s": s - 56.5, "dir": 1, "v": 6.0, "lane_m": 1.8, "look": 1},
		{"id": "c51-0", "s": s - 58.0, "dir": 1, "v": 19.0, "lane_m": 1.4, "look": 1}]
	m5.sync_core(slow_list, 1, s, s)
	m5.update(s, v, 1.0 / 60.0)
	m5.sync_core([{"id": "c51-0", "s": s - 57.7, "dir": 1, "v": 19.0, "lane_m": 1.4, "look": 1}], 2, s, s)
	_check(str(_by_id(m5)["c50-0"]["group"]["case"]) == "ahead", "groupe sorti de la liste rendu au décor")
	var s50 := float(_by_id(m5)["c50-0"]["s"])
	for _i in range(30):
		m5.update(s, v, 1.0 / 60.0)
	var moved := float(_by_id(m5).get("c50-0", {"s": NAN})["s"]) - s50
	_check(moved > 2.0 and moved < 4.0, "groupe rendu par le core : garde sa vitesse (%.2f m en 0,5 s, attendu ~3)" % moved)

	# 5. Lot AS10 : les groupes évitent le cycliste à sa vraie place en travers (`lane_m` de la trame)
	var m6 = _model(route, s, v)
	m6.update(s, v, 1.0 / 60.0, false, [], 0.3)
	m6.place_for_test(s, v, "overtake", -20.0, 1)
	var og: Dictionary = m6.groups[-1]
	og["side"] = "left"
	_check(absf(m6._base_lateral(og, og["members"][0]) - (0.3 - Model.MIN_CENTRE_M)) < 1e-6,
		"dépassement à MIN_CENTRE_M à gauche du cycliste là où il est (%.2f m)" % m6._base_lateral(og, og["members"][0]))

	print("test_road_cyclists_limit : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)

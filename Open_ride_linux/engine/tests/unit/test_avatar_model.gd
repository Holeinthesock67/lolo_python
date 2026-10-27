extends SceneTree

## Tests sans écran de l'avatar du cycliste (lot V6) : réglages et bornes, intégration de la cadence,
## pause, hystérésis assis / danseuse, cinématique, niveaux de détail et visibilité par vue.
## Lancement : godot --headless --path engine --script res://tests/unit/test_avatar_model.gd

const AvatarModel := preload("res://scripts/avatar_model.gd")
const AvatarMesh := preload("res://scripts/avatar_mesh.gd")
const AvatarView := preload("res://scripts/avatar_view.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _test_settings() -> void:
	var d := AvatarModel.parse_settings(null)
	_check(d == AvatarModel.DEFAULTS, "sans réglages : valeurs par défaut")
	var s := AvatarModel.parse_settings({"height": "XL", "build": "strong", "skin": 7, "hair": 0, "hair_color": 7,
		"kit_primary": 15, "kit_secondary": 0, "number": 999, "standing_grade_pct": 6, "standing_power_pct": 120})
	_check(s["height"] == "XL" and s["build"] == "strong" and s["skin"] == 7 and s["hair"] == 0 and s["number"] == 999
		and s["kit_primary"] == 15 and s["kit_secondary"] == 0, "réglages valides repris (bornes incluses)")
	_check(s["standing_grade_pct"] == 6.0 and s["standing_power_pct"] == 120.0, "seuils de danseuse repris")
	var bad := AvatarModel.parse_settings({"height": "XXL", "build": 3, "skin": 8, "hair": -1, "hair_color": 2.5,
		"kit_primary": 16, "kit_secondary": "x", "number": 1000, "standing_grade_pct": 2, "standing_power_pct": 400})
	_check(bad == AvatarModel.DEFAULTS, "valeurs hors bornes ou mal typées : défauts")
	_check(AvatarModel.SKIN_COLORS.size() == AvatarModel.SKIN_MAX + 1 and AvatarModel.HAIR_COLORS.size() == AvatarModel.HAIR_COLOR_MAX + 1
		and AvatarModel.KIT_COLORS.size() == AvatarModel.KIT_MAX + 1, "une couleur par indice de palette")


func _test_crank() -> void:
	var m = AvatarModel.new()
	m.configure(null, 250.0)
	m.update(0.0, 60.0, 200.0, 0.0, false)
	for i in range(1, 11):
		m.update(i * 0.1, 60.0, 200.0, 0.0, false)
	_check(absf(m.crank_angle - TAU) < 0.001 or m.crank_angle < 0.001, "60 tr/min pendant 1 s : un tour (%.3f rad)" % m.crank_angle)
	m.reset()
	m.update(0.0, 100.0, 200.0, 0.0, false)
	m.update(0.1, 100.0, 200.0, 0.0, false)
	m.update(0.2, 100.0, 200.0, 0.0, false)
	_check(absf(m.crank_angle - 100.0 / 60.0 * TAU * 0.2) < 0.001, "100 tr/min : angle proportionnel au temps (%.3f rad)" % m.crank_angle)
	var a: float = m.crank_angle
	m.update(0.3, 0.0, 0.0, 0.0, false)
	m.update(0.4, null, 0.0, 0.0, false)
	_check(m.crank_angle == a, "0 tr/min ou sans cadence : pédalier figé")
	m.update(0.5, 90.0, 200.0, 0.0, true)
	m.update(0.6, 90.0, 200.0, 0.0, true)
	_check(m.crank_angle == a, "en pause : pédalier figé")
	m.update(10.0, 90.0, 200.0, 0.0, false)
	_check(m.crank_angle - a < 90.0 / 60.0 * TAU * (AvatarModel.MAX_STEP_S + 0.01), "grand écart de temps borné (%.2f rad)" % (m.crank_angle - a))


func _test_standing() -> void:
	var m = AvatarModel.new()
	m.configure({"standing_grade_pct": 8, "standing_power_pct": 150}, 200.0)
	m.update(0.0, 80.0, 150.0, 4.0, false)
	_check(not m.standing, "pente 4 %, 75 % de la FTP : assis")
	m.update(1.0, 80.0, 150.0, 9.0, false)
	_check(m.standing, "pente 9 % : danseuse")
	m.update(1.5, 80.0, 150.0, 7.5, false)
	_check(m.standing, "7,5 % (sous le seuil de 8 % mais pas 1 point en dessous) : toujours debout")
	m.update(2.5, 80.0, 150.0, 5.0, false)
	_check(m.standing, "retour assis refusé avant 2 s debout")
	m.update(3.2, 80.0, 150.0, 5.0, false)
	_check(not m.standing, "retour assis après 2 s et sous les marges")
	m.update(4.0, 80.0, 320.0, 0.0, false)
	_check(m.standing, "320 W (160 % de la FTP) à plat : danseuse")
	m.update(7.0, 80.0, 280.0, 0.0, false)
	_check(m.standing, "140 % de la FTP : encore debout (marge de 10 points)")
	m.update(8.0, 80.0, 250.0, 0.0, false)
	_check(not m.standing, "125 % de la FTP : assis")
	var n = AvatarModel.new()
	n.configure(null, 0.0)
	n.update(0.0, 80.0, 900.0, 0.0, false)
	_check(not n.standing, "FTP inconnue : la puissance ne déclenche pas la danseuse")
	_check(AvatarModel.visible_in_view("follow") and AvatarModel.visible_in_view("side") and not AvatarModel.visible_in_view("subjective"),
		"caché en vue subjective, visible ailleurs")


func _test_kinematics() -> void:
	var d := AvatarMesh.dims(AvatarModel.DEFAULTS)
	var worst := 0.0
	for height in AvatarModel.HEIGHTS:
		var dd := AvatarMesh.dims({"height": height, "build": "medium"})
		for standing in [false, true]:
			for i in range(24):
				var angle := TAU * i / 24.0
				var p := AvatarMesh.pose(angle, standing, dd)
				for side in ["r", "l"]:
					var hip: Vector3 = p["hip_" + side]
					var knee: Vector3 = p["knee_" + side]
					var ankle: Vector3 = p["ankle_" + side]
					worst = maxf(worst, absf(hip.distance_to(knee) - float(dd["thigh"])))
					worst = maxf(worst, absf(knee.distance_to(ankle) - float(dd["shin"])))
					if knee.z > hip.z:   # genou vers l'avant (−Z)
						worst = maxf(worst, 1.0)
	_check(worst < 0.002, "segments de longueur constante, genou vers l'avant (écart max %.4f m)" % worst)
	var low := AvatarMesh.pose(0.0, false, d)
	var high := AvatarMesh.pose(PI, false, d)
	_check(absf(float(low["ankle_r"].y) - float(high["ankle_r"].y)) > 0.25, "pédales à des hauteurs différentes à 0 et π")
	_check(absf(float(low["ankle_r"].y) - float(low["ankle_l"].y)) > 0.25, "pédales droite et gauche en opposition")
	_check(float(AvatarMesh.pose(0.0, true, d)["hip"].y) > float(low["hip"].y), "danseuse : hanche plus haute qu'assis")
	var reach := 0.0
	for i in range(24):
		var p := AvatarMesh.pose(TAU * i / 24.0, false, d)
		reach = maxf(reach, absf(p["ankle_r"].distance_to(p["hip_r"]) - (float(d["thigh"]) + float(d["shin"]))))
	_check(true, "portée mesurée (%.3f m)" % reach)


func _test_lods() -> void:
	var d := AvatarMesh.dims(AvatarModel.DEFAULTS)
	var counts := []
	for lod in range(3):
		var n := AvatarMesh.triangle_count(lod, d)
		counts.append(n)
		_check(n <= int(AvatarMesh.LOD_MAX_TRIANGLES[lod]) and n > 0, "niveau %d : %d triangles (≤ %d)" % [lod, n, AvatarMesh.LOD_MAX_TRIANGLES[lod]])
	_check(counts[0] > counts[1] and counts[1] > counts[2], "chaque niveau est plus léger que le précédent")


func _test_view() -> void:
	var v = AvatarView.new()
	v.configure(AvatarModel.parse_settings({"number": 27, "hair": 0}), 0)
	root.add_child(v)
	var info: Dictionary = v.test_info()
	_check(info["nodes"] > 20 and info["triangles"] > 1000, "niveau 0 : %d nœuds, %d triangles affichés" % [info["nodes"], info["triangles"]])
	_check(not v.visible, "caché en vue subjective au départ")
	v.set_visible_for_view("follow")
	_check(v.visible, "visible en vue de suivi")
	v.set_visible_for_view("subjective")
	_check(not v.visible, "caché de nouveau en vue subjective")
	var m = AvatarModel.new()
	m.configure(null, 250.0)
	m.update(0.0, 90.0, 200.0, 0.0, false)
	m.update(0.1, 90.0, 200.0, 0.0, false)
	v.apply(m)
	var shoe_a: Vector3 = v._list("shoe")[0].position
	for i in range(1, 8):
		m.update(0.1 + i * 0.1, 90.0, 200.0, 0.0, false)
	v.apply(m)
	_check(shoe_a.distance_to(v._list("shoe")[0].position) > 0.05, "le pied bouge avec le pédalier")
	var number: Label3D = v._number
	_check(number != null and number.visible and number.text == "27", "numéro 27 sur le dos")
	v.set_lod(2)
	var low: Dictionary = v.test_info()
	_check(low["lod"] == 2 and low["triangles"] <= 300, "niveau 2 : %d triangles" % low["triangles"])
	v.configure(AvatarModel.parse_settings({"hair": 3, "skin": 5}), 0)
	_check(v._list("hair")[0].visible, "cheveux visibles quand le style n'est pas 0")
	var ms := PerfBudget.measure_ms(func():
		for i in range(20):
			m.update(2.0 + i * 0.016, 90.0, 200.0, 0.0, false)
			v.apply(m), 10, 2) / 20.0
	_check(PerfBudget.check("avatar_frame", ms), "mise à jour de l'avatar en %.3f ms par image" % ms)
	v.free()


func _init() -> void:
	_test_settings()
	_test_crank()
	_test_standing()
	_test_kinematics()
	_test_lods()
	_test_view()
	print("test_avatar_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

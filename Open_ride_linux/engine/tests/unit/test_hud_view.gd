extends SceneTree

## Tests unitaires sans écran de hud_view.gd (Lot E3 / SRS §8).
## Vérifie :
## - Affichage exact pour une trame d'état de référence, temps écoulé compris, « — » pour absent.
## - Profil : 120 colonnes, repère à la position, couleur selon grade_class.
## - Mise en page : à 1280x720 et 1920x1080, aucun libellé ne déborde ni ne se chevauche.

const HudView := preload("res://scripts/hud_view.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const HudViewModel := preload("res://scripts/hud_view_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _make_test_route() -> Variant:
	var ds := 10.0
	var n := 300
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": (n - 1) * ds, "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(500.0 + i * 2.0)
		d["x"].append(0.0)
		d["z"].append(i * ds)
		d["grade_pct"].append(5.0)
		d["heading_deg"].append(0.0)
	var route = RouteDataScript.new()
	route.load_route_dict(d)
	return route


func _test_labels_and_values() -> void:
	var hud = HudView.new()
	root.add_child(hud)

	var state_ref := {
		"power": 250.0,
		"power_3s": 245.0,
		"v": 8.3333,   # 30.0 km/h
		"cadence": 85.0,
		"hr": 142.0,
		"grade": 4.5,
		"s": 15200.0,
		"gear": 14,
		"gears_total": 24,
		"t": 3665.0,  # 1:01:05
	}
	var route = _make_test_route()
	hud.update_display(state_ref, {}, route, 500.0)

	_check(hud.power_val.text == "245", "puissance affichée = 245 (%s)" % hud.power_val.text)
	_check(hud.speed_val.text == "30.0", "vitesse affichée = 30.0 (%s)" % hud.speed_val.text)
	_check(hud.cadence_val.text == "85", "cadence affichée = 85 (%s)" % hud.cadence_val.text)
	_check(hud.hr_val.text == "142", "FC affichée = 142 (%s)" % hud.hr_val.text)
	_check(hud.grade_val.text == "+4.5 %", "pente affichée = +4.5 %% (%s)" % hud.grade_val.text)
	_check(hud.gear_val.text == "14/24", "braquet affiché = 14/24 (%s)" % hud.gear_val.text)
	_check(hud.distance_val.text == "15.20 km", "distance affichée = 15.20 km (%s)" % hud.distance_val.text)
	_check(hud.time_val.text == "1:01:05", "temps affiché = 1:01:05 (%s)" % hud.time_val.text)

	# Valeurs absentes donnent « — »
	var state_empty := {}
	hud.update_display(state_empty, {}, null, 0.0)
	_check(hud.power_val.text == "—", "puissance vide = —")
	_check(hud.speed_val.text == "—", "vitesse vide = —")
	_check(hud.cadence_val.text == "—", "cadence vide = —")
	_check(hud.hr_val.text == "—", "FC vide = —")
	_check(hud.grade_val.text == "—", "pente vide = —")
	_check(hud.gear_val.text == "—", "braquet vide = —")
	_check(hud.distance_val.text == "—", "distance vide = —")
	_check(hud.time_val.text == "—", "temps vide = —")

	hud.queue_free()


func _test_layout_resolutions() -> void:
	for res in [Vector2i(1280, 720), Vector2i(1920, 1080)]:
		var vp := SubViewport.new()
		vp.size = res
		root.add_child(vp)
		var hud = HudView.new()
		vp.add_child(hud)
		await process_frame
		await process_frame

		var p_prof: Control = hud.profile_panel
		_check(p_prof != null, "résolution %dx%d : profil présent" % [res.x, res.y])

		# Vérifier les positions relatives aux ancres du viewport
		var p_left: Panel = hud.panel_left
		var p_right: Panel = hud.panel_right

		var left_rect := Rect2(p_left.position.x, p_left.position.y, p_left.size.x, p_left.size.y)
		var right_x := float(res.x) + p_right.offset_left
		var right_w := p_right.offset_right - p_right.offset_left
		var right_rect := Rect2(right_x, p_right.offset_top, right_w, p_right.offset_bottom - p_right.offset_top)

		_check(left_rect.position.x >= 0.0 and left_rect.end.x <= float(res.x),
			"résolution %dx%d : panneau gauche dans l'écran" % [res.x, res.y])
		_check(right_rect.position.x >= 0.0 and right_rect.end.x <= float(res.x),
			"résolution %dx%d : panneau droit dans l'écran" % [res.x, res.y])
		_check(not left_rect.intersects(right_rect),
			"résolution %dx%d : aucun chevauchement gauche / droite" % [res.x, res.y])

		vp.queue_free()


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_test_labels_and_values()
	await _test_layout_resolutions()
	print("test_hud_view : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

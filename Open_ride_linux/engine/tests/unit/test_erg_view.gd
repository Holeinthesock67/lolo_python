extends SceneTree

## Tests sans écran de l'affichage ERG `erg_view.gd` (Lot N7) :
## - textes du bandeau (bloc i/n, type, cible biais compris, temps restant, cible suivante) ;
## - zones de Coggan aux mêmes seuils que `openride-core summary` ;
## - histogramme : largeurs selon les durées du profil, bloc en cours, curseur au temps écoulé ;
##   repli sur des cases égales sans profil ou avec un profil qui ne correspond pas ;
## - caché en SIM (erg null), visible en ERG, mise en page dans l'écran à 1280x720 et 1920x1080.

const ErgView := preload("res://scripts/erg_view.gd")
const ErgViewModel := preload("res://scripts/erg_view_model.gd")

## sweet_spot_3x10 : échauffement 10 min, 3 × (10 min à 90 %, 5 min à 55 %), retour au calme 10 min.
const SWEET_SPOT := [[600, 0.5, 0.75], [600, 0.9, 0.9], [300, 0.55, 0.55], [600, 0.9, 0.9], [300, 0.55, 0.55],
		[600, 0.9, 0.9], [300, 0.55, 0.55], [600, 0.6, 0.4]]

var _failures := 0
var _checked := 0


func _init() -> void:
	call_deferred("_run")


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _erg(overrides: Dictionary = {}) -> Dictionary:
	var e := {"workout_name": "Sweet spot 3x10", "block_index": 2, "block_count": 8, "block_type": "interval_on",
		"block_remaining_s": 150.0, "block_total_s": 600.0, "target_w": 225.0, "next_target_w": 138.0,
		"bias_pct": 100, "paused": false}
	for k in overrides:
		e[k] = overrides[k]
	return e


func _run() -> void:
	_test_banner()
	_test_zones()
	_test_layout_profile()
	_test_layout_fallback()
	_test_view()
	await _test_layout_resolutions()
	print("test_erg_view : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _test_banner() -> void:
	var vm = ErgViewModel.new()
	var e := _erg()
	var l := ErgView.banner_lines(e, vm.update(e, 0.0))
	_check(l["title"] == "Sweet spot 3x10 — Bloc 2 / 8 · Effort", "titre : nom, bloc i/n et type (%s)" % l["title"])
	_check(l["target"] == "225 W", "cible 225 W (%s)" % l["target"])
	_check(l["remaining"] == "2:30", "temps restant 2:30 (%s)" % l["remaining"])
	_check(l["next"] == "Ensuite : 138 W", "cible suivante (%s)" % l["next"])
	e = _erg({"bias_pct": 102, "target_w": 230.0})
	l = ErgView.banner_lines(e, vm.update(e, 1.0))
	_check(l["target"] == "230 W (102 %)", "biais affiché avec la cible (%s)" % l["target"])
	e = _erg({"block_index": 8, "block_type": "cooldown", "next_target_w": null})
	l = ErgView.banner_lines(e, vm.update(e, 2.0))
	_check(l["next"] == "" and l["title"].ends_with("Retour au calme"), "dernier bloc : pas de cible suivante")
	e = _erg({"next_target_w": null})
	l = ErgView.banner_lines(e, vm.update(e, 3.0))
	_check(l["next"] == "Ensuite : roue libre", "bloc suivant en roue libre")
	e = _erg({"paused": true})
	l = ErgView.banner_lines(e, vm.update(e, 4.0))
	_check(l["remaining"].ends_with("(pause)"), "pause signalée (%s)" % l["remaining"])


func _test_zones() -> void:
	# Seuils de session_summary.ZONES : 55, 75, 90, 105, 120, 150 % (borne haute exclue).
	var cases := [[0.30, 0], [0.549, 0], [0.55, 1], [0.749, 1], [0.75, 2], [0.90, 3], [1.05, 4], [1.20, 5], [1.50, 6], [2.5, 6]]
	var ok := true
	for c in cases:
		if ErgView.zone_of_frac(c[0]) != c[1]:
			ok = false
			printerr("zone de %.3f : %d au lieu de %d" % [c[0], ErgView.zone_of_frac(c[0]), c[1]])
	_check(ok, "zones de Coggan aux seuils de openride-core summary")
	_check(ErgView.zone_color(null) == ErgView.FREERIDE_COLOR, "roue libre en gris")


func _test_layout_profile() -> void:
	var vm = ErgViewModel.new()
	var e := _erg()
	var ev: Dictionary = vm.update(e, 0.0)
	var lay := ErgView.layout(e, ev, SWEET_SPOT, 250.0, 1200.0, 80.0)
	var bars: Array = lay["bars"]
	_check(lay["from_profile"] and bars.size() == 8, "profil : 8 barres")
	# Durée totale 3900 s : le bloc 2 commence à 600 s, soit x = 1200 × 600 / 3900.
	var x0 := 1200.0 * 600.0 / 3900.0
	var w := 1200.0 * 600.0 / 3900.0
	_check(absf(float(bars[1]["x0"]) - x0) < 0.01 and absf(float(bars[1]["width"]) - w) < 0.01, "largeur selon la durée")
	_check(bars[1]["current"] and not bars[0]["current"] and bars[0]["past"] and not bars[2]["past"], "bloc en cours et blocs faits")
	# 450 s écoulées sur 600 : curseur aux trois quarts du bloc 2.
	_check(absf(float(lay["cursor_x"]) - (x0 + 0.75 * w)) < 0.01, "curseur au temps écoulé (%.1f)" % lay["cursor_x"])
	_check(bars[1]["color"] == ErgView.ZONE_COLORS[3], "bloc à 90 % en zone 4")
	_check(bars[2]["color"] == ErgView.ZONE_COLORS[1], "récupération à 55 % en zone 2")
	_check(float(bars[1]["h0"]) > float(bars[2]["h0"]), "barre plus haute pour la cible la plus forte")
	# Une seconde plus tard (interpolation du modèle), le curseur avance de 1/3900 de la largeur.
	var ev2: Dictionary = vm.evaluate(1.0)
	var lay2 := ErgView.layout(e, ev2, SWEET_SPOT, 250.0, 1200.0, 80.0)
	var dx := float(lay2["cursor_x"]) - float(lay["cursor_x"])
	_check(absf(dx - 1200.0 / 3900.0) < 0.01, "curseur juste à la seconde (+%.3f px)" % dx)
	var free_prof := [[60, null, null], [60, 1.0, 1.0]]
	var lay3 := ErgView.layout(_erg({"block_index": 1, "block_count": 2, "block_type": "freeride"}), ev, free_prof, 250.0, 100.0, 50.0)
	_check(lay3["bars"][0]["color"] == ErgView.FREERIDE_COLOR, "bloc libre du profil en gris")


func _test_layout_fallback() -> void:
	var vm = ErgViewModel.new()
	var e := _erg()
	var ev: Dictionary = vm.update(e, 0.0)
	var lay := ErgView.layout(e, ev, null, 250.0, 800.0, 80.0)
	var bars: Array = lay["bars"]
	_check(not lay["from_profile"] and bars.size() == 8, "sans profil : 8 cases")
	_check(absf(float(bars[1]["x0"]) - 100.0) < 0.01 and absf(float(bars[1]["width"]) - 100.0) < 0.01, "cases égales")
	_check(absf(float(lay["cursor_x"]) - 175.0) < 0.01, "curseur dans la case en cours (%.1f)" % lay["cursor_x"])
	_check(bars[1]["color"] == ErgView.ZONE_COLORS[3], "case en cours colorée par la cible (225 W / 250 W)")
	var lay2 := ErgView.layout(e, ev, SWEET_SPOT.slice(0, 5), 250.0, 800.0, 80.0)
	_check(not lay2["from_profile"], "profil d'un autre nombre de blocs : repli")


func _test_view() -> void:
	var layer := CanvasLayer.new()
	root.add_child(layer)
	var view = ErgView.new()
	layer.add_child(view)
	var vm = ErgViewModel.new()
	view.update_display(null, vm.update(null, 0.0))
	_check(not view.visible, "SIM : bandeau caché")
	view.set_profiles([{"name": "Sweet spot 3x10", "profile": SWEET_SPOT, "profile_truncated": false},
			{"name": "Coupé", "profile": SWEET_SPOT, "profile_truncated": true}])
	_check(view.has_profile("Sweet spot 3x10") and not view.has_profile("Coupé"), "profil coupé ignoré")
	var e := _erg()
	view.ftp_w = 250.0
	view.update_display(e, vm.update(e, 0.0))
	_check(view.visible and view.target_label.text == "225 W", "ERG : bandeau visible, cible affichée")
	view.update_display(null, vm.update(null, 1.0))
	_check(not view.visible, "retour en SIM : bandeau caché")
	layer.queue_free()


func _test_layout_resolutions() -> void:
	for res in [Vector2i(1280, 720), Vector2i(1920, 1080)]:
		var vp := SubViewport.new()
		vp.size = res
		root.add_child(vp)
		var layer := CanvasLayer.new()
		vp.add_child(layer)
		var view = ErgView.new()
		layer.add_child(view)
		var vm = ErgViewModel.new()
		var e := _erg({"workout_name": "Un entraînement au nom vraiment très long pour la mise en page"})
		view.update_display(e, vm.update(e, 0.0))
		await process_frame
		await process_frame
		var r: Rect2 = view.get_global_rect()
		var screen := Rect2(Vector2.ZERO, Vector2(res))
		_check(screen.encloses(r) and r.size.x > 0.8 * res.x, "%dx%d : bandeau dans l'écran, toute la largeur (%s)" % [res.x, res.y, r])
		_check(r.end.y <= res.y - ErgView.BOTTOM_OFFSET + 0.5, "%dx%d : en bas de l'écran, profil d'altitude caché en ERG" % [res.x, res.y])
		r.size.y = 1000.0   # sans écran, la hauteur des textes est surestimée : seule la largeur compte
		var labels: Array = [view.title_label, view.target_label, view.remaining_label, view.next_label]
		var inside := true
		for l in labels:
			if not r.encloses((l as Control).get_global_rect()):
				inside = false
		_check(inside, "%dx%d : textes du bandeau dans le cadre" % [res.x, res.y])
		var narrow := false
		for l in labels:
			if (l as Control).get_global_rect().size.x < 20.0:
				narrow = true
		_check(not narrow, "%dx%d : titre long coupé, chiffres entiers" % [res.x, res.y])
		var hr: Rect2 = view.histogram.get_global_rect()
		# Hauteurs non vérifiées ici : sans écran, les métriques de police sont fausses (tests graphiques).
		_check(hr.size.x >= 0.8 * res.x and hr.size.y >= 50.0, "%dx%d : histogramme sur toute la largeur (%s)" % [res.x, res.y, hr])
		vp.queue_free()

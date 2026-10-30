extends SceneTree

## Tests sans écran de l'encart des bots du HUD (lot T15) : modèle bot_hud_model.gd (voisins marqués sur
## leur ligne, présents ou absents, bots sans champs de profil, FTP en W et en W/kg, réserve W′, maillots
## et porteurs, lignes qui tiennent autour du cycliste) et encart de hud_view.gd (lignes affichées, colonne
## de droite sans chevauchement, au-dessus du profil d'altitude ; lot X22 : en 720 lignes avec les blocs
## segment et bonus, les deux voisins avec maillot et W′ et la ligne des maillots).
## Lancement : godot --headless --path engine --script res://tests/unit/test_bot_hud_model.gd

const Model := preload("res://scripts/bot_hud_model.gd")
const BotsViewModel := preload("res://scripts/bots_view_model.gd")
const HudView := preload("res://scripts/hud_view.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _init() -> void:
	call_deferred("_run")


## Quatre bots à profil (révision 1.4) autour du cycliste à s = 1000 m.
func _profile_bots() -> Array:
	return [
		{"id": "b1", "name": "Grimpeur", "s": 1060.0, "v": 7.0, "kind": "constant", "profile": "climber",
			"cp_w": 248.0, "mass_kg": 60.0, "wbal_pct": 71.5, "jersey": "kom", "gap_s": 8.4},
		{"id": "b2", "name": "Rouleur", "s": 1010.0, "v": 7.0, "kind": "constant", "profile": "rouleur",
			"cp_w": 259.0, "mass_kg": 72.0, "wbal_pct": 100.0, "jersey": null, "gap_s": 1.2},
		{"id": "b3", "name": "Diesel", "s": 980.0, "v": 7.0, "kind": "constant", "profile": "diesel",
			"cp_w": 285.0, "mass_kg": 75.0, "wbal_pct": 0.0, "jersey": "sprint", "gap_s": -3.14},
		{"id": "b4", "name": "Bot 2", "s": 900.0, "v": 7.0, "kind": "constant", "profile": "sprinter",
			"cp_w": 264.0, "mass_kg": 80.0, "wbal_pct": 40.0, "jersey": null, "gap_s": -14.0},
	]


func _view(bots: Array) -> Array:
	var m = BotsViewModel.new()
	m.push(bots, 0)
	return m.view(1000.0, 7.0, 0)


func _run() -> void:
	_test_model()
	_test_race_fields()
	_test_fit()
	_test_hud()
	print("test_bot_hud_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _test_model() -> void:
	var bv := _view(_profile_bots())
	var v: Dictionary = Model.view(bv, {"bot_ahead": "b2", "bot_behind": "b3",
		"jerseys": {"sprint": "me", "kom": "b1"}})
	var rows: Array = v["rows"]
	_check(rows[1]["dir"] == "ahead" and rows[1]["name"] == "Rouleur" and rows[1]["gap_text"] == "+1,2 s",
		"voisin devant marqué sur sa ligne : %s" % str(rows[1]))
	_check(rows[2]["dir"] == "behind" and rows[2]["name"] == "Diesel" and rows[2]["gap_text"] == "−3,1 s",
		"voisin derrière marqué sur sa ligne : %s" % str(rows[2]))
	_check(rows[0]["dir"] == "" and rows[3]["dir"] == "" and v["rider_index"] == 2, "autres lignes sans triangle, cycliste en 3e place")
	_check(rows.size() == 4 and rows[0]["name"] == "Grimpeur" and rows[0]["detail"] == "248 W · 4,1 W/kg",
		"ligne du grimpeur : nom, FTP en W et en W/kg (%s)" % str(rows[0]))
	_check(is_equal_approx(rows[0]["wbal"], 0.715) and rows[0]["jersey"] == "kom" and rows[0]["gap_text"] == "+8,4 s",
		"ligne du grimpeur : réserve, maillot à pois, écart")
	_check(rows[3]["name"] == "Bot 2 · Sprinteur", "profil traduit ajouté quand il diffère du nom (%s)" % rows[3]["name"])
	_check(rows[2]["jersey"] == "sprint" and rows[2]["wbal"] == 0.0 and rows[1]["jersey"] == "", "maillot vert, réserve vide, sans maillot")
	_check(v["jerseys_text"] == "Vert : toi · Pois : Grimpeur", "porteurs des maillots : %s" % v["jerseys_text"])
	_check(v["visible"], "encart visible avec des bots")
	# Voisins absents : pas de triangle.
	v = Model.view(bv, {"bot_ahead": null, "bot_behind": "b3", "jerseys": null})
	_check(v["rows"].map(func(r): return r["dir"]) == ["", "", "behind", ""], "bot_ahead à null : un seul voisin marqué")
	_check(Model.view(bv, {"bot_ahead": "inconnu"})["rows"].all(func(r): return r["dir"] == ""), "voisin hors de la liste : aucun triangle")
	_check(Model.view(bv, {})["jerseys_text"] == "", "sans jerseys : pas de ligne des maillots")
	_check(Model.view(bv, {"jerseys": {"sprint": null, "kom": null}})["jerseys_text"] == "", "maillots sans porteur : pas de ligne")
	# Bots sans champs de profil (puissance constante, fantôme, core sans T12).
	var plain := _view([{"id": "c1", "name": "Bot 200 W", "s": 1100.0, "v": 7.0, "kind": "constant"},
		{"id": "g", "name": "Fantôme du 26/10", "s": 900.0, "v": 7.0, "kind": "ghost"}])
	var pr: Array = Model.view(plain, {})["rows"]
	_check(pr.size() == 2 and pr[0]["name"] == "Bot 200 W" and pr[0]["detail"] == "" and pr[0]["wbal"] == -1.0
		and pr[0]["jersey"] == "", "bot à puissance constante : nom et écart seulement (%s)" % str(pr[0]))
	_check(pr[0]["gap_text"] == "+14,3 s" and pr[1]["gap_text"] == "−14,3 s", "écarts calculés sans gap_s (%s, %s)" % [pr[0]["gap_text"], pr[1]["gap_text"]])
	_check(Model.ftp_text(250.0, null) == "250 W" and Model.ftp_text(null, 70.0) == "", "FTP sans masse, sans cp_w")
	_check(not Model.view([], {})["visible"], "sans bot : encart caché")


func _test_race_fields() -> void:
	var m = BotsViewModel.new()
	m.set_race({"bot_ahead": "b1", "jerseys": {"sprint": "me", "kom": null}, "s": 12.0})
	var race: Dictionary = m.race()
	_check(race.size() == 3 and race["bot_ahead"] == "b1" and race["bot_behind"] == null and race["jerseys"]["sprint"] == "me",
		"champs voisins et maillots gardés de la trame (%s)" % str(race))
	m.set_race(null)
	_check(m.race().is_empty(), "hors séance : rien")
	m.push(_profile_bots(), 0)
	var b: Dictionary = m.view(1000.0, 7.0, 0)[0]
	_check(b["profile"] == "climber" and b["cp_w"] == 248.0 and b["wbal_pct"] == 71.5 and b["jersey"] == "kom",
		"champs de profil transmis par bots_view_model")
	_check(b["color"] == BotsViewModel.PROFILE_COLOR and BotsViewModel.color_of("constant") != BotsViewModel.PROFILE_COLOR,
		"bot à profil (kind constant, contrat 1.4) : couleur du profil")
	m.push([{"id": "c", "name": "C", "s": 1.0, "v": 1.0, "kind": "constant"}], 0)
	b = m.view(0.0, 1.0, 0)[0]
	_check(b["profile"] == null and b["cp_w"] == null and b["jersey"] == null, "bot sans profil : champs à null")


func _test_fit() -> void:
	var v: Dictionary = Model.view(_view(_profile_bots()), {"bot_ahead": "b2", "bot_behind": "b3",
		"jerseys": {"sprint": "me", "kom": "b1"}})
	var full := Model.height(4, true)
	_check(Model.fit(v, full) == {"first": 0, "count": 4, "jerseys": true} and Model.fit(v, full + 500.0)["count"] == 4,
		"toutes les lignes tiennent")
	_check(Model.fit(v, full - 1.0) == {"first": 0, "count": 3, "jerseys": true}, "un pixel de moins : une ligne en moins, le plus loin derrière")
	_check(Model.fit(v, Model.height(2, true)) == {"first": 1, "count": 2, "jerseys": true},
		"place pour deux lignes : les deux voisins, puis les maillots")
	_check(Model.fit(v, 40.0) == {"first": 1, "count": 2, "jerseys": false}, "sans place : les deux voisins restent, sans maillots")
	_check(Model.window_start(0, 2, 4) == 0 and Model.window_start(4, 2, 4) == 2 and Model.window_start(2, 1, 4) == 1,
		"fenêtre au début, à la fin, ligne devant pour un compte impair")


func _test_hud() -> void:
	var hud = HudView.new()
	root.add_child(hud)
	var bv := _view(_profile_bots())
	hud.update_bots(bv, {"bot_ahead": "b2", "bot_behind": "b3", "jerseys": {"sprint": "me", "kom": "b1"}})
	_check(hud.panel_bots.visible and hud.neighbor_line("ahead") == hud.bots_lines[1]
		and hud.neighbor_line("behind") == hud.bots_lines[2] and hud.bots_gaps[2].text == "−3,1 s"
		and not hud.bots_arrows[0].visible, "HUD : triangles des voisins sur leurs lignes")
	_check(hud.bots_lines[0].text == "Grimpeur  248 W · 4,1 W/kg" and hud.bots_gaps[0].text == "+8,4 s"
		and hud.bots_jerseys[0].visible and hud.bots_kom_dots[0].visible and hud.bots_wbal_bg[0].visible,
		"HUD : ligne du grimpeur (%s)" % hud.bots_lines[0].text)
	_check(hud.bots_lines[3].visible and not hud.bots_lines[4].visible, "HUD : quatre lignes de bots")
	_check(hud.jerseys_label.visible and hud.jerseys_label.text == "Vert : toi · Pois : Grimpeur", "HUD : porteurs des maillots")
	var right: Rect2 = hud.panel_right.get_rect()
	var bots: Rect2 = hud.panel_bots.get_rect()
	var prof: Rect2 = hud.profile_panel.get_rect()
	var bottom: float = maxf(hud.get_viewport().get_visible_rect().size.y, 720.0) - HudView.SCREEN_BOTTOM
	_check(prof.position.y >= right.end.y and bots.position.y >= prof.end.y and bots.end.y <= bottom,
		"profil sous le panneau de droite, encart sous le profil et dans l'écran (%s, %s)" % [prof, bots])
	# Blocs segment et bonus affichés en 720 lignes : l'encart descend, les lignes de bots qui ne tiennent plus
	# sont cachées.
	root.size = Vector2i(1280, 720)
	bottom = 720.0 - HudView.SCREEN_BOTTOM
	hud.update_segment({"segment": {"mode": "active", "title": "Montée 1", "main": "1:02", "detail": "", "tone": ""},
		"powerup": {"visible": true, "held_text": "Z : Aéro", "active_text": "", "fraction": 0.0}})
	var seg: Rect2 = hud.panel_segment.get_rect()
	var bonus: Rect2 = hud.panel_bonus.get_rect()
	bots = hud.panel_bots.get_rect()
	_check(not seg.intersects(bonus) and not bonus.intersects(bots) and bots.position.y >= bonus.end.y,
		"colonne de droite empilée sans chevauchement (%s, %s, %s)" % [seg, bonus, bots])
	# Blocs réduits à HudView.BLOCK_SCALE (28/10) : les quatre lignes tiennent de nouveau sous les blocs.
	var shown: int = hud.bots_lines.filter(func(l): return l.visible).size()
	_check(shown == 4 and hud.neighbor_line("ahead") != null
		and hud.neighbor_line("behind") != null and hud.jerseys_label.visible
		and hud.panel_bots.get_global_rect().end.y <= bottom + 0.5,
		"720 lignes, segment et bonus : voisins et maillots, encart au-dessus du profil (%d lignes, encart %s)" % [shown, hud.panel_bots.get_global_rect()])
	_check(bots.end.y <= bottom, "encart au-dessus du profil (%s)" % bots)
	_check(hud.panel_segment.size.y < 100.0 and hud.panel_bonus.size.y < 72.0,
		"blocs à la hauteur de leur contenu (segment %.0f, bonus %.0f px)" % [hud.panel_segment.size.y, hud.panel_bonus.size.y])
	# Sans voisin ni bot.
	hud.update_bots(_view([{"id": "c1", "name": "Bot 200 W", "s": 1100.0, "v": 7.0, "kind": "constant"}]), {})
	_check(not hud.bots_arrows[0].visible and not hud.jerseys_label.visible and not hud.bots_wbal_bg[0].visible
		and not hud.bots_jerseys[0].visible, "bot sans profil : ni voisin, ni maillot, ni jauge")
	hud.update_bots([], {})
	_check(not hud.panel_bots.visible, "sans bot : encart caché")
	hud.queue_free()

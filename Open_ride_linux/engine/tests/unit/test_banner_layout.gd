extends SceneTree

## Placement du bandeau (banner.gd, layout_for) : à droite du HUD s'il reste la place,
## sinon dessous ; jamais par-dessus le HUD. Défaut trouvé par les tests graphiques (visual_check.py).

const Banner := preload("res://scripts/banner.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	_run()
	print("test_banner_layout : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _banner_rect(hud: Rect2, width: float) -> Rect2:
	var pos := Banner.layout_for(hud, width)
	return Rect2(pos["left"], pos["top"], width - Banner.MARGIN - float(pos["left"]), 40.0)


func _run() -> void:
	var narrow_hud := Rect2(20, 20, 300, 197)
	var pos := Banner.layout_for(narrow_hud, 1280.0)
	_check(pos["left"] == 340.0 and pos["top"] == 20.0, "HUD étroit, 1280 px : à droite du HUD (%s)" % pos)
	var wide_hud := Rect2(20, 20, 493, 197)
	pos = Banner.layout_for(wide_hud, 1280.0)
	_check(pos["left"] == 533.0 and pos["top"] == 20.0, "HUD élargi, 1280 px : décalé à droite (%s)" % pos)
	var erg_hud := Rect2(20, 20, 700, 226)
	pos = Banner.layout_for(erg_hud, 1024.0)
	_check(pos["left"] == 20.0 and pos["top"] == 256.0, "HUD ERG, 1024 px : sous le HUD (%s)" % pos)
	# Limite : exactement MIN_WIDTH de place à droite.
	var edge := Rect2(20, 20, 1280.0 - 20.0 - Banner.MIN_WIDTH - 20.0 - 20.0, 197)
	pos = Banner.layout_for(edge, 1280.0)
	_check(pos["top"] == 20.0, "place exacte de MIN_WIDTH : encore à droite")
	edge.size.x += 1.0
	pos = Banner.layout_for(edge, 1280.0)
	_check(pos["top"] > edge.end.y, "un pixel de moins : sous le HUD")
	for w in [800.0, 1024.0, 1280.0, 1920.0, 3840.0]:
		for hud_w in [300.0, 500.0, 700.0, 900.0]:
			var hud := Rect2(20, 20, hud_w, 226)
			var r := _banner_rect(hud, w)
			_check(not r.intersects(hud) and r.size.x > 0.0,
				"%d px, HUD de %d px : pas de recouvrement, largeur %d" % [w, hud_w, r.size.x])

	# Ton du bandeau (28/10) : rouge seulement pour une alerte, fond des panneaux du HUD sinon.
	var b = Banner.new()
	b.show_message("controls", "Click : Y = pause")
	var info: StyleBoxFlat = b.get_theme_stylebox("normal")
	_check(not b.is_alert() and info.bg_color == Banner.UiTheme.PANEL_BG, "rappel des boutons : bandeau d'information")
	b.show_message("core_lost", "Core non joignable")
	var alert: StyleBoxFlat = b.get_theme_stylebox("normal")
	_check(b.is_alert() and alert.bg_color == Banner.UiTheme.BANNER_ALERT, "core perdu : bandeau rouge, même avec le rappel")
	b.clear_message("core_lost")
	_check(not b.is_alert(), "alerte effacée : retour au bandeau d'information")
	b.free()

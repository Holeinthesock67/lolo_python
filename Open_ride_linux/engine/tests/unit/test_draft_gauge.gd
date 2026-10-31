extends SceneTree

## Tests unitaires sans écran de la jauge d'abri au-dessus des bots (`draft_gauge_model.gd`, `draft_gauge.gd`,
## réglage `render.draft_gauge`, maquette C validée le 29 octobre).
## Vérifie : cachée réglage coupé, sans abri, sous 5 % ou sans `draft_bot` ; même pourcentage que la pastille
## « Abri » du HUD ; texte en medium et high seulement, halo en high seulement ; posée au-dessus du bot qui
## abrite, cachée quand ce bot n'est pas affiché ; choix du réglage affiché « oui » / « non ».
## Lancement : godot --headless --path engine --script res://tests/unit/test_draft_gauge.gd

const DraftGaugeModel := preload("res://scripts/draft_gauge_model.gd")
const DraftGauge := preload("res://scripts/draft_gauge.gd")
const BotsView := preload("res://scripts/bots_view.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const WindViewModel := preload("res://scripts/wind_view_model.gd")
const SettingsViewModel := preload("res://scripts/settings_view_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _test_model() -> void:
	_check(not DraftGaugeModel.view(false, 0.165, "bot1", "medium")["visible"], "réglage coupé : cachée")
	_check(not DraftGaugeModel.view(true, null, "bot1", "medium")["visible"], "sans `draft` : cachée")
	_check(not DraftGaugeModel.view(true, 0.165, null, "medium")["visible"], "sans `draft_bot` : cachée")
	_check(not DraftGaugeModel.view(true, 0.01, "bot1", "medium")["visible"], "abri sous 5 % : cachée, comme la pastille")
	var v := DraftGaugeModel.view(true, 0.165, "bot1", "medium")
	_check(v["visible"] and v["bot"] == "bot1" and v["pct"] == 30 and is_equal_approx(v["fill"], 0.3),
		"abri 0,165 : 30 %% et arc rempli à 30 %% (%s)" % str(v))
	var pill: String = WindViewModel.new().view({"draft": 0.165}, 0.0, 0.0)["draft_text"]
	_check(pill == "Abri %d %%" % v["pct"], "même pourcentage que la pastille du HUD (%s)" % pill)
	_check(v["text"] == "30 %" and not v["glow"], "medium : texte, sans halo")
	var low := DraftGaugeModel.view(true, 0.165, "bot1", "low")
	_check(low["visible"] and low["text"] == "" and not low["glow"], "low : arc seul")
	var high := DraftGaugeModel.view(true, 0.165, "bot1", "high")
	_check(high["text"] == "30 %" and high["glow"], "high : texte et halo")
	_check(is_equal_approx(DraftGaugeModel.view(true, 0.6, "bot1", "low")["fill"], 1.0), "abri au-delà du plafond : arc plein")
	var item := {"key": DraftGaugeModel.SETTING_KEY, "type": "choice", "choices": ["off", "on"]}
	_check(SettingsViewModel.format_value(item, "on") == "oui" and SettingsViewModel.format_value(item, "off") == "non",
		"réglage affiché « oui » / « non »")


func _test_view() -> void:
	var bots = BotsView.new()
	root.add_child(bots)
	var route = FlatRoute.new()
	bots.update_view([{"id": "bot1", "name": "Bot 250 W", "kind": "constant", "s": 20.0, "lateral": RoadBuilder.BOT_LATERAL_M, "visible": true,
		"show_name": true}], route)
	var gauge = DraftGauge.new()
	root.add_child(gauge)
	_check(not gauge.visible, "cachée à la création")
	var v := DraftGaugeModel.view(true, 0.165, "bot1", "high")
	var anchor = bots.anchor_of("bot1")
	_check(anchor is Vector3, "position du bot affiché connue")
	gauge.update_view(v, anchor)
	_check(gauge.visible and gauge.global_position.is_equal_approx(anchor + Vector3.UP * DraftGauge.HEIGHT_M),
		"posée au-dessus du bot (%s)" % str(gauge.global_position))
	_check(gauge.test_info(null)["text"] == "30 %", "texte « 30 % » sous l'arc")
	_check(bots.anchor_of("absent") == null, "bot non affiché : pas de position")
	gauge.update_view(v, null)
	_check(not gauge.visible, "bot non affiché : jauge cachée")
	gauge.update_view(DraftGaugeModel.view(false, 0.165, "bot1", "high"), anchor)
	_check(not gauge.visible, "réglage coupé : jauge cachée")
	gauge.queue_free()
	bots.queue_free()


## Route droite le long de x pour poser les silhouettes (route_data.gd réduit à sample/wrap_s).
class FlatRoute:
	func wrap_s(s: float) -> float:
		return s

	func sample(s: float) -> Dictionary:
		return {"x": s, "y": 0.0, "z": 0.0, "heading_deg": 0.0}


func _run() -> void:
	_test_model()
	_test_view()
	print("test_draft_gauge : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _init() -> void:
	call_deferred("_run")

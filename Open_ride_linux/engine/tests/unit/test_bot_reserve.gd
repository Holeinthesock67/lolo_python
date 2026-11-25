extends SceneTree

## Tests sans écran de la jauge de réserve W′ des bots dans les modes compétitifs (lot RW) : règle unique
## (bot_reserve.gd, la même que l'encart des bots de la session libre), lignes des modèles du Dernier survivant,
## du Grand Prix, de la Course et du vélodrome (`wbal` de 0 à 1, −1 sans barre : cycliste, éliminé, bot loin
## sans `wbal_pct`), barres dessinées par les vues et légende écrite « Trait bleu : réserve des bots ».
## Lancement : godot --headless --path engine --script res://tests/unit/test_bot_reserve.gd

const BotReserve := preload("res://scripts/bot_reserve.gd")
const BotHudModel := preload("res://scripts/bot_hud_model.gd")
const SurvivorModel := preload("res://scripts/survivor/survivor_hud_model.gd")
const SurvivorView := preload("res://scripts/survivor/survivor_view.gd")
const GpModel := preload("res://scripts/grandprix/gp_hud_model.gd")
const GpView := preload("res://scripts/grandprix/gp_view.gd")
const TrackModel := preload("res://scripts/track/track_hud_model.gd")
const TrackView := preload("res://scripts/track/track_view.gd")

var _failures := 0
var _checked := 0

## Trois bots à profil : deux proches avec `wbal_pct`, un loin allégé par le core (bots.light_frame), sans.
const BOTS := [
	{"id": "bot1", "name": "Grimpeur", "s": 1080.0, "v": 9.0, "kind": "constant", "profile": "climber",
		"wbal_pct": 72.4, "gap_s": 8.0},
	{"id": "bot2", "name": "Rouleur", "s": 990.0, "v": 9.0, "kind": "constant", "profile": "rouleur",
		"wbal_pct": 0.0, "gap_s": -1.1},
	{"id": "bot3", "name": "Diesel", "s": 400.0, "v": 9.0, "kind": "constant", "profile": "diesel"},
]


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _init() -> void:
	call_deferred("_run")


func _near(a: float, b: float) -> bool:
	return absf(a - b) < 0.001


func _by_name(rows: Array, key: String) -> Dictionary:
	var out := {}
	for r in rows:
		out[str(r[key])] = float(r.get("wbal", -2.0))
	return out


func _run() -> void:
	# Règle unique
	_check(_near(BotReserve.fraction({"wbal_pct": 50}), 0.5), "règle : 50 % → 0,5")
	_check(_near(BotReserve.fraction({"wbal_pct": 140.0}), 1.0) and _near(BotReserve.fraction({"wbal_pct": -3.0}), 0.0),
		"règle : bornée de 0 à 1")
	_check(BotReserve.fraction({}) < 0.0 and BotReserve.fraction({"wbal_pct": null}) < 0.0 and BotReserve.fraction(null) < 0.0,
		"règle : sans champ, pas de barre")
	var ids := BotReserve.by_id(BOTS)
	_check(ids.size() == 2 and _near(float(ids["bot1"]), 0.724) and _near(float(ids["bot2"]), 0.0), "by_id : bots proches seulement")
	_check(_near(float(BotHudModel.row(BOTS[0])["wbal"]), BotReserve.fraction(BOTS[0])),
		"encart de la session libre : même règle")
	_check(BotReserve.any_shown([{"wbal": -1.0}, {"wbal": 0.0}]) and not BotReserve.any_shown([{"wbal": -1.0}, {}]),
		"légende : seulement avec une barre")

	# Dernier survivant
	var sm = SurvivorModel.new()
	var sv := {"arch": 2, "arches": 4, "d_m": 650.0, "alive": ["bot1", "me", "bot2", "bot3"], "last": "bot3",
		"out": [["bot4", 1]], "winner": null}
	sm.remember_names(BOTS + [{"id": "bot4", "name": "Sprinteur"}])
	var srows: Array = sm.list_rows(sv, BOTS, 1000.0, 9.0)
	var sw := _by_name(srows, "name")
	_check(_near(sw["Grimpeur"], 0.724) and _near(sw["Rouleur"], 0.0), "Dernier survivant : réserve des bots proches")
	_check(sw["Toi"] < 0.0 and sw["Diesel"] < 0.0 and sw["Sprinteur"] < 0.0,
		"Dernier survivant : pas de barre pour toi, le bot loin et l'éliminé")

	# Grand Prix des objets et Course (même bande)
	var gm = GpModel.new()
	gm.remember_bots(BOTS)
	var gp := {"place": 2, "of": 4, "gap_s": 8.0, "lap": [1, 3], "lane": 1}
	var gw := _by_name(gm.strip_rows(gp, BOTS, 1000.0, 9.0), "name")
	_check(_near(gw["Grimpeur"], 0.724) and _near(gw["Rouleur"], 0.0) and gw["Toi"] < 0.0 and gw["Diesel"] < 0.0,
		"Grand Prix : réserve sur la bande de course")
	var race := gp.duplicate()
	race["mode"] = "race"
	var rv: Dictionary = gm.view({"s": 1000.0, "v": 9.0, "bots": BOTS, "gp": race}, 0.0)
	var rw := _by_name(rv["strip"], "name")
	_check(bool(rv.get("race", false)) and _near(rw["Grimpeur"], 0.724) and rw["Toi"] < 0.0 and rw["Diesel"] < 0.0,
		"Course : réserve sur la bande de course")

	# Vélodrome
	var tm = TrackModel.new()
	var tr := {"event": "scratch", "lap": 3, "laps": 20, "laps_to_go": 17, "bell": false,
		"ranking": ["bot1", "me", "bot2", "bot3"], "points": null, "eliminated": [], "finished": false}
	var tv: Dictionary = tm.view({"s": 1000.0, "bots": BOTS, "track": tr})
	var tw := _by_name(tv["list"]["rows"], "name")
	_check(_near(tw["Grimpeur"], 0.724) and _near(tw["Rouleur"], 0.0) and tw["Toi"] < 0.0 and tw["Diesel"] < 0.0,
		"vélodrome : réserve sur la liste")
	var el := tr.duplicate()
	el["event"] = "elimination"
	el["eliminated"] = ["bot2"]
	var ew := _by_name(tm.view({"s": 1000.0, "bots": BOTS, "track": el})["list"]["rows"], "name")
	_check(ew["Rouleur"] < 0.0, "vélodrome : pas de barre pour un sorti")

	# Vues : barres dessinées et légende écrite
	var svw = SurvivorView.new()
	get_root().add_child(svw)
	sm.after_out = "ride"
	svw.update_view(sm.view({"session_state": "RUNNING", "s": 1000.0, "v": 9.0, "bots": BOTS, "survivor": sv}, 0.0))
	await process_frame
	var si: Dictionary = svw.test_info()
	_check(si["reserve"].size() == si["list"].size() and _near(float(si["reserve"][0]), 0.724), "vue Dernier survivant : barre du premier")
	_check(si["reserve_legend"], "vue Dernier survivant : légende écrite")
	svw.update_view(sm.view({"session_state": "RUNNING", "s": 1000.0, "v": 9.0, "bots": [BOTS[2]], "survivor": sv}, 0.0))
	await process_frame
	_check(not svw.test_info()["reserve_legend"], "vue Dernier survivant : pas de légende sans barre")
	svw.queue_free()

	for spec in [["Grand Prix", gp], ["Course", race]]:
		var gvw = GpView.new()
		get_root().add_child(gvw)
		gvw.update_view(GpModel.new().view({"s": 1000.0, "v": 9.0, "bots": BOTS, "gp": spec[1]}, 0.0))
		await process_frame
		var gi: Dictionary = gvw.test_info()
		var at: int = gi["strip"].find("Grimpeur")
		_check(at >= 0 and _near(float(gi["reserve"][at]), 0.724) and float(gi["reserve"][gi["strip"].find("Toi")]) < 0.0,
			"vue %s : barre du bot, pas pour toi" % spec[0])
		_check(gi["reserve_legend"] and gi["strip_bottom"] < 720.0, "vue %s : légende, bande dans l'écran (%.0f)" % [spec[0], gi["strip_bottom"]])
		gvw.queue_free()

	# Plateau complet (11 bots, 5 proches avec réserve) : la bande et la liste tiennent dans l'écran de base
	var many: Array = []
	for i in range(11):
		var b := {"id": "b%d" % i, "name": "Bot %d" % i, "s": 1300.0 - 50.0 * i, "v": 9.0, "kind": "constant"}
		if i >= 3 and i < 8:
			b["wbal_pct"] = 10.0 * i
		many.append(b)
	var g12 = GpView.new()
	get_root().add_child(g12)
	g12.update_view(GpModel.new().view({"s": 1000.0, "v": 9.0, "bots": many, "gp": {"place": 7, "of": 12}}, 0.0))
	await process_frame
	var g12i: Dictionary = g12.test_info()
	_check(g12i["strip"].size() == 12 and g12i["strip_bottom"] < 720.0,
		"vue Grand Prix à 12 : bande, barres et légende dans l'écran (%.0f)" % g12i["strip_bottom"])
	g12.queue_free()

	var tvw = TrackView.new()
	get_root().add_child(tvw)
	tvw.update_view(tv)
	await process_frame
	var ti: Dictionary = tvw.test_info()
	_check(_near(float(ti["reserve"][0]), 0.724) and float(ti["reserve"][1]) < 0.0, "vue vélodrome : barre du bot, pas pour toi")
	_check(ti["reserve_legend"], "vue vélodrome : légende écrite")
	tvw.queue_free()

	print("test_bot_reserve : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

extends SceneTree

## « Ma forme » dans « Ma puissance » (lot FO1, objet `fitness` du message `power_curve`) : ligne de la liste,
## carte avec condition, fatigue et fraîcheur en mots, courbe nommée (trait plein, pointillé), aucun watt.
## Valeurs fictives. Lancement : godot --headless --path engine --script res://tests/unit/test_fitness_menu.gd

const Power := preload("res://scripts/power_view_model.gd")
const DetailCard := preload("res://scripts/detail_card.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if not cond:
		_failures += 1
		printerr("ÉCHEC : " + msg)


func _fitness() -> Dictionary:
	var ctl: Array = []
	var atl: Array = []
	for i in range(42):
		ctl.append(20 + i / 2)
		atl.append(18 + i)
	return {"days": 84, "step_days": 2, "ctl": ctl, "atl": atl, "weeks": [1, 2, 0, 1, 2, 2, 1, 0, 2, 2, 1, 2],
		"ctl_now": 40.4, "atl_now": 59.2, "form": -18.8, "trend": "up", "weeks_up": 4, "label": "fatigue",
		"label_text": "un peu fatigué, une séance légère aide"}


func _init() -> void:
	var pv = Power.new()
	pv.on_power_curve({"type": "power_curve", "ftp_set_w": 250, "sessions": {"m6": 9, "w6": 4},
		"points": [{"s": 5, "m6": {"w": 880, "e": "libre", "d": "2026-10-28", "r": null, "k": null}, "w6": null}],
		"fitness": _fitness()})
	var ids: Array = pv.items({}).map(func(it): return str(it["id"]))
	_check(Power.FITNESS_ID in ids and ids.find(Power.FITNESS_ID) < ids.find("d:5"), "ligne « Ma forme » avant les durées")
	var row: Dictionary = pv.fitness_row()
	_check(row["label"] == "Ma forme : un peu fatigué" and row["detail"] == "condition 40, en hausse",
		"ligne en mots (%s · %s)" % [row["label"], row["detail"]])
	var card: Dictionary = pv.card(Power.FITNESS_ID, {})
	_check(card["title"] == "MA FORME" and card["name"] == "12 dernières semaines", "carte : titre et période")
	_check(card["tiles"].map(func(t): return t["label"]) == ["Condition", "Fatigue", "Fraîcheur"]
		and card["tiles"][2]["value"] == "-19", "tuiles condition, fatigue, fraîcheur")
	var lines: Array = card["lines"]
	_check(lines[0] == "Condition 40, en hausse depuis 4 semaines. Fatigue 59.", "tendance en mots (%s)" % lines[0])
	_check(lines[1] == "Fraîcheur -19 : un peu fatigué, une séance légère aide.", "fraîcheur en mots (%s)" % lines[1])
	_check(lines[2] == "10 semaines sur 12 avec au moins une séance.", "semaines régulières (%s)" % lines[2])
	_check(Power.FITNESS_LEGEND in lines, "légende écrite : le trait et le mot, pas la couleur")
	_check(not " ".join(PackedStringArray(lines)).contains(" W") and not card.has("curve"), "aucun watt, pas la courbe de puissance")
	var dc = DetailCard.new()
	dc.update_display(card)
	_check(dc.chart_kind() == "fitness", "la carte dessine la courbe de forme")
	dc.free()
	# core sans `fitness` (ou profil sans séance) : pas de ligne
	var empty = Power.new()
	empty.on_power_curve({"type": "power_curve", "points": [], "fitness": null})
	_check(empty.fitness().is_empty() and not (Power.FITNESS_ID in empty.items({}).map(func(it): return str(it["id"]))),
		"sans objet fitness : pas de ligne")
	var stable = Power.new()
	var fit := _fitness()
	fit["trend"] = "flat"
	fit["form"] = 6.0
	fit["label_text"] = "frais, prêt pour un gros effort"
	stable.on_power_curve({"type": "power_curve", "ftp_set_w": 250, "sessions": {"m6": 1, "w6": 1},
		"points": [{"s": 5, "m6": {"w": 500, "e": "libre", "d": "2026-11-20", "r": null, "k": null}, "w6": null}], "fitness": fit})
	_check(stable.fitness_row()["label"] == "Ma forme : frais" and stable.fitness_lines()[0].begins_with("Condition 40, stable.")
		and stable.fitness_lines()[1].begins_with("Fraîcheur +6 :"), "forme stable et fraîche")
	print("test_fitness_menu : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

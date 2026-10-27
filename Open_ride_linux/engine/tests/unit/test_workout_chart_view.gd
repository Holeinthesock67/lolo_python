extends SceneTree

## Tests sans écran de la vue des courbes de la séance (workout_chart_view.gd, lot O14) :
## légende par taille, repli du mode, remplacement de l'histogramme ERG, profil retrouvé par nom.
## Lancement : godot --headless --path engine --script res://tests/unit/test_workout_chart_view.gd

const ChartView := preload("res://scripts/workout_chart_view.gd")
const ChartModel := preload("res://scripts/workout_chart_model.gd")
const ErgView := preload("res://scripts/erg_view.gd")

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


func _run() -> void:
	# Légende : puissance seule en taille réduite, avec FC et cadence en taille complète ; trou = tiret.
	var cur := {"power": 231.6, "hr": 141.2, "cadence": 88.4}
	var reduced := ChartView.legend(cur, "reduced")
	_check(reduced.size() == 1 and reduced[0]["text"] == "232 W", "taille réduite : puissance seule (%s)" % str(reduced))
	var full := ChartView.legend(cur, "full")
	_check(full.size() == 3 and full[1]["text"] == "141 bpm" and full[2]["text"] == "88 rpm", "taille complète : W, bpm, rpm")
	var holes := ChartView.legend({"power": null, "hr": null, "cadence": null}, "full")
	_check(holes[0]["text"] == "—" and holes[1]["text"] == "—" and holes[2]["text"] == "—", "valeurs absentes : tiret")
	_check(full[0]["color"] != full[1]["color"] and full[1]["color"] != full[2]["color"], "une couleur par courbe")

	# Mode : valeur inconnue -> taille réduite ; trois tailles connues.
	var v = ChartView.new()
	_check(ChartView.MODES == ["hidden", "reduced", "full"], "trois tailles : hidden, reduced, full")
	v.set_mode("full")
	_check(v.mode == "full", "mode full pris")
	v.set_mode("énorme")
	_check(v.mode == "reduced", "mode inconnu : taille réduite")
	v.free()

	# ERG : le graphique remplace l'histogramme, sauf en « hidden » ; profil retrouvé par nom.
	var erg = ErgView.new()
	var items := [{"name": "Sweet spot 3x10", "profile": [[600, 0.5, 0.75], [600, 0.9, 0.9]], "profile_truncated": false},
		{"name": "Coupé", "profile": [[60, 0.5, 0.5]], "profile_truncated": true}]
	erg.set_profiles(items)
	_check(erg.profile_of("Sweet spot 3x10").size() == 2, "profil retrouvé par nom")
	_check(erg.profile_of("Coupé").is_empty() and erg.profile_of("Inconnu").is_empty(), "profil coupé ou inconnu : vide")
	var m = ChartModel.new()
	var chart = ChartView.new()
	chart.model = m
	erg.set_chart(chart, "full")
	_check(erg.chart == chart and chart.visible and not erg.histogram.visible, "full : courbes visibles, histogramme replié")
	erg.set_chart(null, "hidden")
	_check(not chart.visible and erg.histogram.visible, "hidden : histogramme de N7 de retour")
	erg.set_chart(null, "reduced")
	_check(chart.visible and not erg.histogram.visible and chart.mode == "reduced", "reduced : courbes visibles")
	_check(chart.get_parent() == erg.histogram.get_parent(), "courbes dans le bandeau, à côté de l'histogramme")
	erg.free()

	print("test_workout_chart_view : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)

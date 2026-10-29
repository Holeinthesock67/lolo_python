extends SceneTree

## Tests unitaires sans écran de la gigue des trames state reçues (lot X17, `ipc_client.gd`) :
## histogramme des écarts (p50, p99, maximum), une ligne « [gigue] » par minute puis remise à zéro.
## Lancement : godot --headless --path engine --script res://tests/unit/test_state_gap.gd

const IpcClientScript := preload("res://scripts/ipc_client.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _run() -> void:
	var c = IpcClientScript.new()   # sans _ready : aucun port ouvert
	var t := 1_000_000
	# 98 écarts de 33 ms, un de 60 ms, un de 120 ms.
	for i in 98:
		t += 33_000
		c.note_state_gap(33.4, t)
	c.note_state_gap(60.0, t + 60_000)
	c.note_state_gap(120.0, t + 180_000)
	_check(c.state_gap_percentile(0.5) == 34.0, "p50 : case de 33 ms (borne haute 34) : %.1f" % c.state_gap_percentile(0.5))
	_check(c.state_gap_percentile(0.99) == 61.0, "p99 : l'écart de 60 ms (borne haute 61) : %.1f" % c.state_gap_percentile(0.99))
	_check(c._gap_max_ms == 120.0, "maximum exact : %.1f" % c._gap_max_ms)
	_check(c.state_gap_line() == "[gigue] state : écart entre trames p50 34.0 p99 61.0 max 120.0 ms (100 trames)",
		"ligne du journal : « %s »" % c.state_gap_line())
	# Fin de la minute : ligne publiée, compteurs remis à zéro.
	c.note_state_gap(700.0, 1_000_000 + 61_000_000)
	_check(c._gap_n == 0 and c._gap_max_ms == 0.0, "remise à zéro après la ligne de la minute")
	_check(c.state_gap_percentile(0.99) == 0.0, "aucun écart : quantile nul")
	c.free()


func _initialize() -> void:
	_run()
	print("test_state_gap : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

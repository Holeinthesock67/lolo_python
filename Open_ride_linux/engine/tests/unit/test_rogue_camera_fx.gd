extends SceneTree

## Tests sans écran des effets de caméra du Cyber-Rogue (lot R11) : champ de vision 75° → 95° en sprint,
## retour en 1 s, tremblement de 0,05 m sur 0,2 s, coupé par « réduire les mouvements ».
## Lancement : godot --headless --path engine --script res://tests/unit/test_rogue_camera_fx.gd

const CameraFx := preload("res://scripts/rogue/rogue_camera_fx.gd")

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
	var fx = CameraFx.new()
	_check(is_equal_approx(fx.fov_deg(), 75.0) and fx.shake_offset() == Vector3.ZERO, "repos : 75°, pas de secousse")
	for i in 20:
		fx.update(0.05, 150.0, [])
	_check(is_equal_approx(fx.fov_deg(), 95.0), "sprint à 150 % : 95°")
	fx.update(0.5, 100.0, [])
	_check(is_equal_approx(fx.fov_deg(), 85.0), "retour : 10° en 0,5 s")
	fx.update(0.5, 100.0, [])
	_check(is_equal_approx(fx.fov_deg(), 75.0), "retour complet en 1 s")
	fx.update(0.05, 139.0, [])
	_check(is_equal_approx(fx.fov_deg(), 75.0), "139 % : pas de sprint")

	fx.update(0.01, 100.0, ["hit"])
	var amp := 0.0
	for i in 8:
		amp = maxf(amp, fx.shake_offset().length())
		fx.update(0.02, 100.0, [])
	_check(amp > 0.0 and amp <= 0.05 * 1.5, "secousse au plus 0,05 m par axe")
	fx.update(0.1, 100.0, [])
	_check(fx.shake_offset() == Vector3.ZERO, "secousse finie après 0,2 s")
	fx.update(0.01, 100.0, ["firewall_contact"])
	_check(fx.shake_offset() == Vector3.ZERO, "événement sans secousse")

	fx.reduce_motion = true
	fx.update(0.01, 200.0, ["perfect_shift"])
	_check(fx.shake_offset() == Vector3.ZERO and is_equal_approx(fx.fov_deg(), 75.0), "réduire les mouvements : ni secousse ni champ de vision large")

	print("test_rogue_camera_fx : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

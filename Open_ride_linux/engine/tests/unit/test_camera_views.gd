extends SceneTree

## Tests sans écran des vues de caméra (lot V12) : passage en boucle, vue par défaut, sans avatar, placements,
## pente, transition de moins de 0,5 s, mémorisation et journal de chaque changement.
## Lancement : godot --headless --path engine --script res://tests/unit/test_camera_views.gd

const CameraViews := preload("res://scripts/camera_views.gd")
const EngineArgs := preload("res://scripts/engine_args.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _test_cycle() -> void:
	var v = CameraViews.new()
	_check(v.current == "follow_near" and v.effective() == "follow_near", "vue par défaut : suivi proche avec avatar")
	var seen: Array = []
	for i in range(4):
		v.next_view()
		seen.append(v.current)
	_check(seen == ["follow_far", "side", "subjective", "follow_near"], "A court / flèche haut : quatre vues en boucle : %s" % str(seen))
	v.previous_view()
	_check(v.current == "subjective", "flèche bas : vue précédente")
	v.previous_view()
	v.previous_view()
	v.previous_view()
	v.previous_view()
	_check(v.current == "subjective", "quatre vues précédentes : retour à la même")
	_check(v.reset_default() and v.current == "follow_near", "A long : retour à la vue par défaut")
	_check(not v.reset_default(), "A long déjà sur la vue par défaut : rien")
	_check(not v.set_view("drone") and v.current == "follow_near", "vue inconnue refusée")
	_check(v.set_view("side") and v.current == "side" and not v.set_view("side"), "choix d'une vue (réglage)")
	for name in CameraViews.VIEWS:
		_check(CameraViews.is_valid(name), "vue valide : " + name)


func _test_no_avatar() -> void:
	var v = CameraViews.new()
	v.has_avatar = false
	_check(v.effective() == "subjective", "sans avatar : vue subjective (2.0-CAM-3)")
	_check(not v.next_view() and not v.previous_view() and not v.reset_default(), "sans avatar : pas de changement de vue")
	_check(v.effective() == "subjective", "sans avatar : toujours subjective")
	v.has_avatar = true
	_check(v.effective() == "follow_near", "l'avatar arrive : suivi proche")


func _test_placement() -> void:
	var v = CameraViews.new()
	var pos := Vector3(10.0, 5.0, -20.0)
	var heading := deg_to_rad(90.0)   # cap est : l'avant est +X
	v.set_view("subjective")
	var g: Transform3D = v.goal(pos, heading, 0.0)
	_check(g.origin.is_equal_approx(pos + Vector3(0.0, 1.4, 0.0)), "subjective : yeux à 1,4 m")
	var fwd: Vector3 = -g.basis.z
	_check(fwd.is_equal_approx(Vector3(1.0, 0.0, 0.0)), "subjective : regarde vers l'avant : %s" % str(fwd))
	v.set_view("follow_near")
	g = v.goal(pos, heading, 0.0)
	_check(g.origin.is_equal_approx(pos + Vector3(-4.0, 1.8, 0.0)), "suivi proche : 4 m derrière, 1,8 m de haut : %s" % str(g.origin))
	var dir: Vector3 = (-g.basis.z)
	_check(absf(dir.dot((Vector3(pos.x + 10.0, pos.y + 1.0, pos.z) - g.origin).normalized()) - 1.0) < 1e-4, "suivi proche : regard 10 m devant")
	v.set_view("follow_far")
	g = v.goal(pos, heading, 0.0)
	_check(g.origin.is_equal_approx(pos + Vector3(-12.0, 6.0, 0.0)) and (-g.basis.z).y < 0.0, "suivi éloigné : 12 m derrière, 6 m de haut, regard vers le bas")
	v.set_view("side")
	g = v.goal(pos, heading, 0.0)
	var right := Vector3(cos(heading), 0.0, sin(heading))
	_check(g.origin.is_equal_approx(pos + right * 8.0 + Vector3(0.0, 1.6, 0.0)), "latérale : à 8 m de la route : %s" % str(g.origin))
	var to_rider: Vector3 = (pos - g.origin).normalized()
	_check((-g.basis.z).dot(to_rider) > 0.9, "latérale : le cycliste reste au centre")
	# pente (Q2) : en montée de 10°, la caméra de suivi est plus basse que le cycliste ne le laisse supposer à plat
	v.set_view("follow_near")
	var flat: Transform3D = v.goal(pos, heading, 0.0)
	var climb: Transform3D = v.goal(pos, heading, 10.0)
	_check(climb.origin.y < flat.origin.y and (-climb.basis.z).y > (-flat.basis.z).y, "montée : suivi plus bas et regard relevé (pente sur toutes les vues)")
	v.set_view("subjective")
	_check(absf((-v.goal(pos, heading, 10.0).basis.z).y - sin(deg_to_rad(10.0 * CameraViews.CAMERA_PITCH_FOLLOW))) < 1e-4,
		"subjective : tangage partiel de la pente (lot Y15)")


func _test_transition() -> void:
	var v = CameraViews.new()
	var pos := Vector3.ZERO
	var heading := 0.0
	var a: Transform3D = v.step(0.016, v.goal(pos, heading, 0.0))
	_check(a.origin.is_equal_approx(v.goal(pos, heading, 0.0).origin) and not v.in_transition(), "première image : placement direct")
	v.next_view(1.0)
	var target: Transform3D = v.goal(pos, heading, 0.0)
	var p1: Transform3D = v.step(0.1, target)
	_check(v.in_transition() and not p1.origin.is_equal_approx(target.origin) and not p1.origin.is_equal_approx(a.origin), "pendant la transition : pose intermédiaire")
	var t := 0.1
	var guard := 0
	while v.in_transition() and guard < 100:
		v.step(0.016, target)
		t += 0.016
		guard += 1
	_check(t < 0.5 and t >= 0.38, "transition de moins de 0,5 s : %.2f s" % t)
	_check(v.step(0.016, target).origin.is_equal_approx(target.origin), "après la transition : pose visée")
	# pose visée qui bouge pendant la transition : pas de saut à l'arrivée
	var w = CameraViews.new()
	w.step(0.016, w.goal(Vector3.ZERO, 0.0, 0.0))
	w.next_view(0.0)
	var prev: Transform3D = w.step(0.016, w.goal(Vector3(0, 0, 0), 0.0, 0.0))
	var worst := 0.0
	for i in range(40):
		var moving: Transform3D = w.goal(Vector3(0, 0, -0.15 * (i + 1)), 0.0, 0.0)
		var cur: Transform3D = w.step(0.016, moving)
		worst = maxf(worst, cur.origin.distance_to(prev.origin))
		prev = cur
	_check(worst < 0.8, "pas d'à-coup : plus grand déplacement d'une image à l'autre %.2f m" % worst)
	# reprise après un menu
	v.snap()
	v.next_view()
	var s := v.step(0.016, v.goal(Vector3(50, 0, 50), 0.0, 0.0))
	_check(not v.in_transition() and s.origin.is_equal_approx(v.goal(Vector3(50, 0, 50), 0.0, 0.0).origin), "snap : pas de glissement depuis l'ancienne pose")


func _test_remember() -> void:
	var v = CameraViews.new()
	_check(not v.remember_due(100.0), "rien à mémoriser avant un changement")
	v.next_view(10.0)
	_check(not v.remember_due(11.0), "trop tôt pour écrire la vue")
	v.next_view(11.5)
	_check(not v.remember_due(13.0), "le délai repart à chaque changement")
	_check(v.remember_due(13.6), "vue à mémoriser 2 s après le dernier changement")
	_check(not v.remember_due(20.0), "une seule écriture")


func _test_log() -> void:
	var v = CameraViews.new()
	v.has_avatar = false
	_check(v.log_line() == "Vue de caméra : subjective (sans avatar)", "journal : vue de départ sans avatar")
	_check(v.log_line() == "", "journal : rien tant que la vue affichée ne change pas")
	v.has_avatar = true
	_check(v.log_line() == "Vue de caméra : follow_near (départ)", "journal : l'avatar arrive, vue affichée changée")
	v.next_view(1.0, "UP_SHORT")
	_check(v.log_line() == "Vue de caméra : follow_far (UP_SHORT)", "journal : flèche haut")
	v.previous_view(2.0, "DOWN_SHORT")
	_check(v.log_line() == "Vue de caméra : follow_near (DOWN_SHORT)", "journal : flèche bas")
	v.set_view("side", -1.0, "message de test")
	v.set_view("follow_near")
	_check(v.log_line() == "", "journal : aller-retour entre deux images, vue affichée inchangée")
	v.set_view("side")
	_check(v.log_line() == "Vue de caméra : side (réglage)", "journal : réglage render.camera")
	v.has_avatar = false
	_check(v.log_line() == "Vue de caméra : subjective (sans avatar)", "journal : avatar perdu, retour à la subjective")


func _test_args() -> void:
	var cfg: Dictionary = EngineArgs.parse(PackedStringArray(["--camera=side"]))
	_check(cfg["camera"] == "side", "--camera=side")
	cfg = EngineArgs.parse(PackedStringArray([]))
	_check(cfg["camera"] == "follow_near", "défaut : suivi proche")
	cfg = EngineArgs.parse(PackedStringArray(["--camera=drone"]))
	_check(cfg["camera"] == "follow_near" and EngineArgs.last_error != "", "vue inconnue : ignorée avec un message")


func _init() -> void:
	_test_cycle()
	_test_no_avatar()
	_test_placement()
	_test_transition()
	_test_remember()
	_test_log()
	_test_args()
	print("test_camera_views : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

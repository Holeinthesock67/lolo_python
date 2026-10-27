extends SceneTree

## Tests sans écran des blocs « segment » et « bonus » du HUD (lot T9) : modèle segment_hud_model.gd
## (approche, chrono, écart au record, résultat et doublons, bonus en réserve et actif, ERG) et blocs de
## hud_view.gd (visibles, cachés sans champ, sans chevauchement du panneau de droite).
## Lancement : godot --headless --path engine --script res://tests/unit/test_segment_hud_model.gd

const Model := preload("res://scripts/segment_hud_model.gd")
const HudView := preload("res://scripts/hud_view.gd")

const SEGMENTS := [
	{"id": "climb2", "name": "Montée 2", "type": "climb", "category": "3"},
	{"id": "sprint1", "name": "Sprint du village", "type": "sprint", "category": null},
]

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


func _seg(extra: Dictionary) -> Dictionary:
	var seg := {"id": "climb2", "kind": "climb", "category": "3", "d_to_start_m": 0.0, "elapsed_s": null,
		"gap_to_pr_s": null}
	seg.merge(extra, true)
	return {"segment": seg}


func _run() -> void:
	var m = Model.new()
	m.set_segments(SEGMENTS)
	# Approche
	var v: Dictionary = m.view(_seg({"d_to_start_m": 1200.0}), 0.0)["segment"]
	_check(v["mode"] == "approach" and v["title"] == "Montée 2 · cat. 3 dans 1,2 km", "approche : %s" % v["title"])
	v = m.view(_seg({"d_to_start_m": 450.0}), 0.0)["segment"]
	_check(v["title"].ends_with("dans 450 m"), "approche sous 1 km en mètres (%s)" % v["title"])
	_check(m.view(_seg({"d_to_start_m": 2500.0}), 0.0)["segment"]["mode"] == "", "au-delà de 2 km : bloc caché")
	# Dans le segment
	v = m.view(_seg({"elapsed_s": 83.4, "gap_to_pr_s": -3.24}), 0.0)["segment"]
	_check(v["mode"] == "active" and v["main"] == "1:23" and v["detail"] == "−3,2 s" and v["tone"] == "good",
		"chrono et écart négatif en vert (%s)" % str(v))
	v = m.view(_seg({"elapsed_s": 12.0, "gap_to_pr_s": 1.8}), 0.0)["segment"]
	_check(v["detail"] == "+1,8 s" and v["tone"] == "bad", "écart positif en rouge (%s)" % v["detail"])
	v = m.view(_seg({"elapsed_s": 12.0}), 0.0)["segment"]
	_check(v["detail"] == "" and v["tone"] == "", "sans record : pas d'écart")
	var sprint: Dictionary = {"segment": {"id": "sprint1", "kind": "sprint", "category": null, "d_to_start_m": 800.0,
		"elapsed_s": null, "gap_to_pr_s": null}}
	_check(m.view(sprint, 0.0)["segment"]["title"] == "Sprint du village dans 800 m", "nom lu dans la couche segments")
	var unknown := {"segment": {"id": "x9", "kind": "sprint", "category": null, "d_to_start_m": 300.0}}
	_check(m.view(unknown, 0.0)["segment"]["title"] == "Sprint dans 300 m", "segment inconnu : nom du type")
	# Résultat et doublons
	var msg := {"type": "segment_result", "segment_id": "climb2", "name": "Montée 2", "kind": "climb",
		"time_s": 248.07, "with_powerup": false, "pr": true, "pr_time_s": 251.5, "rank": 2, "rank_total": 5,
		"points": 3, "equipment_gain_s": null}
	_check(m.on_result(msg, 10.0) and not m.on_result(msg, 11.0) and not m.on_result(msg, 12.0),
		"segment_result répété 3 fois : affiché une fois")
	v = m.view(_seg({"d_to_start_m": 900.0}), 15.0)["segment"]
	_check(v["mode"] == "result" and v["main"] == "4:08,1" and v["detail"] == "Record ! Ancien : 4:11,5 · 2 / 5 · +3 pts",
		"résultat : temps, record, place et points (%s / %s)" % [v["main"], v["detail"]])
	_check(m.view(_seg({"d_to_start_m": 900.0}), 18.5)["segment"]["mode"] == "approach", "résultat affiché 8 s")
	var lap2 := msg.duplicate()
	lap2["time_s"] = 252.0
	lap2["pr"] = false
	_check(m.on_result(lap2, 30.0), "passage suivant (autre temps) : nouveau résultat")
	_check(m.view({}, 31.0)["segment"]["detail"] == "2 / 5 · +3 pts", "sans record : place et points")
	# Bonus
	var none: Dictionary = m.view({}, 40.0)["powerup"]
	_check(not none["visible"], "ERG ou option coupée (pas de champ powerup) : bloc bonus caché")
	var held: Dictionary = m.view({"powerup": {"held": "aero", "active": null, "remaining_s": 0.0}}, 40.0)["powerup"]
	_check(held["visible"] and held["held_text"] == "Z : Aéro" and held["active_text"] == "", "réserve : « Z : Aéro »")
	_check(not m.view({"powerup": {"held": null, "active": null, "remaining_s": 0.0}}, 40.0)["powerup"]["visible"],
		"ni réserve ni bonus actif : bloc caché")
	var on: Dictionary = m.view({"powerup": {"held": null, "active": "light", "remaining_s": 15.0}}, 41.0)["powerup"]
	_check(on["active_text"] == "Légèreté · 15 s" and is_equal_approx(on["fraction"], 1.0), "bonus actif plein")
	on = m.view({"powerup": {"held": "power", "active": "light", "remaining_s": 7.5}}, 48.0)["powerup"]
	_check(is_equal_approx(on["fraction"], 0.5) and on["held_text"] == "Z : Puissance" and on["active_text"] == "Légèreté · 8 s",
		"barre de temps à moitié, nouvelle réserve affichée (%s)" % str(on))
	_check(Model.time_text(3725.0) == "62:05" and Model.time_text(59.96, true) == "1:00,0", "format des temps")
	_hud_blocks(m)
	print("test_segment_hud_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _hud_blocks(m) -> void:
	var hud = HudView.new()
	root.add_child(hud)
	hud.update_segment(m.view({}, 100.0))
	_check(not hud.panel_segment.visible and not hud.panel_bonus.visible, "trame sans segment ni powerup : HUD d'aujourd'hui")
	hud.update_segment(m.view(_seg({"elapsed_s": 20.0, "gap_to_pr_s": -1.0}), 100.0)
		.merged({"powerup": {"visible": true, "held_text": "Z : Aéro", "active_text": "", "fraction": 0.0}}, true))
	_check(hud.panel_segment.visible and hud.segment_main.text == "0:20" and hud.panel_bonus.visible
		and hud.bonus_held.text == "Z : Aéro", "blocs segment et bonus affichés")
	var right: Rect2 = hud.panel_right.get_rect()
	var seg_rect: Rect2 = hud.panel_segment.get_rect()
	var bonus_rect: Rect2 = hud.panel_bonus.get_rect()
	_check(not right.intersects(seg_rect) and not seg_rect.intersects(bonus_rect) and seg_rect.position.y >= right.end.y,
		"blocs empilés sous le panneau de droite, sans chevauchement (%s, %s, %s)" % [right, seg_rect, bonus_rect])
	hud.queue_free()

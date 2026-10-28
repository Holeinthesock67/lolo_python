extends SceneTree

## Tests sans écran du bilan de progression de fin de séance (lot V9) : modèle (progress_view_model.gd) et
## déroulé dans les menus (menu_flow.gd : xp_result, bandeau de niveau, accès au Garage).
## Lancement : godot --headless --path engine --script res://tests/unit/test_progress_view_model.gd

const ProgressViewModel := preload("res://scripts/progress_view_model.gd")
const MenuFlow := preload("res://scripts/menu_flow.gd")

const SIM := {"eligible": true, "reason": null,
	"gains": [{"source": "distance", "points": 302}, {"source": "climb", "points": 302}],
	"total": 604, "xp_total": 1200, "xp_next_level": 1500, "level_before": 9, "level_after": 9,
	"coins_gained": 42, "coins_total": 232, "equipment_gain_s": -12.5, "unlocked": [], "challenges": [], "more": false}

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _values(v: Dictionary) -> Dictionary:
	var out := {}
	for ln in v["lines"]:
		out[ln["label"]] = ln["value"]
	return out


func _test_model() -> void:
	var m = ProgressViewModel.new()
	_check(m.view({}).is_empty() and m.view(null).is_empty(), "sans message : {} (bilan de N4 seul)")
	var v: Dictionary = m.view(SIM, {"distance_m": 30200.0, "elevation_gain_m": 412.4})
	var vals := _values(v)
	_check(vals.get("Distance 30,2 km") == "+302 XP" and vals.get("Dénivelé 412 m") == "+302 XP", "SIM : distance et dénivelé : %s" % str(vals))
	_check(vals.get("Total") == "+604 XP" and vals.get("Pièces") == "+42 (solde 232)", "total et pièces")
	_check(vals.get("Équipement") == "−12,5 s sur la séance", "temps de l'équipement : gagné")
	_check(v["bar"]["text"] == "Niveau 9 : ■■■■■■■■□□ 1200 / 1500 XP", "barre : %s" % v["bar"]["text"])
	_check(is_equal_approx(v["bar"]["before"], 596.0 / 1500.0) and is_equal_approx(v["bar"]["after"], 0.8), "barre : de avant à après")
	_check(v["level_up"] == "" and not v["garage"], "pas de montée de niveau")
	var s := SIM.duplicate(true)
	s["equipment_gain_s"] = null
	_check(not _values(m.view(s)).has("Équipement"), "temps de l'équipement absent si null")
	s["equipment_gain_s"] = 8.0
	_check(_values(m.view(s))["Équipement"] == "+8,0 s sur la séance", "temps de l'équipement : perdu")
	# ERG terminé
	var e := SIM.duplicate(true)
	e["gains"] = [{"source": "erg", "points": 400}, {"source": "erg_bonus", "points": 50}]
	e["total"] = 450
	var ev := _values(m.view(e))
	_check(ev.get("Entraînement terminé") == "+400 XP" and ev.get("Bonus d'entraînement") == "+50 XP", "ERG : entraînement terminé et bonus")
	# séance refusée
	for reason in ["too_short", "replay", "simulated", "imported"]:
		var r: Dictionary = m.view({"eligible": false, "reason": reason})
		_check(r["lines"].size() == 1 and r["lines"][0]["label"].contains("pas d'expérience") and r["bar"].is_empty(), "refusée (%s) : une ligne" % reason)
	_check(m.view({"eligible": false, "reason": "autre"})["lines"][0]["label"] == "Séance sans expérience", "refusée, motif inconnu")
	# montée de niveau, déblocages, défis
	var u := SIM.duplicate(true)
	u.merge({"level_before": 9, "level_after": 10, "xp_total": 100, "xp_next_level": 1600, "total": 604,
		"unlocked": ["f_aero", "inconnu"], "challenges": [{"id": "c1", "name": "Tour du lac", "reward_item": "f_aero"}], "more": true}, true)
	var names := {"f_aero": {"name": "Profilé", "slot": "frame"}}
	var uv: Dictionary = m.view(u, {}, names)
	_check(uv["level_up"] == "Niveau 10 !" and uv["bar"]["before"] == 0.0, "niveau 10 : annonce, barre repart de zéro")
	_check(uv["unlocked"] == ["Débloqué : cadre Profilé", "Débloqué : inconnu"], "déblocages nommés : %s" % str(uv["unlocked"]))
	_check(uv["challenges"] == ["Défi réussi : Tour du lac — cadre Profilé"] and uv["more"] != "" and uv["garage"], "défi, suite et accès au Garage")
	# niveau maximal
	var x := SIM.duplicate(true)
	x["xp_next_level"] = null
	var xv: Dictionary = m.view(x)
	_check(xv["bar"]["max"] and xv["bar"]["text"] == "Niveau maximal", "niveau maximal : pas de seuil suivant")
	_check(ProgressViewModel.signed_seconds(0.0) == "−0,0 s" and ProgressViewModel.bar_text(1.0) == "■■■■■■■■■■", "aides de format")


func _ids(f) -> Array:
	return f.state()["items"].map(func(it): return it["id"])


func _new_session(f) -> void:
	f.menu.focus_item("new_session")
	f.handle("A_LONG")


func _test_flow() -> void:
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "IDLE"})
	f.on_hello_progression({"level": 9, "xp": 1200, "xp_next_level": 1500, "coins": 232, "equipped": {}, "avatar": {}})
	_check(f.on_xp_result(SIM) == "" and f.xp_result.is_empty(), "xp_result hors FINISHED : ignoré")
	f.on_state({"session_state": "FINISHED", "summary": {"duration_s": 1800.0, "distance_m": 30200.0}})
	_check(f.state()["screen"] == "summary" and not f.state().has("progress") or f.state()["progress"].is_empty(), "bilan sans xp_result : pas de bloc")
	_check(f.on_xp_result(SIM) == "" and not f.state()["progress"].is_empty(), "xp_result reçu : bloc affiché, pas de bandeau")
	_check(not ("garage" in _ids(f)), "sans pièce débloquée : pas d'accès au Garage")
	var up := SIM.duplicate(true)
	up.merge({"level_before": 9, "level_after": 10, "unlocked": ["f_aero"]}, true)
	f.on_state({"session_state": "IDLE"})
	f.on_state({"session_state": "FINISHED", "summary": {"duration_s": 1800.0}})
	_check(f.on_xp_result(up) == "Niveau 10 !", "montée de niveau : texte du bandeau")
	_check(f.on_xp_result(up) == "", "répétition du message : bandeau une seule fois")
	_check(f.state()["progress"]["level_up"] == "Niveau 10 !", "bloc toujours affiché après répétition")
	f.on_state({"session_state": "IDLE"})
	_check(f.xp_result.is_empty(), "retour à l'accueil : bilan effacé")
	f.on_state({"session_state": "FINISHED", "summary": {}})
	_new_session(f)
	_check(f.on_xp_result(up) == "" and f.xp_result.is_empty(), "après « nouvelle séance » : message tardif ignoré")


func _init() -> void:
	_test_model()
	_test_flow()
	print("test_progress_view_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

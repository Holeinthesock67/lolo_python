extends SceneTree

## Tests sans écran des retours du Cyber-Rogue (lot R23, contrat révision 1.17) : un retour pour chaque Z court
## (accepté avec son action, refusé avec sa raison, selon la phase), anneau et son du Z, surchauffe dite à l'écran
## (avant et pendant), consigne en plage en endurance, tendance de l'adrénaline, pavé de la vitesse, vue sur le vélo.
## Lancement : godot --headless --path engine --script res://tests/unit/test_rogue_r23_retours.gd

const GuideModel := preload("res://scripts/rogue/rogue_guide_model.gd")
const HudModel := preload("res://scripts/rogue/rogue_hud_model.gd")
const HudView := preload("res://scripts/rogue/rogue_hud_view.gd")
const SoundModel := preload("res://scripts/rogue/rogue_sound_model.gd")
const Synth := preload("res://scripts/rogue/rogue_sound_synth.gd")
const RogueScene := preload("res://scripts/rogue/rogue_scene.gd")

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


func _rogue(over: Dictionary = {}) -> Dictionary:
	var r := {"phase": "ROOM", "room_id": 3, "room_index": 2, "rooms_total": 9, "archetype": "diesel",
		"boss_phase": null, "s_room": 500.0, "adrenaline": 32.0, "firewall_gap_m": 96.0, "firewall_gap_s": 12.0,
		"hack": null, "events": [], "phase_left_s": null, "next": [], "loot_stage": null, "overheat": false,
		"target_pct": {"lo": 70, "hi": 75}, "z_reason": null, "z_action": null, "shift_miss": null,
		"adrenaline_trend": {"rate_per_s": 0.5, "cause": "gain", "overheat_in_s": null}}
	r.merge(over, true)
	return r


func _run() -> void:
	var g = GuideModel.new()
	var st := {"route_length_m": 1120.0, "v": 8.0}

	# Z accepté : un retour immédiat par action, et l'anneau or.
	for action in ["strike", "charges", "rock", "rock_chip", "parry", "purge", "reroll"]:
		_check(GuideModel.Z_ACTION_TEXT.has(action), "texte de l'action « %s »" % action)
	g.compute(st, _rogue({"z_action": "strike"}), 72.0, ["hit", "z_ok"])
	var t: Array = g.take_toasts()
	_check(t.size() == 1 and t[0]["title"] == "FRAPPE ! −6 % PV" and t[0]["tone"] == "ok" and t[0]["now"], "Z accepté : « FRAPPE ! », tout de suite")
	_check(g.z_pulse == "ok", "Z accepté : anneau or")
	g.z_pulse = ""
	g.compute(st, _rogue({"z_action": "rock_chip"}), 72.0, ["z_ok"])
	_check(g.take_toasts()[0]["title"] == "Rocher entamé", "rocher entamé")

	# Z refusé : raison, selon la phase pour « rien à frapper ».
	g.compute(st, _rogue({"phase": "WARMUP", "phase_left_s": 252.0, "z_reason": "no_target"}), 60.0, ["z_refused"])
	t = g.take_toasts()
	_check(t[0]["title"] == "Z : pas encore de cible" and t[0]["sub"] == "Z sert en salle · première salle dans 4:12",
		"échauffement : Z sert en salle, première salle dans 4:12")
	_check(g.z_pulse == "refused", "Z refusé : anneau rouge")
	g.compute(st, _rogue({"phase": "COOLDOWN", "phase_left_s": 30.0, "z_reason": "no_target"}), 40.0, ["z_refused"])
	_check(g.take_toasts()[0]["title"] == "Z : la run est finie", "retour au calme : la run est finie")
	g.compute(st, _rogue({"z_reason": "no_target"}), 72.0, ["z_refused"])
	_check(g.take_toasts()[0]["title"] == "Z : rien à frapper ici", "en salle : rien à frapper ici")

	# Endurance : consigne en plage, alerte avant la surchauffe, bandeau pendant.
	var o: Dictionary = g.compute(st, _rogue(), 72.0, [])
	_check(o["fw"]["sub"] == "Garde 70–75 % FTP", "Firewall : garde 70–75 % FTP")
	_check(o["adr_trend"] == "▲ +0,5/s", "tendance : ▲ +0,5/s")
	o = g.compute(st, _rogue({"adrenaline_trend": {"rate_per_s": 0.5, "cause": "gain", "overheat_in_s": 2.4}}), 80.0, [])
	_check(o["hint"] == "Trop fort : au-dessus de 75 % FTP, surchauffe dans 3 s" and o["tone"] == "warn", "alerte : surchauffe dans 3 s")
	o = g.compute(st, _rogue({"overheat": true, "adrenaline": 60.0,
		"adrenaline_trend": {"rate_per_s": -2.0, "cause": "overheat", "overheat_in_s": null}}), 85.0, [])
	_check(o["hint"] == "SURCHAUFFE : descends sous 75 % FTP · adrénaline −2/s, Z bloqué" and o["tone"] == "danger", "surchauffe : bandeau rouge et sortie")
	_check(o["adr_trend"] == "▼ −2/s surchauffe", "tendance : ▼ −2/s surchauffe")
	_check(o["keys"][0][2] == "off" and o["keys"][0][1] == "frapper (bloqué : surchauffe)", "surchauffe : Z grisé, bloqué")
	o = g.compute(st, _rogue({"adrenaline_trend": {"rate_per_s": 0.0, "cause": "below", "overheat_in_s": null}}), 50.0, [])
	_check(o["adr_trend"] == "= sous la cible" and o["hint"].begins_with("Tiens 70–75 % FTP"), "sous la cible : stable, consigne en plage")
	_check(GuideModel.target_band(95, null) == "≥ 95 % FTP" and GuideModel.target_band(70, 75) == "70–75 % FTP", "consigne : ouverte ou en plage")
	_check(GuideModel.adrenaline_trend_text({"phase": "ROOM"}) == "", "sans le champ (core ancien) : pas de tendance")

	o = g.compute(st, _rogue({"hack": {"locked": true, "forced_gear": null, "until_s": 99.0}}), 72.0, [])
	_check(o["keys"][0] == ["Z", "purger (sur la balise)", "on"], "piratage : le bouton Z dit « purger »")

	# Légende de la surchauffe à la première salle d'endurance.
	var g2 = GuideModel.new()
	g2.compute(st, _rogue({"firewall_gap_m": 150.0}), 72.0, [])
	var leg: Array = g2.take_legend()
	_check(leg.size() == 2 and leg[0] == "Nouveau : surchauffe (endurance)", "légende de la surchauffe une fois")
	g2.compute(st, _rogue({"firewall_gap_m": 150.0}), 72.0, [])
	_check(g2.take_legend().is_empty(), "légende de la surchauffe pas répétée")

	# Modèle du HUD : vitesse engagée et anneau une seule fois.
	var hm = HudModel.new()
	hm.set_ftp(250.0)
	hm.update({"seq": 1, "gear": 7, "gears_total": 12, "power_3s": 180.0, "rogue": _rogue({"phase": "CORRIDOR", "events": ["z_ok"], "z_action": "reroll"})}, 0.0)
	var v: Dictionary = hm.values()
	_check(v["gear"] == 7 and v["gears_total"] == 12, "HUD : vitesse 7 sur 12 au couloir")
	_check(v["z_pulse"] == "ok", "HUD : anneau du Z de la trame")
	hm.update({"seq": 1, "gear": 7, "power_3s": 180.0, "rogue": _rogue({"phase": "CORRIDOR", "events": ["z_ok"], "z_action": "reroll"})}, 0.1)
	_check(hm.values()["z_pulse"] == "", "HUD : trame renvoyée (même seq), pas d'anneau rejoué")

	# Vue : pavé VITESSE allumé au changement, anneau, nom de la vue.
	var view = HudView.new()
	root.add_child(view)
	await process_frame
	hm.update({"seq": 2, "gear": 7, "power_3s": 180.0, "rogue": _rogue()}, 0.2)
	view.apply(hm.values(), Vector3.ZERO, 0.016)
	_check(view.gear_panel.visible and view.gear_value.text == "07" and view.gear_flash_s == 0.0, "pavé VITESSE 07, sans éclat au premier affichage")
	hm.update({"seq": 3, "gear": 8, "power_3s": 180.0, "rogue": _rogue()}, 0.3)
	view.apply(hm.values(), Vector3.ZERO, 0.016)
	_check(view.gear_value.text == "08" and view.gear_flash_s > 0.0, "changement de vitesse : 08, le pavé s'allume")
	view.pulse("refused")
	_check(view.z_pulse.left_s > 0.0 and view.z_pulse.color == view.UiTheme.DANGER, "anneau rouge au refus")
	view.push_feedback([{"title": "a", "sub": "", "tone": "info"}, {"title": "b", "sub": "", "tone": "info"}], [])
	view.apply(hm.values(), Vector3.ZERO, 0.016)
	view.push_feedback([{"title": "FRAPPE ! −6 % PV", "sub": "", "tone": "ok", "now": true}], [])
	view.apply(hm.values(), Vector3.ZERO, 0.016)
	_check(view.toast_title.text == "FRAPPE ! −6 % PV", "retour du Z affiché tout de suite, devant ceux en attente")
	view.show_view_name("sur le vélo")
	view.apply(hm.values(), Vector3.ZERO, 0.016)
	_check(view.view_label.visible and view.view_label.text == "Vue : sur le vélo", "nom de la vue affiché")
	view.queue_free()

	# Sons : Z accepté a le sien, prioritaire comme le refus.
	_check(SoundModel.EVENT_SOUNDS.get("z_ok", "") == "rogue_z_ok" and Synth.names().has("rogue_z_ok"), "son du Z accepté")
	_check(int(SoundModel.PRIORITY["rogue_z_ok"]) > int(SoundModel.PRIORITY["rogue_perfect_shift"])
		and SoundModel.PRIORITY["rogue_refused"] == SoundModel.PRIORITY["rogue_z_ok"], "réponse à Z au-dessus du Perfect Shift")
	var sm = SoundModel.new()
	sm.update(_rogue({"events": ["hit", "z_ok"]}), 6, 1, 1.0)
	var plays: Array = sm.take_plays()
	_check(plays.has("rogue_z_ok") and plays.has("rogue_hit"), "frappe : son du Z et impact")

	# Vues du mode : 4, la dernière sur le vélo.
	_check(RogueScene.VIEW_NAMES == ["derrière", "haute", "proche", "sur le vélo"] and RogueScene.RIDER_VIEW == 3, "4 vues, la 4e sur le vélo")
	_check(float(RogueScene.VIEWS[3][1]) == 1.4, "vue sur le vélo : yeux à 1,4 m")

	print("test_rogue_r23_retours : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

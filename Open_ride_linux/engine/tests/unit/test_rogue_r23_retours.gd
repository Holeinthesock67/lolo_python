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
const SummaryModel := preload("res://scripts/summary_view_model.gd")

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
		"target_pct": {"lo": 70, "hi": 75}, "z_reason": null, "z_action": null, "card_on": null, "shift_miss": null,
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
	_check(g.z_pulse == "hit", "attaque réussie : anneau or et éclair")
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
	_check(o["fw"]["sub"] == "Garde 70–75 % FTP · ✔ dans la plage", "Firewall : garde 70–75 % FTP, dans la plage")
	_check(o["adr_trend"] == "▲ +0,5/s", "tendance : ▲ +0,5/s")
	o = g.compute(st, _rogue({"adrenaline_trend": {"rate_per_s": 0.5, "cause": "gain", "overheat_in_s": 2.4}}), 80.0, [])
	_check(o["hint"] == "Trop fort : au-dessus de 75 % FTP, surchauffe dans 3 s" and o["tone"] == "warn", "alerte : surchauffe dans 3 s")
	o = g.compute(st, _rogue({"adrenaline_trend": {"rate_per_s": 0.5, "cause": "gain", "overheat_in_s": 0.0}}), 80.0, [])
	_check(o["hint"].ends_with("surchauffe dans 1 s"), "alerte : jamais « dans 0 s »")
	o = g.compute(st, _rogue({"overheat": true, "adrenaline": 60.0,
		"adrenaline_trend": {"rate_per_s": -2.0, "cause": "overheat", "overheat_in_s": null}}), 85.0, [])
	_check(o["hint"] == "SURCHAUFFE : descends sous 75 % FTP · adrénaline −2/s, Z bloqué" and o["tone"] == "danger", "surchauffe : bandeau rouge et sortie")
	_check(o["adr_trend"] == "▼ −2/s surchauffe", "tendance : ▼ −2/s surchauffe")
	_check(o["keys"][0][2] == "off" and o["keys"][0][1] == "frapper (bloqué : surchauffe)", "surchauffe : Z grisé, bloqué")
	o = g.compute(st, _rogue({"adrenaline_trend": {"rate_per_s": 0.0, "cause": "below", "overheat_in_s": null}}), 50.0, [])
	_check(o["adr_trend"] == "= sous la cible" and o["hint"].begins_with("Monte dans la plage"), "sous la cible : stable, plage écrite une seule fois (R28)")
	_check(GuideModel.target_band(95, null) == "≥ 95 % FTP" and GuideModel.target_band(70, 75) == "70–75 % FTP", "consigne : ouverte ou en plage")
	_check(GuideModel.adrenaline_trend_text({"phase": "ROOM"}) == "", "sans le champ (core ancien) : pas de tendance")

	o = g.compute(st, _rogue({"hack": {"locked": true, "forced_gear": null, "until_s": 99.0}}), 72.0, [])
	_check(o["keys"][0] == ["Z", "débloquer (sur la borne)", "on"], "piratage : le bouton Z dit « débloquer »")

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

	# Carte déclenchée (seuil de puissance ou de cadence atteint) : message, anneau vert et son.
	var g3 = GuideModel.new()
	g3.compute(st, _rogue({"card_on": "overdrive"}), 72.0, ["card_on"])
	t = g3.take_toasts()
	_check(t.size() == 1 and t[0]["title"] == "OVERDRIVE !" and t[0]["sub"] == "Dégâts ×2 pendant 8 s" and t[0]["now"], "Overdrive déclenché : message tout de suite")
	_check(g3.z_pulse == "card", "carte déclenchée : anneau")
	g3.z_pulse = ""
	g3.compute(st, _rogue({"card_on": "cursed"}), 72.0, ["card_on"])
	_check(g3.take_toasts()[0]["title"] == "MAUDIT ACTIF", "Maudit actif")
	for c in ["overdrive", "heal", "cursed", "springboard", "polarity"]:
		_check(GuideModel.CARD_ON_TEXT.has(c), "texte de la carte « %s »" % c)
	_check(SoundModel.EVENT_SOUNDS.get("card_on", "") == "rogue_card_on" and Synth.names().has("rogue_card_on"), "son de la carte déclenchée")
	var view2 = HudView.new()
	root.add_child(view2)
	await process_frame
	view2.pulse("card")
	_check(view2.z_pulse.left_s > 0.0 and view2.z_pulse.color == view2.UiTheme.OK, "anneau vert à la carte déclenchée")
	view2.pulse("hit")
	_check(view2.hit_flash_s > 0.0 and view2.z_pulse.color == view2.UiTheme.GOLD, "attaque réussie : éclair et anneau or")
	view2.apply(hm.values(), Vector3.ZERO, 0.1)
	_check(view2.hit_flash.color.a > 0.0 and view2.hit_flash.color.a < 0.45, "l'éclair s'éteint en 0,25 s")
	view2.pulse("ok")
	_check(view2.z_pulse.color == view2.UiTheme.GOLD, "relance ou déblocage : anneau or seul")
	var hm2 = HudModel.new()
	hm2.set_ftp(250.0)
	hm2.update({"seq": 10, "gear": 6, "power_3s": 180.0, "rogue": _rogue({"shield": 40.0})}, 0.0)
	_check(not hm2.values()["hurt"], "première trame : pas de dégâts")
	hm2.update({"seq": 11, "gear": 6, "power_3s": 180.0, "rogue": _rogue({"shield": 25.0, "events": ["parry_miss"]})}, 0.1)
	_check(hm2.values()["hurt"], "bouclier qui baisse : dégâts reçus")
	view2.apply(hm2.values(), Vector3.ZERO, 0.016)
	_check(view2.hurt_flash_s > 0.0, "dégâts reçus : bords rouges")
	hm2.update({"seq": 11, "gear": 6, "power_3s": 180.0, "rogue": _rogue({"shield": 25.0})}, 0.2)
	_check(not hm2.values()["hurt"], "même trame : pas de nouveaux dégâts")
	hm2.update({"seq": 12, "gear": 6, "power_3s": 180.0, "rogue": _rogue({"shield": 25.0, "firewall_gap_m": 0.0})}, 0.3)
	_check(hm2.values()["hurt"], "Firewall au contact : bords rouges tant qu'il touche")
	var g5 = GuideModel.new()
	g5.compute(st, _rogue(), 72.0, ["parry_miss"])
	_check(g5.take_toasts()[0]["title"] == "TOUCHÉ ! Coup non paré", "coup non paré : « TOUCHÉ ! »")
	view2.queue_free()

	# Invite « Z : FRAPPE ! » d'après les fenêtres du core, tant que Z agit ; rien en approche, sans adrénaline, en surchauffe.
	var wins := [{"kind": "strike_target", "s_start": 497.0, "s_end": 510.0}, {"kind": "parry_zone", "s_start": 800.0, "s_end": 820.0},
		{"kind": "rock", "s_start": 900.0, "s_end": 903.0}]
	var g4 = GuideModel.new()
	o = g4.compute(st, _rogue({"windows": wins, "s_room": 505.0, "adrenaline": 60.0, "archetype": "grimpeur"}), 72.0, [])
	_check(o["z_call"] == "Z : FRAPPE !", "cible sous la roue, Z prêt : « Z : FRAPPE ! »")
	o = g4.compute(st, _rogue({"windows": wins, "s_room": 505.0, "adrenaline": 20.0, "archetype": "grimpeur"}), 72.0, [])
	_check(o["z_call"] == "", "sans adrénaline : pas d'invite")
	o = g4.compute(st, _rogue({"windows": wins, "s_room": 505.0, "adrenaline": 20.0, "archetype": "diesel"}), 72.0, [])
	_check(o["z_call"] == "Z : FRAPPE !", "Diesel : charges de tunnel, invite sans adrénaline")
	o = g4.compute(st, _rogue({"windows": wins, "s_room": 450.0, "adrenaline": 60.0, "archetype": "grimpeur"}), 72.0, [])
	_check(o["z_call"] == "", "cible à 50 m : pas encore d'invite")
	o = g4.compute(st, _rogue({"windows": wins, "s_room": 805.0, "adrenaline": 20.0, "archetype": "grimpeur"}), 72.0, [])
	_check(o["z_call"] == "Z : PARADE !", "zone de parade : « Z : PARADE ! »")
	o = g4.compute(st, _rogue({"windows": wins, "s_room": 901.0, "adrenaline": 20.0, "archetype": "grimpeur"}), 72.0, [])
	_check(o["z_call"] == "Z : ROCHER !", "rocher : « Z : ROCHER ! »")
	o = g4.compute(st, _rogue({"windows": wins, "s_room": 505.0, "adrenaline": 60.0, "overheat": true, "archetype": "grimpeur"}), 85.0, [])
	_check(o["z_call"] == "", "surchauffe : pas d'invite (Z bloqué)")

	# Consignes en watts dès que la FTP est connue (lot R23 : jamais de % à calculer).
	var gw = GuideModel.new()
	gw.ftp_w = 250.0
	o = gw.compute(st, _rogue(), 72.0, [])
	_check(o["fw"]["sub"] == "Garde 175–190 W · ✔ dans la plage", "Firewall : garde 175–190 W, dans la plage (R28)")
	o = gw.compute(st, _rogue({"overheat": true, "adrenaline_trend": {"rate_per_s": -2.0, "cause": "overheat", "overheat_in_s": null}}), 85.0, [])
	_check(o["hint"] == "SURCHAUFFE : descends sous 190 W · adrénaline −2/s, Z bloqué", "surchauffe en watts")
	o = gw.compute(st, _rogue({"phase": "WARMUP", "target_pct": {"lo": 55, "hi": 65}, "phase_left_s": 200.0}), 58.0, [])
	_check(o["consigne"]["big"] == "140–165 W" and o["consigne"]["sub"] == "✔ dans la plage", "échauffement : 140–165 W, dans la plage (R28)")
	gw.compute(st, _rogue({"z_reason": "cursed"}), 110.0, ["z_refused"])
	_check(gw.take_toasts()[0]["sub"] == "Redescends sous 250 W pour frapper", "Maudit : sortie en watts")
	_check(GuideModel.watts(72.0, 0.0) == "72 % FTP" and GuideModel.watts(72.0, 250.0) == "180 W", "watts, ou % sans FTP")

	# Bandeau des règles : à l'échauffement seulement, et il défile.
	var gr = GuideModel.new()
	o = gr.compute(st, _rogue({"phase": "WARMUP", "phase_left_s": 200.0}), 60.0, [])
	_check(o["rules"].begins_with("RÈGLES DU CYBER-ROGUE") and "Firewall" in o["rules"] and "surchauffe" in o["rules"], "échauffement : bandeau des règles")
	_check(gr.compute(st, _rogue(), 72.0, [])["rules"] == "", "en salle : pas de bandeau")
	var view3 = HudView.new()
	root.add_child(view3)
	await process_frame
	var hm3 = HudModel.new()
	hm3.update({"seq": 20, "gear": 6, "power_3s": 150.0, "rogue": _rogue({"phase": "WARMUP", "phase_left_s": 200.0})}, 0.0)
	view3.apply(hm3.values(), Vector3.ZERO, 0.016)
	var x0: float = view3.rules_label.position.x
	view3.apply(hm3.values(), Vector3.ZERO, 0.5)
	_check(view3.rules_strip.visible and view3.rules_label.position.x < x0, "le bandeau défile")
	view3.queue_free()

	# Vues du mode : 4, la dernière sur le vélo.
	_check(RogueScene.VIEW_NAMES == ["derrière", "haute", "proche", "sur le vélo"] and RogueScene.RIDER_VIEW == 3, "4 vues, la 4e sur le vélo")
	_check(float(RogueScene.VIEWS[3][1]) == 1.4, "vue sur le vélo : yeux à 1,4 m")

	# Essai du 15 novembre : fin de salle annoncée avec ce qu'il reste à l'ennemi ; au boss, la phase 3 seulement.
	var hp := {"enemy_hp": 60.0, "enemy_hp_max": 100.0}
	_check(GuideModel.room_end_text(st, _rogue(hp.merged({"s_room": 920.0}))) == "Fin de salle dans 200 m : ennemi encore à 60 %",
		"fin de salle dans 200 m, ennemi à 60 %")
	_check(GuideModel.room_end_text(st, _rogue(hp.merged({"s_room": 500.0}))) == "", "loin de la fin : rien")
	_check(GuideModel.room_end_text(st, _rogue({"s_room": 920.0, "enemy_hp": 0.0, "enemy_hp_max": 100.0})) == "", "ennemi à terre : rien")
	_check(GuideModel.room_end_text(st, _rogue(hp.merged({"s_room": 920.0, "phase": "BOSS", "boss_phase": 2}))) == "",
		"boss phase 2 : rien (seule la phase 3 décide)")
	_check(GuideModel.room_end_text(st, _rogue(hp.merged({"s_room": 920.0, "phase": "BOSS", "boss_phase": 3}))) == "Fin du boss dans 200 m : boss encore à 60 %",
		"boss phase 3 : fin annoncée")
	var g_end = GuideModel.new()
	var out2: Dictionary = g_end.compute(st, _rogue(hp.merged({"s_room": 920.0, "adrenaline": 10.0})), 72.0, [])
	_check(out2["hint"] == "Fin de salle dans 200 m : ennemi encore à 60 %" and out2["tone"] == "warn", "fin de salle au guide : %s" % out2["hint"])

	# Bilan : la cause de la défaite en une phrase, et ce qu'il fallait faire ; plus de « fui ».
	var sum_m = SummaryModel.new()
	var vd: Dictionary = sum_m.verdict({"rogue": {"result": "defeat", "boss": "fled",
		"end_cause": {"cause": "boss_time", "boss_phase": 3, "enemy_pct": 42}}})
	_check(vd["text"] == "Défaite : la phase 3 du boss s'est finie avec encore 42 % de PV au boss." and "FRAPPE" in vd["tip"] and vd["tone"] == "warn",
		"défaite au temps : %s" % str(vd))
	vd = sum_m.verdict({"rogue": {"result": "defeat", "end_cause": {"cause": "boss_shield", "boss_phase": 2, "enemy_pct": 70}}})
	_check("bouclier est tombé à zéro face au boss (phase 2)" in vd["text"] and "PARADE" in vd["tip"], "défaite au bouclier")
	_check(sum_m.verdict({"rogue": {"result": "victory", "end_cause": null}})["tone"] == "ok", "victoire")
	_check(sum_m.verdict({"distance_m": 1000.0}).is_empty(), "séance sans mode : pas de verdict")
	var rl: Array = sum_m.rogue_lines({"result": "defeat", "boss": "fled"})
	var rlabels := []
	for ln in rl:
		rlabels.append("%s : %s" % [ln["label"], ln["value"]])
	_check("Boss : non vaincu" in rlabels and "Salles non gagnées / sautées : 0 / 0" in rlabels, "bilan sans « fui » : %s" % str(rlabels))

	print("test_rogue_r23_retours : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

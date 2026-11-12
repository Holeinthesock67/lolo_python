extends SceneTree

## Tests sans écran de la lisibilité du Cyber-Rogue (lot R22) : textes du guide (panneau, Firewall, consigne,
## boutons), retours des appuis (Z refusé, arches ratées), légendes une seule fois, étiquettes des objets, zone Z
## à la taille de la fenêtre du core, bandeau des deux temps du couloir, décor latéral (densité, motif périodique).
## Lancement : godot --headless --path engine --script res://tests/unit/test_rogue_guide_model.gd

const GuideModel := preload("res://scripts/rogue/rogue_guide_model.gd")
const MarkerGuides := preload("res://scripts/rogue/marker_guides.gd")
const CorridorView := preload("res://scripts/rogue/rogue_corridor_view.gd")
const SideDecor := preload("res://scripts/rogue/rogue_side_decor.gd")

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
	var r := {"phase": "ROOM", "room_id": 3, "room_index": 3, "rooms_total": 9, "archetype": "puncheur",
		"boss_phase": null, "s_room": 500.0, "adrenaline": 32.0, "firewall_gap_m": 96.0, "firewall_gap_s": 12.0,
		"hack": null, "events": [], "phase_left_s": null, "next": [{"kind": "corridor", "in_s": 80.0, "archetype": null}],
		"loot_stage": null, "target_pct": {"lo": 95, "hi": null}, "z_reason": null, "shift_miss": null}
	r.merge(over, true)
	return r


func _run() -> void:
	var g = GuideModel.new()
	var st := {"route_length_m": 1120.0, "v": 8.0}

	# Échauffement : compte à rebours, étapes à venir, consigne de puissance, boutons sans Z.
	var warm := _rogue({"phase": "WARMUP", "phase_left_s": 222.0, "room_index": 1, "target_pct": {"lo": 55, "hi": 65},
		"next": [{"kind": "relic", "in_s": 80.0, "archetype": null}, {"kind": "room", "in_s": 222.0, "archetype": "diesel"}]})
	var o: Dictionary = g.compute(st, warm, 58.0, [])
	_check(o["title"] == "Échauffement" and o["countdown"] == "3:42", "échauffement : titre et compte à rebours 3:42")
	_check(o["next_lines"][0] == "Prochaine étape : relique à choisir dans 1:20", "prochaine étape : relique dans 1:20")
	_check(o["next_lines"][1].begins_with("Puis : salle 1/9 · Diesel"), "puis : première salle Diesel")
	_check(o["consigne"]["big"] == "55–65 % FTP" and o["consigne"]["ok"], "consigne 55–65 %, tenue à 58 %")
	_check(o["fw"].is_empty() and o["hint"].begins_with("Roule souple"), "échauffement : pas de Firewall, consigne d'attente")
	o = g.compute(st, _rogue({"phase": "WARMUP", "loot_stage": "card", "target_pct": {"lo": 55, "hi": 65}}), 58.0, [])
	_check(o["hint"].begins_with("Relique") and o["keys"][1][0] == "A long", "relique : A long pour la prendre")

	# Salle : titre, distance restante, Firewall en secondes et ses couleurs.
	o = g.compute(st, _rogue(), 92.0, [])
	_check(o["title"] == "Salle 3/9 · Puncheur" and o["title_right"] == "620 m restants", "salle : titre et 620 m restants")
	_check(o["fw"]["text"] == "12 s d'avance" and o["fw"]["level"] == "ok" and o["fw"]["sub"] == "Garde ≥ 95 % FTP", "Firewall à 12 s : vert")
	o = g.compute(st, _rogue({"firewall_gap_s": 7.0}), 92.0, [])
	_check(o["fw"]["level"] == "warn" and o["fw"]["sub"].begins_with("Accélère"), "Firewall à 7 s : orange, accélère")
	o = g.compute(st, _rogue({"firewall_gap_m": 0.0, "firewall_gap_s": 0.0}), 92.0, [])
	_check(o["fw"]["text"] == "TE TOUCHE !" and o["fw"]["level"] == "danger" and o["tone"] == "danger", "contact : rouge, consigne d'urgence")
	_check(o["keys"][0][2] == "off" and o["keys"][0][1].contains("32/50"), "Z grisé sous 50 d'adrénaline")

	# Objets devant : la consigne du bas parle du plus proche, avec sa distance.
	g.set_room(3, [{"kind": "strike_target", "s_m": 540.0, "len_m": 0.0, "param": null},
		{"kind": "arch", "s_m": 700.0, "len_m": 0.0, "param": "down"},
		{"kind": "tunnel", "s_m": 900.0, "len_m": 60.0, "param": 92.0}])
	o = g.compute(st, _rogue(), 92.0, [])
	_check(o["hint"] == "Cible Z dans 40 m : appuie sur Z quand la roue passe sur l'anneau", "cible Z dans 40 m")
	o = g.compute(st, _rogue({"s_room": 540.0, "adrenaline": 60.0}), 92.0, [])
	_check(o["hint"] == "Appuie sur Z maintenant" and o["keys"][0][2] == "on", "sur la cible, Z prêt : maintenant")
	o = g.compute(st, _rogue({"s_room": 640.0}), 92.0, [])
	_check(o["hint"] == "Arche ▼ dans 60 m : prépare −" and o["keys"][0][0] == "−", "arche descendante : prépare −")
	o = g.compute(st, _rogue({"s_room": 905.0}), 92.0, [])
	_check(o["hint"] == "Tunnel : tiens 92 rpm", "tunnel : tiens 92 rpm")

	# Retours des appuis.
	g.take_toasts()
	g.compute(st, _rogue({"z_reason": "adrenaline", "events": ["z_refused"]}), 92.0, ["z_refused"])
	var t: Array = g.take_toasts()
	_check(t.size() == 1 and t[0]["title"] == "Z refusé : adrénaline 32 / 50" and t[0]["tone"] == "warn", "Z refusé : raison et valeur")
	g.compute(st, _rogue({"z_reason": "cursed", "events": ["z_refused"]}), 92.0, ["z_refused"])
	_check(g.take_toasts()[0]["title"] == "Z bloqué par la carte Maudit", "Z refusé par la carte Maudit")
	g.compute(st, _rogue({"shift_miss": {"reason": "early", "dt_s": -0.42}}), 92.0, ["shift_missed"])
	_check(g.take_toasts()[0]["title"] == "Trop tôt (−0,4 s)", "arche : trop tôt de 0,4 s")
	g.compute(st, _rogue({"shift_miss": {"reason": "wrong_way", "dt_s": 0.1}}), 92.0, ["shift_missed"])
	_check(g.take_toasts()[0]["title"] == "Mauvais sens", "arche : mauvais sens")
	g.compute(st, _rogue(), 92.0, ["perfect_shift"])
	_check(g.take_toasts()[0]["title"] == "PERFECT SHIFT +10", "Perfect Shift réussi")
	g.compute(st, _rogue(), 92.0, [])
	_check(g.take_toasts().is_empty(), "sans événement : aucun retour")
	for reason in ["adrenaline", "overheat", "no_target", "no_charge", "no_roc_charge", "no_surge", "no_hack", "cursed", "recovery", "gold"]:
		_check(GuideModel.Z_REASON_TEXT.has(reason), "texte de la raison « %s »" % reason)

	# Légendes : une seule fois par sorte d'objet, gardées dans un fichier d'une run à l'autre.
	var path := "user://test_rogue_legendes.json"
	if FileAccess.file_exists(path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	var g2 = GuideModel.new()
	g2.load_seen(path)
	g2.set_room(3, [{"kind": "strike_target", "s_m": 540.0, "len_m": 0.0, "param": null}])
	g2.compute(st, _rogue({"firewall_gap_m": 150.0}), 92.0, [])
	var leg: Array = g2.take_legend()
	_check(leg.size() == 2 and leg[0] == "Nouveau : cible Z", "légende de la cible Z au premier passage")
	g2.compute(st, _rogue({"firewall_gap_m": 150.0}), 92.0, [])
	_check(g2.take_legend().is_empty(), "légende de la cible montrée une seule fois")
	g2.compute(st, _rogue({"firewall_gap_m": 40.0}), 92.0, [])
	_check(g2.take_legend()[0] == "Le Firewall", "légende du Firewall quand il approche")
	var g3 = GuideModel.new()
	g3.load_seen(path)
	_check(g3.seen_legends.has("strike_target") and g3.seen_legends.has("firewall"), "légendes vues relues à la run suivante")
	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))

	# Étiquettes et zone Z.
	_check(GuideModel.marker_tag("tunnel", 92.0) == "92 rpm" and GuideModel.marker_tag("pad", 1.4) == "≥ 140 % · vitesse 10+",
		"étiquettes du tunnel et du pavé")
	_check(GuideModel.marker_tag("arch", "up") == "▲ +" and GuideModel.marker_tag("strike_target", null) == "Z !", "étiquettes de l'arche et de la cible")
	_check(is_equal_approx(MarkerGuides.half_window_m("strike_target", 8.0), 4.0), "zone Z à 8 m/s : ± 4 m (± 0,5 s)")
	_check(is_equal_approx(MarkerGuides.half_window_m("strike_target", 4.0), 3.0), "zone Z à 4 m/s : plancher ± 3 m")
	_check(is_equal_approx(MarkerGuides.half_window_m("rock", 8.0), 6.0), "rocher à 8 m/s : ± 6 m (± 0,75 s)")
	var node := Node3D.new()
	var parts: Dictionary = MarkerGuides.decorate(node, "strike_target", null, 0.0, "low", false)
	MarkerGuides.update(parts, "strike_target", 540.0, 0.0, 520.0, 10.0)
	_check(parts["zone"] != null and is_equal_approx(parts["zone"].scale.z, 5.0) and parts["tag"].visible, "zone à 10 m/s : ± 5 m, étiquette visible à 20 m")
	MarkerGuides.update(parts, "strike_target", 540.0, 0.0, 300.0, 10.0)
	_check(not parts["tag"].visible, "étiquette cachée à 240 m")
	var arch_node := Node3D.new()
	var ap: Dictionary = MarkerGuides.decorate(arch_node, "arch", "up", 0.0, "low", false)
	MarkerGuides.update(ap, "arch", 700.0, 0.0, 684.0, 8.0)
	_check(ap["ring"].visible and ap["ring"].scale.x > 1.0 and arch_node.get_node("Sign").text == "+", "arche à 2 s : anneau d'approche, signe +")
	MarkerGuides.update(ap, "arch", 700.0, 0.0, 701.0, 8.0)
	_check(not ap["ring"].visible, "arche passée : anneau caché")
	node.free()
	arch_node.free()

	# Couloir : deux temps, temps restant, une seule porte quand les deux mènent au boss.
	var doors := [{"side": "left", "room_id": 8, "archetype": "diesel"}, {"side": "right", "room_id": 9, "archetype": "grimpeur"}]
	var txt: Array = CorridorView.step_texts({"stage": "card", "doors": doors, "left_s": 17.2, "focus": 1})
	_check(txt[0] == "1. Choisis une carte" and txt[1] == "2. Choisis ta porte" and txt[2] == "⏱ 18 s", "couloir : 1. carte, 2. porte, 18 s")
	txt = CorridorView.step_texts({"stage": "door", "doors": doors, "left_s": 6.5, "focus": 4})
	_check(txt[0] == "1. Carte prise ✔" and txt[3] == "door", "couloir : carte prise, porte à choisir")
	var boss := [{"side": "left", "room_id": 12, "archetype": "boss"}, {"side": "right", "room_id": 12, "archetype": "boss"}]
	_check(CorridorView.one_way(boss) and not CorridorView.one_way(doors), "deux portes vers le boss : une seule porte")
	_check(CorridorView.step_texts({"stage": "card", "doors": boss, "left_s": 9.0})[1] == "2. Puis : Boss", "dernier couloir : « Puis : Boss »")

	# Décor latéral : plus dense en high, motif périodique de la bande hors salle, ruban suivi en salle.
	var flat := func(_s): return 0.0
	var low: Dictionary = SideDecor.layout(1200.0, "low", 4, flat)
	var high: Dictionary = SideDecor.layout(1200.0, "high", 4, flat)
	var n_low: int = low["pylons_a"].size() + low["pylons_b"].size()
	var n_high: int = high["pylons_a"].size() + high["pylons_b"].size()
	_check(n_high > n_low * 2 and n_low >= 80, "pylônes : %d en low, %d en high sur 1,2 km" % [n_low, n_high])
	_check(not low["blocks"].is_empty() and not low["rings"].is_empty(), "blocs de données et anneaux posés")
	var per: Dictionary = SideDecor.layout(SideDecor.STRIP_M, "medium", 7, flat, true)
	var period := SideDecor.spacing("medium") * SideDecor.PATTERN
	# deuxième et troisième périodes (la première n'a pas de voisin avant elle)
	var b0: Array = per["blocks"].filter(func(x): return x.origin.z > -2.0 * period and x.origin.z <= -period)
	var b1: Array = per["blocks"].filter(func(x): return x.origin.z > -3.0 * period and x.origin.z <= -2.0 * period)
	b0.sort_custom(func(a, b): return a.origin.z > b.origin.z)
	b1.sort_custom(func(a, b): return a.origin.z > b.origin.z)
	var same := b0.size() == b1.size()
	for k in mini(b0.size(), b1.size()):
		same = same and absf(b0[k].origin.x - b1[k].origin.x) < 0.001 and absf(b0[k].origin.z - period - b1[k].origin.z) < 0.001
	_check(same, "bande hors salle : motif identique d'une période à l'autre (recalage sans saut)")
	var slope := func(s): return s * 0.05
	var room: Dictionary = SideDecor.layout(400.0, "low", 4, slope)
	var p0: Transform3D = room["pylons_a"][0]
	_check(absf(p0.origin.y - (-p0.origin.z * 0.05 + 4.0 - SideDecor.PYLON_H * 0.5)) < 0.01, "pylônes posés sur le relief du ruban")
	_check(absf(absf(p0.origin.x) - SideDecor.PYLON_X) < 0.001, "pylônes à %.1f m de l'axe" % SideDecor.PYLON_X)

	print("test_rogue_guide_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)

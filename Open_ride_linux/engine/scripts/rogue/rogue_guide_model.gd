extends RefCounted

## Textes de lisibilité du Cyber-Rogue (lot R22, maquettes validées le 12 novembre) : panneau d'état en haut à
## gauche, Firewall ou consigne en haut à droite, consigne et boutons utiles en bas, retours des appuis (Z refusé
## et sa raison, verdict des arches de Perfect Shift), légende au premier passage de chaque objet. Calcul pur
## depuis `state.rogue` (révision 1.16), la trame `state` et les repères de la salle (message `room`) ; aucune
## règle de jeu ici. Pas de class_name : preload("res://scripts/rogue/rogue_guide_model.gd").

const ARCHETYPE_NAMES := {"diesel": "Diesel", "puncheur": "Puncheur", "grimpeur": "Grimpeur",
	"sprinteur": "Sprinteur", "saboteur": "Saboteur", "boss": "Boss"}
const ARCHETYPE_HINTS := {"diesel": "rampe longue et régulière", "puncheur": "bosses courtes et raides",
	"grimpeur": "paliers de montée", "sprinteur": "plat, salves du Firewall",
	"saboteur": "pente changeante, piratages", "boss": "tout à la fois"}
const ADRENALINE_Z := 50
## Distance d'annonce d'un objet de salle (m) : la consigne du bas en parle à partir de là.
const ANNOUNCE_M := 120.0
## Écart au Firewall (s) : vert au-delà de WARN, orange entre DANGER et WARN, rouge en dessous.
const FW_WARN_S := 10.0
const FW_DANGER_S := 5.0
## Lot R23 (essai du 15 novembre) : distance avant la fin d'une salle (ou de la phase 3 du boss) à partir de laquelle
## le guide dit ce qu'il reste à l'ennemi : la salle se finit au bout de sa distance, gagnée ou non.
const END_WARN_M := 300.0
const TOAST_S := 2.5
const OVERHEAT_RATE_DEFAULT := 2.0  # adrénaline perdue par seconde en surchauffe, si le core ne la dit pas
const FIGHT_PHASES := ["ROOM", "BOSS"]

## Étiquette flottante au-dessus de chaque objet (lisible de loin, en majuscules courtes).
const MARKER_TAGS := {"strike_target": "Z !", "purge": "DÉBLOQUER : Z", "rock": "ROCHER : Z", "parry_zone": "PARADE : Z",
	"tunnel": "%d rpm", "pad": "≥ %d %% · vitesse 10+", "arch": "%s"}
## Légende montrée la première fois que le joueur croise chaque sorte d'objet (et le Firewall).
const LEGENDS := {
	"strike_target": ["Nouveau : cible Z", "Appuie sur Z quand ta roue passe sur l'anneau rouge. Coûte 50 d'adrénaline et retire 6 % des PV de l'ennemi (Diesel : utilise tes charges de tunnel)."],
	"arch": ["Nouveau : arche de changement parfait", "La flèche et le signe disent le sens. Passe une vitesse dans ce sens quand l'anneau touche l'arche (± 0,75 s). Réussi : +10 d'adrénaline."],
	"tunnel": ["Nouveau : tunnel de cadence", "Tiens la cadence affichée (± 3 rpm) dans le tunnel vert : chaque 10 s donne une charge pour la prochaine cible Z."],
	"pad": ["Nouveau : pavé de sprint", "En vitesse 10 ou plus, au-dessus de la puissance affichée, tes dégâts sont multipliés sur le pavé."],
	"parry_zone": ["Nouveau : zone de parade", "Relance fort la puissance puis appuie sur Z dans la zone. Sinon, le coup te retire du bouclier."],
	"purge": ["Nouveau : borne de déblocage", "Le Saboteur pirate tes vitesses : elles restent bloquées, ou une vitesse t'est imposée. Sur cette borne, appuie sur Z pour les débloquer."],
	"rock": ["Nouveau : rocher", "Roule en Roc (sous 70 rpm) pour gagner des charges, puis Z sur le rocher pour le briser."],
	"overheat": ["Nouveau : surchauffe (endurance)", "En salle d'endurance, reste dans la plage de la consigne. Au-dessus du plafond de la plage pendant 5 s, tu surchauffes : l'adrénaline fond de 2 par seconde et Z est bloqué jusqu'à ce que tu redescendes."],
	"firewall": ["Le Firewall", "Un mur roule derrière toi à la puissance de la salle. S'il te touche, ton bouclier fond et tu perds de l'or. Tiens la consigne pour garder ton avance."],
}
const Z_REASON_TEXT := {
	"adrenaline": ["Z refusé : adrénaline %d / 50", "Tiens la puissance cible pour remplir la jauge (+1 par seconde, +10 par changement parfait)"],
	"overheat": ["Z refusé : surchauffe", "Baisse la puissance pour refroidir"],
	"no_target": ["Z : rien à frapper ici", "Attends un objet marqué « Z »"],
	"no_charge": ["Z refusé : aucune charge", "Tiens la cadence dans les tunnels verts pour charger"],
	"no_roc_charge": ["Z refusé : aucune charge de Roc", "Roule en Roc (sous 70 rpm) pour charger"],
	"no_surge": ["Parade ratée : pas de relance", "Accélère fort juste avant d'appuyer sur Z"],
	"no_hack": ["Z : rien à débloquer", "La borne ne sert que si tes vitesses sont bloquées ou imposées"],
	"cursed": ["Z bloqué par la carte Maudit", "Redescends sous %s pour frapper"],
	"recovery": ["Z indisponible pendant la récupération", "Roule souple, le combat reprend bientôt"],
	"gold": ["Relance refusée : pas assez d'or", ""],
}
## Retour d'un Z court accepté (lot R23, événement `z_ok`, champ `z_action`, révision 1.17).
const Z_ACTION_TEXT := {
	"strike": ["FRAPPE ! −6 % PV", "−50 d'adrénaline"],
	"charges": ["FRAPPE ! Charges de tunnel utilisées", ""],
	"rock": ["ROCHER BRISÉ !", "−8 % PV de l'ennemi"],
	"rock_chip": ["Rocher entamé", "Encore Z (charge de Roc) pour le briser"],
	"parry": ["PARADE !", ""],
	"purge": ["VITESSES DÉBLOQUÉES", "Tu peux de nouveau changer de vitesse"],
	"reroll": ["Cartes relancées", ""],
}
## Invite animée au centre de l'écran tant qu'un Z court agit maintenant (lot R23, demande du propriétaire :
## « une animation pour lancer l'action ») : cible à frapper, zone de parade, rocher, borne de déblocage.
const Z_CALL := {"strike_target": "Z : FRAPPE !", "parry_zone": "Z : PARADE !", "rock": "Z : ROCHER !",
	"purge": "Z : DÉBLOQUE !"}
## Règles du jeu, en bandeau défilant pendant l'échauffement (lot R23, demande du propriétaire).
const RULES := [
	"RÈGLES DU CYBER-ROGUE",
	"Tiens la consigne de puissance, dès l'échauffement : l'adrénaline monte",
	"Z frappe l'ennemi quand ta roue passe sur l'anneau rouge, avec 50 d'adrénaline ou plus",
	"Le Firewall te poursuit : roule au-dessus de la consigne pour garder ton avance, sinon ton bouclier fond",
	"Endurance : reste dans la plage ; au-dessus du plafond pendant 5 s, c'est la surchauffe (adrénaline qui fond, Z bloqué)",
	"Arche : change de vitesse dans le sens de la flèche quand l'anneau touche l'arche (changement parfait : +10 d'adrénaline)",
	"Zone de parade : relance la puissance puis Z, sinon tu perds du bouclier",
	"Rocher : roule en Roc (cadence basse, en force) pour charger, puis Z",
	"Couloir : A pour choisir une carte puis une porte, Z pour relancer les cartes contre de l'or",
	"Les cartes se déclenchent toutes seules quand tu atteins leur puissance ou leur cadence",
	"↑ ↓ : changer de vue",
]
## Seuil de la carte Maudit en % de FTP (`cursed_power_frac` de balance.toml, lot R23), pour écrire sa sortie en watts.
const CURSED_PCT := 100.0
## Carte qui vient de se déclencher (lot R23, événement `card_on`, champ `card_on`) : seuil atteint, effet en cours.
const CARD_ON_TEXT := {
	"overdrive": ["OVERDRIVE !", "Dégâts ×2 pendant 8 s"],
	"heal": ["SOIN ACTIF", "+1 de bouclier par seconde"],
	"cursed": ["MAUDIT ACTIF", "Dégâts ×1,35 · Z bloqué"],
	"springboard": ["TREMPLIN !", "+15 d'adrénaline · dégâts ×1,5 pendant 5 s"],
	"polarity": ["INVERSION !", "La montée devient une descente pendant 8 s"],
}
## Actions de Z qui touchent l'ennemi ou un obstacle : l'écran fait un éclair (lot R23, demande du propriétaire).
const ATTACK_ACTIONS := ["strike", "charges", "rock", "rock_chip", "parry"]
## Z sans effet (raison `no_target`) : ce qu'il faut attendre, selon la phase (lot R23).
const NO_TARGET_TEXT := {
	"WARMUP": ["Z : pas encore de cible", "Z sert en salle · première salle dans %s"],
	"CORRIDOR": ["Z : rien à faire ici", "Z sert en salle · salle suivante dans %s"],
	"COOLDOWN": ["Z : la run est finie", "Roule souple jusqu'au bilan (%s)"],
	"RESULTS": ["Z : la run est finie", ""],
}

var _markers: Array = []          # repères de la salle affichée (message `room`)
var _room_id := -1
var seen_legends: Dictionary = {} # sortes d'objets déjà expliquées
## Fichier où garder les légendes déjà vues d'une run à l'autre (vide : en mémoire seulement, tests).
var store_path := ""
var _toasts: Array = []           # [{title, sub, tone}]
var _legend: Array = []           # [titre, texte] à afficher, vide sinon
## Relance des cartes du couloir (message `loot`, posé par rogue_hud_model) : prix affiché dans le bouton Z.
var reroll_cost := 0
## Dernier retour de la trame (lot R23) : « hit » (attaque réussie), « ok », « refused » (Z court), « card » (carte
## déclenchée) ou vide ; la vue dessine l'anneau, et l'éclair pour « hit ».
var z_pulse := ""
## FTP du coureur (posée par rogue_hud_model) : consignes écrites en watts (lot R23) ; 0 : en % de FTP.
var ftp_w := 0.0


## Relit les légendes déjà vues (fichier JSON {sorte: true}) ; fichier absent ou illisible : aucune.
func load_seen(path: String) -> void:
	store_path = path
	if path == "" or not FileAccess.file_exists(path):
		return
	var data = JSON.parse_string(FileAccess.get_file_as_string(path))
	if data is Dictionary:
		seen_legends = data


func _save_seen() -> void:
	if store_path == "":
		return
	var f := FileAccess.open(store_path, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(seen_legends))


## Repères de la salle `room_id` (message `room`) : sert aux consignes et au sens des arches.
func set_room(room_id: int, markers: Array) -> void:
	_room_id = room_id
	_markers = markers


## Retours à afficher depuis le dernier appel : [{title, sub, tone}] (tone : ok, warn, danger, info).
func take_toasts() -> Array:
	var out := _toasts
	_toasts = []
	return out


## Légende à montrer une fois ([titre, texte]) ; vide s'il n'y en a pas de nouvelle.
func take_legend() -> Array:
	var out := _legend
	_legend = []
	return out


static func clock(seconds: Variant) -> String:
	if seconds == null:
		return ""
	var s := maxi(int(ceil(float(seconds))), 0)
	return "%d:%02d" % [s / 60, s % 60]


static func step_name(step: Dictionary, rogue: Dictionary) -> String:
	match str(step.get("kind", "")):
		"relic":
			return "relique à choisir"
		"room":
			var a := str(step.get("archetype", ""))
			var total := int(rogue.get("rooms_total", 1))
			var idx := int(rogue.get("room_index", 1))
			if str(rogue.get("phase", "")) != "WARMUP":
				idx += 1
			return "salle %d/%d · %s (%s)" % [mini(idx, total), total, ARCHETYPE_NAMES.get(a, a), ARCHETYPE_HINTS.get(a, "")]
		"corridor":
			return "couloir : carte et porte"
		"boss":
			return "boss"
		"cooldown":
			return "retour au calme"
		"results":
			return "bilan"
	return ""


## Objets de la salle devant le joueur (le plus proche d'abord), avec leur distance.
func upcoming(s_room: float, limit_m: float = ANNOUNCE_M) -> Array:
	var out := []
	for m in _markers:
		var s0 := float(m.get("s_m", 0.0))
		var s1 := s0 + float(m.get("len_m", 0.0))
		if s1 + 2.0 < s_room or s0 - s_room > limit_m:
			continue
		out.append({"kind": str(m.get("kind", "")), "d_m": maxf(s0 - s_room, 0.0), "inside": s0 - 3.0 <= s_room and s_room <= s1 + 3.0,
			"param": m.get("param", null)})
	out.sort_custom(func(a, b): return a["d_m"] < b["d_m"])
	return out


static func marker_tag(kind: String, param: Variant) -> String:
	match kind:
		"tunnel":
			return MARKER_TAGS["tunnel"] % int(round(float(param if param != null else 90.0)))
		"pad":
			return MARKER_TAGS["pad"] % int(round(float(param if param != null else 1.4) * 100.0))
		"arch":
			return "▲ +" if str(param) == "up" else "▼ −"
	return MARKER_TAGS.get(kind, "")


## Valeurs du guide pour la trame. `power_pct` : puissance du joueur en % de FTP (lissée).
func compute(state: Dictionary, rogue: Dictionary, power_pct: float, events: Array) -> Dictionary:
	var phase := str(rogue.get("phase", ""))
	var adr := int(floor(float(rogue.get("adrenaline", 0.0))))
	var z_ready := adr >= ADRENALINE_Z
	var target = rogue.get("target_pct", null)
	var nxt: Array = rogue.get("next", []) if rogue.get("next", null) is Array else []
	var out := {"phase": phase, "panel": true, "title": "", "title_right": "", "countdown": "", "countdown_label": "",
		"next_lines": [], "fw": {}, "consigne": {}, "hint": "", "keys": [], "tone": "info", "z_call": ""}
	var arch := str(rogue.get("archetype", ""))
	var room_txt := "Salle %d/%d" % [int(rogue.get("room_index", 1)), int(rogue.get("rooms_total", 1))]
	var left = rogue.get("phase_left_s", null)
	match phase:
		"WARMUP":
			out["title"] = "Échauffement"
			out["countdown"] = clock(left)
			out["countdown_label"] = "avant la première salle"
		"COOLDOWN":
			out["title"] = "Retour au calme"
			out["countdown"] = clock(left)
			out["countdown_label"] = "avant le bilan"
		"RECOVERY":
			out["title"] = "Récupération"
			out["countdown"] = clock(left)
			out["countdown_label"] = "avant la reprise du combat"
		"BOSS":
			out["title"] = "Boss · phase %d/3" % int(rogue.get("boss_phase", 1) if rogue.get("boss_phase", null) != null else 1)
		"ROOM":
			out["title"] = "%s · %s" % [room_txt, ARCHETYPE_NAMES.get(arch, arch)]
		"CORRIDOR":
			out["title"] = "Couloir"
			out["panel"] = false            # l'écran du couloir a son propre bandeau
	if phase in FIGHT_PHASES:
		var raw_len = state.get("route_length_m", null)
		var length := float(raw_len) if raw_len is float or raw_len is int else 0.0
		if length > 0.0:
			out["title_right"] = "%d m restants" % int(maxf(length - float(rogue.get("s_room", 0.0)), 0.0))
	for st in nxt:
		if st is Dictionary:
			var when := clock(st.get("in_s", null))
			var name := step_name(st, rogue)
			var lead := "Prochaine étape" if out["next_lines"].is_empty() else "Puis"
			out["next_lines"].append(("%s : %s" % [lead, name]) if when == "" or lead == "Puis" else ("%s : %s dans %s" % [lead, name, when]))
	# Firewall (salle et boss) ou consigne de puissance (échauffement, retour au calme).
	if phase in FIGHT_PHASES or phase == "RECOVERY":
		var gap_s = rogue.get("firewall_gap_s", null)
		var gap_m := float(rogue.get("firewall_gap_m", 0.0))
		if gap_s == null:
			var v := maxf(float(state.get("v", 0.0)), 1.0)
			gap_s = minf(maxf(gap_m, 0.0) / v, 99.0)
		var level := "ok"
		if gap_m <= 0.0:
			level = "danger"
		elif float(gap_s) < FW_DANGER_S:
			level = "danger"
		elif float(gap_s) < FW_WARN_S:
			level = "warn"
		var tgt_lo := int(target.get("lo", 0)) if target is Dictionary else 0
		var tgt_hi = target.get("hi", null) if target is Dictionary else null
		var band := target_band(tgt_lo, tgt_hi, ftp_w)
		var live := live_gap(power_pct, tgt_lo, tgt_hi, ftp_w, rogue.get("in_target", null))   # lot R26 : écart en direct
		var sub := ("Garde %s · %s" % [band, live]) if tgt_lo > 0 else ""
		if level == "warn" and tgt_lo > 0:
			sub = "Accélère : %s · %s" % [band, live]
		if gap_m <= 0.0:
			sub = "Bouclier qui fond · or perdu"
		out["fw"] = {"text": "TE TOUCHE !" if gap_m <= 0.0 else "%d s d'avance" % int(round(float(gap_s))), "sub": sub, "level": level}
	elif target is Dictionary and phase in ["WARMUP", "COOLDOWN"]:
		var lo := int(target.get("lo", 0))
		var hi = target.get("hi", null)
		var big := (("≤ %d W" % bound_w(int(hi), ftp_w, false)) if ftp_w > 0.0 else ("≤ %d %% FTP" % int(hi))) if lo <= 0 and hi != null else target_band(lo, hi, ftp_w)
		var flag = rogue.get("in_target", null)   # lot R26 : plage jugée par le core (tolérance et marge comprises)
		var inside: bool = bool(flag) if flag is bool else (power_pct >= float(lo) and (hi == null or power_pct <= float(hi)))
		var sub_c := live_gap(power_pct, lo, hi, ftp_w, flag) if lo > 0 else ("✔ dans la plage" if inside else "trop haut")   # lot R28
		out["consigne"] = {"big": big, "sub": sub_c.substr(0, 1).to_upper() + sub_c.substr(1), "ok": inside}
	out["adr_trend"] = adrenaline_trend_text(rogue)
	out["rules"] = "     •     ".join(RULES) if phase == "WARMUP" else ""
	_hint(out, state, rogue, phase, z_ready, adr, target)
	_feedback(rogue, events, adr)
	_legends(rogue, phase)
	return out


func _hint(out: Dictionary, state: Dictionary, rogue: Dictionary, phase: String, z_ready: bool, adr: int, target) -> void:
	var keys := []
	var hint := ""
	var tone := "info"
	var stage = rogue.get("loot_stage", null)
	var tgt_lo := int(target.get("lo", 0)) if target is Dictionary else 0
	if phase == "WARMUP":
		if stage == "card":
			hint = "Relique : choisis une carte, puis prends-la"
			keys = [["A / ← →", "changer", ""], ["A long", "prendre la relique", "on"], ["Y", "pause", ""]]
		else:
			hint = "Tiens la consigne : ton adrénaline se charge pour la première salle"   # lot R26
			keys = [["+ / −", "vitesse", ""], ["Y", "pause", ""], ["↑ / ↓", "vue", ""]]
	elif phase == "COOLDOWN":
		hint = "Roule souple jusqu'au bilan"
		keys = [["+ / −", "vitesse", ""], ["Y", "pause", ""]]
	elif phase == "RECOVERY":
		hint = "Défaite : roule souple, le combat reprend dans %s" % clock(rogue.get("phase_left_s", 0.0))
		tone = "warn"
		keys = [["+ / −", "vitesse", ""], ["Y", "pause", ""]]
	elif phase == "CORRIDOR":
		if stage == "card":
			hint = "Choisis une carte, puis prends-la"
			keys = [["A / ← →", "changer", ""], ["A long", "prendre la carte", "on"], reroll_key(reroll_cost, int(rogue.get("gold", 0))), ["Y", "pause", ""]]
		elif stage == "door":
			hint = "Choisis ta porte, puis entre"
			keys = [["A / ← →", "gauche / droite", ""], ["A long", "entrer", "on"], ["Y", "pause", ""]]
		else:
			hint = "Roule souple, la salle suivante arrive"
			keys = [["+ / −", "vitesse", ""], ["Y", "pause", ""]]
	elif phase in FIGHT_PHASES:
		var overheat := bool(rogue.get("overheat", false))
		var trend = rogue.get("adrenaline_trend", null)
		var soon = trend.get("overheat_in_s", null) if trend is Dictionary else null
		var tgt_hi = target.get("hi", null) if target is Dictionary else null
		var z_state := "on" if z_ready and not overheat else "off"
		var z_label := "frapper (Z prêt)" if z_ready else "frapper (%d/50 : pas assez)" % adr
		if overheat:
			z_label = "frapper (bloqué : surchauffe)"
		keys = [["Z", z_label, z_state], ["+ / −", "vitesse", ""], ["Y", "pause", ""], ["↑ / ↓", "vue", ""]]
		var gap_m := float(rogue.get("firewall_gap_m", 1.0))
		var hack = rogue.get("hack", null)
		var ups := upcoming(float(rogue.get("s_room", 0.0)))
		var end_warn := room_end_text(state, rogue)
		var limit := int(tgt_hi) if tgt_hi != null else 75
		if gap_m <= 0.0:
			hint = "Accélère ! Le Firewall te touche"
			tone = "danger"
		elif overheat:
			# Lot R23 : la surchauffe se dit tout le temps qu'elle dure, avec ce qu'elle coûte et la sortie.
			var melt := OVERHEAT_RATE_DEFAULT
			if trend is Dictionary:
				melt = absf(float(trend.get("rate_per_s", -OVERHEAT_RATE_DEFAULT)))
			hint = "SURCHAUFFE : descends sous %s · adrénaline −%s/s, Z bloqué" % [watts(limit, ftp_w), _num(melt)]
			tone = "danger"
		elif soon != null:
			hint = "Trop fort : au-dessus de %s, surchauffe dans %d s" % [watts(limit, ftp_w), maxi(int(ceil(float(soon))), 1)]
			tone = "warn"
		elif end_warn != "" and not (not ups.is_empty() and bool(ups[0]["inside"])):
			hint = end_warn
			tone = "warn"
		elif hack is Dictionary:
			hint = "Vitesses %s par le Saboteur : Z sur la borne pour les débloquer" % ("bloquées" if bool(hack.get("locked", false)) else "imposées")
			tone = "warn"
			keys[0] = ["Z", "débloquer (sur la borne)", "on"]   # lot R23 : le bouton dit ce que Z fait maintenant
		elif not ups.is_empty():
			var u: Dictionary = ups[0]
			var d := int(round(float(u["d_m"])))
			var now: bool = u["inside"]
			match str(u["kind"]):
				"strike_target":
					if now:
						hint = "Appuie sur Z maintenant" if z_ready or str(rogue.get("archetype", "")) == "diesel" else "Cible Z : adrénaline %d/50, pas encore assez" % adr
					else:
						hint = "Cible Z dans %d m : appuie sur Z quand la roue passe sur l'anneau" % d
					if z_ready:
						keys[0][2] = "on"
				"arch":
					var sign := "+" if str(u["param"]) == "up" else "−"
					hint = ("Arche : passe %s maintenant" % sign) if now else ("Arche %s dans %d m : prépare %s" % ["▲" if sign == "+" else "▼", d, sign])
					keys.insert(0, [sign, "Changement parfait", "on"])
				"tunnel":
					hint = ("Tunnel : tiens %d rpm" % int(round(float(u["param"] if u["param"] != null else 90.0)))) + ("" if now else " (dans %d m)" % d)
				"pad":
					hint = ("Pavé : vitesse 10+ et ≥ %s" % watts(float(u["param"] if u["param"] != null else 1.4) * 100.0, ftp_w)) + ("" if now else " (dans %d m)" % d)
				"parry_zone":
					hint = "Parade : relance la puissance puis Z" if now else "Zone de parade dans %d m : prépare une relance puis Z" % d
				"purge":
					hint = "Borne de déblocage : Z seulement si tes vitesses sont bloquées" if now else "Borne de déblocage dans %d m" % d
				"rock":
					hint = "Rocher : Z (charges de Roc)" if now else "Rocher dans %d m : roule en Roc pour charger, puis Z" % d
		if hint == "":
			if z_ready:
				hint = "Z prêt : vise la prochaine cible"
			elif tgt_lo > 0 and rogue.get("in_target", null) == true:
				hint = "Dans la plage : l'adrénaline monte (%d/50)" % adr   # lot R28 : la plage n'est écrite qu'en haut à droite
			elif tgt_lo > 0:
				hint = "Monte dans la plage pour remplir l'adrénaline (%d/50)" % adr
			else:
				hint = "Tiens la puissance pour remplir l'adrénaline (%d/50)" % adr
	out["hint"] = hint
	out["keys"] = keys
	out["tone"] = tone
	out["z_call"] = z_call(rogue, z_ready, bool(rogue.get("overheat", false))) if phase in FIGHT_PHASES else ""


## Fin proche d'une salle encore debout (lot R23) : « Fin de salle dans 200 m : ennemi encore à 60 % » ; au boss,
## seule la phase 3 décide de la run. "" loin de la fin, ennemi à terre ou longueur inconnue.
static func room_end_text(state: Dictionary, rogue: Dictionary) -> String:
	var raw_len = state.get("route_length_m", null)
	var length := float(raw_len) if raw_len is float or raw_len is int else 0.0
	var hp_max := float(rogue.get("enemy_hp_max", 0.0))
	var hp := float(rogue.get("enemy_hp", 0.0))
	var phase = rogue.get("boss_phase", null)
	if length <= 0.0 or hp_max <= 0.0 or hp <= 0.0 or (phase != null and int(phase) < 3):
		return ""
	var left := length - float(rogue.get("s_room", 0.0))
	if left > END_WARN_M or left < 0.0:
		return ""
	var pct := clampi(int(ceil(hp / hp_max * 100.0)), 1, 100)
	if phase != null:
		return "Fin du boss dans %d m : boss encore à %d %%" % [int(left), pct]
	return "Fin de salle dans %d m : ennemi encore à %d %%" % [int(left), pct]


## Invite de Z (lot R23) : d'après les fenêtres d'acceptation du core (`windows`), la même règle que le core, et non
## d'après la consigne affichée : une cible frappable (adrénaline prête, ou charges du Diesel), une zone de parade, un
## rocher, une borne de déblocage pendant un piratage. Rien en surchauffe (Z bloqué).
static func z_call(rogue: Dictionary, z_ready: bool, overheat: bool) -> String:
	if overheat:
		return ""
	var s := float(rogue.get("s_room", 0.0))
	var hacked := rogue.get("hack", null) is Dictionary
	for w in rogue.get("windows", []):
		if not (w is Dictionary) or s < float(w.get("s_start", 0.0)) or s > float(w.get("s_end", -1.0)):
			continue
		match str(w.get("kind", "")):
			"strike_target":
				if z_ready or str(rogue.get("archetype", "")) == "diesel":
					return Z_CALL["strike_target"]
			"parry_zone":
				return Z_CALL["parry_zone"]
			"rock":
				return Z_CALL["rock"]
			"purge":
				if hacked:
					return Z_CALL["purge"]
	return ""


## Puissance en texte (lot R23 : le joueur lit des watts, jamais un % à calculer) : « 175 W », arrondi à `step` W
## (5 W pour une consigne, 1 W pour la mesure) ; « 70 % FTP » seulement si la FTP est inconnue.
static func watts(pct: float, ftp: float, step: int = 5) -> String:
	if ftp <= 0.0:
		return "%d %% FTP" % int(round(pct))
	return "%d W" % (int(round(pct * ftp / 100.0 / float(step))) * step)


## Consigne de puissance en texte : « ≥ 175 W », ou « 175–190 W » quand elle a un plafond (endurance, R23).
## Lot R28 : bornes arrondies vers l'intérieur (bas au 5 W au-dessus, haut au 5 W en dessous) : à la puissance écrite,
## on est dans la plage jugée.
static func target_band(lo: int, hi: Variant, ftp: float = 0.0) -> String:
	if ftp <= 0.0:
		if hi == null or int(hi) <= lo:
			return "≥ %d %% FTP" % lo if hi == null else "%d %% FTP" % lo
		return "%d–%d %% FTP" % [lo, int(hi)]
	if hi == null or int(hi) <= lo:
		return "≥ %d W" % bound_w(lo, ftp, true) if hi == null else "%d W" % bound_w(lo, ftp, true)
	return "%d–%d W" % [bound_w(lo, ftp, true), maxi(bound_w(int(hi), ftp, false), bound_w(lo, ftp, true))]


## Borne de plage en watts, au pas de 5 W, arrondie vers l'intérieur de la plage (lot R28).
static func bound_w(pct: int, ftp: float, low: bool) -> int:
	var w := float(pct) * ftp / 100.0
	return int(ceil(w / 5.0 - 1e-6)) * 5 if low else int(floor(w / 5.0 + 1e-6)) * 5


## Écart à la plage (lots R26 et R28) : « ✔ dans la plage », sinon « il manque 12 W » ou « 15 W de trop » au-dessus du
## plafond. La puissance elle-même n'est écrite qu'en haut à gauche (lot R28 : elle l'était trois fois). `inside` :
## `rogue.in_target` (révision 1.28) ; null : comparaison simple. `lo` et `hi` : la plage jugée (`target_pct`, R28).
static func live_gap(power_pct: float, lo: int, hi: Variant, ftp: float, inside: Variant) -> String:
	var ok: bool = bool(inside) if inside is bool else (power_pct >= float(lo) and (hi == null or power_pct <= float(hi)))
	var below := power_pct < float(lo)
	# écart compté sur les nombres écrits à l'écran : borne de la plage et puissance en haut à gauche (lot R28)
	var now_w := int(round(power_pct * ftp / 100.0))
	if ok:
		# lot R28 : on entre à la consigne écrite ; la tolérance ne sert qu'à la sortie, et elle se dit en mots
		if below and ftp > 0.0 and bound_w(lo, ftp, true) > now_w:
			return "✔ marge : remonte de %d W" % (bound_w(lo, ftp, true) - now_w)
		return "✔ dans la plage"
	if ftp <= 0.0:
		return "trop bas" if below else "trop haut"
	if below and bound_w(lo, ftp, true) > now_w:
		return "il manque %d W" % (bound_w(lo, ftp, true) - now_w)
	if hi != null and power_pct > float(hi) and now_w > bound_w(int(hi), ftp, false):
		return "%d W de trop" % (now_w - bound_w(int(hi), ftp, false))
	return "presque dans la plage"   # puissance écrite dans la plage, moyenne jugée sur 8 s pas encore


## Tendance de l'adrénaline (champ `adrenaline_trend`, révision 1.17) : « +0,5/s », « −2/s surchauffe »,
## « stable : sous la cible », « stable : arrêt », « pleine » ; vide hors salle ou sans le champ.
static func adrenaline_trend_text(rogue: Dictionary) -> String:
	var t = rogue.get("adrenaline_trend", null)
	if not t is Dictionary:
		return ""
	var rate := float(t.get("rate_per_s", 0.0))
	match str(t.get("cause", "none")):
		"gain":
			return "▲ +%s/s" % _num(rate)
		"overheat":
			return "▼ −%s/s surchauffe" % _num(absf(rate))
		"below":
			return "= sous la cible"
		"stopped":
			return "= arrêt"
		"full":
			return "pleine"
	return ""


static func _num(x: float) -> String:
	var txt := ("%.1f" % x).replace(".", ",")
	return txt.trim_suffix(",0")


## Bouton Z du couloir : prix de la relance et or du joueur, estompé si l'or manque (lot R22).
static func reroll_key(cost: int, gold: int) -> Array:
	if gold < cost:
		return ["Z", "relancer (%d or, tu as %d : pas assez)" % [cost, gold], "off"]
	return ["Z", "relancer (%d or, tu as %d)" % [cost, gold], ""]


func _feedback(rogue: Dictionary, events: Array, adr: int) -> void:
	for e in events:
		match str(e):
			"z_refused":
				var reason := str(rogue.get("z_reason", ""))
				var t: Array = Z_REASON_TEXT.get(reason, ["Z refusé", ""])
				var phase := str(rogue.get("phase", ""))
				if reason == "no_target" and NO_TARGET_TEXT.has(phase):
					t = NO_TARGET_TEXT[phase]
					var sub: String = t[1]
					t = [t[0], (sub % clock(rogue.get("phase_left_s", 0.0))) if "%s" in sub else sub]
				elif reason == "cursed":
					t = [t[0], t[1] % watts(CURSED_PCT, ftp_w)]
				var title: String = t[0] % adr if reason == "adrenaline" else t[0]
				# Z : retour immédiat (lot R23), il remplace le retour affiché au lieu d'attendre son tour
				_toasts.append({"title": title, "sub": t[1], "tone": "warn", "now": true})
				z_pulse = "refused"
			"z_ok":
				var a: Array = Z_ACTION_TEXT.get(str(rogue.get("z_action", "")), ["Z !", ""])
				_toasts.append({"title": a[0], "sub": a[1], "tone": "ok", "now": true})
				# attaque réussie (frappe, charges, rocher, parade) : anneau et éclair ; sinon anneau seul
				z_pulse = "hit" if str(rogue.get("z_action", "")) in ATTACK_ACTIONS else "ok"
			"card_on":
				var c: Array = CARD_ON_TEXT.get(str(rogue.get("card_on", "")), ["Carte déclenchée", ""])
				_toasts.append({"title": c[0], "sub": c[1], "tone": "warn" if str(rogue.get("card_on", "")) == "cursed" else "ok", "now": true})
				if z_pulse == "":
					z_pulse = "card"
			"shift_missed":
				var miss = rogue.get("shift_miss", null)
				if miss is Dictionary:
					var dt := float(miss.get("dt_s", 0.0))
					match str(miss.get("reason", "")):
						"early":
							_toasts.append({"title": "Trop tôt (%s s)" % _signed(dt), "sub": "Change quand l'anneau touche l'arche", "tone": "warn"})
						"late":
							_toasts.append({"title": "Trop tard (%s s)" % _signed(dt), "sub": "Change quand l'anneau touche l'arche", "tone": "warn"})
						"wrong_way":
							_toasts.append({"title": "Mauvais sens", "sub": "Suis la flèche de l'arche (+ ou −)", "tone": "warn"})
						_:
							_toasts.append({"title": "Arche manquée", "sub": "Passe une vitesse sous l'arche, dans le sens de la flèche", "tone": "warn"})
			"perfect_shift":
				_toasts.append({"title": "CHANGEMENT PARFAIT +10", "sub": "", "tone": "ok"})
			"firewall_contact":
				_toasts.append({"title": "TOUCHÉ PAR LE FIREWALL", "sub": "Ton bouclier fond : passe au-dessus de la consigne pour le distancer · Roc protège (−30 %)", "tone": "danger", "now": true})
			"parry_miss":
				# lot R23 : les dégâts reçus se disent, comme les attaques réussies
				_toasts.append({"title": "TOUCHÉ ! Coup non paré", "sub": "Bouclier entamé · dans la zone de parade : relance la puissance puis Z", "tone": "danger", "now": true})


static func _signed(dt: float) -> String:
	return ("+" if dt >= 0.0 else "−") + ("%.1f" % absf(dt)).replace(".", ",")


func _legends(rogue: Dictionary, phase: String) -> void:
	if not _legend.is_empty() or not phase in FIGHT_PHASES:
		return
	var tp = rogue.get("target_pct", null)
	if not seen_legends.has("overheat") and tp is Dictionary and tp.get("hi", null) != null:
		seen_legends["overheat"] = true    # lot R23 : la règle de la surchauffe s'explique à la première salle d'endurance
		_legend = LEGENDS["overheat"].duplicate()
		_save_seen()
		return
	if not seen_legends.has("firewall") and float(rogue.get("firewall_gap_m", 999.0)) < 80.0:
		seen_legends["firewall"] = true
		_legend = LEGENDS["firewall"].duplicate()
		_save_seen()
		return
	for u in upcoming(float(rogue.get("s_room", 0.0)), 60.0):
		var k := str(u["kind"])
		if LEGENDS.has(k) and not seen_legends.has(k):
			seen_legends[k] = true
			_legend = LEGENDS[k].duplicate()
			_save_seen()
			return

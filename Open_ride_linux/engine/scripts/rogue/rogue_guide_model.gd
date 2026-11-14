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
const TOAST_S := 2.5
const OVERHEAT_RATE_DEFAULT := 2.0  # adrénaline perdue par seconde en surchauffe, si le core ne la dit pas
const FIGHT_PHASES := ["ROOM", "BOSS"]

## Étiquette flottante au-dessus de chaque objet (lisible de loin, en majuscules courtes).
const MARKER_TAGS := {"strike_target": "Z !", "purge": "PURGE : Z", "rock": "ROCHER : Z", "parry_zone": "PARADE : Z",
	"tunnel": "%d rpm", "pad": "≥ %d %% · vitesse 10+", "arch": "%s"}
## Légende montrée la première fois que le joueur croise chaque sorte d'objet (et le Firewall).
const LEGENDS := {
	"strike_target": ["Nouveau : cible Z", "Appuie sur Z quand ta roue passe sur l'anneau rouge. Coûte 50 d'adrénaline et retire 6 % des PV de l'ennemi (Diesel : utilise tes charges de tunnel)."],
	"arch": ["Nouveau : arche de Perfect Shift", "La flèche et le signe disent le sens. Passe une vitesse dans ce sens quand l'anneau touche l'arche (± 0,75 s). Réussi : +10 d'adrénaline."],
	"tunnel": ["Nouveau : tunnel de cadence", "Tiens la cadence affichée (± 3 rpm) dans le tunnel vert : chaque 10 s donne une charge pour la prochaine cible Z."],
	"pad": ["Nouveau : pavé de sprint", "En vitesse 10 ou plus, au-dessus de la puissance affichée, tes dégâts sont multipliés sur le pavé."],
	"parry_zone": ["Nouveau : zone de parade", "Relance fort la puissance puis appuie sur Z dans la zone. Sinon, le coup te retire du bouclier."],
	"purge": ["Nouveau : balise de purge", "Pendant un piratage (vitesse bloquée ou imposée), appuie sur Z sur la balise pour l'arrêter."],
	"rock": ["Nouveau : rocher", "Roule en Roc (sous 70 rpm) pour gagner des charges, puis Z sur le rocher pour le briser."],
	"overheat": ["Nouveau : surchauffe (endurance)", "En salle d'endurance, reste dans la plage de la consigne. Au-dessus du plafond (75 % FTP, ou la cible + 10 points si elle est plus haute) pendant 5 s, tu surchauffes : l'adrénaline fond de 2 par seconde et Z est bloqué jusqu'à ce que tu redescendes."],
	"firewall": ["Le Firewall", "Un mur roule derrière toi à la puissance de la salle. S'il te touche, ton bouclier fond et tu perds de l'or. Tiens la consigne pour garder ton avance."],
}
const Z_REASON_TEXT := {
	"adrenaline": ["Z refusé : adrénaline %d / 50", "Tiens la puissance cible pour remplir la jauge (+0,5 par seconde, +10 par Perfect Shift)"],
	"overheat": ["Z refusé : surchauffe", "Baisse la puissance pour refroidir"],
	"no_target": ["Z : rien à frapper ici", "Attends un objet marqué « Z »"],
	"no_charge": ["Z refusé : aucune charge", "Tiens la cadence dans les tunnels verts pour charger"],
	"no_roc_charge": ["Z refusé : aucune charge de Roc", "Roule en Roc (sous 70 rpm) pour charger"],
	"no_surge": ["Parade ratée : pas de relance", "Accélère fort juste avant d'appuyer sur Z"],
	"no_hack": ["Z : aucun piratage à purger", "La balise ne sert que pendant un piratage"],
	"cursed": ["Z bloqué par la carte Maudit", "Quitte la vitesse 10 pour frapper"],
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
	"purge": ["PIRATAGE PURGÉ", "Tes vitesses sont libres"],
	"reroll": ["Cartes relancées", ""],
}
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
## Dernier retour d'un Z court de la trame (lot R23) : « ok », « refused » ou vide ; la vue dessine l'anneau.
var z_pulse := ""


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
		"next_lines": [], "fw": {}, "consigne": {}, "hint": "", "keys": [], "tone": "info"}
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
		var band := target_band(tgt_lo, tgt_hi)
		var sub := "Garde %s" % band if tgt_lo > 0 else ""
		if level == "warn" and tgt_lo > 0:
			sub = "Accélère : %s" % band
		if gap_m <= 0.0:
			sub = "Bouclier qui fond · or perdu"
		out["fw"] = {"text": "TE TOUCHE !" if gap_m <= 0.0 else "%d s d'avance" % int(round(float(gap_s))), "sub": sub, "level": level}
	elif target is Dictionary and phase in ["WARMUP", "COOLDOWN"]:
		var lo := int(target.get("lo", 0))
		var hi = target.get("hi", null)
		var big := ("≤ %d %% FTP" % int(hi)) if lo <= 0 and hi != null else (("%d–%d %% FTP" % [lo, int(hi)]) if hi != null else "≥ %d %% FTP" % lo)
		var inside := power_pct >= float(lo) and (hi == null or power_pct <= float(hi))
		out["consigne"] = {"big": big, "sub": "Tu es à %d %%%s" % [int(round(power_pct)), " ✔" if inside else ""], "ok": inside}
	out["adr_trend"] = adrenaline_trend_text(rogue)
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
			hint = "Roule souple, rien à faire pour l'instant : la grille se charge"
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
		var limit := int(tgt_hi) if tgt_hi != null else 75
		if gap_m <= 0.0:
			hint = "Accélère ! Le Firewall te touche"
			tone = "danger"
		elif overheat:
			# Lot R23 : la surchauffe se dit tout le temps qu'elle dure, avec ce qu'elle coûte et la sortie.
			var melt := OVERHEAT_RATE_DEFAULT
			if trend is Dictionary:
				melt = absf(float(trend.get("rate_per_s", -OVERHEAT_RATE_DEFAULT)))
			hint = "SURCHAUFFE : descends sous %d %% FTP · adrénaline −%s/s, Z bloqué" % [limit, _num(melt)]
			tone = "danger"
		elif soon != null:
			hint = "Trop fort : au-dessus de %d %% FTP, surchauffe dans %d s" % [limit, maxi(int(ceil(float(soon))), 1)]
			tone = "warn"
		elif hack is Dictionary:
			hint = "Piratage ! Vitesse %s : Z sur la balise de purge pour l'arrêter" % ("bloquée" if bool(hack.get("locked", false)) else "imposée")
			tone = "warn"
			keys[0] = ["Z", "purger (sur la balise)", "on"]   # lot R23 : le bouton dit ce que Z fait maintenant
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
					keys.insert(0, [sign, "Perfect Shift", "on"])
				"tunnel":
					hint = ("Tunnel : tiens %d rpm" % int(round(float(u["param"] if u["param"] != null else 90.0)))) + ("" if now else " (dans %d m)" % d)
				"pad":
					hint = ("Pavé : vitesse 10+ et ≥ %d %% FTP" % int(round(float(u["param"] if u["param"] != null else 1.4) * 100.0))) + ("" if now else " (dans %d m)" % d)
				"parry_zone":
					hint = "Parade : relance la puissance puis Z" if now else "Zone de parade dans %d m : prépare une relance puis Z" % d
				"purge":
					hint = "Balise de purge : Z seulement pendant un piratage" if now else "Balise de purge dans %d m" % d
				"rock":
					hint = "Rocher : Z (charges de Roc)" if now else "Rocher dans %d m : roule en Roc pour charger, puis Z" % d
		if hint == "":
			if z_ready:
				hint = "Z prêt : vise la prochaine cible"
			elif tgt_lo > 0:
				hint = "Tiens %s pour remplir l'adrénaline (%d/50)" % [target_band(tgt_lo, tgt_hi), adr]
			else:
				hint = "Tiens la puissance pour remplir l'adrénaline (%d/50)" % adr
	out["hint"] = hint
	out["keys"] = keys
	out["tone"] = tone


## Consigne de puissance en texte : « ≥ 70 % FTP », ou « 70–75 % FTP » quand elle a un plafond (endurance, R23).
static func target_band(lo: int, hi: Variant) -> String:
	if hi == null or int(hi) <= lo:
		return "≥ %d %% FTP" % lo if hi == null else "%d %% FTP" % lo
	return "%d–%d %% FTP" % [lo, int(hi)]


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
				var title: String = t[0] % adr if reason == "adrenaline" else t[0]
				# Z : retour immédiat (lot R23), il remplace le retour affiché au lieu d'attendre son tour
				_toasts.append({"title": title, "sub": t[1], "tone": "warn", "now": true})
				z_pulse = "refused"
			"z_ok":
				var a: Array = Z_ACTION_TEXT.get(str(rogue.get("z_action", "")), ["Z !", ""])
				_toasts.append({"title": a[0], "sub": a[1], "tone": "ok", "now": true})
				z_pulse = "ok"
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
				_toasts.append({"title": "PERFECT SHIFT +10", "sub": "", "tone": "ok"})
			"firewall_contact":
				_toasts.append({"title": "LE FIREWALL TE TOUCHE", "sub": "Passe au-dessus de la consigne pour le distancer · Roc protège (−30 %)", "tone": "danger"})


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

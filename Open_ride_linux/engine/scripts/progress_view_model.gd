extends RefCounted

## Bilan de progression de la fin de séance sans affichage (lot V9, contrat IPC 1.4 §5 `xp_result`) :
## expérience par source, total, pièces, temps de l'équipement, barre d'expérience avant et après, passage
## de niveau, déblocages et défis. Format français, comme summary_view_model.gd (lot N4).
##
## - `view(xp, summary, names)` renvoie {} sans message (le bilan de N4 reste inchangé), sinon
##   {eligible, lines: [{label, value}], bar: {before, after, text} ou {}, level_up: texte ou "",
##   unlocked: [texte], challenges: [texte], more: texte, garage: vrai si une pièce est devenue achetable}.
## - Séance refusée (`eligible` faux) : une seule ligne explicative selon `reason`.
## - La barre va de 0 au seuil du niveau suivant (`xp_total / xp_next_level`) ; si le niveau a changé, elle
##   repart de zéro. Niveau maximal (pas de seuil suivant) : pas de barre, la ligne « Niveau maximal ».
## - `names` : {identifiant: {name, slot}} des pièces (message `garage`) pour « Débloqué : cadre Profilé » ;
##   identifiant inconnu : l'identifiant lui-même.
## Pas de class_name : charger par preload("res://scripts/progress_view_model.gd").

const SOURCE_LABELS := {
	"distance": "Distance", "climb": "Dénivelé", "erg": "Entraînement terminé", "erg_bonus": "Bonus d'entraînement",
	"segment": "Segments", "segment_pr": "Records de segments", "jersey": "Maillots",
	"rogue": "Cyber-Rogue", "rogue_boss": "Boss de Cyber-Rogue",
}
const REASON_TEXTS := {
	"too_short": "Séance de moins de 5 minutes : pas d'expérience",
	"replay": "Séance déjà comptée : pas d'expérience",
	"simulated": "Séance simulée : pas d'expérience",
	"imported": "Séance importée : pas d'expérience",
}
const SLOT_NAMES := {"frame": "cadre", "wheels": "roues", "helmet": "casque", "kit": "tenue",
	"socks": "chaussettes", "glasses": "lunettes"}
const BAR_CELLS := 10


static func _fr(value: float, decimals: int) -> String:
	return (("%%.%df" % decimals) % value).replace(".", ",")


## « −12,5 s » (gagné) ou « +8,0 s » (perdu) : signe typographique, virgule décimale.
static func signed_seconds(seconds: float) -> String:
	return ("+" if seconds > 0.0 else "−") + _fr(absf(seconds), 1) + " s"


static func bar_text(fraction: float) -> String:
	var n := clampi(int(round(fraction * BAR_CELLS)), 0, BAR_CELLS)
	return "■".repeat(n) + "□".repeat(BAR_CELLS - n)


func view(xp, summary: Dictionary = {}, names: Dictionary = {}) -> Dictionary:
	if not (xp is Dictionary) or xp.is_empty():
		return {}
	if not bool(xp.get("eligible", false)):
		var reason := str(xp.get("reason", ""))
		return {"eligible": false, "lines": [{"label": REASON_TEXTS.get(reason, "Séance sans expérience"), "value": ""}],
			"bar": {}, "level_up": "", "unlocked": [], "challenges": [], "more": "", "garage": false}
	var lines: Array = []
	for g in xp.get("gains", []):
		if g is Dictionary:
			lines.append({"label": _gain_label(str(g.get("source", "")), summary), "value": "+%d XP" % int(g.get("points", 0))})
	lines.append({"label": "Total", "value": "+%d XP" % int(xp.get("total", 0))})
	var coins := int(xp.get("coins_gained", 0))
	lines.append({"label": "Pièces", "value": "+%d (solde %d)" % [coins, int(xp.get("coins_total", 0))]})
	var gain = xp.get("equipment_gain_s", null)
	if gain is float or gain is int:
		lines.append({"label": "Équipement", "value": signed_seconds(float(gain)) + " sur la séance"})
	var level_before := int(xp.get("level_before", 1))
	var level_after := int(xp.get("level_after", level_before))
	var level_up := "Niveau %d !" % level_after if level_after > level_before else ""
	var unlocked: Array = []
	for id in xp.get("unlocked", []):
		unlocked.append("Débloqué : " + _item_text(str(id), names))
	var challenges: Array = []
	for c in xp.get("challenges", []):
		if c is Dictionary:
			var text := "Défi réussi : %s" % str(c.get("name", c.get("id", "")))
			if c.get("reward_item") != null:
				text += " — " + _item_text(str(c["reward_item"]), names)
			challenges.append(text)
	return {"eligible": true, "lines": lines, "bar": _bar(xp, level_before, level_after), "level_up": level_up,
		"unlocked": unlocked, "challenges": challenges,
		"more": "… et d'autres déblocages ou défis" if bool(xp.get("more", false)) else "",
		"garage": not xp.get("unlocked", []).is_empty()}


func _gain_label(source: String, summary: Dictionary) -> String:
	var label := str(SOURCE_LABELS.get(source, source))
	if source == "distance" and summary.get("distance_m") != null:
		return "%s %s km" % [label, _fr(float(summary["distance_m"]) / 1000.0, 1)]
	if source == "climb" and summary.get("elevation_gain_m") != null:
		return "%s %d m" % [label, int(round(float(summary["elevation_gain_m"])))]
	return label


func _item_text(id: String, names: Dictionary) -> String:
	var info = names.get(id)
	if info is Dictionary:
		var slot := str(SLOT_NAMES.get(str(info.get("slot", "")), ""))
		return ("%s %s" % [slot, info.get("name", id)]).strip_edges()
	return id


func _bar(xp: Dictionary, level_before: int, level_after: int) -> Dictionary:
	var next := float(xp.get("xp_next_level", 0) if xp.get("xp_next_level") != null else 0)
	if next <= 0.0:
		return {"max": true, "text": "Niveau maximal", "before": 1.0, "after": 1.0}
	var total := float(xp.get("xp_total", 0))
	var after := clampf(total / next, 0.0, 1.0)
	var before := clampf((total - float(xp.get("total", 0))) / next, 0.0, 1.0) if level_after == level_before else 0.0
	return {"max": false, "before": before, "after": after,
		"text": "Niveau %d : %s %d / %d XP" % [level_after, bar_text(after), int(total), int(next)]}

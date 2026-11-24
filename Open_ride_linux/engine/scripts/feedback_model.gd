extends RefCounted

## Retours et consignes communs à tous les modes (lot RT1, audit du 21 novembre 2026,
## /mnt/project-files/plans/AUDIT_RETOURS_JEU_2026-11-21.md, maquettes validées le 21 novembre). Sans nœud.
##
## Règle : chaque moment se voit, s'entend et se lit, de la même façon dans tous les modes.
## - Cinq familles de moments (`FAMILIES`) : DÉPART, BIEN (gain, adversaire éliminé, dépassement), ATTENTION
##   (dernier, danger), REFUSÉ (appui sans effet et sa raison), RÉSULTAT (victoire, place, éliminé, entraînement
##   fini). Chaque moment donne ensemble un mot en tête (« + BIEN »…), une couleur fixe de la famille, un titre, une
##   ligne de détail et un son de la famille (un mode peut donner sa variante, ex. `jingle_elim`).
## - Bandeau du moment (`toast`) au-dessus de la zone de consigne, TOAST_S secondes ; le RÉSULTAT au milieu de
##   l'écran (`result`), RESULT_S secondes.
## - Zone de consigne unique en bas de l'écran (`consigne`), la même pour tous les modes : `k` (« À FAIRE »),
##   `action` (quoi faire maintenant), `detail` (« Objectif … · Pourquoi … »), `chips` (boutons). Chaque mode la
##   calcule dans son propre modèle (`consigne(...)`) : ce modèle-ci ne connaît aucune règle de jeu.
## - Moment de fin unique (choix du propriétaire, 21 novembre 10h37) : une fois l'issue connue, la consigne devient
##   « COURSE FINIE · 1er sur 8 / Roule au calme autant que tu veux / Y puis A maintenu = bilan » jusqu'à la fin de
##   la séance ; plus jamais une course qui a l'air de durer.
## - Fin commune (lot RT2, révision 1.34) : `state.arrival` (bout d'un parcours en ligne, arrivée du Grand Prix ou
##   de la Course, entraînement fini) donne le même RÉSULTAT et la même consigne de fin, si aucun mode ne l'a déjà
##   annoncé ; le bilan reprend les mêmes mots (`arrival_result`, summary_view_model.gd `result_card`).
## Le Click perdu ne s'affiche pas (choix du propriétaire, 21 novembre 11h05 : journal technique seulement).
## Pas de class_name : preload("res://scripts/feedback_model.gd").

const UiTheme := preload("res://scripts/ui_theme.gd")

const TOAST_S := 4.0
const RESULT_S := 6.0
const GOLD_BG := UiTheme.FB_GOLD
const PLACE_BG := UiTheme.FB_PLACE
const OUT_BG := UiTheme.FB_OUT
## Famille -> mot de tête, couleur du bandeau, son par défaut (event_sounds_model.gd JINGLES ; "" : aucun).
const FAMILIES := {
	"depart": {"tag": "▶ DÉPART", "color": UiTheme.FB_DEPART, "sound": ""},
	"bien": {"tag": "+ BIEN", "color": UiTheme.FB_BIEN, "sound": "fb_bien"},
	"attention": {"tag": "! ATTENTION", "color": UiTheme.FB_ATTENTION, "sound": "fb_attention"},
	"refus": {"tag": "× REFUSÉ", "color": UiTheme.FB_REFUS, "sound": "fb_refus"},
	"resultat": {"tag": "★ RÉSULTAT", "color": GOLD_BG, "sound": "jingle_winner"},
}
## Ton d'un résultat -> couleur et son : victoire (or), autre place (bleu), éliminé ou abandon (rouge), fini (or).
const RESULT_TONES := {"win": [GOLD_BG, "jingle_winner"], "place": [PLACE_BG, "jingle_finish"],
	"out": [OUT_BG, "jingle_elim"], "done": [GOLD_BG, "jingle_finish"]}
const BILAN_CHIP := "Y puis A maintenu = bilan"
const CALM_ACTION := "Roule au calme autant que tu veux"
const CALM_DETAIL := "Ton résultat est gardé · le bilan s'ouvre quand tu le demandes"

var _toast := {}        # {family, title, sub, until}
var _result := {}       # {tone, title, sub, until}
var _done := {}         # consigne de fin, gardée jusqu'à la fin de la séance : {k, action, detail}
var _prev_session := ""
var _erg_done := false
var _arrival_seen := false
## Boutons écrits ajoutés devant « Y puis A maintenu = bilan » dans la consigne de fin (place réservée : le fil
## « Enchaîner plusieurs parcours en session libre » y mettra « A : Enchaîner un autre parcours » quand la trame le
## permet) ; [] par défaut. Posés par main.gd à chaque trame, jamais gardés d'une séance à l'autre.
var end_chips: Array = []


func reset() -> void:
	_toast = {}
	_result = {}
	_done = {}
	_prev_session = ""
	_erg_done = false
	_arrival_seen = false


## Moment d'une famille (`bien`, `attention`, `refus`, `depart`) : bandeau TOAST_S secondes. Rend le son à jouer
## (`sound` : variante du mode ; vide : son de la famille). Un moment remplace le précédent.
func push(family: String, title: String, sub: String, now_s: float, sound := "") -> String:
	if not FAMILIES.has(family) or family == "resultat":
		return ""
	_toast = {"family": family, "title": title, "sub": sub, "until": now_s + TOAST_S}
	return sound if sound != "" else str(FAMILIES[family]["sound"])


## Résultat (`tone` : win, place, out, done) au milieu RESULT_S secondes, puis consigne de fin `done_k`
## (« COURSE FINIE · 1er sur 8 ») jusqu'à la fin de la séance ; `done_action` remplace « Roule au calme… »
## (cycliste éliminé : la course continue sans lui). Rend le son à jouer.
func result(tone: String, title: String, sub: String, now_s: float, done_k: String, done_action := "",
		sound := "", done_detail := "") -> String:
	var t: Array = RESULT_TONES.get(tone, RESULT_TONES["place"])
	_result = {"tone": tone, "title": title, "sub": sub, "until": now_s + RESULT_S}
	_toast = {}
	_done = {"k": done_k, "action": done_action if done_action != "" else CALM_ACTION,
		"detail": done_detail if done_detail != "" else CALM_DETAIL}
	return sound if sound != "" else str(t[1])


## Moments rendus par les modèles des modes : [{family, title, sub, sound?}] ou, pour un résultat,
## {family: "resultat", tone, title, sub, done_k, done_action?, sound?}. Rend les sons à jouer.
func push_all(moments: Array, now_s: float) -> Array:
	var out := []
	for m in moments:
		if not m is Dictionary:
			continue
		var snd := ""
		if str(m.get("family", "")) == "resultat":
			snd = result(str(m.get("tone", "place")), str(m.get("title", "")), str(m.get("sub", "")), now_s,
				str(m.get("done_k", "COURSE FINIE")), str(m.get("done_action", "")), str(m.get("sound", "")))
		else:
			snd = push(str(m.get("family", "")), str(m.get("title", "")), str(m.get("sub", "")), now_s,
				str(m.get("sound", "")))
		if snd != "" and not snd in out:
			out.append(snd)
	return out


## Une fois par trame `state` : départ (READY vers RUNNING, avec l'objectif du mode `goal`), fin d'un
## entraînement ERG (`workout_done`), oubli de la fin quand la séance s'arrête. Rend les sons à jouer.
func on_state(state: Dictionary, now_s: float, goal := "") -> Array:
	var out := []
	var session := str(state.get("session_state", ""))
	if session in ["IDLE", "READY", "FINISHED"] and _prev_session in ["RUNNING", "PAUSED"]:
		_done = {}
		_result = {}
		_toast = {}
		_erg_done = false
		_arrival_seen = false
	if session == "RUNNING" and _prev_session == "READY" and goal != "":
		push("depart", "C'est parti !", goal, now_s)
	var done = state.get("workout_done", null)
	if done is Dictionary and session in ["RUNNING", "PAUSED"] and not _erg_done:
		_erg_done = true
		var name := str(done.get("workout_name", "")).strip_edges()
		out.append(result("done", "ENTRAÎNEMENT TERMINÉ", ("« %s »" % name) if name != "" else "Bravo !", now_s,
			"ENTRAÎNEMENT FINI", "", "jingle_finish", "Ta séance est gardée · le bilan s'ouvre quand tu le demandes"))
	elif not done is Dictionary:
		_erg_done = false
	var arr = state.get("arrival", null)
	if arr is Dictionary and session in ["RUNNING", "PAUSED"] and not _arrival_seen:
		_arrival_seen = true
		var r := arrival_result(arr)
		if not is_done() and not r.is_empty():   # un mode a déjà donné son résultat (piste, survivant, ERG)
			out.append(result(str(r["tone"]), str(r["title"]), str(r["sub"]), now_s, str(r["done_k"]),
				str(r.get("done_action", "")), "", str(r.get("done_detail", ""))))
	elif not arr is Dictionary:
		_arrival_seen = false
	_prev_session = session
	return out


## Fin déjà annoncée (la consigne de fin remplace celle du mode).
func is_done() -> bool:
	return not _done.is_empty()


## Vue : {visible, toast: {tag, title, sub, color} ou {}, result: {tag, title, sub, color} ou {},
## consigne: {k, action, detail, chips} ou {}}. `mode_consigne` : consigne du mode ({} : aucune), remplacée par la
## consigne de fin une fois l'issue connue. Rien hors de RUNNING et PAUSED.
func view(state: Dictionary, now_s: float, mode_consigne: Dictionary = {}) -> Dictionary:
	var session := str(state.get("session_state", ""))
	if not session in ["RUNNING", "PAUSED"]:
		return {"visible": false, "toast": {}, "result": {}, "consigne": {}}
	var out := {"visible": true, "toast": {}, "result": {}, "consigne": {}}
	if not _toast.is_empty() and now_s < float(_toast["until"]):
		var f: Dictionary = FAMILIES[_toast["family"]]
		out["toast"] = {"family": _toast["family"], "tag": f["tag"], "title": _toast["title"], "sub": _toast["sub"],
			"color": f["color"]}
	if not _result.is_empty() and now_s < float(_result["until"]):
		out["result"] = {"tag": FAMILIES["resultat"]["tag"], "title": _result["title"], "sub": _result["sub"],
			"color": RESULT_TONES.get(_result["tone"], RESULT_TONES["place"])[0]}
	if not _done.is_empty():
		out["consigne"] = {"k": _done["k"], "action": _done["action"], "detail": _done["detail"],
			"chips": end_chips + [BILAN_CHIP]}
	elif not mode_consigne.is_empty():
		out["consigne"] = {"k": str(mode_consigne.get("k", "À FAIRE")), "action": str(mode_consigne.get("action", "")),
			"detail": str(mode_consigne.get("detail", "")), "chips": mode_consigne.get("chips", [])}
	return out


## Ligne de détail d'une consigne : « Objectif … · Pourquoi … » (parties vides sautées).
static func detail(goal: String, why: String) -> String:
	var parts := []
	if goal != "":
		parts.append("Objectif : " + goal)
	if why != "":
		parts.append("Pourquoi : " + why)
	return " · ".join(parts)


## « 1er », « 2e »…
static func place_text(n: int) -> String:
	return "1er" if n == 1 else "%de" % n


## Titre et ton d'un résultat de course : (« VICTOIRE ! », win) à la 1re place, (« ARRIVÉE · 3e sur 8 », place) sinon.
static func race_result(place: int, of: int) -> Array:
	if place == 1:
		return ["VICTOIRE !", "win"]
	return ["ARRIVÉE · %s sur %d" % [place_text(place), of], "place"]


## Titres de l'issue de la séance (`state.arrival` et `summary.arrival`, révision 1.34, lot RT2), mêmes mots en
## séance et au bilan : {tone, title, sub, done_k, done_action?} ; {} pour un entraînement fini (annoncé par
## `workout_done`) ou une sorte inconnue.
static func arrival_result(arr: Dictionary) -> Dictionary:
	var kind := str(arr.get("kind", ""))
	if kind == "grandprix" or kind == "race":
		var name := "Grand Prix des objets" if kind == "grandprix" else "Course"
		var place = arr.get("place", null)
		var of = arr.get("of", null)
		if not (place is int or place is float) or not (of is int or of is float) or int(of) < 2:
			return {"tone": "done", "title": "ARRIVÉE", "sub": name, "done_k": "COURSE FINIE"}
		var rr := race_result(int(place), int(of))
		var pl := "%s sur %d" % [place_text(int(place)), int(of)]
		return {"tone": rr[1], "title": rr[0], "sub": ("Tu remportes la course · " + pl) if int(place) == 1 else name,
			"done_k": "COURSE FINIE · " + pl}
	if kind == "route":
		return {"tone": "done", "title": "ARRIVÉE", "sub": "Bout du parcours : demi-tour automatique",
			"done_k": "PARCOURS FINI", "done_action": "Roule au calme : tu repars dans l'autre sens"}
	return {}

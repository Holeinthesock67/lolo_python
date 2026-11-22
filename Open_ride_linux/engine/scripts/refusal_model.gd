extends RefCounted

## Refus expliqués (lot RT4, audit des retours du 21 novembre 2026, /mnt/project-files/plans/
## AUDIT_RETOURS_JEU_2026-11-21.md §4 et §6). Sans nœud, sans règle de jeu propre : ce modèle ne fait que
## traduire en mots simples ce que le core a refusé (ou ce qu'un appui ne peut pas faire), avec, à chaque fois,
## POURQUOI et QUOI FAIRE.
##
## Trois sortes de refus, un seul format :
## - départ refusé par le core (`error` en réponse à `start`, écran Prêt) : `launch(code, text)` rend
##   {why, todo} ; l'écran Prêt affiche « × REFUSÉ · Départ impossible : <why> » puis « À faire : <todo> »
##   (`launch_text`). Auparavant : « Échec : <texte du core> » sur quelques écrans seulement, et rien du tout
##   pour un entraînement ou un plan refusés en séance libre ;
## - appui sans effet en séance (Z court en Grand Prix sans objet, pendant le tirage, en piste ou au Dernier
##   survivant, sans bonus en réserve) : `press(event, state)` rend un moment de la famille « refus » de
##   feedback_model.gd (bandeau « × REFUSÉ », couleur grise, son `fb_refus`, titre et quoi faire) ;
## - bonus refusé par le core (`powerup.refused`, contrat 1.13) : `on_state(state)` rend le même moment, une
##   fois par refus, avec la raison du core et quoi faire ;
## - perte du trainer en séance : `on_state(state)` rend un moment « ! ATTENTION » (Trainer perdu, quoi faire),
##   une fois par perte. La ligne « ÉTAT: … TRAINER … ENTRÉE » est retirée par le lot NI1 (#963).
## Le Click perdu ne s'affiche jamais (choix du propriétaire, 21 novembre 11h05 : journal technique seulement).
## Cyber-Rogue et mode WTF gardent leurs propres refus (z_reason, lot R22 ; plat refusé), déjà expliqués.
## Le mot écrit vient toujours avant la couleur. Pas de class_name : preload("res://scripts/refusal_model.gd").

const SegmentHud := preload("res://scripts/segment_hud_model.gd")

const TAG := "× REFUSÉ"
const LAUNCH_HEAD := "Départ impossible : "
const TODO_HEAD := "À faire : "
## Message du core quand rien d'autre ne correspond : on garde son texte, et on dit quoi faire.
const LAUNCH_FALLBACK_TODO := "change le réglage indiqué puis relance avec « Lancer »"

## Refus d'un départ, par code d'erreur du contrat (§5, codes d'erreur) : [pourquoi, quoi faire]. Le texte du
## core précise parfois le pourquoi (`LAUNCH_PATTERNS`, essayés d'abord).
const LAUNCH_CODES := {
	"workout_invalid": ["l'entraînement choisi est illisible", "choisis un autre entraînement, ou « Session libre »"],
	"plan_invalid": ["aucune séance du plan à faire aujourd'hui", "choisis « Session libre » ou un entraînement de la liste"],
	"bot_invalid": ["les bots choisis ne conviennent pas", "change les lignes « Bot » de cet écran (4 bots au plus)"],
	"run_invalid": ["objectif ou durée de run hors liste", "choisis un objectif et une durée de la liste"],
	"item_locked": ["une pièce choisie n'est pas débloquée", "choisis une pièce que tu possèdes au Garage"],
	"world_unavailable": ["pas de route proche, ou carte pas encore téléchargée",
		"rapproche le départ d'une route, ou connecte le PC à Internet"],
	"route_not_found": ["le parcours choisi n'existe plus", "choisis un autre parcours dans la liste"],
	"route_invalid": ["le parcours choisi est illisible", "choisis un autre parcours dans la liste"],
	"busy": ["une autre action est en cours", "attends quelques secondes puis relance"],
	"trainer_control_refused": ["le trainer refuse les consignes",
		"arrête l'appli qui le pilote (Zwift, montre), puis relance"],
}
## Refus du core reconnus à leur texte (session.py, `bad_args` du départ) : [morceau du texte, pourquoi, quoi faire].
const LAUNCH_PATTERNS := [
	["sans entraînement ERG", "ce mode se roule sans entraînement ERG",
		"reviens à l'accueil et lance le mode sans choisir d'entraînement"],
	["se courent en SIM", "cette épreuve se court sans entraînement ERG",
		"reviens à l'accueil et lance l'épreuve sans choisir d'entraînement"],
	["sur un vélodrome", "les épreuves de piste se courent sur un vélodrome",
		"choisis un vélodrome dans la liste des parcours"],
	["compose lui-même", "ce mode choisit lui-même ses adversaires", "retire les bots choisis puis relance"],
	["composent elles-mêmes", "l'épreuve choisit elle-même ses adversaires", "retire les bots choisis puis relance"],
	["trop court", "le parcours est trop court pour cette course",
		"choisis un parcours plus long, ou baisse les adversaires ou l'écart"],
	["ftp_test", "test de FTP inconnu", "relance le test depuis « Test de FTP »"],
	["Aucune séance du plan", "aucune séance du plan à faire aujourd'hui",
		"choisis « Session libre » ou un entraînement de la liste"],
	["pour le fantôme", "pas encore de fantôme sur ce parcours", "roule-le une fois en entier, ou retire la ligne « Fantôme »"],
	["Bots refusés", "les bots choisis ne conviennent pas", "change les lignes « Bot » de cet écran (4 bots au plus)"],
	["monde ouvert", "cette course a besoin d'un parcours de la liste", "choisis un circuit ou un parcours en ligne"],
	["refusé (", "un réglage du mode est hors bornes", "remets les réglages de cet écran dans leurs bornes"],
]

## Raisons d'un bonus refusé (contrat 1.13, `powerup.refused.reason`) : quoi faire.
const POWERUP_TODO := {
	"no_bots": "ajoute des bots sur l'écran Prêt, ou garde-le pour une autre séance",
	"no_descent": "garde-le pour la prochaine descente",
	"near_finish": "garde-le pour la prochaine séance",
	"no_gravel": "garde-le pour le prochain chemin",
	"erg": "repasse en SIM (pause, « Mode ») pour t'en servir",
}

var _trainer_lost := false
var _refused_key := ""


func reset() -> void:
	_trainer_lost = false
	_refused_key = ""


## Départ refusé : {why, todo}, toujours rempli (texte du core gardé en dernier recours).
static func launch(code: String, text: String) -> Dictionary:
	for p in LAUNCH_PATTERNS:
		if text.find(str(p[0])) >= 0:
			return {"why": str(p[1]), "todo": str(p[2])}
	if LAUNCH_CODES.has(code):
		return {"why": str(LAUNCH_CODES[code][0]), "todo": str(LAUNCH_CODES[code][1])}
	var why := text.strip_edges().trim_suffix(".")
	if why == "":
		why = "refusé par le core (%s)" % code if code != "" else "refusé par le core"
	return {"why": why.left(1).to_lower() + why.substr(1) if why.length() > 1 else why, "todo": LAUNCH_FALLBACK_TODO}


## Ligne d'état de l'écran Prêt pour un départ refusé : deux lignes, mot écrit en tête.
static func launch_text(code: String, text: String) -> String:
	var r := launch(code, text)
	return "%s · %s%s\n%s%s" % [TAG, LAUNCH_HEAD, r["why"], TODO_HEAD, r["todo"]]


## Appui relayé par le core pendant la séance : moment « refus » ({family, title, sub}) quand l'appui ne peut
## rien faire, {} sinon (appui utile, menu affiché, Cyber-Rogue, mode WTF, entraînement ERG où Z passe le bloc).
## `state` : dernière trame, d'avant l'appui (le core relaie l'appui avant de le traiter).
static func press(event: String, state: Dictionary, rogue_active := false, menu_visible := false) -> Dictionary:
	if event != "Z_SHORT" or rogue_active or menu_visible:
		return {}
	if str(state.get("session_state", "")) != "RUNNING" or state.get("wtf", null) is Dictionary:
		return {}
	var erg = state.get("erg", null)
	if erg is Dictionary and str(erg.get("kind", "workout")) == "workout":
		return {}   # Z court : bloc suivant de l'entraînement
	var gp = state.get("gp", null)
	if gp is Dictionary:
		var roll = gp.get("roll_s", 0.0)
		if (roll is float or roll is int) and float(roll) > 0.0:
			return _moment("Z refusé : tirage en cours", "Attends la fin du tirage, puis Z lance ton objet")
		if gp.get("held", null) == null:
			return _moment("Z refusé : aucun objet", "Passe dans une boîte « + BONUS » pour en prendre un")
		return {}
	if state.get("track", null) is Dictionary:
		return _moment("Z sans effet sur la piste", "Ici, tout se joue aux jambes : suis la consigne en bas")
	if state.get("survivor", null) is Dictionary:
		return _moment("Z sans effet au Dernier survivant", "Ici, tout se joue aux jambes : passe l'arche avant le dernier")
	var pu = state.get("powerup", null)
	if pu is Dictionary:
		if pu.get("active", null) != null:
			return _moment("Z refusé : un bonus est déjà en cours", "Attends sa fin pour lancer le suivant")
		if pu.get("held", null) == null and not pu.get("refused", null) is Dictionary:
			return _moment("Z refusé : aucun bonus en réserve", "Passe sous une arche bonus pour en gagner un")
	return {}


## Une fois par trame `state` : bonus refusé par le core (une fois par refus) et perte du trainer en séance (une
## fois par perte). Rend les moments à pousser dans feedback_model.gd (push_all).
func on_state(state: Dictionary) -> Array:
	var out: Array = []
	var session := str(state.get("session_state", ""))
	var riding := session in ["RUNNING", "PAUSED"]
	var lost := riding and str(state.get("trainer_status", "")) == "LOST"
	if lost and not _trainer_lost:
		out.append({"family": "attention", "title": "Trainer perdu : reconnexion en cours",
			"sub": "Continue de pédaler pour le réveiller · la séance reprend toute seule"})
	_trainer_lost = lost
	var pu = state.get("powerup", null) if riding else null
	var refused = pu.get("refused", null) if pu is Dictionary else null
	if refused is Dictionary:
		var kind := str(refused.get("kind", ""))
		var reason := str(refused.get("reason", ""))
		var key := kind + "/" + reason
		if key != _refused_key:
			var why := str(SegmentHud.REFUSAL_REASONS.get(reason, SegmentHud.KEPT))
			var title := SegmentHud.power_up_name(kind) + (" refusée" if kind in SegmentHud.POWERUP_FEMININE else " refusé")
			out.append({"family": "refus", "title": "%s : %s" % [title, why],
				"sub": "Gardé en réserve · " + str(POWERUP_TODO.get(reason, "réessaie plus tard"))})
		_refused_key = key
	else:
		_refused_key = ""
	return out


static func _moment(title: String, sub: String) -> Dictionary:
	return {"family": "refus", "title": title, "sub": sub}

extends RefCounted

## Écrans de l'historique (lot O28, contrat IPC révision 1.5), sans nœud. Pas de class_name : charger par
## preload("res://scripts/history_view_model.gd").
##
## Les calculs sont ceux du core (`openride-core history`, `summary` et `ftp-test --history`) :
## - SCREEN « Historique » (accueil) : « Cumul par semaine », « Tests de FTP », puis les séances du
##   message `history`, de la plus récente à la plus ancienne (date et parcours ; durée, distance, NP et
##   TSS) ; A sur une séance demande son bilan (`history_session`) ;
## - WEEKS « Cumul par semaine » : les 8 dernières semaines où l'on a roulé ;
## - FTP « Tests de FTP » : FTP calculée, FTP d'avant et avertissements, du plus récent au plus ancien ;
## - SESSION : le bilan de la séance, dans le panneau du bilan de fin de séance (summary_view.gd).

const RecordsViewModel := preload("res://scripts/records_view_model.gd")
const SummaryViewModel := preload("res://scripts/summary_view_model.gd")

const SCREEN := "history"
const WEEKS := "history_weeks"
const FTP := "history_ftp"
const SESSION := "history_session"
const SCREENS := [SCREEN, WEEKS, FTP, SESSION]
const SESSION_PREFIX := "s:"
## Avertissements d'un test de FTP (summary.ftp_test.warnings), comme `openride-core ftp-test`.
const FTP_WARNINGS := {"too_short": "test trop court", "erratic_cadence": "cadence erratique",
	"trainer_dropout": "coupure du trainer pendant l'effort", "paused": "pause pendant l'effort"}
const LOADING := "Chargement…"

var loaded := false
var sessions: Array = []
var weeks: Array = []
var ftp_tests: Array = []
var unreadable := 0
var truncated := false
## Ligne d'état des écrans de l'historique (chargement, erreur du core).
var message := ""
## Bilan de la séance ouverte (`summary` du message `history_session`) et son identifiant.
var detail: Dictionary = {}
var detail_id := ""


## Remet l'écran en attente de la réponse à `list_history` (à chaque ouverture : une séance vient peut-être de finir).
func begin() -> void:
	loaded = false
	message = LOADING


func on_history(msg: Dictionary) -> void:
	sessions = _dicts(msg.get("sessions"))
	weeks = _dicts(msg.get("weeks"))
	ftp_tests = _dicts(msg.get("ftp_tests"))
	unreadable = int(msg.get("unreadable", 0))
	truncated = bool(msg.get("truncated", false))
	loaded = true
	message = ""


## Bilan reçu : faux si ce n'est pas la séance demandée en dernier.
func on_session(msg: Dictionary) -> bool:
	if str(msg.get("id", "")) != detail_id or not (msg.get("summary") is Dictionary):
		return false
	detail = msg["summary"]
	message = ""
	return true


## A sur une séance : identifiant à demander au core ("" pour une autre ligne).
func request(item_id: String) -> String:
	if not item_id.begins_with(SESSION_PREFIX):
		return ""
	detail_id = item_id.substr(SESSION_PREFIX.length())
	detail = {}
	message = "Chargement du bilan…"
	return detail_id


static func _dicts(raw) -> Array:
	var out: Array = []
	if raw is Array:
		for x in raw:
			if x is Dictionary:
				out.append(x)
	return out


static func _num(x) -> float:
	return float(x) if typeof(x) in [TYPE_INT, TYPE_FLOAT] else 0.0


## « 1 h 02 » au-delà d'une heure, « 42 min » en dessous.
static func duration_text(seconds: float) -> String:
	var minutes := int(round(maxf(seconds, 0.0) / 60.0))
	return "%d h %02d" % [minutes / 60, minutes % 60] if minutes >= 60 else "%d min" % minutes


static func km_text(meters: float) -> String:
	return ("%.1f km" % (meters / 1000.0)).replace(".", ",")


func _session(id: String) -> Dictionary:
	for s in sessions:
		if str(s.get("id", "")) == id:
			return s
	return {}


func session_label(s: Dictionary, names: Dictionary) -> String:
	var rid := str(s.get("route", ""))
	return "%s · %s" % [RecordsViewModel.date_text(str(s.get("date", ""))), str(names.get(rid, rid))]


func session_detail(s: Dictionary) -> String:
	var parts: Array = [duration_text(_num(s.get("duration_s"))), km_text(_num(s.get("distance_m"))),
		"NP %d W" % int(round(_num(s.get("np_w")))), "TSS %d" % int(round(_num(s.get("tss"))))]
	if str(s.get("status", "")) == "recover":
		parts.append("sans fichier FIT")
	return " · ".join(parts)


func items(names: Dictionary) -> Array:
	if not loaded:
		return [{"id": "none", "label": LOADING, "enabled": false}]
	var last_test := "aucun test"
	if not ftp_tests.is_empty():
		last_test = "dernier : %s le %s" % [ftp_text(ftp_tests[0]),
			RecordsViewModel.date_text(str(ftp_tests[0].get("date", ""))).substr(0, 10)]
	var out: Array = [
		{"id": "weeks", "label": "Cumul par semaine", "enabled": not weeks.is_empty(),
			"detail": "%d semaine%s" % [weeks.size(), "s" if weeks.size() > 1 else ""] if not weeks.is_empty() else "aucune séance"},
		{"id": "ftp", "label": "Tests de FTP", "enabled": not ftp_tests.is_empty(), "detail": last_test}]
	if sessions.is_empty():
		out.append({"id": "none", "label": "Aucune séance enregistrée", "enabled": false})
	for s in sessions:
		out.append({"id": SESSION_PREFIX + str(s.get("id", "")), "label": session_label(s, names),
			"detail": session_detail(s)})
	if truncated:
		out.append({"id": "more", "label": "Seules les %d séances les plus récentes sont listées" % sessions.size(),
			"enabled": false})
	if unreadable > 0:
		out.append({"id": "unreadable", "label": "%d fichier%s illisible%s ignoré%s" % [unreadable,
			"s" if unreadable > 1 else "", "s" if unreadable > 1 else "", "s" if unreadable > 1 else ""],
			"enabled": false})
	return out


func week_items() -> Array:
	var out: Array = []
	for w in weeks:
		var n := int(w.get("count", 0))
		out.append({"id": "week:" + str(w.get("week", "")),
			"label": "Semaine du %s · %d séance%s" % [RecordsViewModel.date_text(str(w.get("start_date", ""))), n,
				"s" if n > 1 else ""],
			"detail": "%s · %s · %d m · TSS %d" % [duration_text(_num(w.get("duration_s"))),
				km_text(_num(w.get("distance_m"))), int(round(_num(w.get("elevation_gain_m")))),
				int(round(_num(w.get("tss"))))]})
	return out


static func ftp_text(t: Dictionary) -> String:
	return "%d W" % int(t["ftp_w"]) if typeof(t.get("ftp_w")) in [TYPE_INT, TYPE_FLOAT] else "non calculée"


func ftp_items() -> Array:
	var out: Array = []
	for i in range(ftp_tests.size()):
		var t: Dictionary = ftp_tests[i]
		var parts: Array = []
		if typeof(t.get("previous_ftp_w")) in [TYPE_INT, TYPE_FLOAT]:
			parts.append("FTP d'avant %d W" % int(t["previous_ftp_w"]))
		for w in t.get("warnings", []):
			parts.append(str(FTP_WARNINGS.get(str(w), w)))
		out.append({"id": "test:%d" % i, "label": "%s · FTP %s" % [
			RecordsViewModel.date_text(str(t.get("date", "date inconnue"))), ftp_text(t)],
			"detail": " · ".join(parts)})
	return out


func session_title(names: Dictionary) -> String:
	var s := _session(detail_id)
	return "Séance du " + session_label(s, names) if not s.is_empty() else "Séance"


static func session_items() -> Array:
	return [{"id": "details", "label": "Voir le bilan détaillé"}, {"id": "back", "label": "Retour à l'historique"}]

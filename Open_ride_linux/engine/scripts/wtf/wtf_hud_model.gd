extends RefCounted

## Habillage du mode « What the fuck » (série WTF, lot WTF7), sans nœud : traduit l'objet `wtf` de la trame
## `state` (contrat 1.5) en ce que wtf_view.gd affiche, d'après les maquettes validées le 30 octobre :
## - `banner` : bandeau du gag en haut au centre (texte, couleur, temps restant, points) ;
## - `card` : carte du gag à gauche, au-dessus du Katamari (titre, valeur, jauge de 0 à 1 ou −1 sans jauge, note) ;
## - `prompt` : invite d'un bouton (Z : « Non merci, chef ! ») ;
## - `kata`, `clock` : cartes des règles permanentes (Katamari, horloge sous lui) ;
## - `legend_keys` : règles visibles à cet instant, gag en premier (clés de LEGENDS) : wtf_view.gd montre la
##   légende de chacune au premier passage dans la séance (lot WTF9, règle « gameplay lisible » du 11/11).
## Le bandeau porte aussi `do` : ce que le cycliste doit faire pendant le gag, à tout moment.
## Pas de class_name : preload("res://scripts/wtf/wtf_hud_model.gd").

const PINK := Color(1.0, 0.31, 0.6)
const YELLOW := Color(1.0, 0.82, 0.25)
const CYAN := Color(0.18, 0.77, 0.95)
const GREEN := Color(0.48, 0.85, 0.29)
const ORANGE := Color(1.0, 0.54, 0.24)
const PURPLE := Color(0.56, 0.36, 1.0)
const WHITE := Color(1.0, 1.0, 1.0)
const INK := Color(0.106, 0.106, 0.184)

const CAMERAS := {"pigeon": "CAMÉRA PIGEON !", "snail": "CAMÉRA ESCARGOT !", "wheel": "CAMÉRA ROUE !"}
const DISHES := {"spaghetti": "SPAGHETTI", "jelly": "GELÉE", "musette": "BAL MUSETTE", "souffle": "SOUFFLÉ",
	"chili": "PIMENT"}
const KATA_OBJECTS := {"apple": "une pomme", "sign": "un panneau", "cow": "une vache", "car": "une voiture",
	"house": "une maison", "church": "une église"}
## Taille de boule nécessaire pour ramasser chaque objet : copie de KATAMARI (core, wtf/mode.py), pour dire
## avant le contact si l'objet sera ramassé ou s'il fera « boing ».
const KATA_NEED := {"apple": 1.0, "sign": 1.1, "cow": 1.4, "car": 2.0, "house": 3.0, "church": 4.5}
## Légendes du premier passage (lot WTF9) : nom, ce qui se passe, ce que tu fais.
const LEGENDS := {
	"gravity_moon": ["LA LUNE", "Pentes divisées par 6, le vélo fait des bonds.", "Profite : tout est facile pendant 1 min."],
	"gravity_jupiter": ["JUPITER", "Pesanteur × 2,5 : un faux plat devient un mur.", "Passe sur un petit braquet (−) et mouline."],
	"upside_down": ["MONDE À L'ENVERS", "Ciel en bas : les descentes durcissent, les montées sont faciles.",
		"Change de braquet à l'inverse de d'habitude."],
	"collapse": ["LA ROUTE S'EFFONDRE", "La route s'écroule derrière toi et te rattrape.",
		"Garde plus de 60 % de ta FTP pour rester devant le trou."],
	"cheese": ["FROMAGE GÉANT", "Une meule dévale la pente derrière toi.", "Pédale fort : 250 m d'avance et tu lui échappes."],
	"micro": ["MICRO-DÉFIS", "Trois défis de 30 s à la suite, 100 points chacun.", "Suis la consigne de la carte à gauche."],
	"eggs": ["LIVRAISON D'ŒUFS", "Six œufs à livrer sur 1 km.", "Puissance bien régulière : chaque à-coup casse un œuf."],
	"tiny": ["VÉLO MINUSCULE", "Tu rétrécis : la route traverse une cuisine géante.", "Rien à faire : admire la vaisselle."],
	"storm": ["TORNADE DE VACHES", "Tornade et vent de face : il te repousse en arrière.",
		"Pousse au-dessus de 50 % de ta FTP pour tenir."],
	"camera": ["CAMÉRA IMPROBABLE", "La caméra change de place pendant 30 s.", "Rien à faire : continue de rouler."],
	"chef": ["SURPRISE DU CHEF", "Le chef te rejoint en vélo et soulève sa cloche : plat surprise.",
		"Z court pour refuser (une fois), sinon mange le plat."],
	"katamari": ["KATAMARI", "Ta boule ramasse les objets de la route si elle est assez grosse, sinon « boing » !",
		"Roule dessus : pomme et panneau d'abord, l'église à × 4,5."],
	"clock": ["LA CADENCE PILOTE LE MONDE", "Plus tu moulines, plus le soleil tourne vite.",
		"Au-dessus de 100 rpm, il pleut des poissons !"],
	"peloton": ["PELOTON DÉLIRANT", "Les bots sont déguisés : mamies, tracteur, baignoire, baleine volante.",
		"Abrite-toi derrière la baleine ; la mamie en rouge attaque !"],
}
## Consigne du bandeau pendant chaque plat du chef.
const DISH_DO := {"spaghetti": "La route ondule : tiens ton rythme", "jelly": "Ça colle : passe un petit braquet",
	"musette": "Suis le tempo affiché sur la carte", "souffle": "Puissance régulière, sans à-coup",
	"chili": "Profite du + 25 %, ça va brûler"}
const EGGS_TOTAL := 6
const COLLAPSE_START_M := 120.0
const CHEESE_ESCAPE_M := 250.0
const STORM_MAX_M := 30.0


## Vue complète ; `wtf` absent ou nul : rien d'affiché.
static func view(wtf: Variant) -> Dictionary:
	if typeof(wtf) != TYPE_DICTIONARY:
		return {"visible": false}
	var out := {"visible": true, "banner": {}, "card": {}, "prompt": {}, "kata": {}, "clock": {}, "legend_keys": []}
	var pts := "%d pts" % int(wtf.get("points", 0))
	var ev = wtf.get("event", null)
	if typeof(ev) == TYPE_DICTIONARY:
		_event(ev, pts, out)
	else:
		var next = wtf.get("next_s", null)
		out["banner"] = {"text": "MODE WTF", "color": WHITE,
			"time": ("prochain gag dans %d s" % int(next)) if next != null else "", "points": pts, "do": ""}
	var kata = wtf.get("kata", null)
	if typeof(kata) == TYPE_DICTIONARY:
		var size := float(kata.get("size", 1.0))
		var last := str(kata.get("last", ""))
		out["kata"] = {"title": "KATAMARI × %s" % _dec(size), "line": "%d objets%s" % [int(kata.get("count", 0)),
			(" · dernier : " + KATA_OBJECTS.get(last, last)) if last != "" and last != "<null>" else ""],
			"bar": clampf((size - 1.0) / 5.0, 0.0, 1.0), "next": _kata_next(kata.get("next", []), size)}
		out["legend_keys"].append("katamari")
	if wtf.has("clock_h"):
		var h := float(wtf.get("clock_h", 0.0))
		out["clock"] = {"text": "%d h %02d" % [int(h), int((h - floorf(h)) * 60.0)], "fish": bool(wtf.get("fish", false))}
		out["legend_keys"].append("clock")
	var skins = wtf.get("skins", {})
	if typeof(skins) == TYPE_DICTIONARY and not skins.is_empty():
		out["legend_keys"].append("peloton")
	return out


## Clé de LEGENDS du gag en cours (la Lune et Jupiter ont chacune la leur).
static func legend_key(ev: Dictionary) -> String:
	var id := str(ev.get("id", ""))
	if id == "gravity":
		return "gravity_moon" if str(ev.get("planet", "moon")) == "moon" else "gravity_jupiter"
	return id if LEGENDS.has(id) else ""


## Prochain objet du Katamari : « une vache à 12 m : ramassée » ou « … : trop grosse, boing ! ».
static func _kata_next(nxt: Variant, size: float) -> String:
	if typeof(nxt) != TYPE_ARRAY or nxt.is_empty() or typeof(nxt[0]) != TYPE_ARRAY or nxt[0].size() < 2:
		return ""
	var kind := str(nxt[0][1])
	var ok := size >= float(KATA_NEED.get(kind, 1.0))
	return "Prochain : %s à %d m · %s" % [KATA_OBJECTS.get(kind, kind), int(round(float(nxt[0][0]))),
		"ramassé" if ok else "trop gros, boing ! (× %s)" % _dec(float(KATA_NEED.get(kind, 1.0)))]


static func _event(ev: Dictionary, pts: String, out: Dictionary) -> void:
	var id := str(ev.get("id", ""))
	var left := _clock(float(ev.get("left_s", 0.0)))
	var b := {"text": "", "color": YELLOW, "time": left, "points": pts, "do": ""}
	var key := legend_key(ev)
	if key != "":
		out["legend_keys"].append(key)
		b["do"] = LEGENDS[key][2]
	var card := {}
	match id:
		"gravity":
			var moon := str(ev.get("planet", "moon")) == "moon"
			b["text"] = "GRAVITÉ : LA LUNE !" if moon else "GRAVITÉ : JUPITER !"
			b["color"] = YELLOW if moon else ORANGE
			card = _card("Pentes", "× 0,17" if moon else "× 2,5", -1.0,
				"Le vélo bondit" if moon else "Un faux plat devient un mur (10 % au plus sous les pieds)")
		"upside_down":
			b["text"] = "MONDE À L'ENVERS !"
			b["color"] = ORANGE
			card = _card("Pentes", "inversées", -1.0, "Les descentes durcissent, les montées sont faciles")
		"collapse":
			var gap := float(ev.get("gap_m", 0.0))
			b["text"] = "LA ROUTE S'EFFONDRE !"
			b["color"] = PINK
			card = _card("Écart avec l'effondrement", "%d m" % int(round(gap)), clampf(gap / COLLAPSE_START_M, 0.0, 1.0),
				"Garde plus de 60 % de ta FTP")
		"cheese":
			var gap := float(ev.get("gap_m", 0.0))
			b["text"] = "ÉCRASÉ !" if bool(ev.get("squashed", false)) else "LE FROMAGE ARRIVE !"
			card = _card("Avance sur la meule", "%d / %d m" % [int(round(gap)), int(CHEESE_ESCAPE_M)],
				clampf(gap / CHEESE_ESCAPE_M, 0.0, 1.0), "250 m d'avance et tu lui échappes")
		"micro":
			b["text"] = "MICRO-DÉFI %d / 3" % int(ev.get("round", 1))
			b["color"] = CYAN
			b["time"] = _clock(float(ev.get("round_left_s", 0.0)))
			card = _micro(ev)
			b["do"] = str(card.get("do", b["do"]))
		"eggs":
			b["text"] = "LIVRAISON D'ŒUFS"
			b["color"] = WHITE
			b["time"] = "%s km" % _dec(float(ev.get("left_m", 0.0)) / 1000.0)
			var eggs := int(ev.get("eggs", EGGS_TOTAL))
			card = _card("Œufs intacts", "%d / %d" % [eggs, EGGS_TOTAL], float(eggs) / EGGS_TOTAL,
				"Chaque à-coup de puissance en casse un")
		"tiny":
			b["text"] = "TOUT PETIT !"
			b["color"] = GREEN
		"storm":
			var push := float(ev.get("pushback_m", 0.0))
			b["text"] = "TORNADE DE VACHES !"
			b["color"] = ORANGE
			card = _card("Le vent te repousse", "%d m" % int(round(push)), clampf(push / STORM_MAX_M, 0.0, 1.0),
				"Pousse au-dessus de 50 % de ta FTP pour revenir")
		"camera":
			b["text"] = CAMERAS.get(str(ev.get("view", "")), "CAMÉRA IMPROBABLE !")
		"chef":
			_chef(ev, b, out)
			card = _dish_card(ev)
		_:
			b["text"] = id.to_upper()
	out["banner"] = b
	out["card"] = card


static func _micro(ev: Dictionary) -> Dictionary:
	var target := int(round(float(ev.get("target", 0.0))))
	var bar := float(ev.get("progress", 0.0))
	match str(ev.get("kind", "")):
		"cadence":
			return _do(_card("CADENCE PILE !", "%d rpm (± 3)" % target, bar, "Tiens-la 60 % du temps"), "Tiens la cadence affichée")
		"sprint":
			return _do(_card("SAUTE LE RAVIN !", "%d W pendant 5 s" % target, bar, "150 % de ta FTP"), "Sprinte : la puissance affichée 5 s")
		"cap":
			return _do(_card("LE GÂTEAU TIENT ?", "moins de %d W" % target, bar, "3 s de dépassement et il tombe"), "Reste sous la puissance affichée")
		"steady":
			return _do(_card("RÉGULIER !", ("%d W ± 10 %%" % target) if target > 0 else "fixe ta puissance…", bar,
				"Garde la même puissance"), "Garde la même puissance")
		"spin":
			return _do(_card("MOULINETTE !", "%d rpm pendant 10 s" % target, bar, ""), "Mouline : la cadence affichée 10 s")
	return {}


static func _chef(ev: Dictionary, b: Dictionary, out: Dictionary) -> void:
	var phase := str(ev.get("phase", ""))
	var dish: String = DISHES.get(str(ev.get("dish", "")), "")
	b["color"] = PINK
	match phase:
		"arrive":
			b["text"] = "LE CHEF ARRIVE…"
			b["do"] = "Il apporte un plat : Z court pour refuser"
		"reveal":
			b["text"] = "SURPRISE DU CHEF : %s !" % dish
			b["do"] = "Z court pour refuser, sinon tu manges"
			out["prompt"] = {"key": "Z", "text": "NON MERCI, CHEF !",
				"time": "%d s" % int(ceilf(float(ev.get("phase_left_s", 0.0))))}
		_:
			b["text"] = "%s !" % dish
			b["time"] = _clock(float(ev.get("phase_left_s", 0.0)))
			b["do"] = DISH_DO.get(str(ev.get("dish", "")), "")


static func _dish_card(ev: Dictionary) -> Dictionary:
	if str(ev.get("phase", "")) != "eat":
		return {}
	match str(ev.get("dish", "")):
		"spaghetti":
			return _card("Spaghetti", "la route ondule", -1.0, "± 1,5 point toutes les 8 s")
		"jelly":
			return _card("Gelée", "ça colle", -1.0, "Roulement × 1,5")
		"musette":
			return _card("Tempo du bal", "%d rpm" % int(ev.get("tempo_rpm", 0)), -1.0, "À ± 4 rpm, la foule danse")
		"souffle":
			var h := float(ev.get("souffle", 0.0))
			return _card("Hauteur du soufflé", "%d %%" % int(round(h * 100.0)), h, "Réussi au-dessus de 80 %")
		"chili":
			var burning := bool(ev.get("burning", false))
			return _card("Piment", "ÇA BRÛLE ! − 15 %" if burning else "+ 25 %", -1.0, "Vitesse virtuelle seulement")
	return {}


static func _card(title: String, value: String, bar: float, note: String) -> Dictionary:
	return {"title": title, "value": value, "bar": bar, "note": note}


static func _do(card: Dictionary, text: String) -> Dictionary:
	card["do"] = text
	return card


## Temps restant « m:ss ».
static func _clock(s: float) -> String:
	var t := int(ceilf(maxf(s, 0.0)))
	return "%d:%02d" % [t / 60, t % 60]


## Nombre à une décimale avec la virgule française.
static func _dec(x: float) -> String:
	return ("%.1f" % x).replace(".", ",")

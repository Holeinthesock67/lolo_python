extends RefCounted

## Contrôles automatiques des vitrines de la série U (vitrine_biomes.gd, vitrine_sols.gd) : exposition du sol
## (part de pixels saturés, luminance moyenne) et comparaison des captures à un dossier de référence par
## compare_captures.py. Pas de class_name : charger par preload("res://tests/vitrine_checks.gd").
##
## Options communes des vitrines :
##   --compare REF          compare chaque capture à celle de même nom dans REF (images des écarts dans DOSSIER_ecarts/)
##   --max-diff N           écart moyen admis par compare_captures.py (0 à 255, 3 par défaut)
##   --max-saturated PCT    part de pixels saturés admise dans la zone du sol (5 % par défaut)
## Code de sortie de la vitrine : 0 si tout passe, 1 si une capture dépasse un seuil ou s'écarte de la référence.

## Pixel saturé : sa composante la plus claire atteint ce niveau (sol « brûlé », détail perdu).
const SATURATED := 0.985
const DEFAULT_MAX_SATURATED_PCT := 5.0   # marquages blancs de la route : environ 3 % de la vue `route`
const DEFAULT_MAX_DIFF := 3.0
const STEP := 2   # un pixel sur deux dans chaque sens : assez pour une part et une moyenne

var compare_dir := ""
var max_diff := DEFAULT_MAX_DIFF
var max_saturated_pct := DEFAULT_MAX_SATURATED_PCT
var failures := PackedStringArray()


## Lit les options communes dans les arguments de la vitrine.
func parse_args(args: PackedStringArray) -> void:
	for i in range(args.size() - 1):
		match args[i]:
			"--compare":
				compare_dir = args[i + 1]
			"--max-diff":
				max_diff = float(args[i + 1])
			"--max-saturated":
				max_saturated_pct = float(args[i + 1])


## Exposition de la zone du sol (rectangle en fractions de l'image : x0, y0, x1, y1) :
## {"saturated_pct", "luma"} ; luma de 0 à 1 (Rec. 709). Échec noté au-delà de max_saturated_pct.
func exposure(img: Image, name: String, box: Rect2 = Rect2(0.0, 0.6, 1.0, 0.4)) -> Dictionary:
	var x0 := int(box.position.x * img.get_width())
	var y0 := int(box.position.y * img.get_height())
	var x1 := int(box.end.x * img.get_width())
	var y1 := int(box.end.y * img.get_height())
	var n := 0
	var sat := 0
	var luma := 0.0
	for y in range(y0, y1, STEP):
		for x in range(x0, x1, STEP):
			var c := img.get_pixel(x, y)
			n += 1
			if maxf(c.r, maxf(c.g, c.b)) >= SATURATED:
				sat += 1
			luma += 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b
	var out := {"saturated_pct": 100.0 * sat / maxf(n, 1.0), "luma": luma / maxf(n, 1.0)}
	if out["saturated_pct"] > max_saturated_pct:
		failures.append("%s : %.1f %% de pixels saturés dans le sol (au plus %.1f %%)" % [name, out["saturated_pct"], max_saturated_pct])
		printerr("[ÉCHEC] exposition ", failures[-1])
	return out


## Compare out_dir à compare_dir (si donné) avec compare_captures.py ; images des écarts dans out_dir + "_ecarts"
## (hors du dossier des captures, qui peut servir de référence à son tour).
func compare(out_dir: String) -> void:
	if compare_dir == "":
		return
	var script := ProjectSettings.globalize_path("res://tests/compare_captures.py")
	var out := ProjectSettings.globalize_path(out_dir)
	var output := []
	var code := OS.execute("python3", [script, ProjectSettings.globalize_path(compare_dir), out,
		"--out", out.trim_suffix("/") + "_ecarts", "--max-diff", str(max_diff)], output, true)
	for block in output:
		print(str(block).strip_edges())
	if code != 0:
		failures.append("comparaison à %s : code %d" % [compare_dir, code])
		printerr("[ÉCHEC] comparaison à ", compare_dir, " (code ", code, ")")


## Code de sortie de la vitrine, après un résumé.
func exit_code(tool_name: String) -> int:
	if failures.is_empty():
		print("[%s] contrôles automatiques : tout passe" % tool_name)
		return 0
	print("[%s] contrôles automatiques : %d échecs" % [tool_name, failures.size()])
	return 1

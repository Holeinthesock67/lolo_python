shader_type spatial;

// Marquages de la route (Lot P14), dessinés à partir des UV du ruban d'E1 : u en travers de 0 (bord gauche
// du bas-côté) à 1 (bord droit), v = s / v_repeat_m. À appliquer par P17 à la place de
// road_builder.make_material (ce lot ne touche pas road_builder.gd).
// - Ligne médiane discontinue : dash_m peints sur period_m (3 m sur 13 m), largeur line_w_m.
// - Bandes de rive continues à edge_inset_m du bord de la chaussée.
// - Chiffres des kilomètres restants peints sur la voie de droite (marks : s, chiffre), lisibles par le
//   cycliste qui arrive ; au plus 8 par tronçon.
// Anticrénelage par fwidth : pas de scintillement des traits au loin. `wear` éclaircit et casse la
// peinture (0 : neuve).
// Lot P17 : `wetness` (météo de P8, 0 à 1) assombrit la chaussée mouillée et la rend plus brillante.
// Lot Y11 (chaussée, techniques A1 à A4, procédurales, sans texture) : grain de l'enrobé (gravillons de
// 4 cm et bosses de 25 cm) en faux relief et en teinte, effacé quand il devient plus fin qu'un pixel ;
// variation lente de teinte (25 m) et rapiéçages plus sombres et plus rugueux ; bandes de roulement
// plus lisses ; bas-côtés en gravillons et terre avec une limite irrégulière. `grain` règle le relief
// (0 : chaussée lisse d'avant Y11).
// Lot Y17 (essai) : parallaxe du grain (« parallax occlusion mapping ») en `high`, `surface_parallax_steps`
// pas le long du rayon de vue (0 : coupé) ; le relief masque ce qui est derrière lui en vue rasante.
#include "res://shaders/surface_detail.gdshaderinc"
uniform vec3 road_color : source_color = vec3(0.29, 0.29, 0.30);
uniform vec3 line_color : source_color = vec3(0.95, 0.95, 0.95);
uniform float road_width_m = 6.0;
uniform float shoulder_m = 0.5;
uniform float v_repeat_m = 6.0;
uniform float dash_m = 3.0;
uniform float period_m = 13.0;
uniform float line_w_m = 0.12;
uniform float edge_w_m = 0.15;
uniform float edge_inset_m = 0.2;
uniform float wear : hint_range(0.0, 1.0) = 0.15;
uniform float wetness : hint_range(0.0, 1.0) = 0.0;
uniform vec2 marks[8];
uniform int mark_count = 0;
uniform float digit_len_m = 2.4;
uniform float digit_w_m = 1.2;
uniform float digit_lane_m = 1.5;     // centre du chiffre, à droite de l'axe
uniform float grain : hint_range(0.0, 2.0) = 1.0;
uniform vec3 shoulder_color : source_color = vec3(0.36, 0.33, 0.27);
global uniform int surface_parallax_steps;
const float PARALLAX_DEPTH_M = 0.012;   // relief le plus haut du grain (gravillons et bosses), en mètres
// Le relief ne se voit qu'à quelques mètres : au-delà de PARALLAX_FULL_M, la profondeur et le nombre de
// pas décroissent jusqu'à zéro à PARALLAX_MAX_M (la parallaxe partout coûtait ~5 ms sur une GTX 1060)
const float PARALLAX_FULL_M = 2.5;
const float PARALLAX_MAX_M = 6.0;

const int SEG[10] = int[](0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F);

// Couverture d'un trait de demi-largeur half_w par le pixel (largeur aa) : 1 au centre dès qu'il couvre
// un pixel, s'estompe au lieu de scintiller quand il devient plus fin qu'un pixel.
float band(float x, float half_w, float aa) {
	return clamp((half_w - abs(x)) / aa + 0.5, 0.0, 1.0) * clamp(2.0 * half_w / aa, 0.0, 1.0);
}

float box(vec2 p, vec2 lo, vec2 hi) {
	return step(lo.x, p.x) * step(p.x, hi.x) * step(lo.y, p.y) * step(p.y, hi.y);
}

// Chiffre à sept segments dans le carré unité (u en travers, w le long ; w = 1 en haut, vers l'avant).
float digit_mask(int d, vec2 uv) {
	float t = 0.16;
	int m = SEG[clamp(d, 0, 9)];
	float o = 0.0;
	if ((m & 1) != 0) o = max(o, box(uv, vec2(0.0, 1.0 - t), vec2(1.0, 1.0)));
	if ((m & 2) != 0) o = max(o, box(uv, vec2(1.0 - t, 0.5), vec2(1.0, 1.0)));
	if ((m & 4) != 0) o = max(o, box(uv, vec2(1.0 - t, 0.0), vec2(1.0, 0.5)));
	if ((m & 8) != 0) o = max(o, box(uv, vec2(0.0, 0.0), vec2(1.0, t)));
	if ((m & 16) != 0) o = max(o, box(uv, vec2(0.0, 0.0), vec2(t, 0.5)));
	if ((m & 32) != 0) o = max(o, box(uv, vec2(0.0, 0.5), vec2(t, 1.0)));
	if ((m & 64) != 0) o = max(o, box(uv, vec2(0.0, 0.5 - t * 0.5), vec2(1.0, 0.5 + t * 0.5)));
	return o;
}

// Hauteur du grain de l'enrobé au point `p` (m) : gravillons de 4 cm et bosses de 25 cm.
float grain_height(vec2 p, float vis_fine, float vis_mid, out vec2 peb, out float stone) {
	peb = sd_pebbles(p / 0.04);
	stone = 1.0 - smoothstep(0.15, 0.55, peb.x);
	return (stone * 0.004 * (0.6 + 0.8 * peb.y)) * vis_fine + sd_noise(p / 0.25) * 0.006 * vis_mid;
}

// Parallaxe : point de la surface en relief vu à travers le point `p0` du ruban, rayon de vue `vt`
// (repère de la route : x en travers, y le long, z vers le haut). La surface est creusée sous le ruban.
vec2 parallax(vec2 p0, vec3 vt, float vis_fine, float vis_mid, int steps, float depth_m) {
	vec2 step_xy = -vt.xy / max(vt.z, 0.08) * (depth_m / float(steps));
	float dz = depth_m / float(steps);
	vec2 peb;
	float stone;
	vec2 p = p0;
	float depth = 0.0;
	float prev_gap = 0.0;
	for (int i = 0; i < 32; i++) {
		if (i >= steps) break;
		float gap = (depth_m - grain_height(p, vis_fine, vis_mid, peb, stone) * (depth_m / PARALLAX_DEPTH_M)) - depth;
		if (gap <= 0.0) {
			// Entre le pas précédent et celui-ci : interpolation linéaire
			float t = prev_gap / max(prev_gap - gap, 1e-6);
			return p - step_xy * (1.0 - t);
		}
		prev_gap = gap;
		p += step_xy;
		depth += dz;
	}
	return p;
}

void fragment() {
	float total = road_width_m + 2.0 * shoulder_m;
	float lat = UV.x * total - total * 0.5;          // m, positif à droite
	float s = UV.y * v_repeat_m;                       // m le long du parcours
	float aa_lat = max(fwidth(lat), 1e-4);
	float aa_s = max(fwidth(s), 1e-4);
	float vis_fine = sd_visible(vec2(lat, s), 0.04) * grain;
	float vis_mid = sd_visible(vec2(lat, s), 0.25) * grain;
	// Repère de la route dans l'espace de la vue, tiré des dérivées d'écran de (lat, s) ; dérivées
	// prises hors de toute branche (fausses dans un flot non uniforme)
	vec2 dpx = vec2(dFdx(lat), dFdx(s));
	vec2 dpy = vec2(dFdy(lat), dFdy(s));
	vec3 dvx = dFdx(VERTEX);
	vec3 dvy = dFdy(VERTEX);
	bool shifted = false;
	vec3 t_lat = vec3(1.0, 0.0, 0.0);
	vec3 t_s = vec3(0.0, 0.0, 1.0);
	float near = 1.0 - smoothstep(PARALLAX_FULL_M, PARALLAX_MAX_M, length(VERTEX));
	if (surface_parallax_steps > 0 && vis_fine > 0.0 && near > 0.0) {
		float det = dpx.x * dpy.y - dpx.y * dpy.x;
		if (abs(det) > 1e-12) {
			t_lat = normalize((dvx * dpy.y - dvy * dpx.y) / det);
			t_s = normalize((dvy * dpx.x - dvx * dpy.x) / det);
			vec3 v = normalize(-VERTEX);
			vec3 vt = vec3(dot(v, t_lat), dot(v, t_s), dot(v, NORMAL));
			int steps = max(2, int(ceil(float(surface_parallax_steps) * near)));
			vec2 q = parallax(vec2(lat, s), vt, vis_fine, vis_mid, steps, PARALLAX_DEPTH_M * near);
			lat = q.x;
			s = q.y;
			shifted = true;
		}
	}

	float paint = 0.0;
	// Ligne médiane discontinue
	float ph = mod(s, period_m);
	float dash = band(ph - dash_m * 0.5, dash_m * 0.5, aa_s);
	paint = max(paint, band(lat, line_w_m * 0.5, aa_lat) * dash);
	// Bandes de rive
	float edge = road_width_m * 0.5 - edge_inset_m - edge_w_m * 0.5;
	paint = max(paint, band(abs(lat) - edge, edge_w_m * 0.5, aa_lat));
	// Chiffres des kilomètres restants
	for (int i = 0; i < 8; i++) {
		if (i >= mark_count) break;
		vec2 uv = vec2((lat - (digit_lane_m - digit_w_m * 0.5)) / digit_w_m, (s - marks[i].x) / digit_len_m);
		if (uv.x >= 0.0 && uv.x <= 1.0 && uv.y >= 0.0 && uv.y <= 1.0) {
			paint = max(paint, digit_mask(int(marks[i].y + 0.5), uv));
		}
	}
	// Limite chaussée / bas-côté irrégulière (A4)
	vec2 p = vec2(lat, s);
	float edge_jitter = (sd_noise(vec2(s * 1.3, 3.1)) - 0.5) * 0.16;
	float on_road = 1.0 - smoothstep(-0.02, 0.02, abs(lat) - road_width_m * 0.5 - edge_jitter);
	// Hors chaussée (bas-côtés) : pas de peinture
	paint *= on_road;
	// Usure : peinture éclaircie et cassée par plaques de 20 cm
	float worn = step(sd_cell_hash(floor(vec2(lat, s) * 5.0), 4u), wear * 0.6);
	paint *= (1.0 - worn) * (1.0 - 0.35 * wear);

	// Grain de l'enrobé (A1) : gravillons de 4 cm et bosses de 25 cm, effacés au loin
	vec2 peb;
	float stone;
	float h_grain = grain_height(p, vis_fine, vis_mid, peb, stone);
	float h = h_grain;
	// Variation lente (A2) et rapiéçages (A3)
	float macro = sd_noise(p / 25.0) - 0.5;
	vec2 cell = floor(p / vec2(1.5, 5.0));
	vec2 in_cell = fract(p / vec2(1.5, 5.0)) - 0.5;
	vec2 half_size = vec2(0.15, 0.1) + sd_cell_hash2(cell, 5u) * vec2(0.2, 0.2);
	vec2 aa_cell = max(fwidth(in_cell), vec2(1e-4));
	vec2 inside = clamp((half_size - abs(in_cell)) / aa_cell + 0.5, 0.0, 1.0);
	float patch = step(sd_cell_hash(cell, 7u), 0.03) * inside.x * inside.y * on_road;
	// Bandes de roulement : deux par voie, à 0,8 m de part et d'autre du milieu de la voie
	float lane_off = abs(abs(lat) - road_width_m * 0.25);
	float track = (1.0 - smoothstep(0.25, 0.55, abs(lane_off - 0.8))) * on_road;

	h *= 1.0 - 0.7 * paint;
	vec3 n_bump = sd_bump(NORMAL, VERTEX, h * (1.0 - 0.6 * patch));
	if (shifted) {
		// Point déplacé par la parallaxe : ses dérivées d'écran sautent d'un caillou à l'autre (points
		// noirs) ; pente du relief par différences finies de 5 mm le long de la route et en travers.
		float k = (1.0 - 0.7 * paint) * (1.0 - 0.6 * patch);
		vec2 peb2;
		float st2;
		float h0 = h_grain;
		float d_lat = (grain_height(p + vec2(0.005, 0.0), vis_fine, vis_mid, peb2, st2) - h0) / 0.005;
		float d_s = (grain_height(p + vec2(0.0, 0.005), vis_fine, vis_mid, peb2, st2) - h0) / 0.005;
		// Fondu vers la normale d'avant là où la parallaxe s'éteint (pas de couture à PARALLAX_MAX_M)
		n_bump = normalize(mix(n_bump, NORMAL - k * (d_lat * t_lat + d_s * t_s), near));
	}
	NORMAL = n_bump;

	vec3 asphalt = road_color * (1.0 + macro * 0.12 - patch * 0.12 - track * 0.05);
	asphalt *= 1.0 + (peb.y - 0.5) * 0.35 * stone * vis_fine;
	vec3 verge = shoulder_color * (0.85 + 0.3 * peb.y * vis_fine) * (1.0 + macro * 0.2);
	vec3 base = mix(verge, asphalt, on_road);
	ALBEDO = mix(base, line_color, paint) * (1.0 - 0.45 * wetness);
	float rough = mix(0.97, 0.9 - 0.14 * track + 0.06 * patch, on_road);
	ROUGHNESS = mix(mix(rough, 0.7, paint), 0.3, wetness);
}

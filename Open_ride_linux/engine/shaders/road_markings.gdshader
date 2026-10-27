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

float hash12(vec2 p) {
	return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void fragment() {
	float total = road_width_m + 2.0 * shoulder_m;
	float lat = UV.x * total - total * 0.5;          // m, positif à droite
	float s = UV.y * v_repeat_m;                       // m le long du parcours
	float aa_lat = max(fwidth(lat), 1e-4);
	float aa_s = max(fwidth(s), 1e-4);

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
	// Hors chaussée (bas-côtés) : pas de peinture
	paint *= step(abs(lat), road_width_m * 0.5);
	// Usure : peinture éclaircie et cassée par plaques de 20 cm
	float worn = step(hash12(floor(vec2(lat, s) * 5.0)), wear * 0.6);
	paint *= (1.0 - worn) * (1.0 - 0.35 * wear);
	ALBEDO = mix(road_color, line_color, paint) * (1.0 - 0.45 * wetness);
	ROUGHNESS = mix(mix(0.9, 0.7, paint), 0.3, wetness);
}

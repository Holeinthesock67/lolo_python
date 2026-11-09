shader_type spatial;
render_mode cull_disabled;

// Piste du vélodrome (série VD, lot VD4), dessinée à partir des UV du ruban de road_builder.gd (profil de piste) :
// UV.x = distance en m depuis le bord intérieur de la piste, le long de la surface (négative à plat vers
// l'intérieur : côte d'azur puis zone de sécurité ; au-delà de track_width_m : balustrade), UV.y = s / v_repeat_m.
// - Piste : lattes de bois de 5 cm dans le sens de la marche, teinte de chaque latte tirée par un hachage, joints
//   sombres, fil du bois ; vernis (rugosité basse) : les reflets viennent de SSR et SSIL du préréglage.
// - Lignes peintes du plan §3.1 : mesure noire (5 cm), sprinteurs rouge et stayers bleue (5 cm), à leur distance
//   du bord intérieur (couche venue).
// - Lignes en travers : arrivée (bande blanche de 72 cm et trait noir de 4 cm au milieu, sur toute la largeur),
//   lignes de poursuite rouges (sur la moitié intérieure), ligne des 200 m blanche.
// - Côte d'azur bleue, zone de sécurité gris-vert, balustrade blanche bordée de bleu.
// Anticrénelage par fwidth : pas de scintillement des traits au loin.
#include "res://shaders/couleur_srgb.gdshaderinc"

uniform float track_width_m = 7.0;
uniform float apron_width_m = 1.0;
uniform float measure_m = 0.2;
uniform float sprinters_m = 0.85;
uniform float stayers_m = 2.45;
uniform float v_repeat_m = 6.0;
uniform float lap_m = 250.0;
uniform float finish_s = 0.0;
uniform float pursuit_a_s = 0.0;
uniform float pursuit_b_s = 125.0;
uniform float line_200_s = 50.0;

const vec3 BOIS = vec3(0.78, 0.56, 0.34);
const vec3 BOIS_SOMBRE = vec3(0.62, 0.42, 0.24);
const vec3 AZUR = vec3(0.13, 0.36, 0.72);
const vec3 SECURITE = vec3(0.36, 0.42, 0.38);
const vec3 NOIR = vec3(0.04, 0.04, 0.04);
const vec3 ROUGE = vec3(0.80, 0.08, 0.08);
const vec3 BLEU = vec3(0.07, 0.22, 0.70);
const vec3 BLANC = vec3(0.94, 0.94, 0.92);

float hash1(float n) {
	return fract(sin(n * 127.1) * 43758.5453);
}

// Couverture d'une bande [a, b] le long de x, adoucie sur la taille d'un pixel.
float band(float x, float a, float b) {
	float w = max(fwidth(x), 1e-4);
	return clamp(min(x - a, b - x) / w + 0.5, 0.0, 1.0);
}

// Écart signé le plus court de s à la ligne en travers placée en m (boucle de lap_m).
float lap_delta(float s, float m) {
	float d = mod(s - m + 0.5 * lap_m, lap_m) - 0.5 * lap_m;
	return d;
}

void fragment() {
	float x = UV.x;
	float s = UV.y * v_repeat_m;
	vec3 col;
	float rough = 0.35;
	if (x < -apron_width_m) {
		col = SECURITE;
		rough = 0.9;
	} else if (x < 0.0) {
		col = AZUR;
		rough = 0.6;
	} else if (x > track_width_m) {
		// Balustrade : blanche, bande bleue en haut.
		col = mix(BLANC, BLEU, band(x, track_width_m + 0.75, track_width_m + 2.0));
		rough = 0.7;
	} else {
		float plank = floor(x / 0.05);
		float h = hash1(plank);
		col = mix(BOIS_SOMBRE, BOIS, 0.55 + 0.45 * h);
		col *= 0.94 + 0.06 * sin(s * 1.7 + h * 40.0) * sin(s * 0.31 + h * 9.0);   // fil du bois
		float joint = 1.0 - band(fract(x / 0.05) * 0.05, 0.002, 0.048);
		col = mix(col, BOIS_SOMBRE * 0.7, 0.5 * joint);
		col = mix(col, NOIR, band(x, measure_m - 0.025, measure_m + 0.025));
		col = mix(col, ROUGE, band(x, sprinters_m - 0.025, sprinters_m + 0.025));
		col = mix(col, BLEU, band(x, stayers_m - 0.025, stayers_m + 0.025));
		// Lignes en travers.
		float df = lap_delta(s, finish_s);
		col = mix(col, BLANC, band(df, -0.36, 0.36));
		col = mix(col, NOIR, band(df, -0.02, 0.02));
		col = mix(col, BLANC, band(lap_delta(s, line_200_s), -0.025, 0.025));
		float half_w = step(x, 0.5 * track_width_m);
		col = mix(col, ROUGE, half_w * band(lap_delta(s, pursuit_a_s), -0.025, 0.025));
		col = mix(col, ROUGE, half_w * band(lap_delta(s, pursuit_b_s), -0.025, 0.025));
	}
	ALBEDO = lineaire(col);
	ROUGHNESS = rough;
	SPECULAR = 0.5;
}

shader_type spatial;
render_mode cull_disabled;

// Ruban du Cyber-Rogue (lot R10) : volume sombre dont les arêtes (UV.x proche de 0 ou 1) et la surface
// portent la couleur de pente du sommet (COLOR). Au-delà de `ahead_m` devant le joueur, l'éclat baisse.
// COLOR : couleur sRGB du sommet, convertie en linéaire (couleur_srgb.gdshaderinc).
#include "res://shaders/couleur_srgb.gdshaderinc"
uniform vec3 body_color : source_color = vec3(0.07, 0.08, 0.12);
uniform float intensity = 2.0;
uniform float player_s = 0.0;
uniform float ahead_m = 200.0;
uniform float far_dim = 0.35;
// Lot R30 : part de l'éclat sur toute la surface (le reste sur les arêtes). À 0,25, la route jaune éblouissait.
uniform float surface_share = 0.12;

varying float s_local;

void vertex() {
	s_local = -VERTEX.z;
}

void fragment() {
	float edge = min(UV.x, 1.0 - UV.x);
	float w = max(fwidth(edge), 0.00001) * 2.0;
	float line = 1.0 - smoothstep(0.0, w, edge);
	float fade = mix(1.0, far_dim, smoothstep(ahead_m, ahead_m + 40.0, s_local - player_s));
	ALBEDO = body_color + lineaire(COLOR.rgb) * 0.08;
	ROUGHNESS = 0.9;
	EMISSION = lineaire(COLOR.rgb) * intensity * (surface_share + (1.0 - surface_share) * line) * fade;
}

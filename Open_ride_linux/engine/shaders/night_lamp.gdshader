shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_disabled, diffuse_burley, specular_schlick_ggx;

// Lampes de nuit (lot P35) : phare et feu arrière des vélos, têtes des luminaires publics, lanternes.
// COLOR.rgb : couleur de la lampe (sRGB) ; COLOR.a : 1 pour le verre qui s'allume, 0 pour le boîtier.
// Le global `night_glow` (night_lights.gd, 0 de jour) allume le verre ; de jour le verre reste pâle.
// Le global `night_lamps` (0 quand le jour et la nuit est coupé) les fait disparaître : image d'aujourd'hui.

#include "res://shaders/couleur_srgb.gdshaderinc"

global uniform float night_glow;
global uniform float night_lamps;
uniform float energy = 4.0;

void fragment() {
	if (night_lamps < 0.5) {
		discard;
	}
	vec3 c = lineaire(COLOR.rgb);
	float glass = step(0.5, COLOR.a);
	ALBEDO = mix(c, c * 0.6 + vec3(0.25), glass);
	ROUGHNESS = mix(0.6, 0.15, glass);
	EMISSION = c * (glass * night_glow * energy);
}

shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_disabled;

// Écume du rivage (lot U9, sea_mesh.gd build_foam) : ruban posé sur la mer, côté large. UV.y : 0 au rivage,
// 1 au bout de la bande ; UV.x : distance le long de la côte (m) ; COLOR.r : part de la bande toujours
// couverte. L'écume va et vient entre cette part et la bande entière (période d'environ 7 s, décalée le
// long de la côte), en dentelle, plus dense au rivage. Horloge `anim_time` (anim_clock.gd).
#include "res://shaders/couleur_srgb.gdshaderinc"

global uniform float anim_time;
uniform float opacity = 0.85;

const vec3 FOAM = vec3(0.93, 0.95, 0.96);

void fragment() {
	float across = UV.y;
	float wash = mix(COLOR.r, 1.0, 0.5 + 0.5 * sin(anim_time * 0.9 + UV.x * 0.05));
	float edge = 1.0 - smoothstep(wash * 0.55, wash, across);
	float lace = 0.6 + 0.4 * sin(UV.x * 1.7 + anim_time * 1.3) * sin(UV.x * 0.63 - across * 9.0 + anim_time * 0.7);
	ALBEDO = lineaire(FOAM);
	ALPHA = clamp(opacity * edge * mix(1.0, lace, across), 0.0, 1.0);
	ROUGHNESS = 0.9;
}

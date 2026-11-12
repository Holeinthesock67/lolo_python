shader_type spatial;
render_mode cull_back;

// Mer animée (lot U9, sea_mesh.gd) : surface plate dont seules les normales bougent (aucun déplacement de
// sommet) : somme de quatre ondes de gravité (pulsation √(g k)), amplitudes équivalentes de 0,18 ; 0,08 ;
// 0,03 et 0,01 m, soit 0,30 m au plus en tout (cahier U9 : pas plus de 0,3 m). Les ondes s'atténuent avec la
// distance (moins de scintillement au loin). Couleur de sommet COLOR (sRGB) : `water` des biomes au centre de
// l'aire ; plus claire et plus grise vers l'horizon (fresnel), en plus du reflet du ciel de Godot.
// Horloge : `anim_time` (anim_clock.gd), figée avec le reste du décor dans les tests graphiques.
#include "res://shaders/couleur_srgb.gdshaderinc"

global uniform float anim_time;
uniform float wave_strength = 1.0;     // 0 : mer d'huile
uniform float fade_m = 900.0;          // distance où les ondes tombent au quart

varying vec3 world_pos;

// Onde : direction (x, z), longueur d'onde (m), pente maximale a·k.
const vec4 WAVES[4] = {
	vec4(0.94, 0.34, 14.0, 0.08),
	vec4(0.62, -0.78, 7.5, 0.07),
	vec4(-0.33, 0.94, 3.3, 0.05),
	vec4(0.80, 0.60, 1.6, 0.04)
};
const vec3 HORIZON_TINT = vec3(0.70, 0.80, 0.86);

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 p = world_pos.xz;
	float dist = length(world_pos - CAMERA_POSITION_WORLD);
	float fade = mix(1.0, 0.25, clamp(dist / fade_m, 0.0, 1.0)) * wave_strength;
	vec2 grad = vec2(0.0);
	for (int i = 0; i < 4; i++) {
		vec2 d = normalize(WAVES[i].xy);
		float k = 6.2831853 / WAVES[i].z;
		float phase = k * dot(d, p) - sqrt(9.81 * k) * anim_time;
		grad += d * WAVES[i].w * cos(phase);
	}
	grad *= fade;
	vec3 n_world = normalize(vec3(-grad.x, 1.0, -grad.y));
	NORMAL = normalize((VIEW_MATRIX * vec4(n_world, 0.0)).xyz);
	float fres = 0.02 + 0.98 * pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 5.0);
	vec3 base = COLOR.rgb;
	ALBEDO = lineaire(mix(base * 0.9, mix(base, HORIZON_TINT, 0.35), fres));
	ROUGHNESS = 0.06;
	SPECULAR = 0.5;
}

shader_type spatial;
render_mode cull_disabled, diffuse_lambert, specular_disabled;

global uniform float anim_time;

// Animaux du Lot P11 : animation par sommet à partir du temps global anim_time
// (anim_clock.gd : figé avec le décor quand le core ne répond plus).
// - UV.x : poids de l'aile (oiseaux, mode 0) ; battement autour de l'axe du corps.
// - UV.y : poids de la tête (bêtes au sol, mode 1) ; la tête descend brouter puis remonte.
// - INSTANCE_CUSTOM.x : phase de l'individu (0 à 1), pour que les animaux ne bougent pas ensemble.
// - INSTANCE_CUSTOM.y : 1 = tête levée (chevreuil aux aguets ou en fuite), 0 = broutage normal.
// - INSTANCE_CUSTOM.z : amplitude du battement d'ailes (oiseaux, Lot P23) : 1 en vol battu, presque 0 pour
//   un rapace qui plane, 0 pour une corneille posée.
// - CUSTOM0.x : zone de couleur du maillage (Lot Y14, fauna_renderer.gd FAUNA_*) : 0 robe, 1 teinte d'appoint,
//   2 sombre (sabots, yeux), 3 corne, 4 clair ; `patches` : part de la robe en taches claires (vache pie),
//   dessinées dans le repère de la bête et décalées par sa phase.
// - Lot U12 : `stripes` (rayures de la robe par mètre, zèbre ; 0 = aucune), en travers du corps et des pattes ;
//   `graze_m` : descente de la tête qui broute, à l'échelle de la bête (girafe, marmotte, flamant).
#include "res://shaders/surface_detail.gdshaderinc"

uniform int mode = 0;
uniform vec3 albedo : source_color = vec3(0.3, 0.3, 0.3);
uniform vec3 accent : source_color = vec3(0.3, 0.3, 0.3);
uniform vec3 light : source_color = vec3(0.9, 0.9, 0.9);
uniform float patches = 0.0;
uniform float stripes = 0.0;
uniform float graze_m = 0.45;
const vec3 DARK = vec3(0.05, 0.045, 0.04);
const vec3 HORN = vec3(0.82, 0.76, 0.62);

varying flat float v_region;
varying flat float v_seed;
varying vec3 v_local;
uniform float flap_hz = 6.0;
uniform float graze_hz = 0.12;

void vertex() {
	v_region = CUSTOM0.x;
	v_seed = INSTANCE_CUSTOM.x;
	v_local = VERTEX;
	float phase = INSTANCE_CUSTOM.x * 6.2831853;
	if (mode == 0) {
		float flap = sin(anim_time * 6.2831853 * flap_hz + phase);
		VERTEX.y += UV.x * flap * INSTANCE_CUSTOM.z * 0.35 * abs(VERTEX.x) * 2.0;
	} else {
		float down = 0.5 + 0.5 * sin(anim_time * 6.2831853 * graze_hz + phase);
		down = smoothstep(0.35, 0.9, down) * (1.0 - INSTANCE_CUSTOM.y);
		VERTEX.y -= UV.y * down * graze_m;
		VERTEX.z += UV.y * down * graze_m * 0.27;
	}
}

void fragment() {
	int region = int(v_region + 0.5);
	vec3 c = albedo;
	if (region == 1) {
		c = accent;
	} else if (region == 2) {
		c = DARK;
	} else if (region == 3) {
		c = HORN;
	} else if (region == 4) {
		c = light;
	} else if (stripes > 0.0) {
		// Bandes en travers du corps (le long de z), inclinées vers l'avant ; en travers des pattes (le long de y)
		float q = v_local.z + 0.35 * v_local.y + 0.15 * sin(v_local.y * 7.0 + v_local.x * 3.0);
		c = sin(q * stripes * 6.2831853) > 0.1 ? albedo : light;
	} else if (patches > 0.0) {
		vec2 q = v_local.zy * 2.2 + vec2(v_seed * 37.0, v_seed * 11.0);
		float n = sd_noise(q) * 0.7 + sd_noise(q * 2.3 + v_local.x) * 0.3;
		c = n > 1.0 - patches ? light : albedo;
	}
	ALBEDO = c;
}

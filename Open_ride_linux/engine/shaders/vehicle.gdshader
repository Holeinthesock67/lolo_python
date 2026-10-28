shader_type spatial;
render_mode cull_disabled, diffuse_lambert;

// Véhicules du décor (lots P13 et P25), maillages de scripts/vehicle_mesh.gd affichés en MultiMesh.
// - CUSTOM0.x : zone de couleur (vehicle_mesh.gd VEH_*) : 0 peinture (INSTANCE_CUSTOM.rgb), 1 vitres,
//   2 pneus, 3 plastique noir, 4 métal, 5 phares, 6 feux arrière, 7 teinte d'appoint du modèle (`accent`),
//   8 blanc (plaques, girouette), 9 gyrophare.
// - CUSTOM0.y : 1 sur une roue ; UV2 = (y, z) de son axe ; elle tourne de INSTANCE_CUSTOM.w (radians,
//   distance parcourue / rayon) autour de l'axe x, vers l'avant (-z).
// - `lights_on` (0 à 1) : phares et feux allumés (brume, pluie ; nuit avec P19 en 2.0) ; le gyrophare d'un
//   tracteur clignote toujours, plus fort phares allumés.

uniform vec3 accent : source_color = vec3(0.1, 0.1, 0.11);
uniform float lights_on = 0.0;
const vec3 GLASS = vec3(0.22, 0.28, 0.34);
const vec3 TYRE = vec3(0.035, 0.035, 0.035);
const vec3 TRIM = vec3(0.07, 0.07, 0.075);
const vec3 CHROME = vec3(0.62, 0.63, 0.65);
const vec3 HEAD = vec3(0.92, 0.92, 0.86);
const vec3 TAIL = vec3(0.55, 0.04, 0.03);
const vec3 WHITE = vec3(0.88, 0.88, 0.86);
const vec3 BEACON = vec3(0.95, 0.5, 0.05);

varying flat float v_region;
varying flat vec3 v_paint;
varying flat float v_phase;

vec3 rot_x(vec3 p, vec2 axle, float a) {
	vec2 q = p.yz - axle;
	float c = cos(a);
	float s = sin(a);
	return vec3(p.x, axle.x + q.x * c - q.y * s, axle.y + q.x * s + q.y * c);
}

void vertex() {
	v_region = CUSTOM0.x;
	v_paint = INSTANCE_CUSTOM.rgb;
	v_phase = fract(INSTANCE_CUSTOM.r * 7.0 + INSTANCE_CUSTOM.g * 13.0);
	if (CUSTOM0.y > 0.5) {
		float a = -INSTANCE_CUSTOM.w;
		VERTEX = rot_x(VERTEX, UV2, a);
		NORMAL = rot_x(NORMAL, vec2(0.0), a);
	}
}

void fragment() {
	int region = int(v_region + 0.5);
	vec3 c = v_paint;
	float rough = 0.32;
	float metal = 0.15;
	vec3 emit = vec3(0.0);
	if (region == 1) {
		c = GLASS;
		rough = 0.08;
		metal = 0.25;
	} else if (region == 2) {
		c = TYRE;
		rough = 0.9;
		metal = 0.0;
	} else if (region == 3) {
		c = TRIM;
		rough = 0.7;
		metal = 0.0;
	} else if (region == 4) {
		c = CHROME;
		rough = 0.25;
		metal = 0.8;
	} else if (region == 5) {
		c = HEAD;
		rough = 0.1;
		emit = vec3(1.0, 0.95, 0.82) * 3.0 * lights_on;
	} else if (region == 6) {
		c = TAIL;
		rough = 0.2;
		emit = vec3(1.0, 0.08, 0.04) * (0.15 + 1.6 * lights_on);
	} else if (region == 7) {
		c = accent;
		rough = 0.45;
	} else if (region == 8) {
		c = WHITE;
		rough = 0.6;
		metal = 0.0;
	} else if (region == 9) {
		c = BEACON;
		float blink = step(0.5, fract(TIME * 1.4 + v_phase));
		emit = BEACON * blink * (0.6 + 2.0 * lights_on);
	}
	ALBEDO = c;
	ROUGHNESS = rough;
	METALLIC = metal;
	EMISSION = emit;
}

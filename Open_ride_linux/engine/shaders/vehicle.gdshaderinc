// Corps commun des shaders des véhicules (vehicle.gdshader, et vehicle_far.gdshader des avions de ligne du
// Lot P26, sans brouillard) ; zones et paramètres décrits dans vehicle.gdshader.
uniform vec3 paint : source_color = vec3(0.62, 0.08, 0.08);
uniform vec3 second : source_color = vec3(0.5, 0.5, 0.5);
uniform float lights = 0.0;
uniform bool instanced = false;
const vec3 GLASS = vec3(0.05, 0.07, 0.09);
const vec3 DARK = vec3(0.04, 0.04, 0.045);
const vec3 METAL = vec3(0.6, 0.61, 0.63);
const vec3 HEAD = vec3(0.85, 0.85, 0.8);
const vec3 TAIL = vec3(0.45, 0.03, 0.03);
const vec3 PALE = vec3(0.82, 0.82, 0.78);
const vec3 SKIN = vec3(0.78, 0.57, 0.44);
const vec3 WOOD = vec3(0.46, 0.3, 0.17);
const vec3 HEAD_GLOW = vec3(1.0, 0.95, 0.8);
const vec3 TAIL_GLOW = vec3(0.9, 0.05, 0.03);

varying flat float v_region;
varying vec3 v_paint;
varying flat float v_lights;

void vertex() {
	v_region = CUSTOM0.x;
	v_paint = instanced ? COLOR.rgb : paint;
	v_lights = instanced ? INSTANCE_CUSTOM.x : lights;
}

void fragment() {
	int region = int(v_region + 0.5);
	vec3 c = v_paint;
	float rough = 0.35;
	float metal = 0.0;
	float spec = 0.5;
	if (region == 1) {
		c = GLASS;
		rough = 0.06;
		spec = 1.0;
	} else if (region == 2) {
		c = DARK;
		rough = 0.85;
		spec = 0.2;
	} else if (region == 3) {
		c = METAL;
		rough = 0.3;
		metal = 0.8;
	} else if (region == 4) {
		c = HEAD;
		rough = 0.1;
		EMISSION = HEAD_GLOW * v_lights * 2.5;
	} else if (region == 5) {
		c = TAIL;
		rough = 0.2;
		EMISSION = TAIL_GLOW * (0.15 + v_lights * 1.4);
	} else if (region == 6) {
		c = PALE;
		rough = 0.6;
	} else if (region == 7) {
		c = second;
		rough = 0.5;
	} else if (region == 8) {
		c = SKIN;
		rough = 0.7;
		spec = 0.3;
	} else if (region == 9) {
		c = WOOD;
		rough = 0.75;
		spec = 0.3;
	}
	ALBEDO = c;
	ROUGHNESS = rough;
	METALLIC = metal;
	SPECULAR = spec;
}

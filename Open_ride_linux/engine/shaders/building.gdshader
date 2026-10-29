shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

// Habillage des bâtiments OSM (Lot Y8), sans texture : façades (enduit, brique, moellons, bardage de bois,
// colombage, tôle, béton), socle, fenêtres, volets, portes et vitrines, toits (tuiles plates, tuiles rondes,
// ardoise, bac acier, bardeaux, toit plat). Mêmes bruits et même faux relief que la route et le terrain
// (surface_detail.gdshaderinc) ; le détail plus fin qu'un pixel est fondu vers sa teinte moyenne.
//
// Entrées (building_mesh.gd) :
// - COLOR.rgb : teinte du mur ou du toit (sRGB) ; COLOR.a : graine du bâtiment ;
// - UV : mètres (mur : le long du segment et au-dessus de base_y ; toit : le long de l'égout et en remontant
//   la pente, ou x, z pour un toit plat) ;
// - UV2 : x = longueur du segment de mur (m), y = code d'habillage : matière du mur + 8 × ouvertures
//   + 64 × matière du toit + 512 × toit + 1024 × hauteur des murs au quart de mètre.

#include "res://shaders/surface_detail.gdshaderinc"

// Faux relief (0 en `low` : motifs dessinés en couleur seulement)
uniform float relief = 1.0;

const float FLOOR_H = 3.0;
const float PLINTH_H = 0.55;

const int WALL_PLASTER = 0;
const int WALL_BRICK = 1;
const int WALL_STONE = 2;
const int WALL_WOOD = 3;
const int WALL_TIMBER = 4;
const int WALL_METAL = 5;
const int WALL_CONCRETE = 6;

const int WIN_NONE = 0;
const int WIN_HOUSE = 1;
const int WIN_BANDS = 2;
const int WIN_BARN = 3;
const int WIN_CHURCH = 4;
const int WIN_SHOP = 5;

const int ROOF_FLAT = 0;
const int ROOF_TILE_FLAT = 1;
const int ROOF_TILE_ROUND = 2;
const int ROOF_SLATE = 3;
const int ROOF_METAL = 4;
const int ROOF_SHINGLE = 5;

varying float v_under;

void vertex() {
	// Dessous du débord de toit (normale vers le bas)
	v_under = step(NORMAL.y, -0.2);
}

vec3 to_linear(vec3 c) {
	return pow(c, vec3(2.2));
}

// 1 dans le rectangle [a, b] (mètres), bord net
float box(vec2 p, vec2 a, vec2 b) {
	return step(a.x, p.x) * step(p.x, b.x) * step(a.y, p.y) * step(p.y, b.y);
}

// Distance au segment [a, b]
float seg_dist(vec2 p, vec2 a, vec2 b) {
	vec2 pa = p - a;
	vec2 ba = b - a;
	float t = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
	return length(pa - ba * t);
}

// ---------- Matières de mur : couleur, hauteur de relief (m), rugosité ----------

void plaster(vec2 uv, vec3 tint, inout vec3 col, inout float h) {
	float mottle = sd_noise(uv / 2.5) * 0.6 + sd_noise(uv / 0.7) * 0.4;
	float grain = sd_noise(uv / 0.03);
	float vis = sd_visible(uv, 0.03);
	col = tint * (0.9 + mottle * 0.14 + (grain - 0.5) * 0.06 * vis);
	h = grain * 0.0015 * vis;
}

void brick(vec2 uv, vec3 tint, inout vec3 col, inout float h) {
	float row = floor(uv.y / 0.075);
	float bx = uv.x / 0.225 + mod(row, 2.0) * 0.5;
	vec2 cell = vec2(floor(bx), row);
	vec2 f = vec2(fract(bx), fract(uv.y / 0.075));
	float mortar = max(step(f.x, 0.045), step(f.y, 0.14));
	float vis = sd_visible(uv, 0.075);
	vec3 b = tint * (0.78 + 0.4 * sd_hash(cell)) * (0.92 + 0.12 * sd_noise(uv / 0.04));
	vec3 m = vec3(0.62, 0.6, 0.56);
	vec3 avg = tint * 0.92;
	col = mix(avg, mix(b, m, mortar), vis);
	h = smoothstep(0.0, 0.1, f.x) * smoothstep(1.0, 0.9, f.x) * smoothstep(0.08, 0.3, f.y) * smoothstep(1.0, 0.92, f.y) * 0.004 * vis;
}

void stone(vec2 uv, vec3 tint, inout vec3 col, inout float h) {
	vec2 c = sd_pebbles(vec2(uv.x / 0.42, uv.y / 0.28));
	float vis = sd_visible(uv, 0.3);
	float mortar = smoothstep(0.5, 0.62, c.x);
	vec3 s = tint * (0.7 + 0.45 * c.y) * (0.9 + 0.15 * sd_noise(uv / 0.05));
	vec3 m = vec3(0.6, 0.58, 0.53);
	col = mix(tint * 0.88, mix(s, m, mortar * 0.85), vis);
	h = (0.62 - c.x) * 0.05 * vis;
}

void wood(vec2 uv, vec3 tint, inout vec3 col, inout float h) {
	float px = uv.x / 0.18;
	float gap = step(fract(px), 0.07);
	float plank = sd_hash(vec2(floor(px), 3.0));
	float grain = sd_noise(vec2(px * 6.0, uv.y * 0.9 + plank * 13.0));
	float vis = sd_visible(uv, 0.18);
	vec3 w = tint * (0.75 + 0.35 * plank) * (0.85 + 0.25 * grain);
	col = mix(tint * 0.92, mix(w, tint * 0.35, gap), vis);
	h = smoothstep(0.0, 0.12, fract(px)) * smoothstep(1.0, 0.9, fract(px)) * 0.006 * vis;
}

void metal_sheet(vec2 uv, vec3 tint, inout vec3 col, inout float h, inout float rough, inout float metal) {
	float wave = sin(uv.x * 6.2832 / 0.2);
	float vis = sd_visible(uv, 0.2);
	float streak = sd_noise(vec2(uv.x * 3.0, uv.y * 0.25));
	col = tint * (0.92 + 0.06 * wave * vis) * (0.85 + 0.2 * streak);
	h = wave * 0.012 * vis;
	rough = 0.5;
	metal = 0.35;
}

void concrete(vec2 uv, vec3 tint, inout vec3 col, inout float h) {
	vec2 f = fract(uv / vec2(3.0, 1.5));
	float joint = max(step(f.x, 0.008), step(f.y, 0.014));
	float vis = sd_visible(uv, 1.5);
	float stain = sd_noise(uv / vec2(1.2, 3.0));
	col = tint * (0.88 + 0.12 * stain) * (1.0 - 0.25 * joint * vis);
	h = smoothstep(0.0, 0.03, min(f.x, 1.0 - f.x) * 3.0) * smoothstep(0.0, 0.03, min(f.y, 1.0 - f.y) * 1.5) * 0.004 * vis;
}

// ---------- Ouvertures : fenêtre, volets, porte ----------

// Fenêtre de `w` × `ht` m centrée en lx, de ly0 à ly0 + ht ; renvoie 1 dans le vitrage, 0,5 dans le cadre
float window_mask(vec2 l, float w, float ly0, float ht, float frame) {
	float outer = box(l, vec2(-w * 0.5, ly0), vec2(w * 0.5, ly0 + ht));
	float inner = box(l, vec2(-w * 0.5 + frame, ly0 + frame), vec2(w * 0.5 - frame, ly0 + ht - frame));
	return outer * (0.5 + 0.5 * inner);
}

vec3 glass(vec2 l, float seed) {
	// Reflet du ciel en dégradé, quelques rideaux
	float sky = clamp(l.y * 0.4 - 0.2, 0.0, 1.0);
	vec3 g = mix(vec3(0.05, 0.07, 0.09), vec3(0.22, 0.28, 0.34), sky);
	float curtain = step(0.6, sd_hash(vec2(seed * 31.0, floor(l.x * 3.0))));
	return mix(g, vec3(0.55, 0.52, 0.46), curtain * 0.35);
}

vec3 shutter_color(float seed) {
	int k = int(seed * 5.0);
	if (k == 0) return vec3(0.25, 0.38, 0.27);
	if (k == 1) return vec3(0.33, 0.43, 0.5);
	if (k == 2) return vec3(0.42, 0.28, 0.17);
	if (k == 3) return vec3(0.46, 0.16, 0.12);
	return vec3(0.82, 0.8, 0.74);
}

// Porte d'entrée dans sa travée (l : mètres, x centré sur la travée, y depuis le sol) : encadrement de pierre
// à harpes et clé de linteau, seuil, vantail à panneaux moulurés, à lames et pentures ou vitré en partie haute,
// imposte vitrée, poignée et plaque de propreté. Renvoie false hors de l'encadrement (le mur reste visible).
bool house_door(vec2 l, float seed, inout vec3 col, inout float rough, inout float h) {
	const float W = 0.5;            // demi-largeur du vantail
	const float SILL = 0.12;        // dessus du seuil
	const float LEAF_TOP = 2.05;
	const float TOP = 2.42;         // haut de l'imposte
	const float JAMB = 0.17;        // largeur des pierres d'encadrement
	if (abs(l.x) > W + JAMB || l.y > TOP + 0.24) {
		return false;
	}
	float vis = sd_visible(l, 0.04);
	float style = sd_hash(vec2(seed * 23.0, 4.0));
	vec3 paint = shutter_color(fract(seed * 7.0)) * 0.85;
	// Encadrement : piédroits en harpes (pierres alternées longues et courtes), linteau avec clé
	if (abs(l.x) > W || l.y > TOP) {
		float course = floor(l.y / 0.34);
		float long_stone = mod(course, 2.0);
		float reach = W + JAMB - 0.06 + 0.06 * long_stone;
		bool lintel = l.y > TOP;
		if (!lintel && abs(l.x) > reach) {
			return false;
		}
		if (lintel && abs(l.x) > W + JAMB) {
			return false;
		}
		vec3 stone_col = mix(vec3(0.78, 0.74, 0.66), vec3(0.66, 0.6, 0.52), step(0.6, fract(seed * 11.0)));
		float joint = lintel ? step(abs(abs(l.x) - 0.11), 0.008) : step(fract(l.y / 0.34), 0.03);
		float key = lintel ? step(abs(l.x), 0.11) : 0.0;
		col = stone_col * (0.88 + 0.16 * sd_noise(l / 0.06) * vis + 0.06 * key) * (1.0 - 0.3 * joint * vis);
		float edge = lintel ? min(min(TOP + 0.24 - l.y, l.y - TOP), W + JAMB - abs(l.x)) : min(reach - abs(l.x), abs(l.x) - W);
		h = (0.012 + 0.004 * key) * smoothstep(0.0, 0.03, edge) * (1.0 - joint * vis);
		rough = 0.85;
		return true;
	}
	// Seuil de pierre sombre, un peu en avant
	if (l.y < SILL) {
		col = vec3(0.5, 0.48, 0.45) * (0.9 + 0.15 * sd_noise(l / 0.05) * vis);
		h = 0.008 * smoothstep(0.0, 0.02, SILL - l.y);
		rough = 0.8;
		return true;
	}
	// Feuillure : cadre dormant peint autour du vantail et de l'imposte
	float frame_d = min(min(W - abs(l.x), l.y - SILL), TOP - l.y);
	float transom_bar = step(abs(l.y - LEAF_TOP - 0.03), 0.03);
	if (frame_d < 0.05 || transom_bar > 0.5) {
		col = mix(paint, vec3(0.85, 0.84, 0.8), 0.55);
		h = -0.004;
		rough = 0.55;
		return true;
	}
	// Imposte vitrée en éventail
	if (l.y > LEAF_TOP + 0.06) {
		vec2 c = l - vec2(0.0, LEAF_TOP + 0.06);
		float ang = atan(c.x, c.y);
		float ray = step(abs(fract(ang / 0.45 + 0.5) - 0.5), 0.05) * step(0.06, length(c));
		col = mix(glass(l + vec2(0.0, 0.6), seed), mix(paint, vec3(0.85, 0.84, 0.8), 0.55), ray);
		h = -0.012 + 0.006 * ray;
		rough = mix(0.08, 0.55, ray);
		return true;
	}
	// Vantail
	vec2 d = vec2(l.x, l.y - SILL);
	float leaf_h = LEAF_TOP - SILL;
	float wear = 1.0 - 0.18 * (1.0 - smoothstep(0.0, 0.35, d.y)) * sd_noise(l / 0.08);
	h = -0.01;
	rough = 0.5;
	if (style < 0.3) {
		// Porte rurale : lames verticales, deux pentures noires et une écharpe en Z
		float lame = fract((d.x + W) / 0.125);
		float gap = smoothstep(0.06, 0.0, min(lame, 1.0 - lame)) * vis;
		vec3 wood_col = mix(vec3(0.42, 0.29, 0.17), paint, step(0.15, style));
		col = wood_col * (0.82 + 0.25 * sd_hash(vec2(floor((d.x + W) / 0.125), seed))) * (0.9 + 0.12 * sd_noise(vec2(d.x * 30.0, d.y * 2.0)) * vis);
		col *= 1.0 - 0.45 * gap;
		h -= 0.003 * gap;
		float hinge = (step(abs(d.y - 0.3), 0.025) + step(abs(d.y - leaf_h + 0.3), 0.025)) * step(d.x, 0.25);
		col = mix(col, vec3(0.06), hinge);
		h += 0.004 * hinge;
		rough = mix(0.75, 0.4, hinge);
	} else {
		// Porte à panneaux moulurés (deux en bas, deux ou un vitrage en haut)
		bool glazed = style > 0.72;
		float mid = leaf_h * 0.52;
		vec2 q = vec2(abs(d.x), d.y < mid ? d.y : d.y - mid);
		float ph = d.y < mid ? mid : leaf_h - mid;
		float inset = min(min(q.x - 0.08, W - 0.08 - q.x), min(q.y - 0.12, ph - 0.1 - q.y));
		if (glazed && d.y >= mid) {
			float pane = min(W - 0.1 - abs(d.x), min(d.y - mid - 0.06, leaf_h - 0.1 - d.y));
			if (pane > 0.0) {
				float bar = step(abs(d.x), 0.018) + step(abs(d.y - (mid + leaf_h) * 0.5), 0.018);
				col = mix(glass(l, seed), paint, min(bar, 1.0));
				h = -0.016 + 0.006 * min(bar, 1.0);
				rough = mix(0.06, 0.5, min(bar, 1.0));
				return true;
			}
		}
		col = paint * (0.95 + 0.06 * sd_noise(l / 0.3));
		// Moulure en biseau autour de chaque panneau, panneau plat au fond
		float bevel = smoothstep(0.0, 0.035, inset);
		h += inset > 0.0 ? -0.006 * bevel : 0.0;
		col *= inset > 0.0 ? 0.93 + 0.07 * bevel : 1.0;
		// Plaque de propreté au bas du vantail
		if (d.y < 0.1) {
			col = vec3(0.55, 0.45, 0.25);
			rough = 0.3;
		}
	}
	col *= wear;
	// Poignée et serrure, côté opposé aux paumelles
	float knob = smoothstep(0.03, 0.022, length(d - vec2(W - 0.11, 0.95)));
	float plate = box(d, vec2(W - 0.14, 0.82), vec2(W - 0.08, 1.02));
	col = mix(col, vec3(0.62, 0.5, 0.25), max(knob, plate * 0.8));
	h += 0.006 * knob + 0.002 * plate;
	rough = mix(rough, 0.25, max(knob, plate));
	return true;
}

// Bâtiment avec fenêtres à volets (maisons), par travées d'environ 3,2 m ; porte sur certains murs
void house_openings(vec2 uv, float seg, float eave, float seed, bool shutters, inout vec3 col, inout float rough, inout float h) {
	float nb = floor(seg / 3.2);
	if (nb < 1.0) {
		return;
	}
	float bw = seg / nb;
	float cell = floor(uv.x / bw);
	float fi = floor(uv.y / FLOOR_H);
	vec2 l = vec2((fract(uv.x / bw) - 0.5) * bw, uv.y - fi * FLOOR_H);
	if (fi < 0.0 || (fi + 1.0) * FLOOR_H > eave + 0.4) {
		return;
	}
	float slat_vis = sd_visible(uv, 0.07);
	float wall_id = sd_hash(vec2(seg * 7.31, seed * 17.0));
	float door_cell = floor(sd_hash(vec2(seed * 5.0, seg)) * nb);
	if (fi == 0.0 && cell == door_cell && wall_id < 0.55 && seg > 4.0) {
		// Travée de la porte : ni fenêtre ni volets autour
		house_door(l, seed, col, rough, h);
		return;
	}
	float w = window_mask(l, 1.05, 0.9, 1.35, 0.07);
	float sill = box(l, vec2(-0.62, 0.82), vec2(0.62, 0.9));
	if (w > 0.75) {
		// Vitrage et petits bois
		float bar = max(step(abs(l.x), 0.02), step(abs(l.y - 1.9), 0.02));
		col = mix(glass(l, seed + cell), vec3(0.85, 0.84, 0.8), bar);
		rough = mix(0.08, 0.6, bar);
	} else if (w > 0.0) {
		col = vec3(0.86, 0.85, 0.8);
	} else if (sill > 0.0) {
		col = vec3(0.7, 0.68, 0.63);
	} else if (shutters && abs(l.x) < 1.1 && l.y > 0.9 && l.y < 2.25) {
		float open = step(sd_hash(vec2(cell + seed * 13.0, fi)), 0.8);
		if (open > 0.5) {
			float slat = step(0.5, fract(l.y / 0.07)) * slat_vis;
			col = shutter_color(seed) * (0.85 + 0.15 * slat);
		}
	}
}

// Bandeaux vitrés par étage, meneaux tous les 1,5 m
void band_openings(vec2 uv, float eave, inout vec3 col, inout float rough) {
	float fi = floor(uv.y / FLOOR_H);
	float ly = uv.y - fi * FLOOR_H;
	if (fi < 0.0 || (fi + 1.0) * FLOOR_H > eave + 0.4 || ly < 0.9 || ly > 2.5) {
		return;
	}
	float mull = step(fract(uv.x / 1.5), 0.05);
	col = mix(glass(vec2(uv.x, ly), fi), vec3(0.5, 0.52, 0.54), mull);
	rough = mix(0.08, 0.4, mull);
}

// Jours hauts et grand portail (granges, hangars, ateliers)
void barn_openings(vec2 uv, float seg, float eave, float seed, inout vec3 col, inout float rough) {
	if (eave > 3.2) {
		float nb = max(1.0, floor(seg / 3.0));
		vec2 l = vec2((fract(uv.x / (seg / nb)) - 0.5) * (seg / nb), uv.y);
		float w = window_mask(l, 1.6, eave - 1.3, 0.6, 0.05);
		if (w > 0.0) {
			col = w > 0.75 ? glass(l, seed) * 0.8 : vec3(0.35, 0.33, 0.3);
			rough = 0.2;
		}
	}
	if (seg > 7.0 && sd_hash(vec2(seg * 3.1, seed * 11.0)) < 0.6) {
		float gw = min(4.0, seg * 0.4);
		float gh = min(4.0, eave - 0.6);
		vec2 l = vec2(uv.x - seg * 0.5, uv.y);
		float g = window_mask(l, gw, 0.0, gh, 0.1);
		if (g > 0.0) {
			float plank = step(fract(l.x / 0.16), 0.08);
			float brace = step(seg_dist(l, vec2(-gw * 0.5, 0.1), vec2(gw * 0.5, gh - 0.1)), 0.07);
			col = g < 0.75 ? col * 0.6 : col * (0.65 - 0.15 * plank + 0.15 * brace);
		}
	}
}

// Hautes baies cintrées (églises)
void church_openings(vec2 uv, float seg, float eave, float seed, inout vec3 col, inout float rough) {
	float nb = floor(seg / 4.0);
	if (nb < 1.0 || eave < 4.5) {
		return;
	}
	float bw = seg / nb;
	vec2 l = vec2((fract(uv.x / bw) - 0.5) * bw, uv.y);
	float top = min(eave - 1.0, 8.0);
	float y0 = 2.6;
	float r = 0.5;
	bool inside = (abs(l.x) < r && l.y > y0 && l.y < top - r) || length(l - vec2(0.0, top - r)) < r;
	bool frame = (abs(l.x) < r + 0.12 && l.y > y0 - 0.12 && l.y < top - r) || length(l - vec2(0.0, top - r)) < r + 0.12;
	if (inside) {
		float lead = max(step(fract(l.x / 0.25 + 0.5), 0.08), step(fract(l.y / 0.35), 0.06));
		vec3 stained = mix(vec3(0.12, 0.16, 0.3), vec3(0.35, 0.12, 0.1), sd_hash(floor(l * vec2(4.0, 2.9)) + seed));
		col = mix(stained, vec3(0.08), lead);
		rough = 0.15;
	} else if (frame) {
		col = col * 1.12;
	}
}

// Vitrines au rez-de-chaussée, fenêtres aux étages
void shop_openings(vec2 uv, float seg, float eave, float seed, inout vec3 col, inout float rough) {
	if (uv.y < FLOOR_H) {
		float nb = max(1.0, floor(seg / 4.5));
		float bw = seg / nb;
		vec2 l = vec2((fract(uv.x / bw) - 0.5) * bw, uv.y);
		float w = window_mask(l, bw * 0.78, 0.35, 2.3, 0.06);
		float sign_band = box(l, vec2(-bw * 0.45, 2.75), vec2(bw * 0.45, 2.95));
		if (w > 0.75) {
			col = glass(l, seed) * 1.2;
			rough = 0.06;
		} else if (w > 0.0) {
			col = vec3(0.2, 0.21, 0.22);
		} else if (sign_band > 0.0) {
			col = shutter_color(fract(seed * 3.0));
		}
	} else {
		float shop_h = 0.0;
		house_openings(uv, seg, eave, seed, false, col, rough, shop_h);
	}
}

// Colombage : sablières aux étages, poteaux aux bords des travées, écharpes en diagonale
void timber_frame(vec2 uv, float seg, float eave, float seed, inout vec3 col) {
	vec3 beam = vec3(0.22, 0.14, 0.08);
	float bw = seg / max(1.0, floor(seg / 3.2));
	float lx = fract(uv.x / bw) * bw;
	float fi = floor(uv.y / FLOOR_H);
	float ly = uv.y - fi * FLOOR_H;
	float t = 0.11;
	bool on = false;
	if (uv.y > PLINTH_H && uv.y < eave + 0.05) {
		on = ly < t || abs(uv.y - eave) < t || lx < t || lx > bw - t || uv.x < t * 1.5 || uv.x > seg - t * 1.5;
		// Écharpes dans les panneaux de côté (de part et d'autre des fenêtres)
		float side = 0.95 * bw / 3.2;
		on = on || seg_dist(vec2(lx, ly), vec2(0.0, 0.0), vec2(side, FLOOR_H)) < t * 0.6;
		on = on || seg_dist(vec2(lx, ly), vec2(bw, 0.0), vec2(bw - side, FLOOR_H)) < t * 0.6;
	} else if (uv.y >= eave) {
		// Pignon : poinçon au milieu et contrefiches
		float mid = seg * 0.5;
		on = abs(uv.x - mid) < t || abs(fract((uv.y - eave) / 1.4) - 0.0) * 1.4 < t;
		on = on || abs(abs(uv.x - mid) - (uv.y - eave)) < t * 0.8;
	}
	if (on) {
		float grain = sd_noise(vec2(uv.x * 8.0, uv.y * 1.5));
		col = beam * (0.85 + 0.3 * grain);
	}
}

// ---------- Toits ----------

void roof_tile_flat(vec2 uv, vec3 tint, inout vec3 col, inout float h, inout float rough) {
	float row = floor(uv.y / 0.17);
	float tx = uv.x / 0.18 + mod(row, 2.0) * 0.5;
	vec2 cell = vec2(floor(tx), row);
	vec2 f = vec2(fract(tx), fract(uv.y / 0.17));
	// Queue de castor : bas de la tuile arrondi, ombre du rang du dessus
	float edge = 0.18 * (1.0 - sqrt(max(0.0, 1.0 - pow(2.0 * f.x - 1.0, 2.0))));
	float shadow = step(f.y, edge + 0.08);
	float gap = step(abs(f.x - 0.5), 0.47);
	float vis = sd_visible(uv, 0.17);
	float moss = smoothstep(0.55, 0.8, sd_noise(uv / 1.5)) * 0.5;
	vec3 t = tint * (0.72 + 0.4 * sd_hash(cell)) * (1.0 - 0.35 * shadow) * mix(1.0, 0.8, 1.0 - gap);
	t = mix(t, vec3(0.25, 0.27, 0.16), moss * 0.6);
	col = mix(tint * 0.85, t, vis);
	h = smoothstep(edge, edge + 0.15, f.y) * smoothstep(1.0, 0.8, f.y) * 0.01 * vis;
	rough = 0.75;
}

void roof_tile_round(vec2 uv, vec3 tint, inout vec3 col, inout float h, inout float rough) {
	float c = sin(uv.x * 6.2832 / 0.22);
	float row = floor(uv.y / 0.4);
	float f = fract(uv.y / 0.4);
	float vis = sd_visible(uv, 0.22);
	vec2 cell = vec2(floor(uv.x / 0.22), row);
	vec3 t = tint * (0.75 + 0.4 * sd_hash(cell)) * (0.8 + 0.25 * (0.5 + 0.5 * c)) * (1.0 - 0.25 * step(f, 0.06));
	col = mix(tint * 0.88, t, vis);
	h = ((0.5 + 0.5 * c) * 0.03 + smoothstep(0.0, 0.15, f) * smoothstep(1.0, 0.85, f) * 0.008) * vis;
	rough = 0.8;
}

void roof_slate(vec2 uv, vec3 tint, float rows, float width, inout vec3 col, inout float h, inout float rough) {
	float row = floor(uv.y / rows);
	float off = sd_hash(vec2(row, 1.7));
	float tx = uv.x / width + off;
	vec2 cell = vec2(floor(tx), row);
	vec2 f = vec2(fract(tx), fract(uv.y / rows));
	float shadow = step(f.y, 0.1) + step(f.x, 0.04) * 0.5;
	float vis = sd_visible(uv, rows);
	vec3 t = tint * (0.8 + 0.3 * sd_hash(cell)) * (1.0 - 0.3 * shadow);
	col = mix(tint * 0.92, t, vis);
	h = smoothstep(0.0, 0.2, f.y) * smoothstep(1.0, 0.85, f.y) * 0.005 * vis;
	rough = 0.55;
}

void roof_metal(vec2 uv, vec3 tint, inout vec3 col, inout float h, inout float rough, inout float metal) {
	float f = fract(uv.x / 0.33);
	float rib = smoothstep(0.0, 0.04, f) * (1.0 - smoothstep(0.08, 0.12, f));
	float vis = sd_visible(uv, 0.33);
	float streak = sd_noise(vec2(uv.x * 2.0, uv.y * 0.2));
	col = tint * (0.85 + 0.2 * streak) * (1.0 + 0.1 * rib * vis);
	h = rib * 0.025 * vis;
	rough = 0.45;
	metal = 0.4;
}

void roof_flat(vec2 uv, vec3 tint, inout vec3 col, inout float h, inout float rough) {
	float grain = sd_noise(uv / 0.04);
	float vis = sd_visible(uv, 0.04);
	float stain = sd_noise(uv / 4.0);
	col = tint * (0.85 + 0.2 * stain) * (1.0 + (grain - 0.5) * 0.25 * vis);
	h = grain * 0.004 * vis;
	rough = 0.95;
}

void fragment() {
	int code = int(UV2.y + 0.5);
	int wall = code % 8;
	int openings = (code / 8) % 8;
	int roof = (code / 64) % 8;
	bool is_roof = ((code / 512) % 2) == 1;
	float eave = float(code / 1024) * 0.25;
	// Graine et longueur arrondies : les valeurs interpolées varient d'un pixel à l'autre au dernier chiffre
	// près, et un hachage en ferait un tirage différent par pixel (points dans les fenêtres)
	float seed = floor(COLOR.a * 255.0 + 0.5) / 255.0;
	vec3 tint = to_linear(COLOR.rgb);
	vec2 uv = UV;
	float seg = floor(UV2.x * 64.0 + 0.5) / 64.0;
	vec3 col = tint;
	float h = 0.0;
	float rough = 0.85;
	float metal = 0.0;

	if (is_roof && v_under > 0.5) {
		// Voliges sous le débord, dans l'ombre
		float plank = step(fract(uv.x / 0.15), 0.08);
		col = vec3(0.3, 0.22, 0.15) * (1.0 - 0.3 * plank);
	} else if (is_roof) {
		if (roof == ROOF_TILE_FLAT) {
			roof_tile_flat(uv, tint, col, h, rough);
		} else if (roof == ROOF_TILE_ROUND) {
			roof_tile_round(uv, tint, col, h, rough);
		} else if (roof == ROOF_SLATE) {
			roof_slate(uv, tint, 0.2, 0.26, col, h, rough);
		} else if (roof == ROOF_METAL) {
			roof_metal(uv, tint, col, h, rough, metal);
		} else if (roof == ROOF_SHINGLE) {
			roof_slate(uv, tint, 0.14, 0.16, col, h, rough);
			rough = 0.85;
		} else {
			roof_flat(uv, tint, col, h, rough);
		}
	} else {
		if (wall == WALL_BRICK) {
			brick(uv, tint, col, h);
		} else if (wall == WALL_STONE) {
			stone(uv, tint, col, h);
		} else if (wall == WALL_WOOD) {
			wood(uv, tint, col, h);
		} else if (wall == WALL_METAL) {
			metal_sheet(uv, tint, col, h, rough, metal);
		} else if (wall == WALL_CONCRETE) {
			concrete(uv, tint, col, h);
		} else {
			plaster(uv, tint, col, h);
			if (wall == WALL_TIMBER) {
				timber_frame(uv, seg, eave, seed, col);
			}
		}
		// Salissures au pied du mur, plus marquées sur l'enduit
		col *= mix(0.8, 1.0, smoothstep(PLINTH_H, PLINTH_H + 1.4, uv.y));
		// Socle de pierre ou de béton, avec un léger débord
		if (uv.y < PLINTH_H && wall != WALL_METAL) {
			vec3 p = vec3(0.42, 0.4, 0.37);
			float pn = sd_noise(uv / vec2(0.5, 0.25));
			col = p * (0.85 + 0.25 * pn);
			h = pn * 0.01 * sd_visible(uv, 0.25);
		}
		vec3 c_before = col;
		float open_h = 0.0;     // relief des ouvertures (portes)
		if (openings == WIN_HOUSE) {
			house_openings(uv, seg, eave, seed, wall != WALL_CONCRETE && wall != WALL_METAL, col, rough, open_h);
		} else if (openings == WIN_BANDS) {
			band_openings(uv, eave, col, rough);
		} else if (openings == WIN_BARN) {
			barn_openings(uv, seg, eave, seed, col, rough);
		} else if (openings == WIN_CHURCH) {
			church_openings(uv, seg, eave, seed, col, rough);
		} else if (openings == WIN_SHOP) {
			shop_openings(uv, seg, eave, seed, col, rough);
		}
		if (col != c_before) {
			metal = 0.0;
			h = open_h;
		}
	}

	ALBEDO = col;
	ROUGHNESS = rough;
	METALLIC = metal;
	// Hors de toute branche : les dérivées d'écran de sd_bump sont fausses dans un flot non uniforme
	// (points clairs au bord des fenêtres)
	if (relief > 0.0) {
		NORMAL = sd_bump(NORMAL, VERTEX, h * relief);
	}
}

// Trou du terrain dans les tunnels (lot EA5, scripts/tunnel_cut.gd) : vrai si le point du monde `p` est dans le
// volume d'un tunnel proche (tube et approche des portails). Même calcul que TunnelMesh.cut_contains.
// Tronçon i : texel 3i = (a.x, a.y, a.z, haut des piédroits en a), 3i+1 = (b…, haut en b),
// 3i+2 = (demi-largeur, voûte en demi-ellipse, plancher sous la chaussée, 0).
global uniform sampler2D tunnel_cut_data;
global uniform int tunnel_cut_count;
global uniform vec4 tunnel_cut_box;

bool tunnel_cut_inside(vec3 p) {
	if (tunnel_cut_count <= 0 || p.x < tunnel_cut_box.x || p.z < tunnel_cut_box.y || p.x > tunnel_cut_box.z
			|| p.z > tunnel_cut_box.w) {
		return false;
	}
	for (int i = 0; i < tunnel_cut_count; i++) {
		vec4 a = texelFetch(tunnel_cut_data, ivec2(3 * i, 0), 0);
		vec4 b = texelFetch(tunnel_cut_data, ivec2(3 * i + 1, 0), 0);
		vec4 c = texelFetch(tunnel_cut_data, ivec2(3 * i + 2, 0), 0);
		vec2 ab = b.xz - a.xz;
		float l2 = max(dot(ab, ab), 1e-6);
		vec2 ap = p.xz - a.xz;
		float t = dot(ap, ab) / l2;
		if (t < -0.01 || t > 1.01) {
			continue;
		}
		float u = abs(ap.x * ab.y - ap.y * ab.x) * inversesqrt(l2);
		if (u > c.x) {
			continue;
		}
		float tc = clamp(t, 0.0, 1.0);
		float h = p.y - mix(a.y, b.y, tc);
		float k = u / c.x;
		float top = mix(a.w, b.w, tc) + c.y * sqrt(max(0.0, 1.0 - k * k));
		if (h > -c.z && h < top) {
			return true;
		}
	}
	return false;
}

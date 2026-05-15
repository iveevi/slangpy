// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
//
// Progressive SDF path tracer -- dense lit scene.
//
// Primitives:
//   * ground plane
//   * three orbiting Lambertian spheres (one user-tinted)
//   * eight Lambertian pillars in a ring (alternating colours)
//   * central rotating Lambertian box
//   * Lambertian torus around the central box
//   * bobbing perfect-mirror sphere above the centre
//   * three floating, self-rotating Lambertian cubes
//   * five small Lambertian back-row spheres
//   * four animated emissive light spheres (warm / cool / pink / green)
//
// Background is pitch black -- all illumination comes from the
// emissive lights. Russian-roulette is left off; 5 bounces is enough
// for a clean image in <300spp at this geometry.

RWTexture2D<float4> g_output;
RWTexture2D<float4> g_accum;

uniform uint   g_frame;
uniform uint   g_sample_count;
uniform float  g_time;
uniform float3 g_tint;
uniform float4 g_sky;
uniform float  g_exposure;

uniform float3 g_cam_pos;
uniform float3 g_cam_right;
uniform float3 g_cam_up;
uniform float3 g_cam_forward;
uniform float  g_focal;

uniform float4 g_light_intensity;   // per-light intensity (warm, cool, pink, lime)

// ============================================================== RNG (PCG)
uint pcg_hash(uint v)
{
    uint s = v * 747796405u + 2891336453u;
    uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
    return (w >> 22u) ^ w;
}
struct RNG { uint state; };
float rand(inout RNG r)
{
    r.state = pcg_hash(r.state);
    return float(r.state) / 4294967296.0;
}

// ================================================================ SDFs
float sd_sphere(float3 p, float3 c, float r) { return length(p - c) - r; }
float sd_plane_y(float3 p, float y)          { return p.y - y; }

float sd_box(float3 p, float3 c, float3 b)
{
    float3 q = abs(p - c) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}

float sd_torus(float3 p, float R, float r)
{
    float2 q = float2(length(p.xz) - R, p.y);
    return length(q) - r;
}

float3 rotate_y(float3 p, float a)
{
    float ca = cos(a), sa = sin(a);
    return float3(ca * p.x + sa * p.z, p.y, -sa * p.x + ca * p.z);
}

float3 rotate_zx(float3 p, float ay, float ax)
{
    p = rotate_y(p, ay);
    float ca = cos(ax), sa = sin(ax);
    return float3(p.x, ca * p.y + sa * p.z, -sa * p.y + ca * p.z);
}

// ================================================================ scene
// Material codes:
//   0  ground (diffuse, pale)
//   1  orbiter A (user tint)
//   2  orbiter B (NORD11 red)
//   3  orbiter C (NORD14 green)
//   4  central rotating box (pale stone)
//   5  mirror sphere (metal)
//   6  warm light (emissive)
//   7  cool light (emissive)
//   8  pink light (emissive)
//   9  lime light (emissive)
//  10  back-row spheres (NORD8 cyan)
//  11  torus (NORD12 orange)
//  12  pillar even (NORD9 blue)
//  13  pillar odd (NORD7 cyan-green)
//  14  floating cubes (NORD15 magenta)
float scene_sdf(float3 p, out int mat)
{
    float d = sd_plane_y(p, 0.0);
    mat = 0;

    // ---- 3 orbiting spheres ---------------------------------------
    [unroll] for (int i = 0; i < 3; ++i) {
        float a = g_time * 0.55 + float(i) * 2.0944;
        float3 c = float3(1.55 * cos(a), 0.50, 1.55 * sin(a));
        float di = sd_sphere(p, c, 0.36);
        if (di < d) { d = di; mat = i + 1; }
    }

    // ---- central rotating box -------------------------------------
    float3 box_c = float3(0.0, 0.55, 0.0);
    float3 box_local = rotate_y(p - box_c, -g_time * 0.35);
    float d_box = sd_box(box_local, float3(0.0), float3(0.24, 0.55, 0.24));
    if (d_box < d) { d = d_box; mat = 4; }

    // ---- torus around the centre ----------------------------------
    float3 tp = p - float3(0.0, 0.60, 0.0);
    float d_torus = sd_torus(tp, 1.00, 0.08);
    if (d_torus < d) { d = d_torus; mat = 11; }

    // ---- bobbing mirror sphere ------------------------------------
    float bob = 0.24 * sin(g_time * 1.4);
    float d_mirror = sd_sphere(p, float3(0.0, 1.95 + bob, 0.0), 0.34);
    if (d_mirror < d) { d = d_mirror; mat = 5; }

    // ---- four emissive lights at compass corners ------------------
    const float LR = 3.0;
    float l1 = sd_sphere(p, float3( LR * 0.70, 1.50 + 0.30 * sin(g_time * 0.70),  LR * 0.70), 0.20);
    if (l1 < d) { d = l1; mat = 6; }
    float l2 = sd_sphere(p, float3(-LR * 0.70, 1.70 + 0.25 * cos(g_time * 0.90),  LR * 0.70), 0.20);
    if (l2 < d) { d = l2; mat = 7; }
    float l3 = sd_sphere(p, float3(-LR * 0.70, 1.40 + 0.35 * sin(g_time * 0.60 + 1.5), -LR * 0.70), 0.20);
    if (l3 < d) { d = l3; mat = 8; }
    float l4 = sd_sphere(p, float3( LR * 0.70, 1.60 + 0.30 * cos(g_time * 0.80 + 2.1), -LR * 0.70), 0.20);
    if (l4 < d) { d = l4; mat = 9; }

    // ---- 8 pillars in a ring --------------------------------------
    const float PR = 2.30;
    [unroll] for (int k = 0; k < 8; ++k) {
        float ang = float(k) * 0.78539816;   // pi/4
        float3 pc = float3(PR * cos(ang), 0.0, PR * sin(ang));
        float h = 0.55 + 0.20 * sin(float(k) * 1.7 + g_time * 0.25);
        float dp = sd_box(p, pc + float3(0, h, 0), float3(0.10, h, 0.10));
        int pmat = (k % 2 == 0) ? 12 : 13;
        if (dp < d) { d = dp; mat = pmat; }
    }

    // ---- 5 back-row small spheres ---------------------------------
    [unroll] for (int j = 0; j < 5; ++j) {
        float fx = -2.0 + float(j) * 1.0;
        float ds = sd_sphere(p, float3(fx, 0.18, -3.0), 0.18);
        if (ds < d) { d = ds; mat = 10; }
    }

    // ---- 3 floating rotating cubes --------------------------------
    [unroll] for (int c = 0; c < 3; ++c) {
        float ca = g_time * 0.40 + float(c) * 2.0944 + 0.5;
        float radius = 1.05;
        float3 cc = float3(
            radius * cos(ca),
            1.40 + 0.45 * sin(g_time * 0.50 + float(c)),
            radius * sin(ca)
        );
        float3 cube_local = rotate_zx(p - cc, g_time * 0.60 + float(c),
                                              g_time * 0.45 + float(c) * 1.7);
        float dc = sd_box(cube_local, float3(0.0), float3(0.13));
        if (dc < d) { d = dc; mat = 14; }
    }

    return d;
}

float3 scene_normal(float3 p)
{
    const float h = 0.001;
    int m;
    return normalize(float3(
        scene_sdf(p + float3(h, 0, 0), m) - scene_sdf(p - float3(h, 0, 0), m),
        scene_sdf(p + float3(0, h, 0), m) - scene_sdf(p - float3(0, h, 0), m),
        scene_sdf(p + float3(0, 0, h), m) - scene_sdf(p - float3(0, 0, h), m)
    ));
}

bool sphere_trace(float3 ro, float3 rd, out float t, out int mat)
{
    t = 0.0; mat = 0;
    [loop] for (int i = 0; i < 96; ++i) {
        float3 p = ro + rd * t;
        float d = scene_sdf(p, mat);
        if (d < 0.002) return true;
        t += d;
        if (t > 60.0) return false;
    }
    return false;
}

// =========================================================== materials
static const float3 NORD7  = float3(0.561, 0.737, 0.733);  // cyan-green
static const float3 NORD8  = float3(0.533, 0.753, 0.816);  // frost cyan
static const float3 NORD9  = float3(0.506, 0.631, 0.757);  // mid blue
static const float3 NORD11 = float3(0.749, 0.380, 0.416);  // red
static const float3 NORD12 = float3(0.816, 0.529, 0.439);  // orange
static const float3 NORD14 = float3(0.639, 0.745, 0.549);  // green
static const float3 NORD15 = float3(0.706, 0.557, 0.678);  // magenta

bool is_metal(int mat) { return mat == 5; }
bool is_light(int mat) { return mat >= 6 && mat <= 9; }

float3 albedo(int mat, float3 tint)
{
    if (mat == 1)  return tint;
    if (mat == 2)  return NORD11;
    if (mat == 3)  return NORD14;
    if (mat == 4)  return float3(0.80, 0.82, 0.86);
    if (mat == 5)  return float3(0.97, 0.97, 0.98);
    if (mat == 10) return NORD8;
    if (mat == 11) return NORD12;
    if (mat == 12) return NORD9;
    if (mat == 13) return NORD7;
    if (mat == 14) return NORD15;
    return float3(0.85, 0.86, 0.88);  // ground
}

float3 emission(int mat)
{
    if (mat == 6) return float3(1.00, 0.55, 0.22) * 24.0 * g_light_intensity.x; // warm
    if (mat == 7) return float3(0.35, 0.78, 1.00) * 18.0 * g_light_intensity.y; // cool
    if (mat == 8) return float3(1.00, 0.40, 0.70) * 18.0 * g_light_intensity.z; // pink
    if (mat == 9) return float3(0.55, 1.00, 0.40) * 16.0 * g_light_intensity.w; // lime
    return float3(0.0);
}

// ============================================================ NEE light data
struct LightDesc {
    float3 center;
    float  radius;
    float3 emission;
};
static const int LIGHT_COUNT = 4;

LightDesc get_light(int idx)
{
    LightDesc L;
    const float LR = 3.0;
    L.radius = 0.20;
    if (idx == 0) {
        L.center = float3( LR * 0.70, 1.50 + 0.30 * sin(g_time * 0.70),  LR * 0.70);
        L.emission = float3(1.00, 0.55, 0.22) * 24.0 * g_light_intensity.x;
    } else if (idx == 1) {
        L.center = float3(-LR * 0.70, 1.70 + 0.25 * cos(g_time * 0.90),  LR * 0.70);
        L.emission = float3(0.35, 0.78, 1.00) * 18.0 * g_light_intensity.y;
    } else if (idx == 2) {
        L.center = float3(-LR * 0.70, 1.40 + 0.35 * sin(g_time * 0.60 + 1.5), -LR * 0.70);
        L.emission = float3(1.00, 0.40, 0.70) * 18.0 * g_light_intensity.z;
    } else {
        L.center = float3( LR * 0.70, 1.60 + 0.30 * cos(g_time * 0.80 + 2.1), -LR * 0.70);
        L.emission = float3(0.55, 1.00, 0.40) * 16.0 * g_light_intensity.w;
    }
    return L;
}

// Sample one light uniformly + a direction within its subtended cone.
// Trace a shadow ray. If unoccluded (hit the chosen light), return the
// Lambertian direct-lighting contribution. Otherwise zero.
float3 sample_direct_lighting(float3 p, float3 n, float3 alb, inout RNG rng)
{
    int idx = min(LIGHT_COUNT - 1, int(rand(rng) * float(LIGHT_COUNT)));
    LightDesc L = get_light(idx);

    float3 to_centre = L.center - p;
    float dist2 = dot(to_centre, to_centre);
    float dist  = sqrt(dist2);
    if (dist <= L.radius * 1.001) return float3(0.0);
    float3 lc_dir = to_centre / dist;

    // Cone subtended by the light sphere from p.
    float sin_th_max = clamp(L.radius / dist, 0.0, 1.0);
    float cos_th_max = sqrt(max(0.0, 1.0 - sin_th_max * sin_th_max));

    // Uniform direction within the cone.
    float u1 = rand(rng);
    float u2 = rand(rng);
    float cos_th = lerp(cos_th_max, 1.0, u1);
    float sin_th = sqrt(max(0.0, 1.0 - cos_th * cos_th));
    float phi = 6.28318530718 * u2;

    float3 a = abs(lc_dir.x) > 0.5 ? float3(0, 1, 0) : float3(1, 0, 0);
    float3 t = normalize(cross(lc_dir, a));
    float3 b = cross(lc_dir, t);
    float3 wi = normalize(cos(phi) * sin_th * t + sin(phi) * sin_th * b + cos_th * lc_dir);

    float cos_n = dot(n, wi);
    if (cos_n <= 0.0) return float3(0.0);

    // Shadow ray -- the chosen light must be the first hit.
    float ts; int ms;
    bool hit = sphere_trace(p + n * 0.003, wi, ts, ms);
    if (!hit || !is_light(ms)) return float3(0.0);

    float omega = 6.28318530718 * (1.0 - cos_th_max);
    float pdf   = 1.0 / (float(LIGHT_COUNT) * omega);
    float3 brdf = alb / 3.14159265359;
    return brdf * cos_n * L.emission / pdf;
}

// =============================================================== sky
// Pitch black: lights are the entire energy source.
float3 sky_dome(float3 dir, float3 zenith)
{
    return zenith;     // host sets it to (0,0,0); slider can re-enable a tint
}

// ========================================================== path tracer
float3 sample_hemisphere_cos(float3 n, inout RNG rng)
{
    float u1 = rand(rng);
    float u2 = rand(rng);
    float r = sqrt(u1);
    float phi = 6.28318530718 * u2;
    float3 a = abs(n.x) > 0.5 ? float3(0, 1, 0) : float3(1, 0, 0);
    float3 b = normalize(cross(n, a));
    float3 t = cross(b, n);
    return r * cos(phi) * t + r * sin(phi) * b + sqrt(max(0.0, 1.0 - u1)) * n;
}

float3 pathtrace(float3 ro, float3 rd, float3 tint, float3 zenith, inout RNG rng)
{
    float3 L          = float3(0.0);
    float3 throughput = float3(1.0);
    bool   last_spec  = true;       // primary ray: treat as specular
    [loop] for (int bounce = 0; bounce < 3; ++bounce) {
        float t; int mat;
        if (!sphere_trace(ro, rd, t, mat)) {
            L += throughput * sky_dome(rd, zenith);
            break;
        }
        float3 p = ro + rd * t;
        float3 n = scene_normal(p);

        if (is_light(mat)) {
            // Only count emission on primary/specular paths; for
            // diffuse paths NEE already estimated this light's
            // contribution on the previous bounce.
            if (last_spec) L += throughput * emission(mat);
            break;
        }

        float3 alb = albedo(mat, tint);

        // Next-event estimation for diffuse surfaces -- one shadow ray
        // to a random light's subtended cone.
        if (!is_metal(mat)) {
            L += throughput * sample_direct_lighting(p, n, alb, rng);
        }

        ro = p + n * 0.003;
        throughput *= alb;

        if (is_metal(mat)) {
            rd = reflect(rd, n);
            last_spec = true;
        } else {
            rd = sample_hemisphere_cos(n, rng);
            last_spec = false;
        }
    }
    return L;
}

[shader("compute")]
[numthreads(16, 16, 1)]
void compute_main(uint3 tid : SV_DispatchThreadID)
{
    uint2 dims;
    g_output.GetDimensions(dims.x, dims.y);
    if (any(tid.xy >= dims)) return;

    RNG rng;
    rng.state = pcg_hash(tid.x * 1973u + tid.y * 9277u + g_frame * 26699u + 1u);

    float2 jitter = float2(rand(rng), rand(rng));
    float2 uv = (float2(tid.xy) + jitter) / float2(dims);
    uv = uv * 2.0 - 1.0;
    uv.y = -uv.y;
    uv.x *= float(dims.x) / float(dims.y);

    float3 ray_dir = normalize(uv.x * g_cam_right
                             + uv.y * g_cam_up
                             + g_focal * g_cam_forward);

    float3 radiance = pathtrace(g_cam_pos, ray_dir, g_tint, g_sky.rgb, rng);

    float n = max(1.0, float(g_sample_count));
    float3 prev = g_accum[tid.xy].rgb;
    float3 mean = (g_sample_count <= 1u) ? radiance
                                         : (prev * (n - 1.0) + radiance) / n;
    g_accum[tid.xy] = float4(mean, 1.0);

    float3 c = mean * g_exposure;
    c = c / (c + 1.0);
    c = pow(c, 1.0 / 2.2);
    g_output[tid.xy] = float4(c, 1.0);
}

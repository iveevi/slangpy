// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
//
// Progressive path tracer with analytic ray/primitive intersection: a
// bounded Cornell-style box (diffuse walls + boxes, mirror and glass
// spheres) in a gradient sky, with optional homogeneous fog.

RWTexture2D<float4> g_output;
RWTexture2D<float4> g_accum;

uniform uint   g_frame;
uniform uint   g_sample_count;
uniform float  g_time;
uniform float3 g_tint;
uniform float  g_exposure;
uniform int    g_tonemap;   // 0 Reinhard, 1 ACES, 2 Filmic, 3 Clamp
uniform float  g_fog_density; // homogeneous medium extinction (0 = no fog)

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

// =========================================================== transforms
float3 rotate_y(float3 p, float a)
{
    float ca = cos(a), sa = sin(a);
    return float3(ca * p.x + sa * p.z, p.y, -sa * p.x + ca * p.z);
}


static const float T_EPS = 1e-4;

bool hit_sphere(float3 ro, float3 rd, float3 c, float r, out float t, out float3 n)
{
    t = 0.0;
    n = float3(0.0, 0.0, 1.0);
    float3 oc = ro - c;
    float b = dot(oc, rd);
    float k = dot(oc, oc) - r * r;
    float disc = b * b - k;
    if (disc < 0.0)
        return false;
    float s = sqrt(disc);
    float t0 = -b - s;
    float t1 = -b + s;
    float tt = (t0 > T_EPS) ? t0 : ((t1 > T_EPS) ? t1 : -1.0);
    if (tt < 0.0)
        return false;
    t = tt;
    n = normalize((ro + rd * tt) - c);
    return true;
}

bool hit_quad(
    float3 ro,
    float3 rd,
    float3 c,
    float3 nrm,
    float3 u,
    float3 v,
    float hu,
    float hv,
    out float t,
    out float3 n
)
{
    t = 0.0;
    n = nrm;
    float denom = dot(rd, nrm);
    if (abs(denom) < 1e-6)
        return false;
    float tt = dot(c - ro, nrm) / denom;
    if (tt < T_EPS)
        return false;
    float3 d = (ro + rd * tt) - c;
    if (abs(dot(d, u)) > hu || abs(dot(d, v)) > hv)
        return false;
    t = tt;
    return true;
}

// Slab test for an axis-aligned box [-b, b] centred at the origin.
bool slab(float3 ro, float3 rd, float3 b, out float t, out float3 n)
{
    t = 0.0;
    n = float3(0.0, 0.0, 1.0);
    float3 d = rd;
    d.x = (abs(d.x) < 1e-8) ? 1e-8 : d.x;
    d.y = (abs(d.y) < 1e-8) ? 1e-8 : d.y;
    d.z = (abs(d.z) < 1e-8) ? 1e-8 : d.z;
    float3 inv = 1.0 / d;
    float3 t0 = (-b - ro) * inv;
    float3 t1 = (b - ro) * inv;
    float3 tsm = min(t0, t1);
    float3 tbg = max(t0, t1);
    float tN = max(max(tsm.x, tsm.y), tsm.z);
    float tF = min(min(tbg.x, tbg.y), tbg.z);
    if (tN > tF || tF < T_EPS)
        return false;
    bool entry = tN > T_EPS;
    t = entry ? tN : tF;
    if (entry)
        n = -sign(d) * float3(float(tN == tsm.x), float(tN == tsm.y), float(tN == tsm.z));
    else
        n = sign(d) * float3(float(tF == tbg.x), float(tF == tbg.y), float(tF == tbg.z));
    n = normalize(n);
    return true;
}

// Oriented box: centre `c`, half-extents `b`, rotated `a` radians about Y.
bool hit_obb_y(float3 ro, float3 rd, float3 c, float3 b, float a, out float t, out float3 n)
{
    float3 nL;
    bool h = slab(rotate_y(ro - c, -a), rotate_y(rd, -a), b, t, nL);
    n = rotate_y(nL, a);
    return h;
}


static const float BOX_W = 2.2;   // side walls at x = +/- BOX_W
static const float BOX_H = 3.6;   // ceiling height
static const float BOX_BK = -2.4; // back wall z
static const float BOX_FZ = 1.7;  // open front edge z (no wall here)
static const float BOX_CZ = 0.5 * (BOX_BK + BOX_FZ); // depth centre
static const float BOX_HZ = 0.5 * (BOX_FZ - BOX_BK); // depth half-extent

struct Hit {
    float  t;
    float3 n;   // outward geometric normal
    int    mat;
};

void consider(inout Hit best, bool did, float t, float3 n, int mat)
{
    if (did && t < best.t) {
        best.t = t;
        best.n = n;
        best.mat = mat;
    }
}

static const int LIGHT_COUNT = 4;
float3 light_center(int i)
{
    float x = -1.2 + float(i) * 0.8;
    return float3(x, BOX_H - 0.02, -0.5);
}
static const float  LIGHT_HALF = 0.28;          // half-size of each square
static const float3 LIGHT_NRM  = float3(0, -1, 0);
static const float3 LIGHT_U    = float3(1, 0, 0);
static const float3 LIGHT_V    = float3(0, 0, 1);

float3 light_emission(int i)
{
    if (i == 0) return float3(1.00, 0.62, 0.32) * 16.0 * g_light_intensity.x; // warm
    if (i == 1) return float3(0.45, 0.78, 1.00) * 14.0 * g_light_intensity.y; // cool
    if (i == 2) return float3(1.00, 0.45, 0.72) * 14.0 * g_light_intensity.z; // pink
    return float3(0.60, 1.00, 0.45) * 13.0 * g_light_intensity.w;             // lime
}

Hit scene_intersect(float3 ro, float3 rd)
{
    Hit best;
    best.t = 1e30;
    best.n = float3(0.0, 1.0, 0.0);
    best.mat = -1;

    float t;
    float3 n;

    // enclosure: five bounded quads (open toward +z / the camera)
    const float3 AX = float3(1, 0, 0);
    const float3 AY = float3(0, 1, 0);
    const float3 AZ = float3(0, 0, 1);
    // floor
    consider(best, hit_quad(ro, rd, float3(0, 0, BOX_CZ), AY, AX, AZ, BOX_W, BOX_HZ, t, n), t, n, 0);
    // ceiling
    consider(best, hit_quad(ro, rd, float3(0, BOX_H, BOX_CZ), -AY, AX, AZ, BOX_W, BOX_HZ, t, n), t, n, 1);
    // back
    consider(best, hit_quad(ro, rd, float3(0, 0.5 * BOX_H, BOX_BK), AZ, AX, AY, BOX_W, 0.5 * BOX_H, t, n), t, n, 2);
    // left (red)
    consider(best, hit_quad(ro, rd, float3(-BOX_W, 0.5 * BOX_H, BOX_CZ), AX, AZ, AY, BOX_HZ, 0.5 * BOX_H, t, n), t, n, 3);
    // right (green)
    consider(best, hit_quad(ro, rd, float3(BOX_W, 0.5 * BOX_H, BOX_CZ), -AX, AZ, AY, BOX_HZ, 0.5 * BOX_H, t, n), t, n, 4);

    // two diffuse boxes (classic Cornell pair)
    consider(best, hit_obb_y(ro, rd, float3(-0.85, 1.05, -1.0), float3(0.6, 1.05, 0.6), 0.27, t, n), t, n, 7);
    consider(best, hit_obb_y(ro, rd, float3(0.9, 0.6, -0.1), float3(0.62, 0.6, 0.62), -0.30, t, n), t, n, 8);

    // mirror sphere resting on the short box
    consider(best, hit_sphere(ro, rd, float3(0.9, 1.75, -0.1), 0.55, t, n), t, n, 5);
    // glass sphere, front and centre
    consider(best, hit_sphere(ro, rd, float3(-0.1, 0.72, 0.85), 0.72, t, n), t, n, 6);
    // user-tinted diffuse sphere on top of the tall box
    consider(best, hit_sphere(ro, rd, float3(-0.85, 2.5, -1.0), 0.4, t, n), t, n, 9);
    // small accent diffuse sphere on the floor
    consider(best, hit_sphere(ro, rd, float3(1.5, 0.32, 0.8), 0.32, t, n), t, n, 10);

    // ceiling lights: downward-facing square quads
    [unroll]
    for (int i = 0; i < LIGHT_COUNT; ++i)
        consider(
            best,
            hit_quad(ro, rd, light_center(i), LIGHT_NRM, LIGHT_U, LIGHT_V, LIGHT_HALF, LIGHT_HALF, t, n),
            t,
            n,
            30 + i
        );

    return best;
}

// =========================================================== materials
static const float3 NORD11 = float3(0.749, 0.380, 0.416);  // red
static const float3 NORD13 = float3(0.922, 0.796, 0.545);  // yellow
static const float3 NORD14 = float3(0.639, 0.745, 0.549);  // green

static const float GLASS_IOR = 1.50;

bool is_metal(int mat) { return mat == 5; }
bool is_glass(int mat) { return mat == 6; }
bool is_light(int mat) { return mat >= 30 && mat <= 33; }

float3 albedo(int mat, float3 tint)
{
    if (mat == 3)  return NORD11;                  // left wall (red)
    if (mat == 4)  return NORD14;                  // right wall (green)
    if (mat == 5)  return float3(0.97, 0.97, 0.98); // mirror
    if (mat == 7)  return float3(0.82, 0.83, 0.85); // tall box
    if (mat == 8)  return float3(0.82, 0.83, 0.85); // short box
    if (mat == 9)  return tint;                    // tinted sphere
    if (mat == 10) return NORD13;                  // accent sphere
    return float3(0.73, 0.73, 0.74);               // floor / ceiling / back
}

float3 emission(int mat)
{
    if (is_light(mat))
        return light_emission(mat - 30);
    return float3(0.0);
}

float3 sample_direct_lighting(float3 p, float3 n, float3 alb, inout RNG rng)
{
    int idx = min(LIGHT_COUNT - 1, int(rand(rng) * float(LIGHT_COUNT)));
    float3 center = light_center(idx);
    float3 emit   = light_emission(idx);

    // Uniform point on the square emitter.
    float su = rand(rng) * 2.0 - 1.0;
    float sv = rand(rng) * 2.0 - 1.0;
    float3 lp = center + su * LIGHT_HALF * LIGHT_U + sv * LIGHT_HALF * LIGHT_V;

    float3 to_light = lp - p;
    float dist2 = dot(to_light, to_light);
    float dist  = sqrt(dist2);
    if (dist < 1e-4) return float3(0.0);
    float3 wi = to_light / dist;

    float cos_n = dot(n, wi);                 // cosine at the shading point
    float cos_l = dot(LIGHT_NRM, -wi);        // cosine at the (downward) light
    if (cos_n <= 0.0 || cos_l <= 0.0) return float3(0.0);

    // Shadow ray -- the chosen light must be the first thing we reach.
    Hit sh = scene_intersect(p + n * 0.003, wi);
    if (sh.mat < 0 || !is_light(sh.mat) || sh.t < dist - 0.02) return float3(0.0);

    float area = (2.0 * LIGHT_HALF) * (2.0 * LIGHT_HALF);
    // pdf_A = 1 / (LIGHT_COUNT * area);  1/pdf_A = LIGHT_COUNT * area.
    float trans = exp(-g_fog_density * dist);  // fog attenuation along shadow ray
    float geom = (cos_n * cos_l) / dist2;
    float3 brdf = alb / 3.14159265359;
    return brdf * emit * geom * trans * (area * float(LIGHT_COUNT));
}

float3 sky_dome(float3 dir)
{
    float up = clamp(dir.y, -1.0, 1.0);
    const float3 zenith  = float3(0.09, 0.24, 0.60);
    const float3 horizon = float3(0.42, 0.62, 0.86);
    const float3 ground  = float3(0.20, 0.19, 0.18);
    return (up >= 0.0) ? lerp(horizon, zenith, pow(up, 0.42))
                       : lerp(horizon, ground, pow(-up, 0.6));
}

bool fog_interval(float3 ro, float3 rd, float t_hit, out float t0, out float t1)
{
    const float3 bmin = float3(-BOX_W, 0.0, BOX_BK);
    const float3 bmax = float3(BOX_W, BOX_H, BOX_FZ);
    float3 inv = 1.0 / rd;
    float3 ta = (bmin - ro) * inv;
    float3 tb = (bmax - ro) * inv;
    float3 tsmall = min(ta, tb);
    float3 tbig = max(ta, tb);
    float tn = max(max(tsmall.x, tsmall.y), tsmall.z);
    float tf = min(min(tbig.x, tbig.y), tbig.z);
    t0 = max(tn, 0.0);
    t1 = min(tf, t_hit);
    return tf > tn && t1 > t0;
}

// Uniform direction on the sphere (isotropic phase function sampling).
float3 sample_sphere_uniform(inout RNG rng)
{
    float z   = 1.0 - 2.0 * rand(rng);
    float r   = sqrt(max(0.0, 1.0 - z * z));
    float phi = 6.28318530718 * rand(rng);
    return float3(r * cos(phi), r * sin(phi), z);
}

float3 sample_fog_lighting(float3 p, inout RNG rng)
{
    int idx = min(LIGHT_COUNT - 1, int(rand(rng) * float(LIGHT_COUNT)));
    float3 center = light_center(idx);
    float3 emit   = light_emission(idx);

    float su = rand(rng) * 2.0 - 1.0;
    float sv = rand(rng) * 2.0 - 1.0;
    float3 lp = center + su * LIGHT_HALF * LIGHT_U + sv * LIGHT_HALF * LIGHT_V;

    float3 to_light = lp - p;
    float dist2 = dot(to_light, to_light);
    float dist  = sqrt(dist2);
    if (dist < 1e-4) return float3(0.0);
    float3 wi = to_light / dist;

    float cos_l = dot(LIGHT_NRM, -wi);
    if (cos_l <= 0.0) return float3(0.0);

    Hit sh = scene_intersect(p, wi);
    if (sh.mat < 0 || !is_light(sh.mat) || sh.t < dist - 0.02) return float3(0.0);

    float trans = exp(-g_fog_density * dist);
    float area  = (2.0 * LIGHT_HALF) * (2.0 * LIGHT_HALF);
    float phase = 0.25 / 3.14159265359;   // isotropic: 1 / (4 pi)
    float geom  = cos_l / dist2;          // no cosine at the medium point
    return emit * phase * geom * trans * (area * float(LIGHT_COUNT));
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

// Schlick Fresnel reflectance for a dielectric.
float fresnel_schlick(float cos_in, float ior)
{
    float r0 = (1.0 - ior) / (1.0 + ior);
    r0 = r0 * r0;
    float m = clamp(1.0 - cos_in, 0.0, 1.0);
    return r0 + (1.0 - r0) * m * m * m * m * m;
}

float3 pathtrace(float3 ro, float3 rd, float3 tint, inout RNG rng)
{
    float3 L          = float3(0.0);
    float3 throughput = float3(1.0);
    bool   last_spec  = true;       // primary ray: treat as specular
    [loop] for (int bounce = 0; bounce < 8; ++bounce) {
        Hit hit = scene_intersect(ro, rd);
        float t_hit = (hit.mat < 0) ? 1e30 : hit.t;

        if (g_fog_density > 0.0) {
            float ft0, ft1;
            if (fog_interval(ro, rd, t_hit, ft0, ft1)) {
                float t_s = ft0 - log(1.0 - rand(rng)) / g_fog_density;
                if (t_s < ft1) {
                    float3 pm = ro + rd * t_s;
                    L += throughput * sample_fog_lighting(pm, rng);
                    ro = pm;
                    rd = sample_sphere_uniform(rng);
                    last_spec = false;
                    continue;
                }
            }
        }

        if (hit.mat < 0) {
            L += throughput * sky_dome(rd);
            break;
        }
        float3 p = ro + rd * hit.t;
        float3 ng = hit.n;

        if (is_light(hit.mat)) {
            if (last_spec) L += throughput * emission(hit.mat);
            break;
        }

        if (is_glass(hit.mat)) {
            // Dielectric: reflect or refract, chosen by Fresnel.
            bool entering = dot(rd, ng) < 0.0;
            float3 nl = entering ? ng : -ng;
            float eta = entering ? (1.0 / GLASS_IOR) : GLASS_IOR;
            float cos_in = abs(dot(rd, ng));
            float fres = fresnel_schlick(cos_in, GLASS_IOR);
            float3 refr = refract(rd, nl, eta);
            bool tir = dot(refr, refr) < 1e-8;
            if (tir || rand(rng) < fres)
                rd = reflect(rd, nl);
            else
                rd = refr;
            ro = p + rd * 0.001;
            last_spec = true;
            continue;
        }

        // Shading normal faces the incoming ray (handles back faces).
        float3 n = (dot(ng, rd) < 0.0) ? ng : -ng;
        float3 alb = albedo(hit.mat, tint);

        if (is_metal(hit.mat)) {
            throughput *= alb;
            ro = p + n * 0.003;
            rd = reflect(rd, n);
            last_spec = true;
        } else {
            // Diffuse: next-event estimation + cosine-weighted bounce.
            L += throughput * sample_direct_lighting(p, n, alb, rng);
            throughput *= alb;
            ro = p + n * 0.003;
            rd = sample_hemisphere_cos(n, rng);
            last_spec = false;
        }
    }
    return L;
}

float3 tm_reinhard(float3 c)
{
    return c / (c + 1.0);
}

float3 tm_aces(float3 x)
{
    const float a = 2.51, b = 0.03, c = 2.43, d = 0.59, e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

float3 u2_curve(float3 x)
{
    const float A = 0.15, B = 0.50, C = 0.10, D = 0.20, E = 0.02, F = 0.30;
    return ((x * (A * x + C * B) + D * E) / (x * (A * x + B) + D * F)) - E / F;
}

float3 tm_filmic(float3 c)
{
    const float W = 11.2;
    float3 curr = u2_curve(c * 2.0);
    float3 white = u2_curve(float3(W, W, W));
    return clamp(curr / white, 0.0, 1.0);
}

float3 tonemap(float3 c, int mode)
{
    if (mode == 1)
        return tm_aces(c);
    if (mode == 2)
        return tm_filmic(c);
    if (mode == 3)
        return clamp(c, 0.0, 1.0);
    return tm_reinhard(c);
}

// Jittered primary rays per frame for pixel antialiasing.
static const int AA_SAMPLES = 4;

[shader("compute")]
[numthreads(16, 16, 1)]
void compute_main(uint3 tid : SV_DispatchThreadID)
{
    uint2 dims;
    g_output.GetDimensions(dims.x, dims.y);
    if (any(tid.xy >= dims)) return;

    RNG rng;
    rng.state = pcg_hash(tid.x * 1973u + tid.y * 9277u + g_frame * 26699u + 1u);

    float aspect = float(dims.x) / float(dims.y);

    float3 radiance = float3(0.0);
    [unroll]
    for (int s = 0; s < AA_SAMPLES; ++s)
    {
        float2 jitter = float2(rand(rng), rand(rng));
        float2 uv = (float2(tid.xy) + jitter) / float2(dims);
        uv = uv * 2.0 - 1.0;
        uv.y = -uv.y;
        uv.x *= aspect;
        float3 ray_dir = normalize(uv.x * g_cam_right + uv.y * g_cam_up + g_focal * g_cam_forward);
        radiance += pathtrace(g_cam_pos, ray_dir, g_tint, rng);
    }
    radiance *= (1.0 / float(AA_SAMPLES));

    float n = max(1.0, float(g_sample_count));
    float3 prev = g_accum[tid.xy].rgb;
    float3 mean = (g_sample_count <= 1u) ? radiance
                                         : (prev * (n - 1.0) + radiance) / n;
    g_accum[tid.xy] = float4(mean, 1.0);

    float3 c = mean * g_exposure;
    c = tonemap(c, g_tonemap);
    c = pow(c, 1.0 / 2.2);
    c += (rand(rng) - rand(rng)) / 255.0;
    g_output[tid.xy] = float4(c, 1.0);
}

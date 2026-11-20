// KRUNKED // VINYL VAULT v6.0 — WebGL2 / GLSL Direct-Drive Vinyl Wax Physics Renderer
// Supports verified pressing.jpg photo compositing + 9 procedural wax_spec shaders,
// anisotropic microgroove diffraction, Beer-Lambert "Hold Up to the Light" optical transmission,
// 395nm UV underglow, laser-etched D-side metallic relief, quartz strobe rim, and Blind Mode.

import {
  getCenterLabelArtUrl,
  getPressingPhotoUrls,
  safeCssColor,
  safeImageSrc,
} from './utils.js';

function hexToVec3(hex, fallback = [0.1, 0.1, 0.12]) {
  const clean = safeCssColor(hex, '').replace('#', '');
  if (clean.length === 3) {
    return [
      parseInt(clean[0] + clean[0], 16) / 255,
      parseInt(clean[1] + clean[1], 16) / 255,
      parseInt(clean[2] + clean[2], 16) / 255,
    ];
  }
  if (clean.length >= 6) {
    return [
      parseInt(clean.slice(0, 2), 16) / 255,
      parseInt(clean.slice(2, 4), 16) / 255,
      parseInt(clean.slice(4, 6), 16) / 255,
    ];
  }
  return fallback;
}

function patternStringToId(pattern) {
  switch (String(pattern || 'black')) {
    case 'splatter': return 1;
    case 'color_in_color': return 2;
    case 'galaxy': return 3;
    case 'marble': return 4;
    case 'split': return 5;
    case 'translucent': return 6;
    case 'solid_color': return 7;
    default: return 0; // black
  }
}

const VERT_SRC_GL2 = `#version 300 es
precision highp float;
in vec2 a_pos;
out vec2 v_uv;
void main() {
  v_uv = a_pos;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}`;

const VERT_SRC_GL1 = `
precision highp float;
attribute vec2 a_pos;
varying vec2 v_uv;
void main() {
  v_uv = a_pos;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}`;

const FRAG_BODY = `
uniform sampler2D u_pressingTex;
uniform sampler2D u_labelTex;
uniform vec2 u_pointer;
uniform float u_angle;
uniform float u_strobeAngle;
uniform float u_hasPhoto;
uniform float u_hasLabel;
uniform float u_photoRadius;
uniform float u_pattern;
uniform vec3 u_primaryColor;
uniform vec3 u_secondaryColor;
uniform vec3 u_accentColor;
uniform float u_translucent;
uniform float u_etched;
uniform float u_seed;
uniform float u_backlight;
uniform float u_uvMode;
uniform float u_blindMode;
uniform float u_winnerGlow;
uniform float u_audioEnergy;

const float PI = 3.14159265359;

float hash21(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

float noise2(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float a = hash21(i);
  float b = hash21(i + vec2(1.0, 0.0));
  float c = hash21(i + vec2(0.0, 1.0));
  float d = hash21(i + vec2(1.0, 1.0));
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
  float v = 0.0;
  float amp = 0.5;
  for (int i = 0; i < 4; i++) {
    v += amp * noise2(p);
    p = p * 2.03 + vec2(17.1, 31.7);
    amp *= 0.5;
  }
  return v;
}

vec2 rotate2(vec2 p, float a) {
  float c = cos(a);
  float s = sin(a);
  return vec2(c * p.x - s * p.y, s * p.x + c * p.y);
}

float angularDiff(float a, float b) {
  float d = mod(a - b + PI, 2.0 * PI) - PI;
  return abs(d);
}

void main() {
  vec2 p = v_uv;
  float r = length(p);
  if (r > 1.0) {
    OUT_FRAG = vec4(0.0, 0.0, 0.0, 0.0);
    return;
  }

  float theta = atan(p.y, p.x);
  vec2 pRot = rotate2(p, -u_angle);
  float rRotTheta = atan(pRot.y, pRot.x);
  float seedN = fract(u_seed * 0.000137) * 50.0;

  // 1. Machined Platter Bevel & Quartz Strobe Dot Ring (r in [0.962..1.0])
  if (r > 0.962) {
    float rimT = (r - 0.962) / 0.038;
    vec3 metal = mix(vec3(0.05, 0.06, 0.09), vec3(0.14, 0.17, 0.23), smoothstep(0.0, 0.55, rimT) * (1.0 - smoothstep(0.65, 1.0, rimT)));
    float dotAngle = theta - u_strobeAngle;
    float dotWave = cos(dotAngle * 108.0);
    float dotRing1 = smoothstep(0.76, 0.94, dotWave) * smoothstep(0.20, 0.34, rimT) * (1.0 - smoothstep(0.46, 0.60, rimT));
    float dotRing2 = smoothstep(0.80, 0.96, cos(dotAngle * 72.0)) * smoothstep(0.64, 0.74, rimT) * (1.0 - smoothstep(0.84, 0.94, rimT));
    vec3 strobeCol = mix(vec3(0.13, 0.83, 0.93), vec3(0.85, 0.28, 0.93), u_uvMode * 0.55);
    if (u_winnerGlow > 0.05) {
      strobeCol = mix(strobeCol, vec3(0.98, 0.75, 0.14), u_winnerGlow);
    }
    strobeCol *= (1.0 + u_audioEnergy * 0.35);
    vec3 col = metal + strobeCol * (dotRing1 * 0.85 + dotRing2 * 0.45);
    float edgeAlpha = 1.0 - smoothstep(0.988, 1.0, r);
    OUT_FRAG = vec4(col, edgeAlpha);
    return;
  }

  // 2. Center Spindle Hole (r < 0.036)
  if (r < 0.036) {
    float pin = 1.0 - smoothstep(0.016, 0.030, r);
    vec3 holeCol = mix(vec3(0.02, 0.025, 0.04), vec3(0.62, 0.68, 0.76), pin);
    holeCol += vec3(0.15, 0.75, 0.92) * u_backlight * 0.35 * (1.0 - pin);
    OUT_FRAG = vec4(holeCol, 1.0);
    return;
  }

  vec3 waxCol = u_primaryColor;
  float opticalDensity = mix(0.94, 0.32, u_translucent);
  bool inLabelZone = (r <= 0.334);

  // 3. Verified Pressing Photo OR Deterministic Procedural Wax Shader
  if (u_hasPhoto > 0.5) {
    float scaleR = clamp(u_photoRadius, 0.76, 0.98);
    vec2 texUv = vec2(0.5) + (pRot * scaleR) * 0.5;
    vec3 photo = TEX2D(u_pressingTex, clamp(texUv, 0.01, 0.99)).rgb;
    waxCol = photo;
    float lum = dot(photo, vec3(0.299, 0.587, 0.114));
    float sat = max(max(photo.r, photo.g), photo.b) - min(min(photo.r, photo.g), photo.b);
    if (u_translucent > 0.5) {
      opticalDensity = mix(0.65, 0.24, smoothstep(0.18, 0.75, lum + sat * 0.35));
    } else {
      opticalDensity = 0.92;
    }
    if (r < 0.334 && u_blindMode > 0.5) {
      inLabelZone = true;
    } else {
      inLabelZone = false; // Photo already contains real center label when not in blind mode
    }
  } else {
    int pat = int(u_pattern + 0.5);
    if (pat == 0) {
      // 180g Audiophile Black
      waxCol = vec3(0.06, 0.062, 0.075);
      opticalDensity = 0.98;
    } else if (pat == 1) {
      // Splatter: base wax + 36 seeded radial splatter rays + peripheral droplets
      float splatMask = 0.0;
      float accMask = 0.0;
      for (int i = 0; i < 36; i++) {
        float fi = float(i);
        float a0 = fract(sin(fi * 12.9898 + seedN) * 43758.5453) * 2.0 * PI - PI;
        float rStart = 0.18 + fract(sin(fi * 78.233 + seedN) * 19341.12) * 0.25;
        float rEnd = 0.58 + fract(sin(fi * 39.11 + seedN) * 9137.45) * 0.38;
        float twist = a0 + 0.18 * sin(r * 7.5 + fi) + 0.10 * (r - rStart);
        float wRay = (0.014 + 0.022 * fract(fi * 0.37)) / max(0.32, r);
        float dA = angularDiff(rRotTheta, twist);
        float ray = (1.0 - smoothstep(wRay * 0.45, wRay, dA)) * smoothstep(rStart - 0.04, rStart + 0.04, r) * (1.0 - smoothstep(rEnd - 0.05, rEnd, r));
        if (mod(fi, 3.0) < 0.5) {
          accMask = max(accMask, ray);
        } else {
          splatMask = max(splatMask, ray);
        }
      }
      float micro = smoothstep(0.66, 0.82, fbm(pRot * 14.0 + seedN));
      splatMask = max(splatMask, micro * 0.55);
      waxCol = mix(u_primaryColor, u_secondaryColor, clamp(splatMask * 0.92, 0.0, 1.0));
      waxCol = mix(waxCol, u_accentColor, clamp(accMask * 0.88, 0.0, 1.0));
      float blob = max(splatMask, accMask);
      opticalDensity = mix(mix(0.88, 0.25, u_translucent), 0.78, blob);
    } else if (pat == 2) {
      // Color-in-Color (organic warped inner puddle + wispy radial bleed)
      float warp = fbm(pRot * 4.5 + seedN) * 0.14;
      float innerEdge = 0.62 + warp - 0.06 * sin(rRotTheta * 5.0 + seedN);
      float inMask = 1.0 - smoothstep(innerEdge - 0.06, innerEdge + 0.04, r);
      float wisp = smoothstep(0.55, 0.78, fbm(vec2(rRotTheta * 3.0, r * 4.5) + seedN)) * (1.0 - smoothstep(0.55, 0.92, r));
      waxCol = mix(u_primaryColor, u_secondaryColor, clamp(inMask * 0.9 + wisp * 0.5, 0.0, 1.0));
      waxCol = mix(waxCol, u_accentColor, wisp * 0.28);
      opticalDensity = mix(mix(0.85, 0.24, u_translucent), 0.62, inMask);
    } else if (pat == 3) {
      // Galaxy Nebula
      vec2 np = pRot * 3.2 + vec2(seedN, seedN * 0.7);
      float q = fbm(np + fbm(np + vec2(2.3, 4.1)));
      float neb = fbm(np * 1.4 + q * 2.2);
      float stars = smoothstep(0.76, 0.88, noise2(pRot * 28.0 + seedN));
      waxCol = mix(u_primaryColor, u_secondaryColor, smoothstep(0.28, 0.72, neb));
      waxCol = mix(waxCol, u_accentColor, smoothstep(0.55, 0.85, q) * 0.65);
      waxCol += vec3(0.85, 0.92, 1.0) * stars * 0.22;
      opticalDensity = mix(0.86, 0.34, u_translucent) + 0.22 * (1.0 - neb);
    } else if (pat == 4) {
      // Marble Swirl
      float curl = fbm(pRot * 3.4 + seedN) * 4.2;
      float band = 0.5 + 0.5 * sin(rRotTheta * 2.0 + r * 7.0 + curl);
      float vein = smoothstep(0.65, 0.92, abs(sin(r * 10.0 + curl * 1.3)));
      waxCol = mix(u_primaryColor, u_secondaryColor, band);
      waxCol = mix(waxCol, u_accentColor, vein * 0.45);
      opticalDensity = mix(0.90, 0.38, u_translucent);
    } else if (pat == 5) {
      // Split Wax with organic press seam
      float seam = sin(seedN) * pRot.x + cos(seedN) * pRot.y + (fbm(pRot * 6.0 + seedN) - 0.5) * 0.11;
      float side = smoothstep(-0.025, 0.025, seam);
      waxCol = mix(u_primaryColor, u_secondaryColor, side);
      opticalDensity = mix(0.92, 0.32, u_translucent);
    } else if (pat == 6) {
      // Translucent Clear / Coke-Bottle / Milky
      float depthShade = 0.88 + 0.14 * fbm(pRot * 3.0 + seedN);
      waxCol = u_primaryColor * depthShade;
      opticalDensity = 0.22 + 0.12 * smoothstep(0.82, 0.96, r);
    } else {
      // Solid Color
      waxCol = u_primaryColor;
      opticalDensity = 0.92;
    }
  }

  // 4. Center 4" Paper Label Zone (r <= 0.334)
  if (inLabelZone) {
    if (u_blindMode > 0.5) {
      float ring = smoothstep(0.320, 0.332, r);
      float scan = 0.5 + 0.5 * sin(r * 90.0);
      waxCol = mix(vec3(0.06, 0.08, 0.13), vec3(0.11, 0.16, 0.24), scan * 0.4);
      waxCol = mix(waxCol, vec3(0.13, 0.83, 0.93), ring * 0.75);
      opticalDensity = 0.99;
    } else {
      vec2 lblUv = vec2(0.5) + (pRot / 0.334) * 0.5;
      if (u_hasLabel > 0.5) {
        vec3 art = TEX2D(u_labelTex, clamp(lblUv, 0.02, 0.98)).rgb;
        float grain = (noise2(pRot * 95.0) - 0.5) * 0.04;
        waxCol = art + grain;
      } else {
        waxCol = mix(vec3(0.08, 0.09, 0.14), u_accentColor, 0.22);
      }
      // Subtle 1" stamper ring step & outer paper rim
      float pressRing = smoothstep(0.008, 0.0, abs(r - 0.165)) * 0.18;
      float lblEdge = smoothstep(0.010, 0.0, abs(r - 0.330)) * 0.28;
      waxCol = mix(waxCol, waxCol * 0.65, pressRing + lblEdge);
      opticalDensity = 0.98;
    }
  }

  // 5. Vinyl Microgrooves & Etched D-Side Metallic Relief (r in [0.34..0.955])
  vec3 normal = vec3(0.0, 0.0, 1.0);
  if (r > 0.342 && r < 0.958) {
    float trackLeadIn = smoothstep(0.006, 0.0, abs(r - 0.53)) + smoothstep(0.006, 0.0, abs(r - 0.72)) + smoothstep(0.006, 0.0, abs(r - 0.86));
    if (u_etched > 0.5) {
      // Laser-etched concentric/geometric relief
      float sym = 6.0 + floor(mod(u_seed, 7.0));
      float etchA = sin(rRotTheta * sym + r * 24.0 + seedN) * cos(rRotTheta * (sym * 0.5) - r * 18.0);
      float etchB = sin(r * 140.0 + etchA * 3.0);
      float relief = etchA * 0.55 + etchB * 0.45;
      vec2 radialDir = normalize(p + vec2(1e-5));
      vec2 tangDir = vec2(-radialDir.y, radialDir.x);
      normal = normalize(vec3(radialDir * relief * 0.28 + tangDir * sin(rRotTheta * sym) * 0.22, 1.0));
      waxCol = mix(waxCol, waxCol * 1.18 + vec3(0.08, 0.10, 0.13), smoothstep(0.25, 0.85, abs(relief)) * 0.45);
    } else {
      float grooveFreq = sin(r * 740.0) * 0.55 + sin(r * 1320.0 + seedN) * 0.45;
      float grooveDepth = (1.0 - clamp(trackLeadIn, 0.0, 0.85));
      vec2 radialDir = normalize(p + vec2(1e-5));
      normal = normalize(vec3(radialDir * grooveFreq * 0.16 * grooveDepth, 1.0));
      waxCol *= (0.94 + 0.06 * grooveFreq * grooveDepth);
      waxCol = mix(waxCol, waxCol * 0.72, trackLeadIn * 0.45);
    }
  }

  // 6. Anisotropic Dual-Bow Specular Diffraction (tracks cursor / mobile tilt u_pointer)
  vec3 lightDir = normalize(vec3(u_pointer.x * 1.15, u_pointer.y * 1.15, 0.92));
  vec3 viewDir = vec3(0.0, 0.0, 1.0);
  vec3 halfVec = normalize(lightDir + viewDir);

  float diff = clamp(dot(normal, lightDir), 0.25, 1.0);
  // Tangential groove alignment creates signature dual-bow vinyl sheen
  vec2 radial = normalize(p + vec2(1e-5));
  vec2 tangent = vec2(-radial.y, radial.x);
  float anisoDot = abs(dot(tangent, normalize(halfVec.xy + vec2(1e-4))));
  float bowSheen = pow(1.0 - anisoDot, 4.5) * smoothstep(0.34, 0.42, r) * (1.0 - smoothstep(0.94, 0.962, r));
  float spec = pow(max(dot(normal, halfVec), 0.0), u_etched > 0.5 ? 28.0 : 42.0);

  vec3 sheenColor = mix(vec3(0.75, 0.86, 1.0), vec3(0.62, 0.35, 1.0), u_uvMode * 0.65);
  float sheenStrength = mix(0.28, 0.46, u_etched) * (1.0 - clamp(u_backlight * 0.3, 0.0, 0.3));
  vec3 litCol = waxCol * (0.72 + 0.32 * diff) + sheenColor * (bowSheen * sheenStrength + spec * 0.18);
  if (u_audioEnergy > 0.01 && r > 0.34 && r < 0.96) {
    float audioWave = 0.5 + 0.5 * sin(r * 52.0 - u_angle * 6.0);
    litCol += mix(u_accentColor, sheenColor, 0.5) * bowSheen * u_audioEnergy * (0.32 + 0.28 * audioWave);
  }

  // 7. "Hold Up to the Light" Optical Transmission & 395nm UV Slipmat Underglow
  if (u_backlight > 0.01 && r > 0.335) {
    float transmittance = pow(clamp(1.0 - opticalDensity, 0.02, 0.88), 1.35);
    // Warm studio lamp vs UV 395nm blacklight source
    vec3 lampCol = mix(vec3(1.0, 0.92, 0.76), vec3(0.58, 0.26, 1.0), u_uvMode * 0.72);
    float hotspot = exp(-dot(p - u_pointer * 0.35, p - u_pointer * 0.35) * 2.2);
    vec3 transmitted = (waxCol * 1.45 + lampCol * 0.45) * transmittance * u_backlight * (0.75 + 0.65 * hotspot);
    litCol += transmitted;
    // Translucent outer rim glow
    float rimGlow = smoothstep(0.90, 0.96, r) * transmittance * u_backlight * 0.55;
    litCol += (u_primaryColor + lampCol * 0.5) * rimGlow;
  }

  // UV 395nm fluorescence boost on neon/colored wax
  if (u_uvMode > 0.5 && r > 0.335) {
    float chroma = max(max(waxCol.r, waxCol.g), waxCol.b) - min(min(waxCol.r, waxCol.g), waxCol.b);
    litCol += waxCol * chroma * 0.34;
  }

  // Outer 12" bead edge highlight & winner halo
  float outerBead = smoothstep(0.946, 0.958, r);
  litCol = mix(litCol, mix(vec3(0.25, 0.30, 0.38), vec3(0.98, 0.78, 0.22), u_winnerGlow), outerBead * 0.45);
  litCol = clamp(litCol, 0.0, 1.0);

  OUT_FRAG = vec4(litCol, 1.0);
}`;

const FRAG_SRC_GL2 = `#version 300 es
precision highp float;
in vec2 v_uv;
out vec4 fragColor;
#define TEX2D texture
#define OUT_FRAG fragColor
` + FRAG_BODY;

const FRAG_SRC_GL1 = `
precision highp float;
varying vec2 v_uv;
#define TEX2D texture2D
#define OUT_FRAG gl_FragColor
` + FRAG_BODY;

function compileShader(gl, type, source) {
  const sh = gl.createShader(type);
  gl.shaderSource(sh, source);
  gl.compileShader(sh);
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    const info = gl.getShaderInfoLog(sh) || 'Shader compile error';
    gl.deleteShader(sh);
    throw new Error(info);
  }
  return sh;
}

function createProgram(gl, vSrc, fSrc) {
  const vs = compileShader(gl, gl.VERTEX_SHADER, vSrc);
  const fs = compileShader(gl, gl.FRAGMENT_SHADER, fSrc);
  const prog = gl.createProgram();
  gl.attachShader(prog, vs);
  gl.attachShader(prog, fs);
  gl.linkProgram(prog);
  gl.deleteShader(vs);
  gl.deleteShader(fs);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
    const info = gl.getProgramInfoLog(prog) || 'Program link error';
    gl.deleteProgram(prog);
    throw new Error(info);
  }
  return prog;
}

export class WebGLWaxDiscRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.gl = null;
    this.isWebGL2 = false;
    this.program = null;
    this.uniforms = {};
    this.pressingTex = null;
    this.labelTex = null;
    this.hasPhoto = false;
    this.hasLabel = false;
    this.photoRadius = 0.94;
    this.activeRid = 0;
    this.activePressingKey = '';
    this.activeLabelKey = '';
    this.state = {
      angle: 0,
      strobeAngle: 0,
      pointerX: 0.35,
      pointerY: 0.45,
      pattern: 0,
      primaryColor: [0.1, 0.1, 0.12],
      secondaryColor: [0.25, 0.25, 0.28],
      accentColor: [0.02, 0.71, 0.83],
      translucent: 0,
      etched: 0,
      seed: 12345,
      backlight: 0,
      uvMode: 1,
      blindMode: 0,
      winnerGlow: 0,
      audioEnergy: 0,
    };
    this._record = null;
    this._userOverrides = {};
    this._fallbackMode = false;
    this._initGL();
  }

  _initGL() {
    if (!this.canvas) {
      this._fallbackMode = true;
      return;
    }
    const opts = { alpha: true, antialias: true, premultipliedAlpha: false, powerPreference: 'high-performance' };
    let gl = this.canvas.getContext('webgl2', opts);
    let isGL2 = Boolean(gl);
    if (!gl) {
      gl = this.canvas.getContext('webgl', opts) || this.canvas.getContext('experimental-webgl', opts);
      isGL2 = false;
    }
    if (!gl) {
      this._fallbackMode = true;
      return;
    }

    try {
      const prog = createProgram(
        gl,
        isGL2 ? VERT_SRC_GL2 : VERT_SRC_GL1,
        isGL2 ? FRAG_SRC_GL2 : FRAG_SRC_GL1
      );
      this.gl = gl;
      this.isWebGL2 = isGL2;
      this.program = prog;

      const vbo = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
      const loc = gl.getAttribLocation(prog, 'a_pos');
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

      const uNames = [
        'u_pressingTex', 'u_labelTex', 'u_pointer', 'u_angle', 'u_strobeAngle',
        'u_hasPhoto', 'u_hasLabel', 'u_photoRadius', 'u_pattern',
        'u_primaryColor', 'u_secondaryColor', 'u_accentColor',
        'u_translucent', 'u_etched', 'u_seed', 'u_backlight',
        'u_uvMode', 'u_blindMode', 'u_winnerGlow', 'u_audioEnergy',
      ];
      for (const name of uNames) {
        this.uniforms[name] = gl.getUniformLocation(prog, name);
      }

      this.pressingTex = this._createSolidTex(18, 20, 28, 255);
      this.labelTex = this._createSolidTex(20, 22, 32, 255);
      this.resize();
    } catch (err) {
      console.warn('[WebGLWaxDiscRenderer] Shader init failed, using 2D fallback:', err);
      this._fallbackMode = true;
    }
  }

  _createSolidTex(r, g, b, a) {
    const gl = this.gl;
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([r, g, b, a]));
    return tex;
  }

  resize() {
    if (!this.canvas) return;
    const rect = this.canvas.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.round(rect.width * dpr);
    const h = Math.round(rect.height * dpr);
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
      if (this.gl) this.gl.viewport(0, 0, w, h);
    }
  }

  setPointer(nx, ny) {
    this.state.pointerX = Math.max(-1, Math.min(1, nx));
    this.state.pointerY = Math.max(-1, Math.min(1, ny));
  }

  setAngles(discAngleRad, strobeAngleRad = discAngleRad) {
    this.state.angle = discAngleRad;
    this.state.strobeAngle = strobeAngleRad;
  }

  setOptics({ backlight, uvMode, etchedOverride, blindMode, winnerGlow, audioEnergy } = {}) {
    if (typeof backlight === 'number') this.state.backlight = Math.max(0, Math.min(1, backlight));
    if (typeof uvMode === 'boolean') this.state.uvMode = uvMode ? 1 : 0;
    if (typeof etchedOverride === 'boolean') {
      const recEtched = Boolean(this._record && this._record.wax_spec && this._record.wax_spec.etched);
      this.state.etched = recEtched || etchedOverride ? 1 : 0;
    }
    if (typeof blindMode === 'boolean') this.state.blindMode = blindMode ? 1 : 0;
    if (typeof winnerGlow === 'number') this.state.winnerGlow = Math.max(0, Math.min(1, winnerGlow));
    if (typeof audioEnergy === 'number') this.state.audioEnergy = Math.max(0, Math.min(1, audioEnergy));
  }

  _loadTextureFromCandidates(candidates, targetTex, onLoaded, onFailed) {
    const clean = candidates.map((u) => safeImageSrc(u)).filter(Boolean);
    if (!clean.length) {
      onFailed();
      return;
    }
    let idx = 0;
    const attemptNext = () => {
      if (idx >= clean.length) {
        onFailed();
        return;
      }
      const url = clean[idx++];
      const img = new Image();
      if (/^https?:\/\//i.test(url)) {
        img.crossOrigin = 'anonymous';
      }
      img.referrerPolicy = 'no-referrer';
      img.onload = () => {
        if (!this.gl) return;
        try {
          const gl = this.gl;
          gl.bindTexture(gl.TEXTURE_2D, targetTex);
          gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
          gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
          onLoaded(url);
        } catch {
          attemptNext();
        }
      };
      img.onerror = () => attemptNext();
      img.src = url;
    };
    attemptNext();
  }

  setRecord(rec, userOverrides = {}, options = {}) {
    this._record = rec;
    this._userOverrides = userOverrides || {};
    if (!rec) return;

    const wax = rec.wax_spec || {};
    this.state.pattern = patternStringToId(wax.pattern);
    this.state.primaryColor = hexToVec3(wax.primary_color, [0.1, 0.1, 0.12]);
    this.state.secondaryColor = hexToVec3(wax.secondary_color, [0.28, 0.28, 0.34]);
    this.state.accentColor = hexToVec3(wax.accent_color, [0.02, 0.71, 0.83]);
    this.state.translucent = wax.translucent ? 1 : 0;
    this.state.etched = wax.etched || options.etchedOverride ? 1 : 0;
    this.state.seed = Number(wax.deterministic_seed || rec.release_id || 12345);

    if (options.forceSleeveArt) {
      // Optional "Discogs Cover Art" stage mode renders cover across whole platter
      const { primary, fallback } = { primary: getCenterLabelArtUrl(rec), fallback: rec.images?.cover_image_url || '' };
      const key = `sleeve:${rec.release_id}:${primary}`;
      if (this.activePressingKey !== key) {
        this.activePressingKey = key;
        this.photoRadius = 0.72;
        this.hasPhoto = false;
        this._loadTextureFromCandidates(
          [primary, fallback],
          this.pressingTex,
          () => {
            if (this.activePressingKey === key) this.hasPhoto = true;
          },
          () => {
            if (this.activePressingKey === key) this.hasPhoto = false;
          }
        );
      }
      return;
    }

    const { primary: pPrim, fallback: pFb } = getPressingPhotoUrls(rec, this._userOverrides);
    const pressKey = `press:${rec.release_id}:${pPrim}|${pFb}`;
    if (this.activePressingKey !== pressKey) {
      this.activePressingKey = pressKey;
      this.hasPhoto = false;
      const selIdx = rec.images && typeof rec.images.selected_index === 'number' ? rec.images.selected_index : -1;
      const matched = (rec.images?.classified_images || []).find((im) => im.index === selIdx);
      const detRad = Number(matched?.cv_metrics?.detected_disc_radius || 0.95);
      this.photoRadius = Math.max(0.76, Math.min(0.98, detRad));

      if (pPrim || pFb) {
        this._loadTextureFromCandidates(
          [pPrim, pFb],
          this.pressingTex,
          () => {
            if (this.activePressingKey === pressKey) this.hasPhoto = true;
          },
          () => {
            if (this.activePressingKey === pressKey) this.hasPhoto = false;
          }
        );
      }
    }

    const lblPrim = getCenterLabelArtUrl(rec);
    const lblFb = rec.images?.cover_image_url || '';
    const lblKey = `lbl:${rec.release_id}:${lblPrim}`;
    if (this.activeLabelKey !== lblKey) {
      this.activeLabelKey = lblKey;
      this.hasLabel = false;
      if (lblPrim || lblFb) {
        this._loadTextureFromCandidates(
          [lblPrim, lblFb],
          this.labelTex,
          () => {
            if (this.activeLabelKey === lblKey) this.hasLabel = true;
          },
          () => {
            if (this.activeLabelKey === lblKey) this.hasLabel = false;
          }
        );
      }
    }
  }

  render() {
    this.resize();
    if (this._fallbackMode || !this.gl || !this.program) {
      this._render2DFallback();
      return;
    }
    const gl = this.gl;
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(this.program);

    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.pressingTex);
    gl.uniform1i(this.uniforms.u_pressingTex, 0);

    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, this.labelTex);
    gl.uniform1i(this.uniforms.u_labelTex, 1);

    const s = this.state;
    gl.uniform2f(this.uniforms.u_pointer, s.pointerX, s.pointerY);
    gl.uniform1f(this.uniforms.u_angle, s.angle);
    gl.uniform1f(this.uniforms.u_strobeAngle, s.strobeAngle);
    gl.uniform1f(this.uniforms.u_hasPhoto, this.hasPhoto ? 1.0 : 0.0);
    gl.uniform1f(this.uniforms.u_hasLabel, this.hasLabel ? 1.0 : 0.0);
    gl.uniform1f(this.uniforms.u_photoRadius, this.photoRadius);
    gl.uniform1f(this.uniforms.u_pattern, s.pattern);
    gl.uniform3fv(this.uniforms.u_primaryColor, s.primaryColor);
    gl.uniform3fv(this.uniforms.u_secondaryColor, s.secondaryColor);
    gl.uniform3fv(this.uniforms.u_accentColor, s.accentColor);
    gl.uniform1f(this.uniforms.u_translucent, s.translucent);
    gl.uniform1f(this.uniforms.u_etched, s.etched);
    gl.uniform1f(this.uniforms.u_seed, s.seed);
    gl.uniform1f(this.uniforms.u_backlight, s.backlight);
    gl.uniform1f(this.uniforms.u_uvMode, s.uvMode);
    gl.uniform1f(this.uniforms.u_blindMode, s.blindMode);
    gl.uniform1f(this.uniforms.u_winnerGlow, s.winnerGlow);
    gl.uniform1f(this.uniforms.u_audioEnergy, s.audioEnergy);

    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  _render2DFallback() {
    if (!this.canvas || !this._record) return;
    const ctx = this.canvas.getContext('2d');
    if (!ctx) return;
    const w = this.canvas.width;
    const h = this.canvas.height;
    const cx = w / 2;
    const cy = h / 2;
    const rad = Math.min(w, h) * 0.48;
    const wax = this._record.wax_spec || {};

    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(this.state.angle);
    ctx.beginPath();
    ctx.arc(0, 0, rad, 0, Math.PI * 2);
    ctx.fillStyle = safeCssColor(wax.primary_color, '#18181b');
    ctx.fill();
    ctx.lineWidth = Math.max(2, rad * 0.03);
    ctx.strokeStyle = 'rgba(255,255,255,0.22)';
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(0, 0, rad * 0.33, 0, Math.PI * 2);
    ctx.fillStyle = this.state.blindMode > 0.5 ? '#0f172a' : safeCssColor(wax.accent_color, '#06b6d4');
    ctx.fill();

    ctx.beginPath();
    ctx.arc(0, 0, rad * 0.04, 0, Math.PI * 2);
    ctx.fillStyle = '#05060b';
    ctx.fill();
    ctx.restore();
  }
}

import { LANDGEO } from "./landgeo";

export type LonLat = [number, number];
export type NodeKey = string;

// Curated demo-scenario nodes with approximate real-world coordinates,
// merged at runtime with the backend's actual coordinates (ver6 coords.json
// based) via mergeNodeCoords — see below.
export const NODE: Record<NodeKey, [number, number, string]> = {
  KRPUS: [129.04, 35.1, "부산항"],
  KRICN: [126.44, 37.46, "인천공항"],
  KRICH: [127.44, 37.28, "이천"],
  CNQIN: [120.38, 36.07, "칭다오"],
  CNSHA: [121.47, 31.23, "상하이"],
  NLRTM: [4.14, 51.95, "로테르담"],
  DEHAM: [9.98, 53.54, "함부르크"],
  DEDUI: [6.76, 51.43, "뒤스부르크"],
  DEFRA: [8.56, 50.04, "프랑크푸르트"],
  DEMUC: [11.58, 48.14, "뮌헨"],
  SUEZ: [32.55, 30.0, "수에즈"],
  SIN: [103.85, 1.29, "싱가포르"],
  ALA: [76.89, 43.24, "알마티"],
  USLAX: [-118.25, 33.74, "LA"],
  AEJEA: [55.06, 25.0, "제벨알리"],
  GBFXT: [1.29, 51.95, "펠릭스토"],
  KRUSN_YARD: [129.31, 35.54, "울산 출고장"],
  KRUSN: [129.39, 35.5, "울산항"],
  KRINC: [126.6, 37.45, "인천항"],
  ICN: [126.44, 37.46, "인천공항"],
  DEBRV: [8.58, 53.54, "브레머하펜"],
  DEBRV_RAIL: [8.58, 53.54, "브레머하펜 철도"],
  DEHAM_RAIL: [9.98, 53.54, "함부르크 철도"],
  DEDUI_RAIL: [6.76, 51.43, "뒤스부르크 철도"],
  DEDUI_DC: [6.76, 51.43, "뒤스부르크 DC"],
  DEMUC_RAIL: [11.58, 48.14, "뮌헨 철도"],
  DEMUC_YARD: [11.58, 48.14, "뮌헨 출고장"],
  DEMUC_DC: [11.58, 48.14, "뮌헨 DC"],
  MUC: [11.79, 48.35, "뮌헨 공항"],
  DEFRA_RAIL: [8.56, 50.04, "프랑크푸르트 철도"],
};

// 백엔드 /api/scenarios/yum/nodes가 실제 위경도를 주므로, 그걸 받아서 이
// 표에 병합해둔다 — 위에 미리 박아둔 좌표표 밖의 노드도 정확한 좌표로
// 지도에 찍히게 된다.
export function mergeNodeCoords(entries: { node_id: string; longitude?: number | null; latitude?: number | null; label: string }[]): void {
  for (const e of entries) {
    if (e.longitude == null || e.latitude == null) continue;
    NODE[e.node_id] = [e.longitude, e.latitude, e.label];
  }
}

// Falls back to a neutral point rather than throwing when a node has no
// plotted coordinate.
export function getNode(key: NodeKey): [number, number, string] {
  return NODE[key] ?? [20, 25, key];
}

export function proj(b: [number, number, number, number], W: number, H: number) {
  const [l0, l1, t0, t1] = b;
  return ([lng, lat]: LonLat): [number, number] => [((lng - l0) / (l1 - l0)) * W, ((t0 - lat) / (t0 - t1)) * H];
}

export function arc(p: (pt: LonLat) => [number, number], a: NodeKey, b: NodeKey, h = 0.16): string {
  const A: LonLat = [getNode(a)[0], getNode(a)[1]];
  const B: LonLat = [getNode(b)[0], getNode(b)[1]];
  const [x1, y1] = p(A);
  const [x2, y2] = p(B);
  const dx = x2 - x1;
  const dy = y2 - y1;
  const mx = (x1 + x2) / 2 - dy * h;
  const my = (y1 + y2) / 2 + dx * h;
  return `M${x1.toFixed(1)} ${y1.toFixed(1)} Q${mx.toFixed(1)} ${my.toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}`;
}

export function ptOnArc(p: (pt: LonLat) => [number, number], a: NodeKey, b: NodeKey, h: number, t: number): [number, number] {
  const [x1, y1] = p([getNode(a)[0], getNode(a)[1]]);
  const [x2, y2] = p([getNode(b)[0], getNode(b)[1]]);
  const dx = x2 - x1;
  const dy = y2 - y1;
  const mx = (x1 + x2) / 2 - dy * h;
  const my = (y1 + y2) / 2 + dx * h;
  const u = 1 - t;
  return [u * u * x1 + 2 * u * t * mx + t * t * x2, u * u * y1 + 2 * u * t * my + t * t * y2];
}

export function dot(p: (pt: LonLat) => [number, number], k: NodeKey, fill: string, r = 4, stroke = "#fff"): string {
  const [x, y] = p([getNode(k)[0], getNode(k)[1]]);
  return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="1.8"/>`;
}

export function label(
  p: (pt: LonLat) => [number, number],
  k: NodeKey,
  dx = 8,
  dy = -9,
  anchor: "start" | "middle" | "end" = "start",
  fill = "#65748B",
  size = 10
): string {
  const [x, y] = p([getNode(k)[0], getNode(k)[1]]);
  return `<text x="${(x + dx).toFixed(1)}" y="${(y + dy).toFixed(1)}" text-anchor="${anchor}" font-size="${size}" font-weight="600" fill="${fill}">${getNode(k)[2]}</text>`;
}

export const THEME = {
  dark: { bg: "#050C16", bg2: "#0B1B2C", land: "#132A41", edge: "#27506F", grat: "#0F2136", txt: "#93ACC6", sub: "#5E7690" },
  light: { bg: "#EEF4FA", bg2: "#E3EDF6", land: "#CFDDEB", edge: "#B3C6D9", grat: "#D8E3EE", txt: "#4A5C74", sub: "#8E9BAF" },
};

function gratic(b: [number, number, number, number], W: number, H: number, col: string, op: number): string {
  const p = proj(b, W, H);
  let s = "";
  for (let lon = -180; lon <= 180; lon += 20) {
    const [x] = p([lon, 0]);
    if (x < 0 || x > W) continue;
    s += `<line x1="${x.toFixed(1)}" y1="0" x2="${x.toFixed(1)}" y2="${H}" stroke="${col}" stroke-width=".8" opacity="${op}"/>`;
  }
  for (let lat = -60; lat <= 80; lat += 20) {
    const [, y] = p([0, lat]);
    if (y < 0 || y > H) continue;
    s += `<line x1="0" y1="${y.toFixed(1)}" x2="${W}" y2="${y.toFixed(1)}" stroke="${col}" stroke-width=".8" opacity="${op}"/>`;
  }
  return s;
}

function landPath(b: [number, number, number, number], W: number, H: number): string {
  const p = proj(b, W, H);
  let d = "";
  LANDGEO.forEach((r) => {
    let started = false;
    let prev: number | null = null;
    for (const c of r) {
      if (prev !== null && Math.abs(c[0] - prev) > 180) started = false;
      const q = p(c as LonLat);
      d += (started ? "L" : "M") + q[0].toFixed(1) + " " + q[1].toFixed(1) + " ";
      started = true;
      prev = c[0];
    }
    d += "Z ";
  });
  return d;
}

export function mapBase(b: [number, number, number, number], W: number, H: number, mode: "dark" | "light", id: string): string {
  const t = THEME[mode];
  return `<defs>
   <radialGradient id="bg-${id}" cx="50%" cy="42%" r="78%">
     <stop offset="0%" stop-color="${t.bg2}"/><stop offset="100%" stop-color="${t.bg}"/></radialGradient>
   <filter id="glow-${id}" x="-60%" y="-60%" width="220%" height="220%">
     <feGaussianBlur stdDeviation="4.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
   <filter id="soft-${id}" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="9"/></filter>
  </defs>
  <rect width="${W}" height="${H}" fill="url(#bg-${id})"/>
  ${gratic(b, W, H, t.grat, mode === "dark" ? 0.9 : 1)}
  <path d="${landPath(b, W, H)}" fill="${t.land}" stroke="${t.edge}" stroke-width=".8" stroke-linejoin="round" fill-rule="evenodd"/>`;
}

export function hubDot(p: (pt: LonLat) => [number, number], k: NodeKey, col: string, r = 4): string {
  const [x, y] = p([getNode(k)[0], getNode(k)[1]]);
  return `<g><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(r * 2.6).toFixed(1)}" fill="${col}" opacity=".18"/>
   <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r}" fill="${col}" stroke="#FFFFFF" stroke-width="1.6"/></g>`;
}

export function glowArc(d: string, col: string, w: number, id: string, dashed?: boolean): string {
  return `<path d="${d}" fill="none" stroke="${col}" stroke-width="${(w * 2.6).toFixed(1)}" opacity=".18" filter="url(#soft-${id})" stroke-linecap="round"/>
   <path d="${d}" fill="none" stroke="${col}" stroke-width="${w}" stroke-linecap="round" opacity=".95"${dashed ? ' stroke-dasharray="5 8" class="flow-line"' : ""}/>`;
}

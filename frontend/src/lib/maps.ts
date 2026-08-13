import { arc, glowArc, hubDot, label, mapBase, proj, THEME, type NodeKey } from "./worldmap";

// Trimmed from the reference project's lib/maps.ts to just propMap (the
// route-comparison map used by NegotiationResults) — dashMap/netMap/
// trackMapSvg are for the dashboard/network/tracking pages this project
// doesn't have wired up yet, and depend on data/demoData.ts which this
// project doesn't carry.

export interface ProposalRouteForMap {
  id: string;
  color: string;
  legs: [NodeKey, NodeKey, number][];
}

export function propMap(routes: ProposalRouteForMap[], selectedId: string, bounds: [number, number, number, number]): string {
  const [minLon, maxLon, maxLat, minLat] = bounds;
  const W = 780;
  const H = 520;
  const p = proj([minLon, maxLon, maxLat, minLat], W, H);
  const id = "p";
  const nodeSet = new Set<NodeKey>();
  routes.forEach((r) => r.legs.forEach(([a, b]) => { nodeSet.add(a); nodeSet.add(b); }));

  const g = routes
    .map((r) => {
      const d = r.legs.map((l) => arc(p, l[0], l[1], l[2])).join(" ");
      const sel = selectedId === r.id;
      return `<g class="rt" data-id="${r.id}" style="cursor:pointer">
     <path d="${d}" fill="none" stroke="transparent" stroke-width="16"/>
     ${sel ? glowArc(d, r.color, 3.4, id, true) : `<path d="${d}" fill="none" stroke="${r.color}" stroke-width="1.8" opacity=".4" stroke-linecap="round"/>`}</g>`;
    })
    .join("");
  const dots = Array.from(nodeSet)
    .map((k) => hubDot(p, k, "#7FB6F5", 3.8))
    .join("");
  const labs = Array.from(nodeSet)
    .map((k, i) => label(p, k, i % 2 === 0 ? 10 : -10, i % 2 === 0 ? 17 : -11, i % 2 === 0 ? "start" : "end", THEME.dark.txt, 10.5))
    .join("");
  const legend = `<g transform="translate(18,18)">${routes
    .map(
      (r, i) => `<g transform="translate(0,${i * 20})">
     <rect x="0" y="-9" width="150" height="16" rx="8" fill="#0B1A2B" opacity="${selectedId === r.id ? ".9" : ".5"}"/>
     <circle cx="11" cy="-1" r="4" fill="${r.color}"/>
     <text x="21" y="3" font-size="10.5" font-weight="600" fill="${selectedId === r.id ? "#EAF2FB" : "#8FA6C0"}">${r.id}</text></g>`
    )
    .join("")}</g>`;
  return `<svg viewBox="0 0 ${W} ${H}">${mapBase([minLon, maxLon, maxLat, minLat], W, H, "dark", id)}${g}${dots}${labs}${legend}</svg>`;
}

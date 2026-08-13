export type YPLngLat = [number, number];
export type YPSeaGeometry =
  | { type: "LineString"; coordinates: YPLngLat[] }
  | { type: "MultiLineString"; coordinates: YPLngLat[][] };

const ASIA_EUROPE: YPLngLat[] = [
  [118, 20], [105, 8], [103.4, 1.2], [91, 5], [76, 7], [61, 12],
  [44, 12.5], [38, 20], [32.5, 29.8], [29, 34], [18, 36],
];

function europePortApproach(port: YPLngLat): YPLngLat[] {
  // 지중해 항만: 수에즈에서 지중해 연안을 따라 접근한다.
  if (port[1] < 46 && port[0] > -6) {
    return [[12, 36.5], [6, 38], [(port[0] + 6) / 2, Math.min(port[1] - 1.5, 40)], port];
  }

  // 발트해: 지브롤터-대서양-영불해협-북해-덴마크 해협을 지난다.
  if (port[1] >= 53.5 && port[0] > 11) {
    return [[5, 38], [-5.5, 36], [-9, 43], [-5, 49], [1, 51], [4, 54], [8.5, 57], [12, 56], port];
  }

  // 북해·영국·프랑스 북부 항만.
  if (port[1] >= 48) {
    return [[5, 38], [-5.5, 36], [-9, 43], [-5, 49], [1, 51], [4, 53.5], port];
  }

  // 이베리아 서안 등 대서양 유럽 항만.
  return [[5, 38], [-5.5, 36], [-9, 42], port];
}

function smoothSeaPath(points: YPLngLat[], stepsPerSection = 8): YPLngLat[] {
  if (points.length < 3) return points;
  const result: YPLngLat[] = [];
  for (let section = 0; section < points.length - 1; section += 1) {
    const p0 = points[Math.max(0, section - 1)];
    const p1 = points[section];
    const p2 = points[section + 1];
    const p3 = points[Math.min(points.length - 1, section + 2)];
    for (let step = 0; step < stepsPerSection; step += 1) {
      const t = step / stepsPerSection, t2 = t * t, t3 = t2 * t;
      const value = (axis: 0 | 1) => .5 * ((2 * p1[axis]) + (-p0[axis] + p2[axis]) * t +
        (2*p0[axis] - 5*p1[axis] + 4*p2[axis] - p3[axis]) * t2 +
        (-p0[axis] + 3*p1[axis] - 3*p2[axis] + p3[axis]) * t3);
      result.push([value(0), value(1)]);
    }
  }
  result.push(points[points.length - 1]);
  return result;
}

/**
 * 화면 표시용 근사 항로다. 해상 구간이 대륙을 직선 관통하지 않도록
 * 수에즈·말라카·대서양 같은 대표 해역을 경유한다.
 */
export function ypSeaRoute(from: YPLngLat, to: YPLngLat): YPLngLat[] {
  const korea = (point: YPLngLat) => point[0] >= 125 && point[0] <= 132 && point[1] >= 33 && point[1] <= 40;
  const chinaEast = (point: YPLngLat) => point[0] >= 117 && point[0] < 125 && point[1] >= 22 && point[1] <= 41;
  if ((korea(from) && chinaEast(to)) || (chinaEast(from) && korea(to))) {
    const kr = korea(from) ? from : to;
    const cn = chinaEast(from) ? from : to;
    const yellowSea: YPLngLat[] = [kr, [127.8, 34.3], [125.8, 34.2], [123.5, 35], cn];
    return smoothSeaPath(from === kr ? yellowSea : [...yellowSea].reverse());
  }

  const isEurope = (point: YPLngLat) => point[0] >= -12 && point[0] <= 30 && point[1] >= 35 && point[1] <= 61;
  const isAfrica = (point: YPLngLat) => point[0] >= -20 && point[0] <= 55 && point[1] >= -36 && point[1] < 35;
  const african = isAfrica(from) ? from : isAfrica(to) ? to : null;
  const european = isEurope(from) ? from : isEurope(to) ? to : null;
  if (african && european) {
    const eastAfrica = african[0] > 25;
    const path: YPLngLat[] = eastAfrica
      ? [african, [43, 12.5], [38, 20], [32.5, 29.8], [29, 34], [18, 36], european]
      : [african, [-12, Math.max(5, african[1])], [-10, 25], [-8, 34], [-5.5, 36], [-1, 43], european];
    return smoothSeaPath(from === african ? path : [...path].reverse());
  }

  if (isEurope(from) && isEurope(to)) {
    const northFrom = from[1] >= 47;
    const northTo = to[1] >= 47;
    if (northFrom && northTo) {
      const path: YPLngLat[] = [from, [Math.min(from[0], 8), 54.5], [3, 53], [0.5, 51], to];
      return smoothSeaPath(path);
    }
    if (!northFrom && !northTo) {
      return smoothSeaPath([from, [(from[0] + to[0]) / 2, Math.min(from[1], to[1]) - 2.2], to], 12);
    }
    const north = northFrom ? from : to;
    const med = northFrom ? to : from;
    const path: YPLngLat[] = [north, [-4, 49], [-8, 44], [-5.5, 36], [2, 37], med];
    return smoothSeaPath(from === north ? path : [...path].reverse());
  }

  const east = from[0] > 60 ? from : to[0] > 60 ? to : null;
  const europe = isEurope(from) ? from : isEurope(to) ? to : null;
  if (east && europe) {
    const path = [east, ...ASIA_EUROPE, ...europePortApproach(europe)];
    return smoothSeaPath(from === east ? path : [...path].reverse());
  }

  const america = from[0] < -50 ? from : to[0] < -50 ? to : null;
  if (america && europe) {
    const path: YPLngLat[] = [america, [-80, 35], [-55, 40], [-35, 43], [-18, 44], europe];
    return smoothSeaPath(from === america ? path : [...path].reverse());
  }

  const dx = to[0] - from[0], dy = to[1] - from[1];
  const distance = Math.hypot(dx, dy) || 1;
  const bend = Math.min(18, Math.max(4, distance * .16));
  const control: YPLngLat = [(from[0] + to[0]) / 2 + dy / distance * bend, (from[1] + to[1]) / 2 - dx / distance * bend];
  return Array.from({ length: 25 }, (_, index) => {
    const t = index / 24, u = 1 - t;
    return [u*u*from[0] + 2*u*t*control[0] + t*t*to[0], u*u*from[1] + 2*u*t*control[1] + t*t*to[1]];
  });
}

export function ypSeaGeometry(from: YPLngLat, to: YPLngLat): YPSeaGeometry {
  const asia = (point: YPLngLat) => point[0] >= 100 && point[0] <= 150 && point[1] >= 20;
  const westAmerica = (point: YPLngLat) => point[0] <= -105 && point[0] >= -135 && point[1] >= 25 && point[1] <= 55;
  if ((asia(from) && westAmerica(to)) || (westAmerica(from) && asia(to))) {
    const east = asia(from) ? from : to;
    const west = westAmerica(from) ? from : to;
    const asiaSide = smoothSeaPath([east, [145, 34], [163, 38], [179.8, 42]], 10);
    const americaSide = smoothSeaPath([[-179.8, 42], [-163, 40], [-145, 36], west], 10);
    return {
      type: "MultiLineString",
      coordinates: from === east ? [asiaSide, americaSide] : [[...americaSide].reverse(), [...asiaSide].reverse()],
    };
  }
  return { type: "LineString", coordinates: ypSeaRoute(from, to) };
}

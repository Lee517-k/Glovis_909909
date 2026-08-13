import { useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";
import { Badge, Chip, type Mode } from "../lib/YP_ui";
import "./YP_data.css";

export type YpService = {
  carrier_id: string;
  carrier_name: string;
  capability_id: string;
  mode: Mode;
  origin_name: string;
  destination_name: string;
  currency: string;
  base_rate: number | null;
  transit_hours: number | null;
  capacity_value: number | null;
  capacity_unit: string | null;
  on_time_rate: number | null;
  validation_status: string;
};
type Summary = {
  carriers: number;
  services: number;
  locations: number;
  finished_vehicle: number;
  unverified: number;
};
const emptySummary: Summary = {
  carriers: 0,
  services: 0,
  locations: 0,
  finished_vehicle: 0,
  unverified: 0,
};
const columns: (keyof YpService)[] = [
  "carrier_name",
  "capability_id",
  "mode",
  "origin_name",
  "base_rate",
  "transit_hours",
  "capacity_value",
  "on_time_rate",
  "validation_status",
];
const API_BASE = (
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api"
).replace(/\/$/, "");

maplibregl.setWorkerUrl(maplibreWorkerUrl);

const YP_COORDS: Record<string, [number, number]> = {
  ATVIE: [48.2082, 16.3738],
  Vienna: [48.2082, 16.3738],
  BEANR: [51.2194, 4.4025],
  BEBRU: [50.8503, 4.3517],
  BEZEE: [51.3315, 3.2074],
  CNNGB: [29.8683, 121.544],
  CNSHA: [31.2304, 121.4737],
  "Shanghai Pudong": [31.1443, 121.8083],
  CNTAO: [36.0671, 120.3826],
  CZPRG: [50.0755, 14.4378],
  Prague: [50.0755, 14.4378],
  DEBRV: [53.5396, 8.5809],
  DEDUI: [51.4344, 6.7623],
  Duisburg: [51.4344, 6.7623],
  DEFRA: [50.1109, 8.6821],
  Frankfurt: [50.1109, 8.6821],
  DEHAM: [53.5488, 9.9872],
  DEKOL: [50.9375, 6.9603],
  Cologne: [50.9375, 6.9603],
  DELEI: [51.3397, 12.3731],
  DEMUC: [48.1351, 11.582],
  Munich: [48.1351, 11.582],
  DESTR: [48.7758, 9.1829],
  ESMAD: [40.4168, -3.7038],
  Madrid: [40.4168, -3.7038],
  ESVLC: [39.4699, -0.3763],
  Valencia: [39.4699, -0.3763],
  FRLEH: [49.4938, 0.1077],
  FRPAR: [48.8566, 2.3522],
  GBLON: [51.5074, -0.1278],
  "London Heathrow": [51.47, -0.4543],
  GBSOU: [50.9097, -1.4044],
  Southampton: [50.9097, -1.4044],
  HKHKG: [22.3193, 114.1694],
  "Hong Kong": [22.3193, 114.1694],
  HUBUD: [47.4979, 19.0402],
  Budapest: [47.4979, 19.0402],
  ITGOA: [44.4056, 8.9463],
  ITMIL: [45.4642, 9.19],
  ITVER: [45.4384, 10.9916],
  Verona: [45.4384, 10.9916],
  JPNGO: [35.1815, 136.9066],
  JPOSA: [34.6937, 135.5023],
  "Osaka Kansai": [34.4347, 135.244],
  JPTYO: [35.6762, 139.6503],
  "Tokyo Narita": [35.772, 140.3929],
  JPYOK: [35.4437, 139.638],
  KRGJU: [35.1595, 126.8526],
  KRHWA: [37.1995, 126.8312],
  KRICH: [37.4563, 126.7052],
  KRINC: [37.4563, 126.7052],
  Incheon: [37.4563, 126.7052],
  KRPTK: [36.9921, 126.831],
  KRPUS: [35.1796, 129.0756],
  Busan: [35.1796, 129.0756],
  KRSEL: [37.5665, 126.978],
  KRUSN: [35.5384, 129.3114],
  NLAMS: [52.3676, 4.9041],
  Amsterdam: [52.3676, 4.9041],
  NLRTM: [51.9244, 4.4777],
  PLGDN: [54.352, 18.6466],
  PLWAW: [52.2297, 21.0122],
  Warsaw: [52.2297, 21.0122],
  ROCUR: [46.35, 21.306],
  Curtici: [46.35, 21.306],
  SEGOT: [57.7089, 11.9746],
  SGSIN: [1.3521, 103.8198],
  Singapore: [1.3521, 103.8198],
  SIKOP: [45.5481, 13.7302],
  Koper: [45.5481, 13.7302],
  THBKK: [13.7563, 100.5018],
  Bangkok: [13.7563, 100.5018],
  TRIST: [41.0082, 28.9784],
  Istanbul: [41.0082, 28.9784],
  VNHAN: [21.0278, 105.8342],
  Hanoi: [21.0278, 105.8342],
};
const YP_MODE_COLOR: Record<string, string> = {
  sea: "#31A8FF",
  rail: "#32E0A1",
  air: "#B388FF",
  truck: "#FFB84D",
  road: "#FFB84D",
};
// 거점명으로 좌표를 찾는다. 정확히 일치하지 않으면 첫 단어(포트코드)만 잘라 재시도한다.
const findYpCoord = (name: string) =>
  YP_COORDS[name] ?? YP_COORDS[name.split(/[_ ]/)[0]];

// MapLibre 기반 실제 인터랙티브 세계지도에 운송 구간(라인)과 거점(점)을 렌더링한다.
// 좌표를 찾지 못한 서비스는 지도에서 제외된다. (본문이 200줄 이상이라 단계별 주석 포함)
function InteractiveCapabilityMap({ services }: { services: YpService[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [mapError, setMapError] = useState("");
  const modeCounts = useMemo(() => services.reduce<Record<string, number>>((counts, service) => {
    const mode = service.mode === "truck" ? "road" : String(service.mode);
    counts[mode] = (counts[mode] ?? 0) + 1;
    return counts;
  }, {}), [services]);
  // 좌표를 알 수 없는 출발/도착지를 가진 서비스는 걸러내고 [출발, 도착] 좌표쌍만 남긴다
  const routes = useMemo(
    () =>
      services
        .map((service) => ({
          service,
          origin: findYpCoord(service.origin_name),
          destination: findYpCoord(service.destination_name),
        }))
        .filter(
          (route): route is typeof route & {
            origin: [number, number];
            destination: [number, number];
          } => Boolean(route.origin && route.destination),
        ),
    [services],
  );
  // routes에 등장하는 거점을 중복 제거해 지도 위에 찍을 점 목록을 만든다
  const nodes = useMemo(() => {
    const unique = new Map<string, { position: [number, number]; mode: string }>();
    routes.forEach(({ service, origin, destination }) => {
      if (!unique.has(service.origin_name)) unique.set(service.origin_name, { position: origin, mode: String(service.mode) });
      if (!unique.has(service.destination_name)) unique.set(service.destination_name, { position: destination, mode: String(service.mode) });
    });
    return [...unique.entries()];
  }, [routes]);
  // routes를 MapLibre가 요구하는 GeoJSON LineString FeatureCollection으로 변환
  const routeData = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: routes.map(({ service, origin, destination }) => ({
        type: "Feature" as const,
        geometry: {
          type: "LineString" as const,
          coordinates: [
            [origin[1], origin[0]],
            [destination[1], destination[0]],
          ],
        },
        properties: {
          carrier: service.carrier_name,
          route: `${service.origin_name} → ${service.destination_name}`,
          mode: String(service.mode),
        },
      })),
    }),
    [routes],
  );
  // nodes를 GeoJSON Point FeatureCollection으로 변환 (지도 위 거점 마커용)
  const nodeData = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: nodes.map(([name, node]) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [node.position[1], node.position[0]],
        },
        properties: { name, mode: node.mode },
      })),
    }),
    [nodes],
  );
  useEffect(() => {
    if (!containerRef.current) return;
    let map: maplibregl.Map | undefined;
    try {
      map = new maplibregl.Map({
        container: containerRef.current,
        // nolabels 스타일: 도시명·도로명 텍스트를 없애 우리가 그리는 구간선/거점 점이 더 도드라지게 함
        style: "https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json",
        center: [65, 35],
        zoom: 1.8,
        minZoom: 1.5,
        attributionControl: {},
      });
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      map.on("load", () => {
        if (!map) return;
        map.addSource("yp-routes", { type: "geojson", data: routeData });
        map.addLayer({
          id: "yp-route-glow",
          type: "line",
          source: "yp-routes",
          paint: {
            "line-color": [
              "match", ["get", "mode"],
              "sea", YP_MODE_COLOR.sea,
              "rail", YP_MODE_COLOR.rail,
              "air", YP_MODE_COLOR.air,
              "truck", YP_MODE_COLOR.truck,
              "road", YP_MODE_COLOR.road,
              "#94a3b8",
            ],
            "line-width": ["interpolate", ["linear"], ["zoom"], 2, 2.4, 7, 5],
            "line-blur": 3,
            "line-opacity": 0.1,
          },
        });
        map.addLayer({
          id: "yp-route-layer",
          type: "line",
          source: "yp-routes",
          paint: {
            "line-color": [
              "match", ["get", "mode"],
              "sea", YP_MODE_COLOR.sea,
              "rail", YP_MODE_COLOR.rail,
              "air", YP_MODE_COLOR.air,
              "truck", YP_MODE_COLOR.truck,
              "road", YP_MODE_COLOR.road,
              "#64748b",
            ],
            "line-width": ["interpolate", ["linear"], ["zoom"], 2, 1.25, 7, 2.5],
            "line-opacity": 0.72,
            "line-dasharray": [7, 6],
          },
        });
        map.addSource("yp-nodes", { type: "geojson", data: nodeData });
        map.addLayer({
          id: "yp-node-halo",
          type: "circle",
          source: "yp-nodes",
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, 8, 7, 13],
            "circle-color": [
              "match", ["get", "mode"],
              "sea", YP_MODE_COLOR.sea,
              "rail", YP_MODE_COLOR.rail,
              "air", YP_MODE_COLOR.air,
              "truck", YP_MODE_COLOR.truck,
              "road", YP_MODE_COLOR.road,
              "#2f8de4",
            ],
            "circle-blur": 0.72,
            "circle-opacity": 0.3,
          },
        });
        map.addLayer({
          id: "yp-node-layer",
          type: "circle",
          source: "yp-nodes",
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, 4, 7, 6.5],
            "circle-color": [
              "match", ["get", "mode"],
              "sea", YP_MODE_COLOR.sea,
              "rail", YP_MODE_COLOR.rail,
              "air", YP_MODE_COLOR.air,
              "truck", YP_MODE_COLOR.truck,
              "road", YP_MODE_COLOR.road,
              "#2f8de4",
            ],
            "circle-stroke-color": "#f8fbff",
            "circle-stroke-width": 2,
          },
        });
        const showPopup = (event: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
          const feature = event.features?.[0];
          if (!feature) return;
          const title = String(feature.properties?.name ?? feature.properties?.carrier ?? "운송 서비스");
          const detail = feature.properties?.route
            ? `<span>${feature.properties.route} · ${String(feature.properties.mode).toUpperCase()}</span>`
            : "";
          new maplibregl.Popup({ closeButton: false, offset: 10 })
            .setLngLat(event.lngLat)
            .setHTML(`<div class="yp-map-popup"><b>${title}</b>${detail}</div>`)
            .addTo(map!);
        };
        map.on("click", "yp-route-layer", showPopup);
        map.on("click", "yp-node-layer", showPopup);
        let hoverPopup: maplibregl.Popup | undefined;
        map.on("mouseenter", "yp-node-layer", (event) => {
          const feature = event.features?.[0];
          if (!feature) return;
          const coordinates = feature.geometry.type === "Point"
            ? feature.geometry.coordinates as [number, number]
            : [event.lngLat.lng, event.lngLat.lat] as [number, number];
          hoverPopup?.remove();
          hoverPopup = new maplibregl.Popup({
            closeButton: false,
            closeOnClick: false,
            offset: 11,
            className: "yp-port-tooltip",
          })
            .setLngLat(coordinates)
            .setHTML(`<div class="yp-map-popup"><b>${String(feature.properties?.name ?? "거점")}</b></div>`)
            .addTo(map!);
        });
        map.on("mouseleave", "yp-node-layer", () => {
          hoverPopup?.remove();
          hoverPopup = undefined;
        });
        ["yp-route-layer", "yp-node-layer"].forEach((layer) => {
          map!.on("mouseenter", layer, () => { map!.getCanvas().style.cursor = "pointer"; });
          map!.on("mouseleave", layer, () => { map!.getCanvas().style.cursor = ""; });
        });
        map.resize();
      });
      map.on("error", (event) => {
        console.error("MapLibre:", event.error);
        setMapError("지도를 불러오지 못했습니다. CARTO 지도 연결을 확인해 주세요.");
      });
    } catch (error) {
      console.error("MapLibre initialization failed:", error);
      setMapError("이 브라우저에서 지도를 초기화하지 못했습니다.");
    }
    const observer = new ResizeObserver(() => map?.resize());
    observer.observe(containerRef.current);
    return () => {
      observer.disconnect();
      map?.remove();
    };
  }, [routeData, nodeData]);
  return (
    <div className="yp-map-shell">
      <div ref={containerRef} className="yp-maplibre-map" />
      {/* 지도 위에 옅은 격자 라인을 겹쳐 그려 블루프린트 느낌을 낸다 (pointer-events:none이라 지도 조작엔 영향 없음).
          가장자리를 어둡게 눌러주던 비네트는 답답해 보인다는 피드백으로 제거했다. */}
      <div className="yp-map-atmosphere" aria-hidden="true" />
      {mapError && <div className="yp-map-load-error">{mapError}</div>}
      {!services.length && (
        <div className="yp-map-empty">운송 서비스 데이터를 불러오는 중입니다.</div>
      )}
      <div className="yp-map-legend">
        <div className="yp-map-legend-modes">
          <span><i style={{ background: YP_MODE_COLOR.sea }} />해상 <b>{modeCounts.sea ?? 0}</b> 서비스</span>
          <span><i style={{ background: YP_MODE_COLOR.rail }} />철도 <b>{modeCounts.rail ?? 0}</b> 서비스</span>
          <span><i style={{ background: YP_MODE_COLOR.air }} />항공 <b>{modeCounts.air ?? 0}</b> 서비스</span>
          <span><i style={{ background: YP_MODE_COLOR.road }} />도로 <b>{modeCounts.road ?? 0}</b> 서비스</span>
        </div>
        <span className="yp-map-legend-symbols">● 거점　┄ 운송 구간</span>
      </div>
    </div>
  );
}

function _CapabilityMap() {
  const [tip, setTip] = useState<{ name: string; x: number; y: number } | null>(
    null,
  );
  const pts = [
    ["부산 · KRPUS", 885, 170],
    ["울산 · KRUSN", 878, 176],
    ["인천 · KRINC", 895, 159],
    ["상하이 · CNSHA", 848, 188],
    ["싱가포르 · SGSIN", 812, 225],
    ["함부르크 · DEHAM", 552, 122],
    ["브레머하펜 · DEBRV", 539, 130],
    ["로테르담 · NLRTM", 527, 139],
    ["뒤스부르크 · DEDUI", 574, 137],
    ["프랑크푸르트 · DEFRA", 590, 151],
    ["뮌헨 · DEMUC", 604, 173],
    ["프라하 · CZPRG", 627, 160],
    ["비엔나 · ATVIE", 645, 174],
  ] as const;
  return (
    <div className="yp-map-shell">
      {tip && (
        <div
          className="yp-map-tooltip"
          style={{ display: "block", left: tip.x, top: tip.y }}
        >
          {tip.name}
        </div>
      )}
      <svg viewBox="0 0 1100 520" role="img" aria-label="글로벌 운송 역량 지도">
        <rect width="1100" height="520" fill="#EEF4F9" />
        <g fill="#D7E4DB" stroke="#C6D7CE">
          <path d="M78 105L134 70 215 75 260 108 245 145 194 187 123 173 68 132Z" />
          <path d="M490 116L524 98 565 102 589 120 569 139 534 137 487 139Z" />
          <path d="M576 98L638 73 724 81 799 108 905 175 883 201 825 198 740 186 653 171 611 146Z" />
          <path d="M514 171L558 158 593 180 604 224 562 313 529 294 496 206Z" />
          <path d="M866 345L913 326 958 339 983 368 963 399 918 409 881 389Z" />
        </g>
        <g fill="none" opacity=".88">
          <path d="M885 170Q730 80 552 122" stroke="#1E6FBF" strokeWidth="3" />
          <path
            d="M878 176Q728 100 539 130"
            stroke="#1E6FBF"
            strokeWidth="2.5"
          />
          <path
            d="M539 130L574 137 606 151 645 174"
            stroke="#12A47B"
            strokeWidth="2.7"
          />
          <path
            d="M895 159Q748 46 570 115"
            stroke="#7A5AF8"
            strokeWidth="2.3"
            strokeDasharray="7 5"
          />
          <path d="M627 160L645 174" stroke="#E08A00" strokeWidth="3" />
        </g>
        {pts.map(([n, x, y]) => (
          <circle
            key={n}
            className="yp-map-point"
            cx={x}
            cy={y}
            r="5.5"
            fill="#0F3F73"
            stroke="#fff"
            strokeWidth="2.5"
            onMouseEnter={() =>
              setTip({ name: n, x: (x / 1100) * 100, y: (y / 520) * 100 })
            }
            onMouseLeave={() => setTip(null)}
            style={{ transformBox: "fill-box", transformOrigin: "center" }}
          />
        ))}
      </svg>
    </div>
  );
}

// Kept temporarily as a visual fallback while the external tile script loads.
void _CapabilityMap;

export function YpCarrierNetworkPanel({ refreshKey }: { refreshKey?: unknown } = {}) {
  const [services, setServices] = useState<YpService[]>([]);
  const [summary, setSummary] = useState(emptySummary);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<"" | "sea" | "rail" | "air" | "road">("");
  const [error, setError] = useState("");
  useEffect(() => {
    const params = new URLSearchParams({ approval_status: "approved" });
    if (mode) params.set("mode", mode);
    Promise.all([
      fetch(`${API_BASE}/yp/capabilities?${params}`).then((r) => {
        if (!r.ok) throw new Error(`역량 조회 실패 (${r.status})`);
        return r.json();
      }),
      fetch(`${API_BASE}/yp/capabilities/summary`).then((r) => {
        if (!r.ok) throw new Error(`요약 조회 실패 (${r.status})`);
        return r.json();
      }),
    ])
      .then(([d, s]) => {
        setServices(d.items ?? []);
        setSummary(s);
        setError("");
      })
      .catch((e) => setError(e instanceof Error ? e.message : "DB 연결 실패"));
  }, [mode, refreshKey]);
  // 각 열의 필터 입력값과 부분 일치(대소문자 무시)하는 행만 그리드에 표시
  const visible = useMemo(
    () =>
      services.filter((s) =>
        columns.every(
          (c) =>
            !filters[c] ||
            String(s[c] ?? "")
              .toLowerCase()
              .includes(filters[c].toLowerCase()),
        ),
      ),
    [services, filters],
  );
  const set = (c: string, v: string) => setFilters((f) => ({ ...f, [c]: v }));
  return (
    <>
      {error && (
        <div className="yp-aialert" style={{ marginBottom: 14 }}>
          <b>데이터를 불러오지 못했습니다.</b>
          <br />
          {error} · 백엔드와 CORS 설정을 확인하세요.
        </div>
      )}
      <div className="grid yp-kpis" style={{ marginBottom: 14 }}>
        {[
          ["ti-anchor", "등록 운송사", summary.carriers, "해상·철도·도로·항공"],
          [
            "ti-checklist",
            "승인 서비스",
            summary.services,
            `완성차 가능 ${summary.finished_vehicle}개`,
          ],
          ["ti-map-pin", "연결 거점", summary.locations, "출발·도착 위치"],
          [
            "ti-alert-triangle",
            "검토 필요",
            summary.unverified,
            "신뢰도 검증 필요",
          ],
        ].map((x) => (
          <div className="card kpi" key={String(x[1])}>
            <div className="lb">
              <span className="ic">
                <i className={`ti ${x[0]}`} />
              </span>
              {x[1]}
            </div>
            <div className="vl">{x[2]}</div>
            <div className="sub">{x[3]}</div>
          </div>
        ))}
      </div>
      <div className="yp-service-controls">
        <p style={{ fontSize: 12, color: "var(--muted)" }}>
          승인된 운송사 서비스와 모드별 연결을 탐색합니다.
        </p>
        <div className="spacer" />
        <select
          className="yp-actsel"
          value={mode}
          onChange={(event) => setMode(event.target.value as typeof mode)}
          aria-label="운송수단 필터"
        >
          <option value="">전체 운송수단</option>
          <option value="sea">해상</option>
          <option value="rail">철도</option>
          <option value="air">항공</option>
          <option value="road">도로</option>
        </select>
      </div>
      <section
        className="card"
        style={{ overflow: "hidden", marginBottom: 14 }}
      >
        <div className="card-hd">
          <div>
            <h4>글로벌 운송 네트워크</h4>
            <p>파트너 운송사 · 운송 구간 · 주요 물류 거점</p>
          </div>
          <div className="spacer" />
          <span className="yp-map-live"><i className="ti ti-refresh" />실시간 데이터</span>
        </div>
        <InteractiveCapabilityMap services={services} />
      </section>
      <section className="card">
        <div className="card-hd">
          <div>
            <h4>운송 서비스 상세</h4>
          </div>
          <div className="spacer" />
          <button className="btn sm">
            <i className="ti ti-download" />
            내보내기
          </button>
        </div>
        <div className="tablewrap yp-service-tablewrap">
          <table>
            <thead>
              <tr>
                <th>운송사</th>
                <th>역량 ID</th>
                <th>수단</th>
                <th>구간</th>
                <th className="r">기본 운임</th>
                <th className="r">소요일</th>
                <th className="r">용량</th>
                <th className="r">정시율</th>
                <th>검증</th>
              </tr>
              <tr className="yp-filter-row">
                {columns.map((c, i) => (
                  <th key={c}>
                    <div className="yp-filter-cell">
                        <i className="ti ti-filter" />
                      <input
                        className="yp-filter-input"
                        value={filters[c] ?? ""}
                        placeholder={i === 2 || i === 8 ? "전체" : "검색"}
                        onChange={(e) => set(c, e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Escape") set(c, "");
                        }}
                      />
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((s) => (
                <tr key={s.capability_id}>
                  <td>
                    <b>{s.carrier_name}</b>
                    <div className="sub2">{s.carrier_id}</div>
                  </td>
                  <td className="mono" style={{ color: "var(--faint)" }}>
                    {s.capability_id}
                  </td>
                  <td>
                    <Chip mode={s.mode} />
                  </td>
                  <td>
                    {s.origin_name} → {s.destination_name}
                  </td>
                  <td className="r num">
                    {s.base_rate == null
                      ? "—"
                      : `${s.currency} ${s.base_rate.toLocaleString()}`}
                  </td>
                  <td className="r num">
                    {s.transit_hours == null
                      ? "—"
                      : `${(s.transit_hours / 24).toFixed(1)}일`}
                  </td>
                  <td className="r num">
                    {s.capacity_value == null
                      ? "—"
                      : `${s.capacity_value.toLocaleString()} ${s.capacity_unit ?? ""}`}
                  </td>
                  <td className="r num">
                    {s.on_time_rate == null
                      ? "—"
                      : `${(s.on_time_rate * 100).toFixed(1)}%`}
                  </td>
                  <td>
                    <Badge
                      tone={s.validation_status === "verified" ? "ok" : "warn"}
                    >
                      {s.validation_status === "verified" ? "검증됨" : "미검증"}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="yp-grid-status">
          <span>
            <b>{visible.length}</b>건 표시 · 전체 <b>{services.length}</b>건
          </span>
          <span>각 열 검색창에서 즉시 필터링 · Esc로 조건 초기화</span>
        </div>
      </section>
    </>
  );
}
// 사이드바 메뉴에서 직접 진입할 수 있는 독립 페이지 래퍼 (현재는 사용처 없이 UploadPage 내 탭으로만 노출됨)
export function YpCarrierNetworkPage({ active }: { active: boolean }) {
  return (
    <section
      id="yp-carrier-network"
      className={`page ${active ? "active" : ""}`}
    >
      <div className="phead">
        <div>
          <div className="eyebrow">
            <i className="ti ti-chart-dots-3" />
            Carrier Data
          </div>
          <h3>운송사 역량 가시화</h3>
          <p>승인된 운송사 역량 데이터를 네트워크와 그리드로 확인합니다.</p>
        </div>
      </div>
      <YpCarrierNetworkPanel refreshKey={active} />
    </section>
  );
}


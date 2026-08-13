import { useEffect, useRef } from "react";
import { Map as MapLibreMap, LngLatBounds, type Map as MapLibreMapType } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { getNode } from "../lib/worldmap";
import type { HubBubble } from "../api/controlTowerApi";

const STYLE_URL = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

export function HubMapLibre({ bubbles }: { bubbles: HubBubble[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMapType | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    mapRef.current = new MapLibreMap({
      container: containerRef.current,
      style: STYLE_URL,
      center: [20, 30],
      zoom: 1.3,
      renderWorldCopies: false, // 줌아웃 시 지도가 옆으로 반복되는 것 방지
      // maxBounds를 -180~180 전체로 주면 renderWorldCopies:false와 겹쳐서
      // MapLibre 내부에서 크래시가 남(라이브러리 버그) — 빼고 renderWorldCopies만 사용
    });
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const draw = () => {
      if (map.getLayer("hub-points")) map.removeLayer("hub-points");
      if (map.getSource("hub-points")) map.removeSource("hub-points");
      if (bubbles.length === 0) return;

      const features = bubbles.map((b) => {
        const [lng, lat] = getNode(b.node_id);
        return {
          type: "Feature" as const,
          properties: { name: b.name, label: b.t, color: b.color, r: b.r },
          geometry: { type: "Point" as const, coordinates: [lng, lat] },
        };
      });
      map.addSource("hub-points", { type: "geojson", data: { type: "FeatureCollection", features } });
      map.addLayer({
        id: "hub-points",
        type: "circle",
        source: "hub-points",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["get", "r"], 10, 6, 50, 22],
          "circle-color": ["get", "color"],
          "circle-opacity": 0.5,
          "circle-stroke-width": 1.6,
          "circle-stroke-color": ["get", "color"],
        },
      });

      const bounds = new LngLatBounds();
      bubbles.forEach((b) => {
        const [lng, lat] = getNode(b.node_id);
        bounds.extend([lng, lat]);
      });
      if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: 70, maxZoom: 5 });
    };

    if (map.isStyleLoaded()) draw();
    else map.once("load", draw);
  }, [bubbles]);

  return <div ref={containerRef} className="network-hub-map" />;
}

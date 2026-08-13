import { useEffect, useRef } from "react";
import { Map as MapLibreMap, LngLatBounds, type Map as MapLibreMapType } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { getNode } from "../lib/YP_worldmap";
import type { RouteResponse } from "../api/HS_controlTowerApi";
import { ypSeaGeometry } from "../lib/YP_seaRoutes";

const STYLE_URL = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

export function RouteMapLibre({ route }: { route?: RouteResponse | null }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMapType | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    mapRef.current = new MapLibreMap({
      container: containerRef.current,
      style: STYLE_URL,
      center: [20, 30],
      zoom: 1.5,
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
    if (!map || !route || route.legs.length === 0) return;

    const draw = () => {
      ["route-done", "route-active", "route-pending", "route-nodes"].forEach((id) => {
        if (map.getLayer(id)) map.removeLayer(id);
      });
      ["route-lines", "route-points"].forEach((id) => {
        if (map.getSource(id)) map.removeSource(id);
      });

      const lineFeatures = route.legs.map((leg) => {
        const from = getNode(leg.from.node_id);
        const to = getNode(leg.to.node_id);
        return {
          type: "Feature" as const,
          properties: { state: leg.state, color: leg.color },
          geometry: leg.mode === "sea" ? ypSeaGeometry([from[0], from[1]], [to[0], to[1]]) : { type: "LineString" as const, coordinates: [[from[0], from[1]], [to[0], to[1]]] },
        };
      });
      map.addSource("route-lines", { type: "geojson", data: { type: "FeatureCollection", features: lineFeatures } });

      map.addLayer({
        id: "route-done", type: "line", source: "route-lines",
        filter: ["==", ["get", "state"], "done"],
        paint: { "line-color": ["get", "color"], "line-width": 3 },
      });
      map.addLayer({
        id: "route-active", type: "line", source: "route-lines",
        filter: ["==", ["get", "state"], "active"],
        paint: { "line-color": ["get", "color"], "line-width": 3.5 },
      });
      map.addLayer({
        id: "route-pending", type: "line", source: "route-lines",
        filter: ["==", ["get", "state"], "pending"],
        paint: { "line-color": ["get", "color"], "line-width": 2, "line-opacity": 0.5 },
      });

      const nodeMap = new Map<string, [number, number]>();
      route.legs.forEach((l) => {
        nodeMap.set(l.from.node_id, [getNode(l.from.node_id)[0], getNode(l.from.node_id)[1]]);
        nodeMap.set(l.to.node_id, [getNode(l.to.node_id)[0], getNode(l.to.node_id)[1]]);
      });
      const pointFeatures = Array.from(nodeMap.entries()).map(([id, [lng, lat]]) => ({
        type: "Feature" as const,
        properties: { id },
        geometry: { type: "Point" as const, coordinates: [lng, lat] },
      }));
      map.addSource("route-points", { type: "geojson", data: { type: "FeatureCollection", features: pointFeatures } });
      map.addLayer({
        id: "route-nodes", type: "circle", source: "route-points",
        paint: { "circle-radius": 5, "circle-color": "#7FB6F5", "circle-stroke-width": 1.5, "circle-stroke-color": "#fff" },
      });

      const bounds = new LngLatBounds();
      lineFeatures.forEach((feature) => {
        const sections = feature.geometry.type === "MultiLineString"
          ? feature.geometry.coordinates
          : [feature.geometry.coordinates];
        sections.forEach((section) => section.forEach((coordinate) => bounds.extend(coordinate as [number, number])));
      });
      if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: 60, maxZoom: 6 });
    };

    if (map.isStyleLoaded()) draw();
    else map.once("load", draw);
  }, [route]);

  return <div ref={containerRef} style={{ width: "100%", height: "100%", minHeight: 420, borderRadius: 12, overflow: "hidden" }} />;
}

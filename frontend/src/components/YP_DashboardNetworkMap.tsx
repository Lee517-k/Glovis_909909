import { useEffect, useRef, useState } from "react";
import { LngLatBounds, Map as MapLibreMap, NavigationControl, type Map as MapType } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { getNode } from "../lib/YP_worldmap";
import { ypSeaGeometry } from "../lib/YP_seaRoutes";

export type DashboardRoute = { origin_node_id:string;origin_name:string;destination_node_id:string;destination_name:string;mode:string;shipment_id?:string|null };
const COLORS:Record<string,string>={sea:"#31A8FF",rail:"#32E0A1",air:"#B388FF",road:"#FFB84D",truck:"#FFB84D"};

export function YPDashboardNetworkMap({routes,visibleModes}:{routes:DashboardRoute[];visibleModes:string[]}) {
  const el=useRef<HTMLDivElement>(null),map=useRef<MapType|null>(null);
  const [selectedShipment,setSelectedShipment]=useState<string|null>(null);
  useEffect(()=>{const select=(event:Event)=>setSelectedShipment((event as CustomEvent<{shipmentId:string|null}>).detail.shipmentId);window.addEventListener("dashboard:shipment-selected",select);return()=>window.removeEventListener("dashboard:shipment-selected",select)},[]);
  useEffect(()=>{if(!el.current||map.current)return;map.current=new MapLibreMap({container:el.current,style:"https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",center:[25,30],zoom:1.25,renderWorldCopies:false});map.current.addControl(new NavigationControl({showCompass:false}),"top-right");return()=>{map.current?.remove();map.current=null}},[]);
  useEffect(()=>{const m=map.current;if(!m)return;const draw=()=>{
    ["yp-routes","yp-nodes"].forEach(id=>{if(m.getLayer(id))m.removeLayer(id)});["yp-route-source","yp-node-source"].forEach(id=>{if(m.getSource(id))m.removeSource(id)});
    const filtered=routes.filter(route=>selectedShipment?route.shipment_id===selectedShipment:!route.shipment_id&&visibleModes.includes(route.mode==="road"?"truck":route.mode));
    const bounds=new LngLatBounds();
    const lines=filtered.map(route=>{const from=getNode(route.origin_node_id),to=getNode(route.destination_node_id);bounds.extend(from);bounds.extend(to);return{type:"Feature" as const,properties:{color:COLORS[route.mode]??"#79A8D8"},geometry:route.mode==="sea"?ypSeaGeometry(from,to):{type:"LineString" as const,coordinates:[from,to]}}});
    m.addSource("yp-route-source",{type:"geojson",data:{type:"FeatureCollection",features:lines}});m.addLayer({id:"yp-routes",type:"line",source:"yp-route-source",paint:{"line-color":["get","color"],"line-width":2.8,"line-opacity":.9,"line-dasharray":[1.2,2]}});
    const nodes=new Map<string,{point:[number,number],color:string}>();filtered.forEach(route=>{nodes.set(route.origin_node_id,{point:getNode(route.origin_node_id),color:COLORS[route.mode]});nodes.set(route.destination_node_id,{point:getNode(route.destination_node_id),color:COLORS[route.mode]})});
    const points=[...nodes.entries()].map(([id,node])=>({type:"Feature" as const,properties:{id,color:node.color},geometry:{type:"Point" as const,coordinates:node.point}}));m.addSource("yp-node-source",{type:"geojson",data:{type:"FeatureCollection",features:points}});m.addLayer({id:"yp-nodes",type:"circle",source:"yp-node-source",paint:{"circle-radius":5,"circle-color":["get","color"],"circle-stroke-width":1.6,"circle-stroke-color":"#fff"}});if(!bounds.isEmpty())m.fitBounds(bounds,{padding:70,maxZoom:selectedShipment?5.5:4.6})};
    if(m.isStyleLoaded())draw();else m.once("load",draw)
  },[routes,visibleModes,selectedShipment]);
  return <div ref={el} className="yp-dashboard-network-map"/>;
}

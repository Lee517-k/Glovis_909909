export const NODE: Record<string, [number, number]> = {
  KRPUS:[129.04,35.1], KRINC:[126.6,37.45], KRICN:[126.44,37.46], KRUSN:[129.39,35.5],
  DEHAM:[9.98,53.54], DEBRV:[8.58,53.54], DEDUI:[6.76,51.43], DEMUC:[11.58,48.14], DEFRA:[8.56,50.04],
  NLRTM:[4.14,51.95], CNSHA:[121.47,31.23], CNQIN:[120.38,36.07], SGSIN:[103.85,1.29],
  ATVIE:[16.57,48.11], ITGOA:[8.93,44.41], USLAX:[-118.25,33.74], AEJEA:[55.06,25], GBFXT:[1.29,51.95],
};
export function getNode(id: string): [number, number] {
  const base = id.replace(/_(RAIL|YARD|DC)$/, "");
  return NODE[id] ?? NODE[base] ?? [20,25];
}

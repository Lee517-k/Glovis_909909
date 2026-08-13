import json, math, os, glob, shutil
from collections import defaultdict

SRC = "."
OUT = "merged"

# ══════════════════════════════════════════════
# 1) 노드 좌표 사전 (거리 계산용) — 내가 만든 것에서 가져옴
# ══════════════════════════════════════════════
COORD = {
    # 한국
    "KRUSN": (35.54, 129.31, "KR"), "KRPUS": (35.18, 129.08, "KR"),
    "KRINC": (37.46, 126.63, "KR"), "KRPTK": (36.97, 126.82, "KR"),
    "KRGJU": (35.16, 126.85, "KR"), "KRHWA": (37.20, 126.83, "KR"),
    "KRICH": (37.55, 126.74, "KR"), "KRSEL": (37.57, 126.98, "KR"),
    # 중국·일본·동남아
    "CNSHA": (31.23, 121.47, "CN"), "CNNGB": (29.87, 121.54, "CN"),
    "CNTAO": (36.07, 120.38, "CN"), "CNGZH": (23.13, 113.26, "CN"),
    "JPNGO": (35.09, 136.85, "JP"), "JPYOK": (35.44, 139.64, "JP"),
    "SGSIN": (1.35, 103.82, "SG"), "VNHAN": (21.03, 105.85, "VN"),
    "THBKK": (13.76, 100.50, "TH"),
    # 유럽 항만
    "NLRTM": (51.92, 4.48, "NL"), "DEBRV": (53.54, 8.58, "DE"),
    "DEHAM": (53.55, 9.99, "DE"), "BEANR": (51.22, 4.40, "BE"),
    "BEZEE": (51.33, 3.21, "BE"), "FRLEH": (49.49, 0.11, "FR"),
    "ESVLC": (39.45, -0.33, "ES"), "ITGOA": (44.41, 8.93, "IT"),
    "PLGDN": (54.35, 18.65, "PL"), "SEGOT": (57.71, 11.97, "SE"),
    "GBSOU": (50.90, -1.40, "GB"), "SIKOP": (45.55, 13.73, "SI"),
    # 유럽 내륙
    "DEMUC": (48.14, 11.58, "DE"), "DEDUI": (51.43, 6.76, "DE"),
    "DEFRA": (50.11, 8.68, "DE"), "DEKOL": (50.94, 6.96, "DE"),
    "DELEI": (51.34, 12.37, "DE"), "DESTR": (48.78, 9.18, "DE"),
    "ATVIE": (48.21, 16.37, "AT"), "CZPRG": (50.08, 14.44, "CZ"),
    "PLWAW": (52.23, 21.01, "PL"), "ITVER": (45.44, 10.99, "IT"),
    "ITMIL": (45.46, 9.19, "IT"), "ESMAD": (40.42, -3.70, "ES"),
    "FRPAR": (48.86, 2.35, "FR"), "HUBUD": (47.50, 19.04, "HU"),
    "SKBTS": (48.15, 17.11, "SK"),
    # 공항 (도시 좌표 사용)
    "ICN": (37.46, 126.44, "KR"), "PVG": (31.14, 121.81, "CN"),
    "NRT": (35.76, 140.39, "JP"), "SIN": (1.36, 103.99, "SG"),
    "HAN": (21.22, 105.81, "VN"), "BKK": (13.69, 100.75, "TH"),
    "FRA": (50.03, 8.56, "DE"), "MUC": (48.35, 11.79, "DE"),
    "AMS": (52.31, 4.76, "NL"), "CDG": (49.01, 2.55, "FR"),
    "BRU": (50.90, 4.48, "BE"), "VIE": (48.11, 16.57, "AT"),
    "MXP": (45.63, 8.72, "IT"), "MAD": (40.47, -3.56, "ES"),
    "PRG": (50.10, 14.26, "CZ"), "WAW": (52.17, 20.97, "PL"),
    "LHR": (51.47, -0.45, "GB"),
    "HKG": (22.31, 113.91, "HK"), "KIX": (34.43, 135.24, "JP"),
    "TRIST": (45.65, 13.77, "IT"), "ROCUR": (44.18, 28.65, "RO"),
    "SIKOP": (45.55, 13.73, "SI"), "ESBCN": (41.39, 2.17, "ES"),
}

EU = {"NL","DE","BE","FR","ES","IT","PL","SE","GB","SI","AT","CZ","HU","SK","RO"}
ASIA = {"KR","CN","JP","SG","VN","TH","HK"}


def base_loc(node_id):
    """node_id → 좌표 키"""
    if node_id in COORD:
        return node_id
    for suf in ("_YARD", "_RAIL", "_DC", "_WH", "_PLANT", "_PORT"):
        if node_id.endswith(suf):
            b = node_id[: -len(suf)]
            if b in COORD:
                return b
    return None


def hav(a, b):
    ka, kb = base_loc(a), base_loc(b)
    if not ka or not kb:
        return None
    la1, lo1, _ = COORD[ka]; la2, lo2, _ = COORD[kb]
    R = 6371
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = math.radians(la2-la1), math.radians(lo2-lo1)
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(h))


def country(node_id):
    k = base_loc(node_id)
    return COORD[k][2] if k else None


# ══════════════════════════════════════════════
# 2) 파일 로드
# ══════════════════════════════════════════════
files = {}
for f in glob.glob(f"{SRC}/*/*.json"):
    files[f] = json.load(open(f, encoding="utf-8"))

removed, fixed = [], []

for path, d in files.items():
    if "services" not in d:
        continue
    grp = d["carrier"]["group"]
    keep = []

    for s in d["services"]:
        o, dst = s["origin"]["node_id"], s["destination"]["node_id"]
        co, cd = country(o), country(dst)

        # ── 육상(도로·철도)에서 대륙 간 링크 제거
        if grp in ("road", "rail"):
            if co and cd:
                cross_continent = (co in ASIA and cd in EU) or (co in EU and cd in ASIA)
                if cross_continent:
                    removed.append((grp, d["carrier"]["carrier_name"],
                                    s["service_id"], f"{o}→{dst}", "대륙 간 육로 불가"))
                    continue
            # service_area 국가 제약 위반 제거
            sa = s.get("service_area", {}).get("countries")
            if sa and cd and cd not in sa and not s.get("mode_details", {}).get("cross_border_available"):
                removed.append((grp, d["carrier"]["carrier_name"],
                                s["service_id"], f"{o}→{dst}",
                                f"서비스지역{sa} 벗어남 + 국경통과 불가"))
                continue

        # ── 거리 부여
        km = hav(o, dst)
        if km is None:
            removed.append((grp, d["carrier"]["carrier_name"],
                            s["service_id"], f"{o}→{dst}", "좌표 미상"))
            continue
        mult = {"road": 1.28, "rail": 1.35, "sea": 1.85, "air": 1.05}[grp]
        km = round(km * mult)
        s["distance_km"] = km

        # ── 도로: 소요시간 계산해 넣기
        if grp == "road":
            sc = s["schedule"]
            spd = sc.get("average_speed_kmh", 60)
            maxh = sc.get("max_driving_hours_per_day", 9)
            drive_h = km / spd
            days = drive_h / maxh + sc.get("dispatch_lead_hours", 12) / 24
            sc["transit_days"] = round(days, 2)
            sc["driving_hours_total"] = round(drive_h, 1)
            sc["frequency_per_week"] = 7
            sc["average_wait_days"] = round(sc.get("dispatch_lead_hours", 12) / 24, 2)
            fixed.append(("road_transit", s["service_id"], f"{km}km → {days:.1f}일"))

        # ── 시간 단위 통일: 모든 수단에 transit_days / wait_days
        sc = s["schedule"]
        if "transit_days" not in sc and "transit_hours" in sc:
            sc["transit_days"] = round(sc["transit_hours"] / 24, 2)
        if "average_wait_days" not in sc and "average_wait_hours" in sc:
            sc["average_wait_days"] = round(sc["average_wait_hours"] / 24, 2)
        sc["total_days_with_wait"] = round(sc.get("transit_days", 0)
                                           + sc.get("average_wait_days", 0), 2)

        # ── 비용 단위 통일: cost_usd_per_vehicle 파생
        p = s["pricing"]
        if p.get("rate_per_vehicle"):
            unit = p["rate_per_vehicle"]
        elif p.get("rate_per_kg"):
            unit = round(p["rate_per_kg"] * 1700, 1)          # 세단 1.7톤 기준
        elif p.get("rate_per_transporter"):
            cap = 5
            for f_ in s.get("fleet", []):
                cap = f_.get("vehicle_capacity", 5); break
            extra = max(0, km - p.get("included_distance_km", 0)) * p.get("additional_rate_per_km", 0)
            unit = round((p["rate_per_transporter"] + extra) / cap, 1)
        elif p.get("rate_per_wagon"):
            unit = round(p["rate_per_wagon"] / 8, 1)          # 차량당 8대
        else:
            unit = None
        p["cost_usd_per_vehicle"] = unit

        # ── 할증 반영 총액
        sur = 0.0
        pct = 0.0
        for x in s.get("surcharges", []):
            if x["basis"] == "per_vehicle": sur += x["amount"]
            elif x["basis"] == "per_km":    sur += x["amount"] * km / 5
            elif x["basis"] == "percentage": pct += x["amount"]
        if unit is not None:
            p["cost_usd_per_vehicle_all_in"] = round((unit + sur) * (1 + pct), 1)

        # ── 탄소 통일 (GLEC 기준 g/톤-km)
        g = {"sea": 8.4, "rail": 11.0, "road": 63.0, "air": 540.0}[grp]
        s["environment"]["co2_g_per_tonkm"] = g
        s["environment"]["co2_kg_per_vehicle"] = round(km * 1.7 * g / 1000, 1)

        keep.append(s)

    d["services"] = keep
    d["metadata"]["record_count"] = len(keep)

print("=== 제거된 서비스 ===")
for r in removed:
    print(f"  [{r[0]:4}] {r[2]:26} {r[3]:28} {r[4]}")
print(f"  총 {len(removed)}건 제거")
print(f"\n=== 도로 소요시간 부여 {len(fixed)}건 ===")
for f in fixed[:5]:
    print(f"  {f[1]:16} {f[2]}")

os.makedirs(OUT, exist_ok=True)
for path, d in files.items():
    rel = os.path.relpath(path, SRC)
    dst = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    json.dump(d, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\n{OUT}/ 에 저장")

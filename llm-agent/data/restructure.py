"""
구조 정리:
  해운  → 현대글로비스 단독 (자사 PCTC 선대)
  철도  → DB Cargo, Rail Cargo Group (파트너)
  트럭  → 국내 2사 + 유럽 2사 (파트너)
  항공  → 유지 (부품 긴급용)

이유: 글로비스는 PCTC를 직접 운항하는 선사다.
      남의 배를 쓰고 자기는 트럭만 모는 구조는 현실과 반대다.
"""
import json, glob, os, math, random

random.seed(7)
COORD = json.load(open("coords.json", encoding="utf-8"))


def base(n):
    for s in ("_YARD", "_RAIL", "_DC", "_WH", "_PLANT"):
        if n.endswith(s):
            return n[:-len(s)]
    return n


def hav(a, b):
    ka, kb = base(a), base(b)
    if ka not in COORD or kb not in COORD:
        return None
    la1, lo1 = COORD[ka][:2]; la2, lo2 = COORD[kb][:2]
    R = 6371
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = math.radians(la2 - la1), math.radians(lo2 - lo1)
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(h))


# ══════════════════════════════════════════════
# 1) 해운: HMM·WW 완성차 노선 → 글로비스로 통합
# ══════════════════════════════════════════════
sea_services = []
for f in ["sea_hmm.json", "sea_wallenius_wilhelmsen.json"]:
    d = json.load(open(f, encoding="utf-8"))
    for s in d["services"]:
        if s.get("carries_finished_vehicle"):
            sea_services.append(s)

# 중복 노선 제거 (같은 구간·티어는 하나만)
seen = {}
for s in sea_services:
    k = (s["origin"]["node_id"], s["destination"]["node_id"],
         s.get("service_tier", "STANDARD"))
    if k not in seen or (s["pricing"].get("cost_usd_per_vehicle_all_in") or 9e9) < \
       (seen[k]["pricing"].get("cost_usd_per_vehicle_all_in") or 9e9):
        seen[k] = s
sea_services = list(seen.values())

VESSELS = ["GLOVIS SUPERIOR", "GLOVIS SPLENDOR", "GLOVIS COMPOSER",
           "GLOVIS CARDINAL", "GLOVIS SYMPHONY", "GLOVIS CENTURY"]

for i, s in enumerate(sea_services, 1):
    o, dd = s["origin"]["node_id"], s["destination"]["node_id"]
    tier = s.get("service_tier", "STANDARD")
    suf = {"STANDARD": "", "EXPRESS": "-EXP", "ECONOMY": "-ECO"}[tier]
    s["service_id"] = f"GLV-PCTC-{o}-{dd}-{i:03d}{suf}"
    s["vessel_name"] = VESSELS[i % len(VESSELS)]
    s["service_type"] = "pure_car_truck_carrier"
    # 자사 선대라 신뢰도 소폭 상향
    pf = s["performance"]
    pf["on_time_rate"] = round(min(0.97, pf.get("on_time_rate", 0.9) + 0.02), 3)
    pf["delay_probability"] = round((1 - pf["on_time_rate"]) * 1.35, 3)
    pf["reliability_source"] = "measured"
    s.setdefault("capacity", {})
    s["capacity"].setdefault("capacity_type", "vehicle_slot")
    s["capacity"].setdefault("available_vehicle_slots", 7000)
    s["capacity"]["deck_count"] = 12
    s["capacity"]["max_deck_clearance_m"] = 5.2

glovis_sea = {
    "metadata": {
        "dataset_id": "carrier_sea_hyundai_glovis",
        "description": "현대글로비스 자동차운반선(PCTC) 서비스",
        "record_count": len(sea_services),
        "currency": "USD",
        "synthetic_demo_data": True,
    },
    "carrier": {
        "carrier_id": "HYUNDAI_GLOVIS_SEA",
        "carrier_name": "Hyundai Glovis",
        "group": "sea",
        "role": "OWN_FLEET",
        "note": "자사 PCTC 선대 운항. 육상 구간은 파트너 운송사를 이용한다.",
    },
    "services": sea_services,
}
json.dump(glovis_sea, open("sea_hyundai_glovis.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
os.remove("sea_hmm.json")
os.remove("sea_wallenius_wilhelmsen.json")
print(f"해운 → 현대글로비스 단독 {len(sea_services)}건 "
      f"(HMM·WW 통합, 부품·일반화물 제외)")


# ══════════════════════════════════════════════
# 2) 국내 트럭 운송사 2곳 신설
# ══════════════════════════════════════════════
KR_PLANTS = ["KRUSN_YARD", "KRHWA_PLANT", "KRGJU_PLANT", "KRICH_WH", "KRSEL"]
KR_PORTS = ["KRUSN", "KRPUS", "KRPTK", "KRINC"]

DOMESTIC = [
    dict(cid="KOREA_CARLINE", name="한국카라인",
         file="road_korea_carline.json",
         base=142.0, rate=1.18, cap=8, speed=58, otr=0.96,
         co2=64, note="완성차 전용 캐리어. 공장-항만 셔틀 특화"),
    dict(cid="DAEHAN_TRANS", name="대한운수",
         file="road_daehan_trans.json",
         base=128.0, rate=1.09, cap=7, speed=55, otr=0.93,
         co2=67, note="중소 물량 대응. 단가 경쟁력"),
]

for ci, c in enumerate(DOMESTIC):
    svc = []
    n = 0
    for o in KR_PLANTS:
        for p in KR_PORTS:
            km = hav(o, p)
            if km is None or km < 15:
                continue
            km = round(km * 1.28)
            if km > 500:
                continue
            n += 1
            drive = km / c["speed"]
            days = round((6 + drive) / 24, 2)
            wait = 0.4 + ci * 0.2
            per_truck = c["base"] + c["rate"] * km
            unit = round(per_truck / c["cap"], 1)
            allin = round((unit + 0.07 * km / c["cap"]) * 1.09, 1)
            for tier, cm, tm in [("STANDARD", 1.0, 1.0), ("EXPRESS", 1.26, 0.8)]:
                suf = "" if tier == "STANDARD" else "-EXP"
                svc.append({
                    "service_id": f"{c['cid'][:3]}-KR-{o}-{p}-{n:02d}{suf}",
                    "service_type": "car_carrier",
                    "service_tier": tier,
                    "origin": {"node_id": o, "name": o, "country": "KR",
                               "node_type": ("vehicle_yard" if o.endswith("_YARD")
                                             else "plant" if o.endswith("_PLANT")
                                             else "warehouse" if o.endswith("_WH")
                                             else "distribution_center"),
                               "location_id": base(o)},
                    "destination": {"node_id": p, "name": p, "country": "KR",
                                    "node_type": "seaport", "location_id": p},
                    "distance_km": km,
                    "service_area": {"countries": ["KR"], "max_distance_km": 500},
                    "schedule": {
                        "dispatch_lead_hours": 6,
                        "average_speed_kmh": c["speed"],
                        "max_driving_hours_per_day": 9,
                        "transit_days": round(days * tm, 2),
                        "driving_hours_total": round(drive, 1),
                        "frequency_per_week": 7,
                        "average_wait_days": round(wait * (0.6 if tier == "EXPRESS" else 1.0), 2),
                        "total_days_with_wait": round(days * tm + wait * (0.6 if tier == "EXPRESS" else 1.0), 2),
                        "transit_days_p90": round((days * tm + wait) * 1.12, 2),
                        "border_crossings": 0,
                        "booking_lead_days": 1, "cargo_closing_hours": 8,
                    },
                    "fleet": [{"vehicle_type": "CAR_CARRIER", "available_count": 14,
                               "vehicle_capacity": c["cap"], "max_vehicle_height_m": 2.2}],
                    "pricing": {
                        "pricing_model": "per_transporter", "currency": "USD",
                        "rate_per_transporter": round(per_truck * cm, 1),
                        "cost_usd_per_vehicle": round(unit * cm, 1),
                        "cost_usd_per_vehicle_all_in": round(allin * cm, 1),
                        "min_charge_usd": round(allin * cm * 0.85, 1),
                        "rate_validity_type": "QUARTERLY",
                        "valid_from": "2026-07-01", "valid_to": "2026-09-30",
                        "days_until_expiry": 54,
                    },
                    "surcharges": [
                        {"name": "TOLL", "basis": "per_km", "amount": 0.07,
                         "currency": "USD"},
                        {"name": "FUEL_ADJUSTMENT", "basis": "percentage",
                         "amount": 0.09, "currency": "RATIO"}],
                    "cargo_conditions": {
                        "allowed_cargo_types": ["FINISHED_VEHICLE"],
                        "allowed_vehicle_types": ["SEDAN", "SUV", "EV", "LIGHT_COMMERCIAL"],
                        "operable_vehicle_required": True},
                    "mode_details": {"cross_border_available": False,
                                     "gps_tracking": True},
                    "dwell": {"free_time_days": 2, "demurrage_usd_per_unit_day": 0,
                              "detention_usd_per_unit_day": 15},
                    "performance": {
                        "on_time_rate": round(min(0.985, c["otr"] * (1.03 if tier == "EXPRESS" else 1.0)), 3),
                        "damage_rate": 0.0018 + ci * 0.0006,
                        "cancellation_rate": 0.012 + ci * 0.005,
                        "delay_probability": round((1 - c["otr"]) * 1.35, 3),
                        "reliability_source": "measured",
                        "on_time_sample_size": 380 - ci * 110},
                    "environment": {"grade": "C", "co2_g_per_tonkm": c["co2"],
                                    "co2_kg_per_vehicle": round(km * 1.7 * c["co2"] / 1000, 1)},
                    "carries_finished_vehicle": True,
                })

    json.dump({
        "metadata": {"dataset_id": f"carrier_road_{c['cid'].lower()}",
                     "description": c["note"], "record_count": len(svc),
                     "currency": "USD", "synthetic_demo_data": True},
        "carrier": {"carrier_id": c["cid"], "carrier_name": c["name"],
                    "group": "road", "role": "PARTNER",
                    "service_scope": "DOMESTIC_KR", "note": c["note"]},
        "services": svc,
    }, open(c["file"], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"국내 트럭 신설: {c['name']:10} {len(svc)}건")


# ══════════════════════════════════════════════
# 3) 글로비스 도로 → 유럽 파트너로 이름 변경
# ══════════════════════════════════════════════
d = json.load(open("road_hyundai_glovis.json", encoding="utf-8"))
kr = [s for s in d["services"]
      if s["origin"].get("country") == "KR" and s["destination"].get("country") == "KR"]
eu = [s for s in d["services"] if s not in kr]
d["services"] = eu
d["carrier"] = {
    "carrier_id": "EUROTRANS_AUTO",
    "carrier_name": "EuroTrans Auto",
    "group": "road",
    "role": "PARTNER",
    "service_scope": "EUROPE",
    "note": "유럽 완성차 육상운송 파트너. 항만·철도터미널에서 딜러망까지",
}
d["metadata"]["dataset_id"] = "carrier_road_eurotrans_auto"
d["metadata"]["record_count"] = len(eu)
json.dump(d, open("road_eurotrans_auto.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
os.remove("road_hyundai_glovis.json")
print(f"유럽 트럭: EuroTrans Auto {len(eu)}건 (국내 {len(kr)}건은 신설 2사로 대체)")

print("\n=== 최종 구조 ===")
for f in sorted(glob.glob("*.json")):
    if f in {"coords.json", "transfer_rules.json", "customs_rules.json", "incoterms.json"}:
        continue
    j = json.load(open(f, encoding="utf-8"))
    if "services" not in j:
        continue
    c = j["carrier"]
    print(f"  {c['group']:5} {c['carrier_name']:24} {c.get('role','-'):10} {len(j['services']):3}건")

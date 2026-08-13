import json, glob, math
from collections import defaultdict

COORD = json.load(open("coords.json", encoding="utf-8"))

def hav(a, b):
    la1, lo1 = COORD[a][:2]; la2, lo2 = COORD[b][:2]
    R = 6371
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = math.radians(la2-la1), math.radians(lo2-lo1)
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(h))

def base(n):
    for suf in ("_YARD","_RAIL","_DC","_WH","_PLANT"):
        if n.endswith(suf): return n[:-len(suf)]
    return n

# ── 완성차 도로 마지막구간 (항만/철도역 → 딜러망·야드)
LASTMILE = [
    # (from, to)  유럽 내 완성차 배송
    ("DEMUC_RAIL","DEMUC_YARD"), ("DEHAM","DEMUC_YARD"), ("DEBRV","DEMUC_YARD"),
    ("NLRTM","DEMUC_YARD"), ("BEANR","DEMUC_YARD"),
    ("ESMAD_DC","ESMAD_DC"),
    ("NLRTM","ESMAD_DC"), ("ITGOA","ESMAD_DC"), ("ESVLC","ESMAD_DC"),
    ("DEHAM","CZPRG_DC"), ("DEBRV","CZPRG_DC"), ("PLGDN","CZPRG_DC"),
    ("CZPRG_RAIL","CZPRG_DC"), ("PLWAW_RAIL","PLWAW_DC"),
    ("NLRTM","FRPAR_DC"), ("BEANR","FRPAR_DC"),
    ("ITGOA","ITMIL_DC"), ("SIKOP","ITMIL_DC"),
    ("DEHAM","DEFRA_DC"), ("DEBRV","DELEI_DC"),
    ("ATVIE_RAIL","ATVIE_DC"), ("DEDUI_RAIL","DEDUI_DC"),
    ("DEFRA_RAIL","DEFRA_DC"), ("DEKOL_RAIL","DEDUI_DC"),
    ("HUBUD_RAIL","ATVIE_DC"),
    # 한국 내륙 (공장 → 항만)
    ("KRHWA_PLANT","KRPUS"), ("KRHWA_PLANT","KRUSN"),
    ("KRGJU_PLANT","KRPUS"), ("KRGJU_PLANT","KRUSN"),
    ("KRUSN_YARD","KRUSN"), ("KRPUS","KRUSN"),
    ("KRHWA_PLANT","KRINC"), ("KRGJU_PLANT","KRHWA_PLANT"),
]

# ── 완성차 철도 보완 (항만역 → 내륙역)
RAIL_ADD = [
    ("NLRTM_RAIL","DEMUC_RAIL"), ("DEHAM_RAIL","DEMUC_RAIL"),
    ("DEBRV_RAIL","DEMUC_RAIL"), ("BEANR_RAIL","DEMUC_RAIL"),
    ("NLRTM_RAIL","CZPRG_RAIL"), ("DEHAM_RAIL","CZPRG_RAIL"),
    ("NLRTM_RAIL","PLWAW_RAIL"), ("PLGDN_RAIL","PLWAW_RAIL"),
    ("NLRTM_RAIL","ITVER_RAIL"), ("ITGOA_RAIL","ITVER_RAIL"),
    ("NLRTM_RAIL","ATVIE_RAIL"), ("DEHAM_RAIL","ATVIE_RAIL"),
    ("BEANR_RAIL","DEFRA_RAIL"), ("NLRTM_RAIL","DEKOL_RAIL"),
    ("NLRTM_RAIL","DEFRA_RAIL"), ("DEBRV_RAIL","DEKOL_RAIL"),
]

road_new, rail_new = [], []

for i, (o, dd) in enumerate(LASTMILE, 1):
    if o == dd: continue
    bo, bd = base(o), base(dd)
    if bo not in COORD or bd not in COORD: continue
    km = round(hav(bo, bd) * 1.28)
    if km == 0: km = 15
    spd, maxh, lead = 60, 9, 12
    drive = km / spd
    days = round(drive / maxh + lead/24, 2)
    cap = 8
    rate = 1500.0 + max(0, km - 500) * 1.55
    unit = round(rate / cap, 1)
    sur = 0.09 * km / cap
    road_new.append({
        "service_id": f"GLV-FVL-{i:02d}",
        "service_type": "car_carrier",
        "origin": {"node_id": o, "name": o, "country": COORD[bo][2],
                   "node_type": ("seaport" if bo==o and len(o)==5 else
                                 "rail_terminal" if o.endswith("_RAIL") else
                                 "distribution_center" if o.endswith("_DC") else
                                 "vehicle_yard" if o.endswith("_YARD") else
                                 "plant" if o.endswith("_PLANT") else
                                 "warehouse" if o.endswith("_WH") else "seaport"),
                   "location_id": bo},
        "destination": {"node_id": dd, "name": dd, "country": COORD[bd][2],
                        "node_type": ("seaport" if bd==dd and len(dd)==5 else
                                      "rail_terminal" if dd.endswith("_RAIL") else
                                      "distribution_center" if dd.endswith("_DC") else
                                      "vehicle_yard" if dd.endswith("_YARD") else
                                      "plant" if dd.endswith("_PLANT") else
                                      "warehouse" if dd.endswith("_WH") else "seaport"),
                        "location_id": bd},
        "distance_km": km,
        "service_area": {"countries": sorted({COORD[bo][2], COORD[bd][2]}),
                         "max_distance_km": 1500},
        "schedule": {"dispatch_lead_hours": lead, "average_speed_kmh": spd,
                     "max_driving_hours_per_day": maxh,
                     "transit_days": days, "driving_hours_total": round(drive,1),
                     "frequency_per_week": 7,
                     "average_wait_days": round(lead/24, 2),
                     "total_days_with_wait": round(days + lead/24, 2)},
        "fleet": [{"vehicle_type": "CAR_CARRIER", "available_count": 6,
                   "vehicle_capacity": cap, "max_vehicle_height_m": 2.2}],
        "pricing": {"pricing_model": "per_transporter", "currency": "USD",
                    "rate_per_transporter": round(rate,1),
                    "included_distance_km": 500,
                    "additional_rate_per_km": 1.55,
                    "cost_usd_per_vehicle": unit,
                    "cost_usd_per_vehicle_all_in": round((unit + sur) * 1.106, 1)},
        "surcharges": [{"name":"TOLL","basis":"per_km","amount":0.09,"currency":"USD"},
                       {"name":"FUEL_ADJUSTMENT","basis":"percentage","amount":0.106,"currency":"RATIO"}],
        "cargo_conditions": {"allowed_cargo_types": ["FINISHED_VEHICLE"],
                             "allowed_vehicle_types": ["SEDAN","SUV","EV","LIGHT_COMMERCIAL"],
                             "operable_vehicle_required": True},
        "mode_details": {"cross_border_available": COORD[bo][2] != COORD[bd][2],
                         "gps_tracking": True, "enclosed_transport_available": True},
        "performance": {"on_time_rate": 0.96, "damage_rate": 0.0022,
                        "cancellation_rate": 0.015},
        "environment": {"grade": "C", "co2_g_per_tonkm": 63.0,
                        "co2_kg_per_vehicle": round(km*1.7*63/1000,1)},
        "carries_finished_vehicle": True,
    })

for i, (o, dd) in enumerate(RAIL_ADD, 1):
    bo, bd = base(o), base(dd)
    if bo not in COORD or bd not in COORD: continue
    km = round(hav(bo, bd) * 1.35)
    transit = round(km/42/24 + 0.5, 2)
    wait = 1.8
    unit = round((16.0 + 0.082*km), 1)
    rail_new.append({
        "service_id": f"DBC-FVL-{i:02d}",
        "service_type": "automotive_block_train",
        "origin": {"node_id": o, "name": o, "country": COORD[bo][2],
                   "node_type": "rail_terminal", "location_id": bo},
        "destination": {"node_id": dd, "name": dd, "country": COORD[bd][2],
                        "node_type": "rail_terminal", "location_id": bd},
        "distance_km": km,
        "schedule": {"departure_days": ["MON","WED","FRI"],
                     "frequency_per_week": 3,
                     "transit_hours": round(transit*24),
                     "transit_days": transit,
                     "average_wait_hours": round(wait*24),
                     "average_wait_days": wait,
                     "total_days_with_wait": round(transit+wait, 2)},
        "capacity": {"capacity_type": "vehicle_slot",
                     "available_vehicle_slots": 176,
                     "wagons_per_train": 22, "vehicles_per_wagon": 8},
        "pricing": {"pricing_model": "per_vehicle", "currency": "USD",
                    "rate_per_vehicle": unit,
                    "cost_usd_per_vehicle": unit,
                    "cost_usd_per_vehicle_all_in": round(unit + 35, 1)},
        "surcharges": [{"name":"TERMINAL_HANDLING","basis":"per_vehicle",
                        "amount":35.0,"currency":"USD"}],
        "cargo_conditions": {"allowed_cargo_types": ["FINISHED_VEHICLE"],
                             "allowed_vehicle_types": ["SEDAN","SUV","EV"],
                             "operable_vehicle_required": True},
        "mode_details": {"gauge_change_required": False, "transshipment_count": 0},
        "performance": {"on_time_rate": 0.88, "damage_rate": 0.0018,
                        "cancellation_rate": 0.021},
        "environment": {"grade": "A", "co2_g_per_tonkm": 11.0,
                        "co2_kg_per_vehicle": round(km*1.7*11/1000,1)},
        "carries_finished_vehicle": True,
    })

# 파일에 병합
d = json.load(open("merged/Road/road_hyundai_glovis.json", encoding="utf-8"))
d["services"] += road_new
d["metadata"]["record_count"] = len(d["services"])
d["metadata"]["fvl_supplement"] = f"완성차 라스트마일 {len(road_new)}건 추가 (병합 시 보완)"
json.dump(d, open("merged/Road/road_hyundai_glovis.json","w",encoding="utf-8"),
          ensure_ascii=False, indent=2)

d = json.load(open("merged/Train/rail_db_cargo.json", encoding="utf-8"))
d["services"] += rail_new
d["metadata"]["record_count"] = len(d["services"])
d["metadata"]["fvl_supplement"] = f"완성차 블록트레인 {len(rail_new)}건 추가 (병합 시 보완)"
json.dump(d, open("merged/Train/rail_db_cargo.json","w",encoding="utf-8"),
          ensure_ascii=False, indent=2)

print(f"도로 완성차 노선 {len(road_new)}건 추가")
print(f"철도 완성차 노선 {len(rail_new)}건 추가")

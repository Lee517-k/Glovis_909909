"""
하선항 대안 확장.

문제: 뮌헨은 브레머하펜·함부르크에서만 접근 가능 → 항만 선택지가 2곳
목표: 주요 내륙 목적지마다 3~5곳의 항만에서 접근 가능하게

원리: 해상 거리와 육상 거리가 반대로 움직여야 판단이 생긴다
  로테르담 하선 → 해상 짧음 + 육상 김
  제노바 하선   → 해상 김 + 육상 짧음 (남유럽 목적지)
"""
import json, math, glob

COORD = json.load(open("coords.json", encoding="utf-8"))

# 유럽 항만
PORTS = ["NLRTM", "DEBRV", "DEHAM", "BEANR", "BEZEE", "FRLEH",
         "ESVLC", "ITGOA", "PLGDN", "SEGOT", "SIKOP"]
# 내륙 목적지 (DC / YARD)
INLAND = {
    "DEMUC": "YARD", "DESTR": "DC", "DEFRA": "DC", "DEKOL": "DC",
    "DEDUI": "DC", "DELEI": "DC", "ATVIE": "DC", "CZPRG": "DC",
    "PLWAW": "DC", "ITMIL": "DC", "ESMAD": "DC", "FRPAR": "DC",
    "HUBUD": "DC",
}
EU_ORDER = {"ES": 0, "FR": 1, "GB": 1, "BE": 2, "NL": 2, "IT": 2,
            "DE": 3, "SE": 3, "AT": 4, "SI": 4, "CZ": 4, "PL": 5,
            "SK": 5, "HU": 5, "RO": 6}


def hav(a, b):
    la1, lo1 = COORD[a][:2]; la2, lo2 = COORD[b][:2]
    R = 6371
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = math.radians(la2 - la1), math.radians(lo2 - lo1)
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(h))


def borders(a, b):
    ca, cb = COORD[a][2], COORD[b][2]
    if ca == cb:
        return 0
    oa, ob = EU_ORDER.get(ca), EU_ORDER.get(cb)
    return max(1, abs(oa - ob)) if oa is not None and ob is not None else 1


def taper(km, start, exp):
    return km if km <= start else start + (km - start) ** exp * (start ** (1 - exp))


def node(city, kind):
    return city if kind == "PORT" else f"{city}_{kind}"


def ntype(kind):
    return {"YARD": "vehicle_yard", "DC": "distribution_center",
            "RAIL": "rail_terminal", "PORT": "seaport"}[kind]


rail_new, road_new = [], []
ri = ti = 0

for port in PORTS:
    for city, kind in INLAND.items():
        km_straight = hav(port, city)
        if km_straight > 1900:
            continue

        nb = borders(port, city)

        # ── 철도: 항만 → 내륙 철도터미널
        rkm = round(km_straight * 1.35)
        if 120 <= rkm <= 2000:
            ri += 1
            days = round((16 + rkm / 34 + nb * 9) / 24, 2)
            unit = round(48 + 0.098 * taper(rkm, 400, 0.88) + 32, 1)
            rail_new.append({
                "service_id": f"EUR-RAIL-{port}-{city}-{ri:03d}",
                "service_type": "automotive_block_train",
                "service_tier": "STANDARD",
                "origin": {"node_id": f"{port}_RAIL", "name": f"{port} 철도터미널",
                           "country": COORD[port][2], "node_type": "rail_terminal",
                           "location_id": port},
                "destination": {"node_id": f"{city}_RAIL", "name": f"{city} 철도터미널",
                                "country": COORD[city][2], "node_type": "rail_terminal",
                                "location_id": city},
                "distance_km": rkm,
                "schedule": {"departure_days": ["MON", "WED", "FRI"],
                             "frequency_per_week": 3,
                             "transit_days": days,
                             "transit_hours": round(days * 24),
                             "average_wait_days": 1.8,
                             "total_days_with_wait": round(days + 1.8, 2),
                             "transit_days_p90": round((days + 1.8) * 1.32, 2),
                             "border_crossings": nb, "gauge_changes": 0,
                             "booking_lead_days": 3, "cargo_closing_hours": 24},
                "capacity": {"capacity_type": "vehicle_slot",
                             "available_vehicle_slots": 176,
                             "wagons_per_train": 22, "vehicles_per_wagon": 8},
                "pricing": {"pricing_model": "per_vehicle", "currency": "USD",
                            "rate_per_vehicle": unit,
                            "cost_usd_per_vehicle": unit,
                            "cost_usd_per_vehicle_all_in": round(unit + 35, 1),
                            "min_charge_usd": round((unit + 35) * 0.85, 1),
                            "valid_from": "2026-08-01", "valid_to": "2026-10-31"},
                "surcharges": [{"name": "TERMINAL_HANDLING", "basis": "per_vehicle",
                                "amount": 35.0, "currency": "USD"}],
                "cargo_conditions": {"allowed_cargo_types": ["FINISHED_VEHICLE"],
                                     "allowed_vehicle_types": ["SEDAN", "SUV", "EV"],
                                     "operable_vehicle_required": True},
                "dwell": {"free_time_days": 4, "demurrage_usd_per_unit_day": 28,
                          "detention_usd_per_unit_day": 22},
                "performance": {"on_time_rate": 0.88, "damage_rate": 0.0018,
                                "cancellation_rate": 0.021, "delay_probability": 0.162,
                                "reliability_source": "measured",
                                "on_time_sample_size": 210},
                "environment": {"grade": "A", "co2_g_per_tonkm": 11.0,
                                "co2_kg_per_vehicle": round(rkm * 1.7 * 11 / 1000, 1)},
                "carries_finished_vehicle": True,
            })

        # ── 도로: 항만 → 내륙 DC/YARD 직송
        dkm = round(km_straight * 1.28)
        if 60 <= dkm <= 1900:
            ti += 1
            drive = dkm / 54
            full = int(drive // 9)
            days = round((7 + drive + full * 11 + nb * 1.5) / 24, 2)
            per_truck = 165 + 1.32 * taper(dkm, 300, 0.92)
            unit = round(per_truck / 8, 1)
            allin = round((unit + 0.09 * dkm / 8) * 1.106, 1)
            road_new.append({
                "service_id": f"EUR-ROAD-{port}-{city}-{ti:03d}",
                "service_type": "car_carrier",
                "service_tier": "STANDARD",
                "origin": {"node_id": port, "name": port,
                           "country": COORD[port][2], "node_type": "seaport",
                           "location_id": port},
                "destination": {"node_id": node(city, kind), "name": city,
                                "country": COORD[city][2], "node_type": ntype(kind),
                                "location_id": city},
                "distance_km": dkm,
                "service_area": {"countries": sorted({COORD[port][2], COORD[city][2]}),
                                 "max_distance_km": 1900},
                "schedule": {"dispatch_lead_hours": 12, "average_speed_kmh": 54,
                             "max_driving_hours_per_day": 9,
                             "transit_days": days,
                             "driving_hours_total": round(drive, 1),
                             "frequency_per_week": 7,
                             "average_wait_days": 0.5,
                             "total_days_with_wait": round(days + 0.5, 2),
                             "transit_days_p90": round((days + 0.5) * 1.15, 2),
                             "border_crossings": nb,
                             "booking_lead_days": 1, "cargo_closing_hours": 12},
                "fleet": [{"vehicle_type": "CAR_CARRIER", "available_count": 8,
                           "vehicle_capacity": 8, "max_vehicle_height_m": 2.2}],
                "pricing": {"pricing_model": "per_transporter", "currency": "USD",
                            "rate_per_transporter": round(per_truck, 1),
                            "cost_usd_per_vehicle": unit,
                            "cost_usd_per_vehicle_all_in": allin,
                            "min_charge_usd": round(allin * 0.85, 1),
                            "valid_from": "2026-08-01", "valid_to": "2026-10-31"},
                "surcharges": [{"name": "TOLL", "basis": "per_km", "amount": 0.09,
                                "currency": "USD"},
                               {"name": "FUEL_ADJUSTMENT", "basis": "percentage",
                                "amount": 0.106, "currency": "RATIO"}],
                "cargo_conditions": {"allowed_cargo_types": ["FINISHED_VEHICLE"],
                                     "allowed_vehicle_types": ["SEDAN", "SUV", "EV",
                                                               "LIGHT_COMMERCIAL"],
                                     "operable_vehicle_required": True},
                "mode_details": {"cross_border_available": nb > 0,
                                 "gps_tracking": True},
                "dwell": {"free_time_days": 2, "demurrage_usd_per_unit_day": 0,
                          "detention_usd_per_unit_day": 18},
                "performance": {"on_time_rate": 0.95, "damage_rate": 0.0022,
                                "cancellation_rate": 0.015, "delay_probability": 0.068,
                                "reliability_source": "measured",
                                "on_time_sample_size": 265},
                "environment": {"grade": "C", "co2_g_per_tonkm": 63.0,
                                "co2_kg_per_vehicle": round(dkm * 1.7 * 63 / 1000, 1)},
                "carries_finished_vehicle": True,
            })

# 철도역 → 딜러 라스트마일 (철도 쓰면 반드시 필요)
last = []
for city, kind in INLAND.items():
    if kind == "PORT":
        continue
    last.append({
        "service_id": f"EUR-LAST-{city}",
        "service_type": "car_carrier",
        "service_tier": "STANDARD",
        "origin": {"node_id": f"{city}_RAIL", "name": f"{city} 철도터미널",
                   "country": COORD[city][2], "node_type": "rail_terminal",
                   "location_id": city},
        "destination": {"node_id": node(city, kind), "name": city,
                        "country": COORD[city][2], "node_type": ntype(kind),
                        "location_id": city},
        "distance_km": 18,
        "schedule": {"average_speed_kmh": 45, "max_driving_hours_per_day": 9,
                     "transit_days": 0.32, "driving_hours_total": 0.4,
                     "frequency_per_week": 7, "average_wait_days": 0.3,
                     "total_days_with_wait": 0.62, "transit_days_p90": 0.75,
                     "border_crossings": 0, "booking_lead_days": 1,
                     "cargo_closing_hours": 8},
        "fleet": [{"vehicle_type": "CAR_CARRIER", "available_count": 12,
                   "vehicle_capacity": 8, "max_vehicle_height_m": 2.2}],
        "pricing": {"pricing_model": "per_transporter", "currency": "USD",
                    "rate_per_transporter": 189.0,
                    "cost_usd_per_vehicle": 23.6,
                    "cost_usd_per_vehicle_all_in": 26.3,
                    "min_charge_usd": 22.4,
                    "valid_from": "2026-08-01", "valid_to": "2026-10-31"},
        "surcharges": [],
        "cargo_conditions": {"allowed_cargo_types": ["FINISHED_VEHICLE"],
                             "allowed_vehicle_types": ["SEDAN", "SUV", "EV"],
                             "operable_vehicle_required": True},
        "dwell": {"free_time_days": 2, "demurrage_usd_per_unit_day": 0,
                  "detention_usd_per_unit_day": 18},
        "performance": {"on_time_rate": 0.97, "damage_rate": 0.0015,
                        "cancellation_rate": 0.01, "delay_probability": 0.041,
                        "reliability_source": "measured", "on_time_sample_size": 310},
        "environment": {"grade": "C", "co2_g_per_tonkm": 63.0,
                        "co2_kg_per_vehicle": 1.9},
        "carries_finished_vehicle": True,
    })

d = json.load(open("rail_db_cargo.json", encoding="utf-8"))
d["services"] += rail_new
d["metadata"]["record_count"] = len(d["services"])
json.dump(d, open("rail_db_cargo.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

d = json.load(open("road_hyundai_glovis.json", encoding="utf-8"))
d["services"] += road_new + last
d["metadata"]["record_count"] = len(d["services"])
json.dump(d, open("road_hyundai_glovis.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

print(f"철도 {len(rail_new)}건 · 도로 {len(road_new)}건 · 라스트마일 {len(last)}건 추가")

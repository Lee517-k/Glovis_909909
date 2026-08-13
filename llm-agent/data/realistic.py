"""
철도·도로 소요시간과 요금을 현실적으로 재계산.

시간 = 고정절차 + 거리/실운행속도 + 국경지연 + 궤간변경
요금 = (고정비 + 거리비 × 체감) / 대수

핵심 원리
  1) 짧은 구간은 고정비(조성·환적·터미널)가 지배 → 대당 단가 높음
  2) 긴 구간은 거리비가 지배하되 체감(tapering) → km당 단가 낮아짐
  3) 국경마다 지연 누적. 궤간 다르면 추가.
"""
import json, glob, math

COORD = json.load(open("coords.json", encoding="utf-8"))

# ── 국가별 대략 위치 (경유 국가 추정용)
EU_ORDER = {  # 서→동 대략 순서로 배치해 경유국 추정
    "ES": 0, "FR": 1, "BE": 2, "NL": 2, "GB": 1, "IT": 2,
    "DE": 3, "CH": 3, "AT": 4, "SI": 4, "CZ": 4, "PL": 5,
    "SK": 5, "HU": 5, "RO": 6, "SE": 3,
}
# 궤간이 다른 구간 (광궤/협궤 경계)
GAUGE_BREAK = {("PL", "UA"), ("PL", "BY"), ("RO", "MD"), ("FI", "SE")}

# ── 파라미터
RAIL = dict(
    fixed_hours=16,        # 조성·화차 연결·터미널 반출입
    speed_kmh=34,          # 실운행 평균 (정차·대피·기관차교체 포함)
    border_hours=9,        # 국경 1회당
    gauge_hours=26,        # 궤간 변경
    base_fee=48.0,         # 편성 고정비 → 대당 환산 전
    rate_per_km=0.098,     # km당
    taper_start=400,       # 이 거리부터 체감 시작
    taper_exp=0.88,        # 체감 지수 (1.0이면 체감 없음)
    terminal_fee=32.0,     # 양단 터미널 취급비 (대당)
)
ROAD = dict(
    fixed_hours=7,         # 배차·상하차
    speed_kmh=54,
    max_drive_h=9,         # 일 운행 한도
    rest_h=11,             # 일 휴식
    border_hours=1.5,      # EU 역내는 짧음
    base_fee=165.0,        # 차량 1대 고정
    rate_per_km=1.32,
    taper_start=300,
    taper_exp=0.92,
    capacity=8,
)


def base(n):
    for s in ("_YARD", "_RAIL", "_DC", "_WH", "_PLANT"):
        if n.endswith(s):
            return n[:-len(s)]
    return n


def cc(n):
    b = base(n)
    return COORD[b][2] if b in COORD else None


def borders(a, b):
    """출발-도착 사이 추정 국경 통과 횟수"""
    ca, cb = cc(a), cc(b)
    if not ca or not cb or ca == cb:
        return 0
    oa, ob = EU_ORDER.get(ca), EU_ORDER.get(cb)
    if oa is None or ob is None:
        return 1
    # 서·동 순서 차이가 클수록 경유국 많음
    return max(1, abs(oa - ob))


def gauge(a, b):
    ca, cb = cc(a), cc(b)
    return 1 if (ca, cb) in GAUGE_BREAK or (cb, ca) in GAUGE_BREAK else 0


def taper(km, start, exp):
    """taper_start 이후 거리는 체감 적용"""
    if km <= start:
        return km
    return start + (km - start) ** exp * (start ** (1 - exp))


def rail_calc(a, b, km):
    p = RAIL
    nb, ng = borders(a, b), gauge(a, b)
    hours = (p["fixed_hours"] + km / p["speed_kmh"]
             + nb * p["border_hours"] + ng * p["gauge_hours"])
    eff_km = taper(km, p["taper_start"], p["taper_exp"])
    unit = p["base_fee"] + p["rate_per_km"] * eff_km + p["terminal_fee"]
    return round(hours / 24, 2), round(unit, 1), nb, ng


def road_calc(a, b, km):
    p = ROAD
    nb = borders(a, b)
    drive_h = km / p["speed_kmh"]
    # 일 운행한도 넘으면 휴식 삽입
    full_days = int(drive_h // p["max_drive_h"])
    hours = (p["fixed_hours"] + drive_h + full_days * p["rest_h"]
             + nb * p["border_hours"])
    eff_km = taper(km, p["taper_start"], p["taper_exp"])
    per_truck = p["base_fee"] + p["rate_per_km"] * eff_km
    unit = per_truck / p["capacity"]
    return round(hours / 24, 2), round(unit, 1), nb


# ══════════════════════════════════════════════
changed = {"rail": 0, "road": 0}
report = []

for f in glob.glob("merged/*/*.json"):
    d = json.load(open(f, encoding="utf-8"))
    if "services" not in d:
        continue
    grp = d["carrier"]["group"]
    if grp not in ("rail", "road"):
        continue

    for s in d["services"]:
        a, b = s["origin"]["node_id"], s["destination"]["node_id"]
        km = s.get("distance_km")
        if not km:
            continue

        if grp == "rail":
            days, unit, nb, ng = rail_calc(a, b, km)
            s["schedule"]["transit_days"] = days
            s["schedule"]["transit_hours"] = round(days * 24)
            s["schedule"]["border_crossings"] = nb
            s["schedule"]["gauge_changes"] = ng
            wait = s["schedule"].get("average_wait_days", 1.8)
            s["schedule"]["average_wait_days"] = wait
            s["schedule"]["total_days_with_wait"] = round(days + wait, 2)
            s["pricing"]["cost_usd_per_vehicle"] = unit
            sur = sum(x["amount"] for x in s.get("surcharges", [])
                      if x.get("basis") == "per_vehicle")
            s["pricing"]["cost_usd_per_vehicle_all_in"] = round(unit + sur, 1)
            changed["rail"] += 1
        else:
            days, unit, nb = road_calc(a, b, km)
            s["schedule"]["transit_days"] = days
            s["schedule"]["driving_hours_total"] = round(km / ROAD["speed_kmh"], 1)
            s["schedule"]["border_crossings"] = nb
            wait = s["schedule"].get("average_wait_days", 0.5)
            s["schedule"]["average_wait_days"] = wait
            s["schedule"]["total_days_with_wait"] = round(days + wait, 2)
            s["pricing"]["cost_usd_per_vehicle"] = unit
            pct = sum(x["amount"] for x in s.get("surcharges", [])
                      if x.get("basis") == "percentage")
            perkm = sum(x["amount"] for x in s.get("surcharges", [])
                        if x.get("basis") == "per_km")
            allin = (unit + perkm * km / ROAD["capacity"]) * (1 + pct)
            s["pricing"]["cost_usd_per_vehicle_all_in"] = round(allin, 1)
            changed["road"] += 1

        report.append((grp, km, days, unit, nb, f"{a}→{b}"))

    json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print(f"재계산: 철도 {changed['rail']}건 · 도로 {changed['road']}건\n")

for g in ("rail", "road"):
    rows = sorted([r for r in report if r[0] == g], key=lambda r: r[1])
    print(f"=== {g.upper()} ===")
    print(f"{'km':>6} {'일':>6} {'대당$':>8} {'국경':>4} {'km/h':>6} {'$/km':>7}   구간")
    for r in rows[:5] + ["…"] + rows[-5:]:
        if r == "…":
            print("  …")
            continue
        spd = r[1] / (r[2] * 24)
        print(f"{r[1]:>6} {r[2]:>6} {r[3]:>8} {r[4]:>4} {spd:>6.1f} {r[3]/r[1]:>7.3f}   {r[5]}")
    print()

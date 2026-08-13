"""
요율 유효기간 스태거링.

문제: 850건 전부 2026-08-01 ~ 2026-10-31 동일 → 만료 필터가 아무것도 안 걸러냄
목표: 계약 형태별로 갱신 주기와 시작일을 어긋나게 → "곧 만료" 시나리오 테스트 가능

현실 반영
  해운 PCTC : 연간/반기 계약. 화주와 장기 협상 → 주기 길고 갱신일 제각각
  철도      : 반기 계약. 다이어 개정 시기(3월·9월)에 맞춰 갱신
  도로      : 분기 계약. 유가 변동 반영 위해 짧음
  항공      : 월 단위 또는 스팟. 가장 짧고 자주 갱신
  ECONOMY   : 물량 약정 대가로 유효기간 김
  EXPRESS   : 스팟성 → 짧음
"""
import json, glob, random
from datetime import date, timedelta

random.seed(20260807)
TODAY = date(2026, 8, 7)

# 수단별 기본 계약 주기(개월)와 갱신 앵커
PROFILE = {
    "sea": dict(
        kinds=[("ANNUAL_CONTRACT", 12, 0.45), ("SEMI_ANNUAL", 6, 0.40),
               ("QUARTERLY", 3, 0.15)],
        anchors=[1, 4, 7, 10],          # 분기 시작월
    ),
    "rail": dict(
        kinds=[("SEMI_ANNUAL", 6, 0.55), ("QUARTERLY", 3, 0.35),
               ("ANNUAL_CONTRACT", 12, 0.10)],
        anchors=[3, 9],                  # 다이어 개정
    ),
    "road": dict(
        kinds=[("QUARTERLY", 3, 0.60), ("SEMI_ANNUAL", 6, 0.30),
               ("MONTHLY", 1, 0.10)],
        anchors=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    ),
    "air": dict(
        kinds=[("MONTHLY", 1, 0.50), ("SPOT", 1, 0.30), ("QUARTERLY", 3, 0.20)],
        anchors=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    ),
}
# 티어 보정
TIER_MULT = {"ECONOMY": 1.6, "STANDARD": 1.0, "EXPRESS": 0.6}


def pick(kinds):
    r = random.random()
    acc = 0
    for name, months, w in kinds:
        acc += w
        if r <= acc:
            return name, months
    return kinds[-1][0], kinds[-1][1]


def add_months(d, n):
    y, m = d.year, d.month + n
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    day = min(d.day, [31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30,
                      31, 31, 30, 31, 30, 31][m - 1])
    return date(y, m, day)


KB = {"coords.json", "transfer_rules.json", "customs_rules.json", "incoterms.json"}

# 같은 구간 가격대 사전 수집 (저가 요율 판별용)
PRICE_BAND = {}
for _f in sorted(glob.glob("*.json")):
    if _f in KB:
        continue
    _d = json.load(open(_f, encoding="utf-8"))
    if "services" not in _d:
        continue
    for _s in _d["services"]:
        _c = _s["pricing"].get("cost_usd_per_vehicle_all_in")
        if _c:
            PRICE_BAND.setdefault(
                (_d["carrier"]["group"], _s["origin"]["location_id"],
                 _s["destination"]["location_id"]), []).append(_c)

stats = {}
expiring_soon = []

for f in sorted(glob.glob("*.json")):
    if f in KB:
        continue
    d = json.load(open(f, encoding="utf-8"))
    if "services" not in d:
        continue
    grp = d["carrier"]["group"]
    cid = d["carrier"]["carrier_id"]
    prof = PROFILE[grp]
    # 캐리어마다 고유 오프셋 — 같은 수단이라도 갱신일이 다르게
    carrier_shift = random.randint(0, 2)

    for s in d["services"]:
        kind, months = pick(prof["kinds"])
        months = max(1, round(months * TIER_MULT.get(s.get("service_tier", "STANDARD"), 1.0)))

        # 저가 프로모션 요율은 짧게 — 현실에서 할인 요율이 먼저 만료된다
        allin = s["pricing"].get("cost_usd_per_vehicle_all_in")
        if allin and grp in ("sea", "rail", "road"):
            peers = PRICE_BAND.get((grp, s["origin"]["location_id"],
                                    s["destination"]["location_id"]))
            if peers and len(peers) >= 2:
                lo, hi = min(peers), max(peers)
                if hi > lo and (allin - lo) / (hi - lo) < 0.25:   # 하위 25% 가격대
                    kind = "PROMOTIONAL"
                    months = 1

        # 시작월: 수단별 앵커 + 캐리어 오프셋 + 노선별 흔들림
        anchor = prof["anchors"][(hash(s["service_id"]) + carrier_shift)
                                 % len(prof["anchors"])]
        # 현재 유효한 계약이 되도록 시작 시점을 과거로 당김
        start_year = TODAY.year if anchor <= TODAY.month else TODAY.year - 1
        # 계약 개시일을 월중으로 분산 (실제 계약은 1일에만 시작하지 않음)
        dom = 1 + (hash(s["service_id"] + cid) % 28)
        start = date(start_year, anchor, dom)
        # 주기가 짧으면 최근 갱신분으로 롤포워드
        while add_months(start, months) <= TODAY:
            start = add_months(start, months)
        end = add_months(start, months) - timedelta(days=1)

        # 스팟은 짧게 (2~5주)
        if kind in ("SPOT", "PROMOTIONAL"):
            start = TODAY - timedelta(days=random.randint(3, 18))
            end = start + timedelta(days=random.randint(14, 35))

        s["pricing"]["rate_validity_type"] = kind
        s["pricing"]["valid_from"] = start.isoformat()
        s["pricing"]["valid_to"] = end.isoformat()
        s["pricing"]["days_until_expiry"] = (end - TODAY).days

        stats.setdefault(grp, {}).setdefault(kind, 0)
        stats[grp][kind] += 1
        if 0 <= (end - TODAY).days <= 14:
            expiring_soon.append((s["service_id"], d["carrier"]["carrier_name"],
                                  kind, end.isoformat(), (end - TODAY).days))

    json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print(f"기준일 {TODAY}\n")
print("=== 수단별 계약 유형 분포 ===")
for g, k in stats.items():
    print(f"  {g:5} {k}")

# 만료일 분포
import collections
allsvc = []
for f in sorted(glob.glob("*.json")):
    if f in KB:
        continue
    d = json.load(open(f, encoding="utf-8"))
    if "services" in d:
        allsvc += [(s["pricing"]["valid_to"], s["pricing"]["days_until_expiry"])
                   for s in d["services"]]
print(f"\n=== 만료일 분포 (총 {len(allsvc)}건) ===")
buckets = collections.Counter()
for _, dd in allsvc:
    if dd <= 7: buckets["7일 이내"] += 1
    elif dd <= 14: buckets["8~14일"] += 1
    elif dd <= 30: buckets["15~30일"] += 1
    elif dd <= 60: buckets["31~60일"] += 1
    elif dd <= 120: buckets["61~120일"] += 1
    else: buckets["120일 초과"] += 1
for k in ["7일 이내", "8~14일", "15~30일", "31~60일", "61~120일", "120일 초과"]:
    n = buckets.get(k, 0)
    bar = "█" * (n * 40 // max(buckets.values()))
    print(f"  {k:10} {n:4}건 {bar}")

print(f"\n  서로 다른 만료일 {len({v for v,_ in allsvc})}개")
print(f"  14일 이내 만료 {len(expiring_soon)}건")
print("\n=== 곧 만료되는 요율 샘플 ===")
for e in sorted(expiring_soon, key=lambda x: x[4])[:8]:
    print(f"  D-{e[4]:<3} {e[3]}  {e[2]:16} {e[1]:24} {e[0]}")

import json, glob
from collections import defaultdict, deque

KB = {"coords.json", "transfer_rules.json", "customs_rules.json", "incoterms.json"}
SVC, CARRIER = [], {}
for f in sorted(glob.glob("*.json")):
    if f in KB:
        continue
    d = json.load(open(f, encoding="utf-8"))
    if "services" not in d:
        continue
    CARRIER[d["carrier"]["carrier_id"]] = d["carrier"]
    for s in d["services"]:
        s["_carrier"] = d["carrier"]["carrier_name"]
        s["_group"] = d["carrier"]["group"]
        SVC.append(s)

TR = {(t["from_node_type"], t["to_node_type"]): t
      for t in json.load(open("transfer_rules.json", encoding="utf-8"))["transfers"]}
CUS = {(r["origin_country"], r["destination_country"]): r
       for r in json.load(open("customs_rules.json", encoding="utf-8"))["rules"]}

n2l, n2t, n2c = {}, {}, {}
for s in SVC:
    for k in ("origin", "destination"):
        n2l[s[k]["node_id"]] = s[k]["location_id"]
        n2t[s[k]["node_id"]] = s[k]["node_type"]
        n2c[s[k]["node_id"]] = s[k].get("country")
l2n = defaultdict(set)
for n, l in n2l.items():
    l2n[l].add(n)

adj = defaultdict(list)
for s in SVC:
    adj[s["origin"]["node_id"]].append((s["destination"]["node_id"], s, None))
for l, ns in l2n.items():
    for a in ns:
        for b in ns:
            if a != b and (n2t.get(a), n2t.get(b)) in TR:
                adj[a].append((b, None, TR[(n2t[a], n2t[b])]))


def search(sl, gl, maxhop=4, tier=None, min_days_valid=None):
    st, go = l2n.get(sl, set()), l2n.get(gl, set())
    q = deque([(n, [], 0.0, 0.0, 0.0, 1.0) for n in st])
    seen = defaultdict(lambda: 99)
    out = []
    while q:
        node, path, c, d_, e, r = q.popleft()
        if len(path) > maxhop:
            continue
        for nxt, s, tr in adj[node]:
            if s:
                if not s.get("carries_finished_vehicle"):
                    continue
                if tier and s.get("service_tier") != tier:
                    continue
                if min_days_valid is not None and \
                   s["pricing"].get("days_until_expiry", 999) < min_days_valid:
                    continue
                np_ = path + [s]
                nc = c + (s["pricing"].get("cost_usd_per_vehicle_all_in") or 0)
                nd = d_ + s["schedule"].get("total_days_with_wait", 0)
                ne = e + s["environment"].get("co2_kg_per_vehicle", 0)
                nr = r * s["performance"].get("on_time_rate", 1)
            else:
                np_, nc = path, c + tr["cost_usd_per_vehicle"]
                nd, ne, nr = d_ + tr["hours"] / 24, e, r
            if nxt in go and np_:
                out.append((np_, nc, nd, ne, nr))
            elif seen[nxt] > len(np_):
                seen[nxt] = len(np_)
                q.append((nxt, np_, nc, nd, ne, nr))
    u = {}
    for p, c, d_, e, r in out:
        k = tuple(x["service_id"] for x in p)
        if k not in u:
            u[k] = (p, round(c), round(d_, 1), round(e), round(r, 3))
    return list(u.values())


def customs(p):
    oc = n2c.get(p[0]["origin"]["node_id"])
    dc = n2c.get(p[-1]["destination"]["node_id"])
    r = CUS.get((oc, dc))
    return r["typical_clearance_days"] if r else 0


def show(title, a, b, n=6):
    res = search(a, b)
    print(f"\n=== {title} : {len(res)}개 경로 ===")
    if not res:
        print("  경로 없음")
        return
    ports = sorted({x["destination"]["node_id"] for p, *_ in res
                    for x in p if x["_group"] == "sea"})
    print(f"  하선항 대안 {len(ports)}곳: {ports}\n")
    print(f"  {'경로':<46} {'수단':<18} {'일':>6} {'통관':>5} {'비용':>8} {'CO2':>7} {'정시':>6}")
    print("  " + "-" * 104)
    for p, c, d_, e, r in sorted(res, key=lambda x: x[1])[:n]:
        chain = p[0]["origin"]["node_id"] + "→" + "→".join(
            x["destination"]["node_id"] for x in p)
        modes = "+".join(x["_group"] for x in p)
        cd = customs(p)
        print(f"  {chain:<46} {modes:<18} {d_:>5} {cd:>5} ${c:>7,} {e:>6}kg {r:>6.2f}")


print("=" * 106)
print(f"서비스 {len(SVC)}개 / 운송사 {len(CARRIER)}곳")
g = defaultdict(int)
t = defaultdict(int)
for s in SVC:
    g[s["_group"]] += 1
    t[s.get("service_tier", "?")] += 1
print(f"수단별 {dict(g)}")
print(f"티어별 {dict(t)}")
fv = sum(1 for s in SVC if s.get("carries_finished_vehicle"))
print(f"완성차 가능 {fv} / 부품·일반 {len(SVC)-fv}")
print("=" * 106)

for a, b, lab in [("KRUSN", "DEMUC", "울산 → 뮌헨"),
                  ("KRPUS", "CZPRG", "부산 → 프라하"),
                  ("KRUSN", "ESMAD", "울산 → 마드리드"),
                  ("KRUSN", "ITMIL", "울산 → 밀라노"),
                  ("CNSHA", "PLWAW", "상하이 → 바르샤바")]:
    show(lab, a, b)

print("\n=== 무결성 점검 ===")
bad = 0
for s in SVC:
    sc, pr, pf = s["schedule"], s["pricing"], s.get("performance", {})
    if s.get("carries_finished_vehicle"):
        if not pr.get("cost_usd_per_vehicle_all_in"):
            print(f"  [!] {s['service_id']} 비용 없음"); bad += 1
        if sc.get("total_days_with_wait", 0) <= 0:
            print(f"  [!] {s['service_id']} 소요 0"); bad += 1
        if sc.get("transit_days_p90", 0) < sc.get("total_days_with_wait", 0):
            print(f"  [!] {s['service_id']} p90 < 평균"); bad += 1
    cc = s.get("cargo_conditions", {})
    if "EV" in cc.get("allowed_vehicle_types", []) and cc.get("ev_allowed") is False:
        print(f"  [!] {s['service_id']} EV 플래그 모순"); bad += 1
print(f"  {'이상 없음' if not bad else f'이상 {bad}건'}")

print("\n=== 요율 유효기간 ===")
import collections
exp = [s["pricing"].get("days_until_expiry") for s in SVC
       if s["pricing"].get("days_until_expiry") is not None]
kinds = collections.Counter(s["pricing"].get("rate_validity_type") for s in SVC)
print(f"  계약 유형: {dict(kinds)}")
print(f"  서로 다른 만료일 {len({s['pricing'].get('valid_to') for s in SVC})}개")
b = collections.Counter()
for dd in exp:
    b["D-7 이내" if dd <= 7 else "D-30 이내" if dd <= 30 else
      "D-90 이내" if dd <= 90 else "D-90 초과"] += 1
for k in ["D-7 이내", "D-30 이내", "D-90 이내", "D-90 초과"]:
    print(f"    {k:10} {b.get(k,0):4}건")

print("\n=== 유효기간 필터 효과 (울산 → 뮌헨) ===")
for md, lab in [(None, "필터 없음"), (7, "7일 이상 유효"), (30, "30일 이상 유효")]:
    r = search("KRUSN", "DEMUC", min_days_valid=md)
    cheapest = min(r, key=lambda x: x[1])[1] if r else 0
    print(f"  {lab:14} 경로 {len(r):3}개  최저가 ${cheapest:,}")

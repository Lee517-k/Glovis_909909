"""'운송사 배분' 화면용 조회 로직.

병합 DB(glovis_merged.db, scenarios/scenario_legs)에서 직접 집계한다.
예전엔 ct_allocations/ct_carriers/ct_hub_volumes/ct_regions(손으로 채운 데모 값)를 썼지만,
이제 실제 시나리오·구간 데이터에서 지역권/운송사/HHI/거점물량을 계산한다.

이 스키마엔 '지역권' 개념이 없어서 destination_country로 근사 매핑한다(COUNTRY_REGION).
좌표도 없어서(운송 추적과 동일한 이유) 거점 지도는 node_id만 내려주고 프론트가
worldmap.ts의 NodeKey 조회로 좌표를 직접 찾는다.

담당 기능
  1. 지역권 탭 목록            -> get_regions()
  2. 거점별 물량(지도 버블)     -> get_hub_volumes()
  3. 지역권 × 운송사 배분 + HHI -> get_allocations()
  4. 운송사 현황 표             -> get_carriers()
  5. CSV 내보내기               -> carriers_csv()
  6. 배분 요약 KPI              -> get_allocation_summary()

HHI(허핀달-허시먼 지수)는 저장값이 아니라 배분 비중으로 매번 계산한다.
    HHI = Σ (점유율/100)^2      (0~1, 1에 가까울수록 한 운송사에 집중)
"""

from __future__ import annotations

import csv
import io

from app.db.scenario_tracking_store import get_allocation_history_store
from app.domain.presentation import MODE_HEX, MODE_KO
from app.planning.carbon import AVG_VEHICLE_WEIGHT_TON, grade_from_co2_per_ton

TRACKED_STATUSES = ("CONFIRMED", "ACTIVE", "CLOSED")  # DRAFT/CANCELLED는 실적 아님

# destination_country -> (region_id, region_name). 이 스키마엔 지역권 컬럼이 없어 근사한다.
COUNTRY_REGION: dict[str, tuple[str, str]] = {
    "DE": ("RG-EU", "서·북유럽"), "NL": ("RG-EU", "서·북유럽"), "GB": ("RG-EU", "서·북유럽"),
    "KZ": ("RG-CA", "중앙아시아 · TCR"),
    "CN": ("RG-EA", "동아시아"),
    "US": ("RG-NA", "북미"),
    "SG": ("RG-SEA", "동남아시아"),
}
DEFAULT_REGION: tuple[str, str] = ("RG-ETC", "기타")
REGION_SORT = ["RG-EU", "RG-EA", "RG-CA", "RG-NA", "RG-SEA", "RG-ETC"]
REGION_NAME = {rid: name for rid, name in COUNTRY_REGION.values()} | {DEFAULT_REGION[0]: DEFAULT_REGION[1]}

# 운송사 색상 — 예전 ct_carriers.color를 대신하는 고정 팔레트(carrier_id 기준)
CARRIER_COLORS = {
    "HMM": "#0B3C71", "MSC": "#1668C4", "DBCARGO": "#12A47B", "CREBLOCK": "#0A7A57",
    "EUTRUCK": "#E08A00", "GLOVISINLAND": "#96610A", "KECARGO": "#7A5AF8",
    # Current normalized service-data carrier IDs.
    "HYUNDAI_GLOVIS_SEA": "#0B3C71",
    "EUROTRANS_AUTO": "#E08A00",
    "DB_CARGO": "#12A47B",
    "DSV_ROAD": "#0A7A57",
    "KOREAN_AIR_CARGO": "#7A5AF8",
    "LUFTHANSA_CARGO": "#A855F7",
    "RAIL_CARGO_GROUP": "#D65A4A",
}
DEFAULT_COLOR = "#C3CDDA"
OWN_CARRIER_ID = "GLOVISINLAND"  # 자가 운송(GLOVIS Inland)은 의존도 경고 대상에서 제외

# 집중도 판정 기준 (공정거래 실무에서 쓰는 HHI 구간을 0~1 스케일로 옮긴 값)
HHI_LOW = 0.15       # 미만: 비집중
HHI_MODERATE = 0.25  # 미만: 중간 집중

# 단일 운송사 의존 경고 기준(%)
DEPENDENCY_DANGER = 60.0
DEPENDENCY_WARN = 35.0
DEPENDENCY_CAP = 40.0  # 내부 배분 정책상 단일 운송사 상한


def _hhi(shares: list[float]) -> float:
    return round(sum((s / 100.0) ** 2 for s in shares), 4)


def _concentration_label(hhi: float) -> str:
    if hhi < HHI_LOW:
        return "분산"
    if hhi < HHI_MODERATE:
        return "보통"
    if hhi < 0.40:
        return "주의"
    return "높음"


# ---------------------------------------------------------------------------
# 공통 — DB2에서 (시나리오 x 구간) 단위 사실(fact) 목록을 만든다
# ---------------------------------------------------------------------------
def _facts(region_id: str | None = None) -> list[dict]:
    store = get_allocation_history_store()
    scenarios = store.list_scenarios(TRACKED_STATUSES)
    legs_map = store.legs_for_many([s["scenario_id"] for s in scenarios])

    out = []
    for sc in scenarios:
        rid, rname = COUNTRY_REGION.get(sc["destination_country"], DEFAULT_REGION)
        if region_id and rid != region_id:
            continue
        for leg in legs_map.get(sc["scenario_id"], []):
            on_time = (leg["ata"] <= leg["eta"]) if leg.get("ata") else None
            out.append({
                "scenario_id": sc["scenario_id"], "region_id": rid, "region_name": rname,
                "carrier_id": leg["carrier_id"], "carrier_name": leg["carrier_name"],
                "mode": leg["mode"], "quantity": sc["quantity"] or 0,
                "co2_kg_per_vehicle": sc["co2_kg_per_vehicle"],
                "cost_usd_per_vehicle": sc["cost_usd_per_vehicle"] or 0,
                "origin_node_id": leg["origin_node_id"], "origin_name": leg.get("origin_name"),
                "destination_node_id": leg["destination_node_id"], "destination_name": leg.get("destination_name"),
                "on_time": on_time,
            })
    return out


# ---------------------------------------------------------------------------
# 1. 지역권 탭
# ---------------------------------------------------------------------------
def get_regions() -> dict:
    """상단 탭 목록. 맨 앞의 '전체'는 region_id 가 null 인 가상 탭이다."""
    facts = _facts()
    present = {f["region_id"]: f["region_name"] for f in facts}
    regions = [
        {"region_id": rid, "region_name": present[rid],
         "sort_order": REGION_SORT.index(rid) if rid in REGION_SORT else 99, "is_tab": 1}
        for rid in sorted(present, key=lambda r: REGION_SORT.index(r) if r in REGION_SORT else 99)
    ]
    tabs = [{"region_id": None, "region_name": "전체"}]
    tabs += [{"region_id": r["region_id"], "region_name": r["region_name"]} for r in regions]
    return {"tabs": tabs, "regions": regions}


# ---------------------------------------------------------------------------
# 2. 거점별 물량 (지도 버블) — 좌표 없음, node_id만 반환(프론트가 좌표 조회)
# ---------------------------------------------------------------------------
def get_hub_volumes(region_id: str | None = None) -> dict:
    facts = _facts(region_id)
    nodes: dict[str, dict] = {}
    for f in facts:
        for node_id, name in ((f["origin_node_id"], f["origin_name"]),
                               (f["destination_node_id"], f["destination_name"])):
            e = nodes.setdefault(node_id, {"name": name, "volume": 0.0, "modes": {}, "region_id": f["region_id"]})
            e["volume"] += f["quantity"]
            e["modes"][f["mode"]] = e["modes"].get(f["mode"], 0) + f["quantity"]

    max_v = max((e["volume"] for e in nodes.values()), default=1) or 1
    bubbles = []
    for node_id, e in nodes.items():
        primary_mode = max(e["modes"], key=e["modes"].get) if e["modes"] else "sea"
        radius = round(12 + (e["volume"] / max_v) * 32)  # 12~44 px 범위로 정규화
        bubbles.append({
            # 프론트 축약 키(k/r/m/t) — RouteMapLibre와 같은 방식으로 node_id 기반 좌표 조회
            "k": node_id, "r": radius, "m": primary_mode, "t": f"{round(e['volume']):,}대",
            "name": e["name"] or node_id, "node_id": node_id,
            "volume": round(e["volume"]), "volume_unit": "대",
            "color": MODE_HEX.get(primary_mode, "#1668C4"), "region_id": e["region_id"],
        })
    legend = [{"mode": m, "label": MODE_KO[m] + " 주력", "color": MODE_HEX[m]}
              for m in ("sea", "rail", "air", "truck")]
    return {"bubbles": bubbles, "legend": legend, "note": "버블 크기 = 취급 물량(대)"}


# ---------------------------------------------------------------------------
# 3. 지역권 × 운송사 배분 (+ HHI, 의존도 경고)
# ---------------------------------------------------------------------------
def get_allocations(region_id: str | None = None) -> dict:
    facts = _facts(region_id)
    all_facts = facts if region_id is None else _facts(None)
    grand_total = sum(f["quantity"] for f in all_facts) or 1

    grouped: dict[str, dict[str, dict]] = {}
    for f in facts:
        rgroup = grouped.setdefault(f["region_id"], {})
        c = rgroup.setdefault(f["carrier_id"], {
            "name": f["carrier_name"], "volume": 0.0, "spend": 0.0,
            "is_own": f["carrier_id"] == OWN_CARRIER_ID,
        })
        c["volume"] += f["quantity"]
        c["spend"] += f["cost_usd_per_vehicle"] * f["quantity"]

    out = []
    for rid, carriers in grouped.items():
        total = sum(c["volume"] for c in carriers.values()) or 1
        spend = sum(c["spend"] for c in carriers.values())
        ranked = sorted(carriers.items(), key=lambda kv: -kv[1]["volume"])
        shares = [round(c["volume"] / total * 100) for _, c in ranked]
        cs = [[c["name"], pct, CARRIER_COLORS.get(cid, DEFAULT_COLOR)]
              for (cid, c), pct in zip(ranked, shares)]
        hhi = _hhi(shares)

        external = [(cid, c) for cid, c in carriers.items() if not c["is_own"]]
        top_id, top = max(external, key=lambda kv: kv[1]["volume"], default=(None, None))
        own = next((c for c in carriers.values() if c["is_own"]), None)
        top_pct = round(top["volume"] / total * 100) if top else 0
        own_pct = round(own["volume"] / total * 100) if own else 0

        warn_text = warn_tone = None
        if top and top_pct >= DEPENDENCY_DANGER:
            warn_tone, warn_text = "danger", "단일 운송사 의존 위험"
        elif top and top_pct >= DEPENDENCY_WARN:
            warn_tone = "warn"
            warn_text = f"{top['name']} 의존도 상한({DEPENDENCY_CAP:g}%) 근접"
        elif own and own_pct >= 50:
            warn_text = "자가 운송 비중 높음"

        out.append({
            "region_id": rid,
            "rg": REGION_NAME.get(rid, rid),
            "meta": f"{total:,.0f}대 · {total / grand_total * 100:.0f}%",
            "hhi": f"집중도 HHI {hhi:.2f} · ",
            "warn": warn_text,
            "wt": warn_tone,
            "cs": cs,
            "hhi_value": hhi,
            "concentration": _concentration_label(hhi),
            "volume": total,
            "volume_unit": "대",
            "volume_share_pct": round(total / grand_total * 100, 1),
            "spend_100m": round(spend, 2),
            "top_carrier": (top or {}).get("name"),
            "top_share_pct": top_pct if top else None,
            "carriers": [
                {"carrier_id": cid, "name": c["name"], "share_pct": pct,
                 "volume": c["volume"], "volume_unit": "대", "spend_100m": round(c["spend"], 2),
                 "color": CARRIER_COLORS.get(cid, DEFAULT_COLOR)}
                for (cid, c), pct in zip(ranked, shares)
            ],
        })

    out.sort(key=lambda a: REGION_SORT.index(a["region_id"]) if a["region_id"] in REGION_SORT else 99)
    return {"allocations": out, "grand_total_volume": round(grand_total)}


# ---------------------------------------------------------------------------
# 4. 운송사 현황 표
# ---------------------------------------------------------------------------
def _carrier_status(share_pct: float) -> list:
    if share_pct > DEPENDENCY_DANGER:
        return ["danger", "단일 의존"]
    if share_pct > DEPENDENCY_WARN:
        return ["warn", "의존도 주의"]
    return ["ok", "정상"]


def get_carriers(region_id: str | None = None, mode: str | None = None, sort: str = "-share") -> dict:
    facts = _facts(region_id)
    if mode:
        marks = {m.strip().lower() for m in mode.split(",") if m.strip()}
        facts = [f for f in facts if f["mode"] in marks]

    by_carrier: dict[str, dict] = {}
    for f in facts:
        c = by_carrier.setdefault(f["carrier_id"], {
            "name": f["carrier_name"], "modes": set(), "regions": {}, "volume": 0.0,
            "cost_total": 0.0, "co2_list": [], "on_time_done": 0, "on_time_ok": 0,
        })
        c["modes"].add(f["mode"])
        c["regions"][f["region_id"]] = c["regions"].get(f["region_id"], 0) + f["quantity"]
        c["volume"] += f["quantity"]
        c["cost_total"] += f["cost_usd_per_vehicle"] * f["quantity"]
        if f["co2_kg_per_vehicle"] is not None:
            c["co2_list"].append(f["co2_kg_per_vehicle"])
        if f["on_time"] is not None:
            c["on_time_done"] += 1
            c["on_time_ok"] += int(f["on_time"])

    total_all = sum(c["volume"] for c in by_carrier.values()) or 1
    items = []
    for cid, c in by_carrier.items():
        share_pct = round(c["volume"] / total_all * 100, 1)
        primary_region = max(c["regions"], key=c["regions"].get) if c["regions"] else None
        avg_co2 = sum(c["co2_list"]) / len(c["co2_list"]) if c["co2_list"] else None
        grade = grade_from_co2_per_ton(avg_co2, AVG_VEHICLE_WEIGHT_TON) if avg_co2 is not None else None
        on_time_pct = round(c["on_time_ok"] / c["on_time_done"] * 100) if c["on_time_done"] else None
        items.append({
            "n": c["name"], "sub": f"{len(c['modes'])}개 모드 취급",
            "m": sorted(c["modes"]), "rg": REGION_NAME.get(primary_region, "전 지역"),
            "v": f"{round(c['volume']):,}대", "sp": f"${c['cost_total']:,.0f}",
            "sh": round(share_pct), "ot": on_time_pct,
            "g": grade, "gk": "esg",
            "cr": "—",
            "st": _carrier_status(share_pct),
            "carrier_id": cid, "region_id": primary_region,
            "volume": c["volume"], "volume_unit": "대", "total_volume": c["volume"],
            "spend_100m": round(c["cost_total"], 2),
            "share_pct": share_pct, "contract_left_pct": None,
            "color": CARRIER_COLORS.get(cid, DEFAULT_COLOR),
            "share_over_cap": share_pct > DEPENDENCY_DANGER,
        })

    keys = {
        "-share": lambda x: -x["share_pct"],
        "share": lambda x: x["share_pct"],
        "-ot": lambda x: -(x["ot"] or 0),
        "ot": lambda x: (x["ot"] or 0),
        "-volume": lambda x: -x["volume"],
        "volume": lambda x: x["volume"],
        "name": lambda x: x["n"],
    }
    items.sort(key=keys.get(sort, keys["-share"]))
    return {"total": len(items), "items": items}


# ---------------------------------------------------------------------------
# 5. CSV 내보내기 ('CSV' 버튼)
# ---------------------------------------------------------------------------
CSV_HEADER = ["운송사", "설명", "모드", "주력 지역권", "물량", "단위", "집행액(USD)",
              "비중(%)", "정시율(%)", "등급", "등급기준", "계약 잔량(%)", "상태"]


def carriers_csv(region_id: str | None = None, mode: str | None = None) -> str:
    data = get_carriers(region_id, mode)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADER)
    for c in data["items"]:
        writer.writerow([
            c["n"], c["sub"], "/".join(MODE_KO.get(m, m) for m in c["m"]), c["rg"],
            f"{c['volume']:.0f}", c["volume_unit"], f"{c['spend_100m']:.2f}",
            f"{c['share_pct']:.0f}", c["ot"], c["g"], c["gk"].upper(),
            "" if c["contract_left_pct"] is None else f"{c['contract_left_pct']:.0f}",
            c["st"][1],
        ])
    # Excel 한글 깨짐 방지를 위한 UTF-8 BOM
    return "﻿" + buf.getvalue()


# ---------------------------------------------------------------------------
# 6. 요약 KPI
# ---------------------------------------------------------------------------
def get_allocation_summary(region_id: str | None = None) -> dict:
    """배분 화면 상단/요약용. 전체 HHI와 위험 지역권을 뽑아준다."""
    data = get_allocations(region_id)
    allocs = data["allocations"]
    if not allocs:
        return {"region_count": 0, "avg_hhi": 0, "risk_regions": [], "carrier_count": 0}

    carriers = get_carriers(region_id)["items"]
    risky = [
        {"region_id": a["region_id"], "region_name": a["rg"], "hhi": a["hhi_value"],
         "top_carrier": a["top_carrier"], "top_share_pct": a["top_share_pct"], "tone": a["wt"]}
        for a in allocs if a["wt"]
    ]
    return {
        "region_count": len(allocs),
        "carrier_count": len(carriers),
        "total_volume": data["grand_total_volume"],
        "total_spend_100m": round(sum(a["spend_100m"] for a in allocs), 2),
        "avg_hhi": round(sum(a["hhi_value"] for a in allocs) / len(allocs), 4),
        "max_hhi_region": max(allocs, key=lambda a: a["hhi_value"])["rg"],
        "risk_regions": risky,
    }

"""One loader function per candidate dataset. Each returns list[NormalizedService].

Shared by both screen.py (Layer-1, no-LLM data-quality screening) and
agents.py/run_phase2.py (the actual CarrierAgent/Coordinator negotiation) —
this is the one place that knows each dataset's native quirks (CEU vs cbm
pricing, node_id vs location_id, KRW vs USD), so nothing downstream has to.
Known approximations are flagged inline with APPROX.
"""
import glob
import json
import os

from schema import NormalizedService

KRW_PER_USD = 1350.0  # fixed approx FX for v1_final/v2_fixed (no currency field / KRW-only)


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# 1. dataset_v1_final  (Set1/2/3, nested carrier + services[], KRW implied)
# ---------------------------------------------------------------------------
def load_v1_final(base):
    out = []
    for fp in sorted(glob.glob(os.path.join(base, "dataset_v1_final/json/Set*/*.json"))):
        if fp.endswith("v1_all.json") or "scenarios" in fp:
            continue
        set_name = os.path.basename(os.path.dirname(fp))  # Set1 / Set2 / Set3
        d = json.load(open(fp, encoding="utf-8"))
        if "services" not in d:
            continue
        rel = d.get("reliability_score", 0.8)
        for i, s in enumerate(d["services"]):
            unit_cost_krw = (
                _f(s.get("base_rate")) + _f(s.get("fuel_surcharge")) + _f(s.get("season_surcharge"))
            )
            total_days = _f(s.get("real_transit_days")) or _f(s.get("transit_days"))
            transit_days = _f(s.get("transit_days"))
            out.append(NormalizedService(
                service_id=f"{d['carrier_id']}-{i:03d}",
                carrier_id=d["carrier_id"], carrier_name=d.get("carrier_name", d["carrier_id"]),
                mode=d["mode"], origin=s["origin"], destination=s["destination"],
                cost_usd=unit_cost_krw / KRW_PER_USD,
                cost_unit=s.get("cost_basis", "unit"),
                transit_days=transit_days, wait_days=max(total_days - transit_days, 0.0),
                total_days=total_days, reliability_score=rel,
                co2_kg=s.get("co2_per_cbm"), available_capacity=_f(s.get("available_capacity"), None),
                priority_level=d.get("priority_level", "BALANCED"),
                source_dataset="v1_final", scenario_group=set_name, raw=s,
            ))
    return out


# ---------------------------------------------------------------------------
# 2. dataset_v2_fixed  (same shape as v1, richer fields, explicit currency)
# ---------------------------------------------------------------------------
def load_v2_fixed(base):
    out = []
    for fp in sorted(glob.glob(os.path.join(base, "dataset_v2_fixed/json/Set*/*.json"))):
        if "scenarios" in fp:
            continue
        set_name = os.path.basename(os.path.dirname(fp))
        d = json.load(open(fp, encoding="utf-8"))
        if "services" not in d:
            continue
        rel = d.get("reliability_score", 0.8)
        fx = KRW_PER_USD if d.get("currency") == "KRW" else 1.0
        fuel_pct = _f(d.get("fuel_surcharge_pct"))
        for i, s in enumerate(d["services"]):
            base_rate = _f(s.get("base_rate"))
            unit_cost = base_rate * (1 + fuel_pct / 100) + _f(s.get("peak_season_surcharge"))
            transit_days = _f(s.get("transit_days"))
            total_days = _f(s.get("transit_days_p90")) or transit_days
            out.append(NormalizedService(
                service_id=f"{d['carrier_id']}-{i:03d}",
                carrier_id=d["carrier_id"], carrier_name=d.get("carrier_name", d["carrier_id"]),
                mode=d["mode"], origin=s["origin"], destination=s["destination"],
                cost_usd=unit_cost / fx, cost_unit=s.get("cost_basis", "unit"),
                transit_days=transit_days, wait_days=max(total_days - transit_days, 0.0),
                total_days=total_days, reliability_score=rel,
                co2_kg=s.get("co2_kg_per_cbm"), available_capacity=_f(s.get("available_capacity"), None),
                priority_level=d.get("priority_level", "BALANCED"),
                source_dataset="v2_fixed", scenario_group=set_name, raw=s,
            ))
    return out


# ---------------------------------------------------------------------------
# helpers shared by the "node-graph" family (v3 / ver5 / yubin_ver4)
# ---------------------------------------------------------------------------
def _node_code(end):
    return end.get("location_id") or end.get("node_id")


def _vehicle_cost_usd(s):
    """APPROX: mirrors the per_vehicle / per_transporter / per_wagon / per_kg
    conversion documented in yum_plus_yubin_ver4/README_MERGED.md. Falls back
    to None (caller skips the leg) for pricing models we can't reduce to a
    single per-vehicle number without more context (e.g. LCL container legs).
    """
    p = s.get("pricing", {})
    model = p.get("pricing_model")
    if "cost_usd_per_vehicle_all_in" in p:
        return p["cost_usd_per_vehicle_all_in"]
    if model == "per_vehicle":
        return p.get("rate_per_vehicle")
    if model == "per_wagon":
        rpw = p.get("rate_per_wagon")
        return rpw / 8 if rpw else None
    if model == "per_transporter":
        rate = p.get("rate_per_transporter")
        fleet = s.get("fleet") or [{}]
        cap = fleet[0].get("vehicle_capacity", 5)
        return rate / cap if rate else None
    if model == "chargeable_weight":  # air, per_kg
        rate = p.get("rate_per_kg")
        return rate * 1700 if rate else None  # 1.7t reference sedan, per yubin README
    return None


def _transit_total_days(s):
    sch = s.get("schedule", {})
    if "total_days_with_wait" in sch:
        return sch.get("transit_days", 0.0), sch["total_days_with_wait"] - sch.get("transit_days", 0.0), sch["total_days_with_wait"]
    transit_h = sch.get("transit_hours")
    transit_d = sch.get("transit_days", (transit_h / 24) if transit_h is not None else None)
    wait_d = sch.get("average_wait_days")
    if wait_d is None and "average_wait_hours" in sch:
        wait_d = sch["average_wait_hours"] / 24
    if transit_d is None:
        return None, None, None
    wait_d = wait_d or 0.0
    return transit_d, wait_d, transit_d + wait_d


def _capacity(s):
    cap = s.get("capacity", {})
    for k in ("available_vehicle_slots", "available_weight_kg"):
        if k in cap:
            return cap[k]
    fleet = s.get("fleet")
    if fleet:
        return sum(f.get("available_count", 0) * f.get("vehicle_capacity", 1) for f in fleet)
    return None


def _reliability(s):
    perf = s.get("performance", {})
    return perf.get("on_time_rate", 0.8)


def _co2(s):
    env = s.get("environment", {})
    return env.get("co2_kg_per_vehicle")


def _cargo_ok_vehicle(s):
    allowed = s.get("cargo_conditions", {}).get("allowed_cargo_types", [])
    if "carries_finished_vehicle" in s:
        return bool(s["carries_finished_vehicle"])
    return "FINISHED_VEHICLE" in allowed


def _load_node_graph_family(base, subdir, mode_dirs, dataset_tag):
    out = []
    for mode_dir in mode_dirs:
        pattern = os.path.join(base, subdir, mode_dir, "*.json") if mode_dirs != ["."] \
            else os.path.join(base, subdir, "*.json")
        for fp in sorted(glob.glob(pattern)):
            if "인프라" in fp or fp.endswith(("incoterms.json", "customs_rules.json", "transfer_rules.json", "coords.json")):
                continue
            d = json.load(open(fp, encoding="utf-8"))
            if "services" not in d:
                continue
            carrier = d.get("carrier", {})
            for s in d["services"]:
                if not _cargo_ok_vehicle(s):
                    continue
                cost = _vehicle_cost_usd(s)
                transit_d, wait_d, total_d = _transit_total_days(s)
                if cost is None or total_d is None:
                    continue
                out.append(NormalizedService(
                    service_id=s.get("service_id", ""),
                    carrier_id=carrier.get("carrier_id", "?"), carrier_name=carrier.get("carrier_name", "?"),
                    mode=carrier.get("group", s.get("mode", "?")),
                    origin=_node_code(s["origin"]), destination=_node_code(s["destination"]),
                    cost_usd=cost, cost_unit="vehicle",
                    transit_days=transit_d, wait_days=wait_d, total_days=total_d,
                    reliability_score=_reliability(s), co2_kg=_co2(s),
                    available_capacity=_capacity(s),
                    allowed_vehicle_types=s.get("cargo_conditions", {}).get("allowed_vehicle_types") or None,
                    carrier_role=carrier.get("role"),
                    source_dataset=dataset_tag, raw=s,
                ))
    return out


# ---------------------------------------------------------------------------
# 3. glovis_multi_agent_dataset_v3_usd_realistic  (mode subfolders)
# ---------------------------------------------------------------------------
def load_v3(base):
    return _load_node_graph_family(
        base, "glovis_multi_agent_dataset_v3_usd_realistic",
        ["Ship", "Train", "Road", "Plane"], "v3_usd_realistic",
    )


# ---------------------------------------------------------------------------
# 4. all_mixed_ver5  (flat files, most fully pre-enriched)
#    RETIRED — this dataset folder no longer exists on disk (superseded by
#    fina_data(ver6) below). Left in place only as a reference for the
#    _load_node_graph_family shape; calling this will raise FileNotFoundError.
# ---------------------------------------------------------------------------
def load_ver5(base):
    return _load_node_graph_family(base, "all_mixed_ver5", ["."], "ver5")


# ---------------------------------------------------------------------------
# 4b. fina_data(ver6)  (flat files — same shape as ver5, plus carrier.role
#     ("OWN_FLEET" for Glovis vs "PARTNER") and staggered rate validity)
# ---------------------------------------------------------------------------
def load_ver6(base):
    return _load_node_graph_family(base, "fina_data(ver6)", ["."], "ver6")


# ---------------------------------------------------------------------------
# 5. yum_plus_yubin_ver4  (flat files, merged v2+v3 lineage)
# ---------------------------------------------------------------------------
def load_yubin_ver4(base):
    return _load_node_graph_family(base, "yum_plus_yubin_ver4", ["."], "yubin_ver4")


# ---------------------------------------------------------------------------
# 6. yum_ver2_all  (flat carrier_0N rows, CEU/vehicle_class based)
# ---------------------------------------------------------------------------
def load_yum_v2(base):
    out = []
    idx = json.load(open(os.path.join(base, "yum_ver2_all/index.json"), encoding="utf-8"))["carriers"]
    id2meta = {c["id"]: c for c in idx}
    for fp in sorted(glob.glob(os.path.join(base, "yum_ver2_all/carrier_*.json"))):
        rows = json.load(open(fp, encoding="utf-8"))
        for r in rows:
            meta = id2meta.get(r["id"], {})
            out.append(NormalizedService(
                service_id=r.get("row_id", ""),
                carrier_id=meta.get("code", str(r["id"])), carrier_name=meta.get("name", str(r["id"])),
                mode=meta.get("mode", "?").lower(),
                origin=r["from"], destination=r["to"],
                cost_usd=_f(r.get("cost_usd_per_unit")), cost_unit="vehicle",
                transit_days=_f(r.get("transit_days")), wait_days=_f(r.get("avg_wait_days")),
                total_days=_f(r.get("total_days_with_wait")) or _f(r.get("transit_days")),
                reliability_score=_f(r.get("on_time_rate"), 0.8), co2_kg=r.get("co2_kg_per_unit"),
                available_capacity=r.get("capacity_units_per_dispatch"),
                vehicle_class=r.get("vehicle_class"),
                source_dataset="yum_ver2_all", raw=r,
            ))
    return out


LOADERS = {
    "ver6": load_ver6,
    # Retired — dataset folders no longer exist on disk, calling these raises
    # FileNotFoundError. Kept only so the 6-way comparison history is
    # reconstructable if the data ever comes back.
    "v1_final": load_v1_final,
    "v2_fixed": load_v2_fixed,
    "v3_usd_realistic": load_v3,
    "ver5": load_ver5,
    "yubin_ver4": load_yubin_ver4,
    "yum_ver2_all": load_yum_v2,
}

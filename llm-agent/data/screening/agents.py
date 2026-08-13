"""Phase 2: CarrierAgent + GlovisAgent with a real 2-round negotiation.

Mirrors the inquiry -> offer -> accept/reject pattern already used by
agentsociety/cityagent/firmblocks/collaboration_block.py (sending_price_check
-> handle_product_request -> decide_transaction_order), plus one counter-offer
round so CarrierAgent actually behaves like an independent negotiating party
instead of a stateless "echo my rate" function.

Explicit round budget (documented, not implicit):
  Round 1 — GlovisAgent sends an inquiry (target price, quantity) for a leg.
            CarrierAgent decides ACCEPT / COUNTER / REJECT using its own
            state (remaining capacity, priority_level) — not just the source data.
  Round 2 — only if the carrier countered: GlovisAgent decides ACCEPT / WALK_AWAY.
  -> at most 2 LLM calls per leg for the carrier side + 1 for the buyer-side
     counter decision = up to 3 calls/leg, 1 call/leg if accepted immediately.
"""
import json
from dataclasses import replace as dc_replace

from ceu import ceu_multiplier
from kb import customs_for, incoterm_clause
from llm_client import LLMClient
from route_search import find_routes

CARRIER_SYSTEM = """너는 화물 운송사의 협상 담당 에이전트다. 너의 우선순위 성향(priority_level)에 따라 판단이 달라져야 한다:
- LOW_COST: 가격 할인 여지가 있음. 물량이 많으면 카운터오퍼로 할인 제안 가능
- FASTEST/GREEN/BALANCED: 가격은 잘 안 깎아주는 대신 정시성/친환경성을 근거로 제시
너의 서비스 정보(내부 데이터)가 주어진다. 그 안의 숫자를 기준으로만 판단하고 지어내지 마라.
남은 용량(remaining_capacity)이 요청 수량보다 적으면 반드시 REJECT 하거나 가능한 수량만 COUNTER 해라.
반드시 JSON으로만 답하라."""

CARRIER_ROUND1_TMPL = """[내부 데이터 — 외부에 그대로 노출 금지, 판단 근거로만 사용]
{capability}
나의 협상 성향(priority_level): {priority_level}
남은 용량(remaining_capacity): {remaining_capacity}

[화주(GlovisAgent)의 인콰이어리]
구간: {origin} -> {destination}, 화물: {cargo}, 요청 수량: {quantity}
화주 제시 목표가(참고용, 정가 대비 {discount_pct}% 할인 요청): {target_price} USD
화주 우선순위: {priority}

다음 JSON 형식으로만 답하라:
{{
  "service_id": "{service_id}",
  "decision": "ACCEPT" | "COUNTER" | "REJECT",
  "offered_price_usd": 0,
  "offered_quantity": 0,
  "reason": "1~2문장"
}}"""

BUYER_SYSTEM = """너는 화주를 대신하는 GlovisAgent다. 운송사가 카운터오퍼를 보냈다.
화주의 우선순위(COST/TIME/BALANCED)를 기준으로 그 카운터를 받아들일지 판단하라.
COST 우선순위면 가격에 민감하게, TIME 우선순위면 예약 확보를 더 중시해서 판단하라.
반드시 JSON으로만 답하라."""

BUYER_ROUND2_TMPL = """원래 요청가: {target_price} USD
운송사 카운터오퍼: {offer}
화주 우선순위: {priority}

다음 JSON 형식으로만 답하라:
{{
  "decision": "ACCEPT" | "WALK_AWAY",
  "reason": "1문장"
}}"""

def _emit(on_progress, event):
    """Fire-and-forget progress event. A broken/slow frontend callback must
    never take down a negotiation that's mid-flight, so this swallows
    whatever the callback raises."""
    if on_progress is None:
        return
    try:
        on_progress(event)
    except Exception:
        pass


class CarrierAgent:
    """One instance per negotiation session — holds a live capacity ledger,
    so accepting a deal for one route actually consumes capacity that a later
    route (same carrier, same leg) will see reflected in remaining_capacity.
    That statefulness is what makes this an agent rather than a lookup function.
    """

    def __init__(self, llm: LLMClient, on_progress=None):
        self.llm = llm
        self.on_progress = on_progress
        self.capacity_ledger = {}   # service_id -> remaining capacity
        self.log = []               # full negotiation trace
        self._deal_cache = {}       # (service_id, quantity) -> already-negotiated result

    def _remaining(self, leg):
        if leg.service_id not in self.capacity_ledger:
            # `or 9999` would treat an explicit 0 (sold out) as falsy and
            # silently reopen unlimited capacity — only a genuinely unset
            # (None) capacity should fall back to the default.
            self.capacity_ledger[leg.service_id] = (
                leg.available_capacity if leg.available_capacity is not None else 9999
            )
        return self.capacity_ledger[leg.service_id]

    def negotiate(self, leg, request):
        """Runs up to NEGOTIATION_ROUNDS. Returns a dict with the final
        agreed terms (or deal_reached=False if the carrier rejected /
        the buyer walked away).

        Cached per service_id: when the same leg is reused across several
        *alternative* candidate scenarios for the same request, those are
        mutually-exclusive options a shipper is comparing, not sequential
        real bookings — so capacity must not be depleted once per scenario.
        The leg is only actually "consumed" once, the first time it's asked.
        """
        cache_key = (leg.service_id, request["quantity"])
        if cache_key in self._deal_cache:
            return self._deal_cache[cache_key]

        _emit(self.on_progress, {"stage": "negotiate_leg", "status": "round1_start",
                                   "service_id": leg.service_id, "carrier_id": leg.carrier_id, "mode": leg.mode})

        capability = _leg_capability(leg)
        target_price = round(leg.cost_usd * 0.95, 2)  # buyer opens by asking a 5% discount
        remaining = self._remaining(leg)

        user1 = CARRIER_ROUND1_TMPL.format(
            capability=json.dumps(capability, ensure_ascii=False),
            priority_level=leg.priority_level, remaining_capacity=remaining,
            origin=leg.origin, destination=leg.destination,
            cargo=request["cargo"], quantity=request["quantity"],
            target_price=target_price, discount_pct=5, priority=request["priority"],
            service_id=leg.service_id,
        )
        r1, raw1 = self.llm.chat_json(CARRIER_SYSTEM, user1, max_tokens=300)
        record = {"leg_service_id": leg.service_id, "carrier_id": leg.carrier_id,
                   "round1_carrier": r1, "rounds_used": 1,
                   "prompts": {"round1": {"system": CARRIER_SYSTEM, "user": user1, "raw_response": raw1}}}
        _emit(self.on_progress, {"stage": "negotiate_leg", "status": "round1_done",
                                   "service_id": leg.service_id, "carrier_id": leg.carrier_id,
                                   "decision": (r1 or {}).get("decision")})

        result = None
        if not r1:
            result = {"deal_reached": False, "reason": "unparseable_response", "rounds_used": 1,
                      "grounded": True}
        elif r1.get("decision") == "REJECT":
            result = {"deal_reached": False, "reason": r1.get("reason"), "rounds_used": 1,
                      "grounded": True}
        elif r1.get("decision") == "ACCEPT":
            granted_qty = min(request["quantity"], remaining)
            result = {"deal_reached": granted_qty > 0, "price_usd": leg.cost_usd,
                      "quantity": granted_qty, "total_days": leg.total_days,
                      "rounds_used": 1, "grounded": True}
            if granted_qty <= 0:
                result["reason"] = "capacity_exhausted_despite_accept"
        else:  # COUNTER -> round 2, buyer decides
            _emit(self.on_progress, {"stage": "negotiate_leg", "status": "round2_start",
                                       "service_id": leg.service_id, "carrier_id": leg.carrier_id})
            user2 = BUYER_ROUND2_TMPL.format(
                target_price=target_price, offer=json.dumps(r1, ensure_ascii=False),
                priority=request["priority"],
            )
            r2, raw2 = self.llm.chat_json(BUYER_SYSTEM, user2, max_tokens=200)
            record["round2_buyer"] = r2
            record["rounds_used"] = 2
            record["prompts"]["round2"] = {"system": BUYER_SYSTEM, "user": user2, "raw_response": raw2}
            if r2 and r2.get("decision") == "ACCEPT":
                # The deal's actual numbers are computed here, not trusted
                # verbatim from the LLM: offered_price_usd only wins if it's
                # within tolerance of the listed rate (else the listed rate
                # is used), offered_quantity can only ever shrink the deal
                # (never exceed what's requested or physically available),
                # and total_days is a property of the leg — not something a
                # carrier negotiates away, so it's never LLM-supplied at all.
                grounded = _check_grounding(r1.get("offered_price_usd"), leg)
                price_usd = r1.get("offered_price_usd") if grounded else leg.cost_usd
                offered_qty = r1.get("offered_quantity")
                granted_qty = min(offered_qty, request["quantity"], remaining) \
                    if isinstance(offered_qty, (int, float)) and offered_qty > 0 \
                    else min(request["quantity"], remaining)
                result = {"deal_reached": granted_qty > 0,
                          "price_usd": price_usd, "quantity": granted_qty,
                          "total_days": leg.total_days, "rounds_used": 2,
                          "grounded": grounded}
                if granted_qty <= 0:
                    result["reason"] = "capacity_exhausted_despite_accept"
            else:
                result = {"deal_reached": False, "reason": (r2 or {}).get("reason", "walked_away"),
                           "rounds_used": 2, "grounded": True}

        if result["deal_reached"]:
            self.capacity_ledger[leg.service_id] = max(0, remaining - result["quantity"])
        result["self_operated"] = False
        record["final"] = result
        self.log.append(record)
        self._deal_cache[cache_key] = result
        _emit(self.on_progress, {"stage": "negotiate_leg", "status": "done",
                                   "service_id": leg.service_id, "carrier_id": leg.carrier_id,
                                   "deal_reached": result["deal_reached"]})
        return result

    def use_own_capacity(self, leg, request):
        """No negotiation — this leg belongs to Glovis itself, so there's no
        counterparty to bargain with, just an internal capacity check. Costs
        zero LLM calls, which is itself realistic: a company doesn't need an
        LLM negotiation round to decide whether to use its own truck."""
        cache_key = (leg.service_id, request["quantity"])
        if cache_key in self._deal_cache:
            return self._deal_cache[cache_key]

        remaining = self._remaining(leg)
        qty = min(request["quantity"], remaining)
        result = {
            "deal_reached": qty > 0,
            "price_usd": leg.cost_usd, "quantity": qty, "total_days": leg.total_days,
            "rounds_used": 0, "grounded": True, "self_operated": True,
        }
        if not result["deal_reached"]:
            result["reason"] = "own_capacity_exhausted"
        else:
            self.capacity_ledger[leg.service_id] = max(0, remaining - qty)
        self.log.append({"leg_service_id": leg.service_id, "carrier_id": leg.carrier_id,
                          "self_operated": True, "final": result})
        self._deal_cache[cache_key] = result
        _emit(self.on_progress, {"stage": "negotiate_leg", "status": "self_operated",
                                   "service_id": leg.service_id, "carrier_id": leg.carrier_id,
                                   "deal_reached": result["deal_reached"]})
        return result


def _leg_capability(leg):
    """carrier_capability plus whatever extra fields this dataset's raw
    record happens to carry (hazmat/temp flags, dwell/demurrage, environment,
    valid_to, service_tier...) — datasets differ, so we pass through
    everything present instead of hardcoding one dataset's schema."""
    cap = {
        "carrier_id": leg.carrier_id, "service_id": leg.service_id, "mode": leg.mode,
        "lane": {"from": leg.origin, "to": leg.destination},
        "transit_days": leg.transit_days, "wait_days": leg.wait_days,
        "cost_basis": leg.cost_unit, "listed_rate_usd": round(leg.cost_usd, 2),
        "reliability_score": leg.reliability_score,
    }
    raw = leg.raw or {}
    for k in ("cargo_conditions", "surcharges", "dwell", "environment", "mode_details",
              "performance", "valid_to", "service_tier", "cii_grade", "co2_kg_per_unit",
              "co2_per_cbm", "hazmat_extra_requirements"):
        if k in raw:
            cap[k] = raw[k]
    if leg.co2_kg is not None:
        cap["co2_kg"] = leg.co2_kg
    return cap


def _check_grounding(offered_price, leg, tol=0.15):
    """True unless the LLM's offered_price_usd is present but drifts more than
    `tol` from the leg's actual listed rate. Call with None (ACCEPT/REJECT/no
    offer made) to get the trivial "nothing to hallucinate about" True."""
    if offered_price is None:
        return True
    if not isinstance(offered_price, (int, float)):
        return False
    return abs(offered_price - leg.cost_usd) <= tol * max(leg.cost_usd, 1)


GLOVIS_MARKERS = ("GLOVIS", "글로비스")

# 3 of the 6 datasets contain no real Hyundai Glovis entity at all (v1_final,
# v2_fixed, v3_usd_realistic). For comparison purposes only, this designates
# a stand-in "own fleet" carrier per dataset — NOT real Glovis data, just an
# existing carrier in that dataset relabeled as the self-operated leg for
# testing the own-capacity-shortcut logic consistently across all 6.
# v3_usd_realistic has no stand-in: it has zero truck carriers at all (a
# known gap from the phase-1 screening), so there's nothing plausible to
# relabel as "our own inland fleet" — it stays a pure broker.
GLOVIS_STANDIN_BY_DATASET = {
    "v1_final": "TRK001", "v2_fixed": "TRK001", "v3_usd_realistic": None,
}


def is_own_leg(leg, standin_carrier_id=None):
    """True if this leg is operated by Hyundai Glovis itself.

    ver6 states this explicitly (carrier.role == "OWN_FLEET" in the source
    data) — no guessing needed. The name/id string match below is the
    fallback for datasets that don't carry that field, and
    GLOVIS_STANDIN_BY_DATASET covers the 3 retired datasets that had no
    Glovis entity at all."""
    if leg.carrier_role == "OWN_FLEET":
        return True
    hay = f"{leg.carrier_id} {leg.carrier_name}".upper()
    if any(m in hay for m in GLOVIS_MARKERS) or "글로비스" in leg.carrier_name:
        return True
    return standin_carrier_id is not None and leg.carrier_id == standin_carrier_id


class GlovisAgent:
    def __init__(self, llm: LLMClient, kb: dict, standin_carrier_id=None, on_progress=None):
        self.llm = llm
        self.kb = kb
        self.standin_carrier_id = standin_carrier_id  # synthetic Glovis stand-in, or None
        self.on_progress = on_progress  # optional callable(event: dict) -> None

    def run(self, services, origin, destination, priority="BALANCED",
            extra_priorities=None, cargo="SEDAN", quantity=10, top_k=3, max_hops=3):
        """extra_priorities: additional sort axes (e.g. ["TIME"]) whose top_k
        candidates are merged into the same negotiated batch as `priority`'s,
        so one run() call can return a diverse COST+TIME(+...) spread without
        re-negotiating shared legs (CarrierAgent caches per service_id+quantity
        within this one run). Omit it and behavior is identical to a single-
        priority run — existing callers are unaffected."""
        _emit(self.on_progress, {"stage": "route_search", "status": "start",
                                   "origin": origin, "destination": destination})
        # CEU-scale cost *before* search, not after picking a route: ranking
        # by COST has to sort on the price for the vehicle actually being
        # shipped, not the SEDAN-equivalent baseline every ver5-style service
        # is stored at. yum_ver2_all rows are already priced per vehicle_class
        # (multiplier 1.0, no-op); route_search's vehicle_type filter then
        # drops any leg that can't carry this cargo at all.
        services = [dc_replace(s, cost_usd=s.cost_usd * ceu_multiplier(cargo))
                    if s.allowed_vehicle_types is not None else s
                    for s in services]
        routes = find_routes(services, origin, destination, max_hops=max_hops, vehicle_type=cargo)
        if not routes:
            _emit(self.on_progress, {"stage": "route_search", "status": "no_routes"})
            return {"error": "no_routes_found", "origin": origin, "destination": destination}
        _emit(self.on_progress, {"stage": "route_search", "status": "done", "n_routes_found": len(routes)})

        sort_key = {
            "COST": lambda r: r.total_cost_usd,
            "TIME": lambda r: r.total_days,
            "CO2": lambda r: r.total_co2_kg,
        }.get
        default_key = lambda r: r.total_cost_usd + r.total_days * 20

        axes = [priority] + [p for p in (extra_priorities or []) if p != priority]
        seen_paths, picked = set(), []
        for axis in axes:
            n_added = 0
            for r in sorted(routes, key=sort_key(axis, default_key)):
                sig = tuple((l.carrier_id, l.origin, l.destination) for l in r.legs)
                if sig in seen_paths:
                    continue
                seen_paths.add(sig)
                picked.append(r)
                n_added += 1
                if n_added >= top_k:
                    break

        _emit(self.on_progress, {"stage": "scenarios_selected", "count": len(picked),
                                   "paths": [r.path_str() for r in picked]})

        request = {"origin": origin, "destination": destination, "cargo": cargo,
                    "priority": priority, "quantity": quantity}
        carrier_agent = CarrierAgent(self.llm, on_progress=self.on_progress)  # fresh ledger per GlovisAgent run

        scenario_summaries = []
        for i, route in enumerate(picked):
            _emit(self.on_progress, {"stage": "scenario_negotiation", "status": "start",
                                       "scenario_index": i, "of": len(picked), "path": route.path_str()})
            deals = [
                carrier_agent.use_own_capacity(leg, request)
                if is_own_leg(leg, self.standin_carrier_id) else carrier_agent.negotiate(leg, request)
                for leg in route.legs
            ]
            _emit(self.on_progress, {"stage": "scenario_negotiation", "status": "done", "scenario_index": i})
            feasible = all(d["deal_reached"] for d in deals)
            n_own = sum(1 for d in deals if d.get("self_operated"))
            agreed_quantity = min((d.get("quantity", 0) for d in deals), default=0) if feasible else None
            listed_cost_usd_per_vehicle = round(route.total_cost_usd, 1)
            agreed_cost_usd_per_vehicle = round(sum(d.get("price_usd", 0) for d in deals), 1) if feasible else None

            leg_details = []
            path_codes = [route.legs[0].origin] if route.legs else []
            modes, seen_modes = [], set()
            for leg, d in zip(route.legs, deals):
                path_codes.append(leg.destination)
                if leg.mode not in seen_modes:
                    seen_modes.add(leg.mode)
                    modes.append(leg.mode)
                detail = {
                    "carrier_id": leg.carrier_id, "carrier_name": leg.carrier_name,
                    "service_id": leg.service_id, "source_dataset": leg.source_dataset,
                    "mode": leg.mode, "origin": leg.origin, "destination": leg.destination,
                    "self_operated": d.get("self_operated", False),
                    "listed_cost_usd_per_vehicle": round(leg.cost_usd, 2),
                    "agreed_cost_usd_per_vehicle": round(d["price_usd"], 2) if d.get("deal_reached") else None,
                    "days": d.get("total_days", leg.total_days),
                    "co2_kg_per_vehicle": leg.co2_kg,
                    "reliability": leg.reliability_score,
                    "negotiation_rounds": d.get("rounds_used"),
                    "deal_reached": d.get("deal_reached"),
                }
                if leg.available_capacity is not None:
                    detail["available_capacity"] = leg.available_capacity
                leg_details.append(detail)

            scenario_summaries.append({
                "index": i, "path": route.path_str(), "path_codes": path_codes, "modes": modes,
                "feasible": feasible,
                "requested_quantity": quantity, "agreed_quantity": agreed_quantity,
                "agreed_cost_usd_per_vehicle": agreed_cost_usd_per_vehicle,
                "agreed_total_days": round(sum(d.get("total_days", 0) for d in deals), 1) if feasible else None,
                "agreed_shipment_cost_usd": round(agreed_cost_usd_per_vehicle * agreed_quantity, 1)
                                            if feasible and agreed_quantity else None,
                "listed_cost_usd_per_vehicle": listed_cost_usd_per_vehicle,
                "listed_total_days": round(route.total_days, 1),
                "listed_shipment_cost_usd": round(listed_cost_usd_per_vehicle * quantity, 1),
                "total_co2_kg": round(route.total_co2_kg, 1),
                "reliability": round(route.reliability, 3),
                "rounds_used": [d["rounds_used"] for d in deals],
                "legs_operated_by_glovis": n_own, "legs_total": len(deals),
                "legs": leg_details,
            })

        origin_country = origin[:2]
        dest_country = destination[:2]
        customs = customs_for(self.kb, origin_country, dest_country)
        incoterm_code = "CIP" if any(s["path"].count("→") > 1 for s in scenario_summaries) else "FOB"
        clause = incoterm_clause(self.kb, incoterm_code)

        grounded = sum(1 for r in carrier_agent.log if r["final"]["grounded"])
        rejected = sum(1 for r in carrier_agent.log if not r["final"]["deal_reached"])
        n_self = sum(1 for r in carrier_agent.log if r["final"].get("self_operated"))
        _emit(self.on_progress, {"stage": "complete"})
        return {
            "request": request,
            "n_candidate_routes_found": len(routes),
            "scenarios": scenario_summaries,
            "negotiation_trace": carrier_agent.log,
            "customs_used": customs, "incoterm_used": incoterm_code, "incoterm_clause": clause,
            "grounding_check": {
                "total_leg_negotiations": len(carrier_agent.log),
                "grounded": grounded, "hallucinated": len(carrier_agent.log) - grounded,
                "deals_rejected_or_walked": rejected,
                "legs_self_operated_by_glovis": n_self,
                "legs_externally_negotiated": len(carrier_agent.log) - n_self,
            },
            "cost_metrics": {
                "llm_calls": self.llm.total_calls, "total_tokens": self.llm.total_tokens,
                "wall_clock_sec": round(self.llm.total_seconds, 1),
            },
        }

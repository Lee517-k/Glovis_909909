from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

COST_TOLERANCE_PCT = 15.0
TRANSIT_TOLERANCE_HOURS = 24.0


class YPReliabilityService:
    """완료된 시나리오와 운송 능력을 매칭해 GlovisTower 방식으로 점수를 계산한다."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def list_carriers(self) -> list[dict[str, Any]]:
        with self._connect() as con:
            ids = [r[0] for r in con.execute("SELECT carrier_id FROM carrier_capabilities WHERE is_active=1 AND mapping_status='approved' AND validation_status!='excluded' GROUP BY carrier_id ORDER BY MAX(carrier_name)")]
        return [result for carrier_id in ids if (result := self.detail(carrier_id, summary_only=True))]

    def detail(self, carrier_id: str, summary_only: bool = False) -> dict[str, Any] | None:
        capabilities = self._capabilities(carrier_id)
        if not capabilities:
            return None
        grouped, historical_count = self._matched_history(carrier_id)
        pending, verified, costs, times = [], [], [], []
        matched_count = 0
        for capability in capabilities:
            metric, row_costs, row_times, is_verified, completed_count = self._metric(capability, grouped.get(capability["capability_id"], []))
            costs.extend(row_costs); times.extend(row_times); matched_count += completed_count
            (verified if is_verified else pending).append(metric)
        total, verified_count = len(capabilities), len(verified)
        coverage = _pct(verified_count, total)
        cost_error = round(mean(costs), 1) if costs else 0.0
        days_error = round(mean(times) / 24, 1) if times else 0.0
        score = 0.0
        if verified_count:
            score = round(coverage * .5 + coverage * .2 + max(0, 100 - abs(cost_error)) * .15 + max(0, 100 - abs(days_error) / 3 * 100) * .15, 1)
        candidates = total - verified_count
        return {"carrier_id": carrier_id, "carrier_name": capabilities[0]["carrier_name"], "score": score,
                "status": "verified" if score >= 90 and candidates == 0 else "review" if verified_count else "unverified",
                "validated_count": verified_count, "matched_execution_count": matched_count,
                "verified_capability_count": verified_count, "total_capability_count": total,
                "coverage": coverage, "hit_rate": coverage, "cost_error": cost_error, "days_error": days_error,
                "candidates": candidates, "historical_count": historical_count,
                "metrics": [] if summary_only else pending, "verified_metrics": [] if summary_only else verified,
                "impact": self._impact(total, verified_count, matched_count, historical_count, candidates, costs, times)}

    def _matched_history(self, carrier_id: str):
        with self._connect() as con:
            capabilities = con.execute("""SELECT capability_id,carrier_id,mode,COALESCE(origin_location_id,origin_node_id) origin_id,COALESCE(destination_location_id,destination_node_id) destination_id FROM carrier_capabilities WHERE is_active=1 AND mapping_status='approved'""").fetchall()
            index: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
            for cap in capabilities:
                index[_key(cap["carrier_id"], cap["mode"], cap["origin_id"], cap["destination_id"])].append(cap["capability_id"])
            legs = con.execute("""SELECT l.*,UPPER(COALESCE(s.status,'')) scenario_status,COALESCE(l.origin_location_id,l.origin_node_id) origin_id,COALESCE(l.destination_location_id,l.destination_node_id) destination_id FROM scenario_legs l JOIN scenarios s ON s.scenario_id=l.scenario_id""").fetchall()
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        historical_count = 0
        for leg in legs:
            if _token(leg["carrier_id"]) == _token(carrier_id): historical_count += 1
            ids = index.get(_key(leg["carrier_id"], leg["mode"], leg["origin_id"], leg["destination_id"]), [])
            if len(ids) == 1: grouped[ids[0]].append(dict(leg))
        return grouped, historical_count

    def _metric(self, cap: sqlite3.Row, legs: list[dict[str, Any]]):
        completed = [leg for leg in legs if leg.get("atd") and leg.get("ata") and leg.get("scenario_status") != "CANCELLED"]
        base, hours = cap["typical_base_rate"], cap["typical_transit_hours"]
        costs = [(leg["settled_cost_usd_per_vehicle"] - base) / base * 100 for leg in completed if leg.get("settled_cost_usd_per_vehicle") is not None and base not in (None, 0)]
        actual_hours = [(_dt(leg["ata"]) - _dt(leg["atd"])).total_seconds() / 3600 for leg in completed]
        times = [actual - hours for actual in actual_hours if hours is not None]
        within = bool(completed) and bool(costs) and abs(mean(costs)) <= COST_TOLERANCE_PCT and bool(times) and abs(mean(times)) <= TRANSIT_TOLERANCE_HOURS
        is_verified = cap["validation_status"] == "verified" or bool(completed)
        origin, destination = cap["origin_name"] or cap["origin_location_id"], cap["destination_name"] or cap["destination_location_id"]
        db_value = " · ".join((f"운임 ${base:,.1f}" if base is not None else "운임 미등록", f"소요 {hours:.1f}시간" if hours is not None else "일정 미등록"))
        if not legs: actual, error, verdict, reason = "동일 운송 완료 이력 없음", "산정 불가", "검증 필요", "동일 운송사·구간의 과거 완료 운송 이력이 없습니다."
        elif not completed: actual, error, verdict, reason = f"매칭 {len(legs)}건 · 완료 대기", "완료 대기", "검증 대기", "동일 구간 이력은 있으나 실제 운송이 완료되지 않았습니다."
        else:
            settled = [leg["settled_cost_usd_per_vehicle"] for leg in completed if leg.get("settled_cost_usd_per_vehicle") is not None]
            actual = " · ".join((f"평균 운임 ${mean(settled):,.1f}" if settled else "정산 운임 없음", f"평균 {mean(actual_hours):.1f}시간", f"완료 {len(completed)}건"))
            error = " · ".join(([f"운임 {mean(costs):+.1f}%"] if costs else []) + ([f"일정 {mean(times)/24:+.1f}일"] if times else [])) or "산정 불가"
            verdict, reason = ("허용 범위", "실제 완료 이력이 확인되어 검증되었습니다.") if within else ("보정 필요", "운임 또는 일정 오차가 허용 범위를 벗어났습니다.")
        action = "검증 완료" if cap["validation_status"] == "verified" or is_verified else "보정 후보 유지"
        if cap["validation_status"] == "awaiting_carrier_response": action = "운송사 응답 대기 중"
        return ({"capability_id": cap["capability_id"], "metric": f"{origin} → {destination}", "db_value": db_value, "actual_value": actual, "error": error, "verdict": verdict, "reason": reason, "action": action}, costs, times, is_verified, len(completed))

    def _capabilities(self, carrier_id):
        with self._connect() as con:
            return con.execute("""SELECT capability_id,carrier_id,carrier_name,mode,COALESCE(origin_location_id,origin_node_id) origin_location_id,COALESCE(destination_location_id,destination_node_id) destination_location_id,origin_name,destination_name,typical_base_rate,typical_transit_hours,validation_status FROM carrier_capabilities WHERE carrier_id=? AND is_active=1 AND mapping_status='approved' AND validation_status!='excluded' ORDER BY origin_name,destination_name,capability_id""", (carrier_id,)).fetchall()

    def _connect(self):
        con = sqlite3.connect(f"file:{self.db_path.as_posix()}?mode=ro", uri=True); con.row_factory = sqlite3.Row; return con

    @staticmethod
    def _impact(total, verified, matched, historical, candidates, costs, times):
        if not historical: return f"운송 능력 {total}개와 연결되는 과거 운송사 이력이 없어 검증 대기 상태입니다."
        if not matched: return f"과거 이력 {historical}건은 있으나 완료된 동일 구간 이력이 없어 {candidates}개 구간의 추가 증빙이 필요합니다."
        cost = f"평균 운임 오차 {mean(costs):+.1f}%" if costs else "운임 비교 불가"
        days = f"평균 일정 오차 {mean(times)/24:+.1f}일" if times else "일정 비교 불가"
        return f"완료 시나리오 {matched}건으로 {verified}/{total}개 구간을 검증했습니다. {cost}, {days}이며 나머지 {candidates}개 구간은 추가 근거가 필요합니다."


def _token(value): return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
def _mode(value): return "road" if str(value or "").lower() == "truck" else str(value or "").lower()
def _key(carrier, mode, origin, destination): return _token(carrier), _mode(mode), _token(origin), _token(destination)
def _pct(n, d): return round(n / d * 100, 1) if d else 0.0
def _dt(value): return datetime.fromisoformat(value)

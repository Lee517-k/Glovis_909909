from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import httpx


class YPOllamaSimilarityService:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.base_url = os.getenv("LLM_BASE_URL", "http://34.64.204.1:11434/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "qwen2.5:7b")

    def analyze(self, carrier_id: str, capability_ids: list[str] | None = None) -> dict[str, Any]:
        inputs = self._inputs(carrier_id, capability_ids)
        if not inputs:
            return {"model": self.model, "mode": "ollama", "notice": "", "items": []}
        prompt = json.dumps(inputs, ensure_ascii=False)
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 1800,
                "response_format": {"type": "json_object"},
            },
            timeout=120.0,
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
        parsed = _extract_json(raw)
        allowed = {item["capability_id"] for item in inputs}
        items = []
        for item in parsed.get("items", []):
            if item.get("capability_id") not in allowed:
                continue
            items.append({
                "capability_id": item["capability_id"],
                "similar": bool(item.get("similar", False)),
                "confidence": max(0, min(100, int(item.get("confidence", 0)))),
                "reason": str(item.get("reason", "판단 근거가 없습니다."))[:500],
                "reference_leg_ids": [str(value) for value in item.get("reference_leg_ids", [])][:5],
            })
        return {"model": self.model, "mode": "ollama", "notice": "", "items": items}

    def analyze_with_fallback(self, carrier_id: str, capability_ids: list[str] | None = None) -> dict[str, Any]:
        try:
            return self.analyze(carrier_id, capability_ids)
        except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError):
            inputs = self._inputs(carrier_id, capability_ids)
            return {
                "model": self.model,
                "mode": "rule_based",
                "notice": "LLM과 연결되지 않았습니다. DB 단순 비교로 일치 여부를 판단합니다.",
                "items": [self._rule_based_result(item, carrier_id) for item in inputs],
            }

    @staticmethod
    def _rule_based_result(item: dict[str, Any], carrier_id: str) -> dict[str, Any]:
        target = item["target"]
        candidates = item["historical_candidates"]
        ranked = []
        for leg in candidates:
            same_carrier = str(leg.get("carrier_id")) == carrier_id
            same_origin = leg.get("origin_id") == target.get("origin_id")
            same_destination = leg.get("destination_id") == target.get("destination_id")
            reversed_route = leg.get("origin_id") == target.get("destination_id") and leg.get("destination_id") == target.get("origin_id")
            score = 40 + (30 if same_carrier else 0) + (15 if same_origin else 0) + (15 if same_destination else 0) + (15 if reversed_route else 0)
            ranked.append((min(score, 100), leg))
        ranked.sort(key=lambda value: value[0], reverse=True)
        best = ranked[0] if ranked else None
        similar = bool(best and best[0] >= 55)
        if not best:
            reason = "동일 운송수단이며 운송사 또는 거점이 겹치는 완료 이력이 없습니다."
        else:
            matches = []
            leg = best[1]
            if leg.get("carrier_id") == carrier_id: matches.append("운송사")
            if leg.get("origin_id") == target.get("origin_id"): matches.append("출발지")
            if leg.get("destination_id") == target.get("destination_id"): matches.append("도착지")
            if leg.get("origin_id") == target.get("destination_id") and leg.get("destination_id") == target.get("origin_id"): matches.append("역방향 구간")
            reason = f"동일 운송수단이며 {', '.join(matches) or '연결 거점'} 조건이 일치하는 완료 이력을 DB에서 확인했습니다."
        return {
            "capability_id": item["capability_id"], "similar": similar,
            "confidence": best[0] if best else 0, "reason": reason,
            "reference_leg_ids": [str(leg["leg_id"]) for _, leg in ranked[:5]],
        }

    def _inputs(self, carrier_id: str, capability_ids: list[str] | None):
        connection = sqlite3.connect(f"file:{self.db_path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            params: list[Any] = [carrier_id]
            where = "c.carrier_id=? AND c.is_active=1 AND c.mapping_status='approved' AND c.validation_status!='excluded'"
            if capability_ids:
                where += f" AND c.capability_id IN ({','.join('?' for _ in capability_ids)})"
                params.extend(capability_ids)
            capabilities = connection.execute(f"""SELECT c.capability_id,c.mode,
                COALESCE(c.origin_location_id,c.origin_node_id) origin_id,
                COALESCE(c.destination_location_id,c.destination_node_id) destination_id,
                c.origin_name,c.destination_name,c.typical_base_rate,c.typical_transit_hours
                FROM carrier_capabilities c WHERE {where} ORDER BY c.capability_id LIMIT 30""", params).fetchall()
            legs = connection.execute("""SELECT l.leg_id,l.carrier_id,l.carrier_name,l.mode,
                COALESCE(l.origin_location_id,l.origin_node_id) origin_id,
                COALESCE(l.destination_location_id,l.destination_node_id) destination_id,
                l.cost_usd_per_vehicle,l.settled_cost_usd_per_vehicle,l.transit_hours,l.delay_reason
                FROM scenario_legs l JOIN scenarios s ON s.scenario_id=l.scenario_id
                WHERE l.atd IS NOT NULL AND l.ata IS NOT NULL AND UPPER(COALESCE(s.status,''))!='CANCELLED'""").fetchall()
        finally:
            connection.close()
        result = []
        for capability in capabilities:
            # 동일 운송수단을 우선하고, 동일 운송사 또는 한쪽 거점이 겹치는 완료 이력만 LLM에 전달한다.
            candidates = [dict(leg) for leg in legs if str(leg["mode"]).lower().replace("truck", "road") == str(capability["mode"]).lower().replace("truck", "road") and (leg["carrier_id"] == carrier_id or leg["origin_id"] in (capability["origin_id"], capability["destination_id"]) or leg["destination_id"] in (capability["origin_id"], capability["destination_id"]))][:8]
            result.append({"capability_id": capability["capability_id"], "target": dict(capability), "historical_candidates": candidates})
        return result


SYSTEM_PROMPT = """당신은 물류 운송 이력 유사성 판정기다. target과 historical_candidates를 비교하라.
운송수단, 출발·도착 거점 또는 권역, 운송사, 운임과 소요시간을 근거로 판단한다.
정확히 같은 구간이 아니어도 같은 운송수단과 인접/연결 거점이면 유사할 수 있지만, 근거 없는 지리 관계를 만들지 마라.
반드시 JSON 객체만 반환한다. 명세:
{"items":[{"capability_id":"string","similar":true,"confidence":0,"reason":"한국어 한두 문장","reference_leg_ids":["string"]}]}
입력된 모든 capability_id를 한 번씩 반환하고 후보가 없으면 similar=false, confidence=0으로 답하라."""


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:-1])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise ValueError("Ollama가 올바른 JSON을 반환하지 않았습니다.")

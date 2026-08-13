# 운송 스크리닝 & 협상 엔진 (`screening/`)

**화주(Hyundai Glovis) 요청 1건을 받아서, 여러 운송사 데이터를 조합해 경로 후보를 찾고,
LLM 기반 에이전트끼리 실제로 가격 협상을 벌인 다음, 협상이 끝난 경로들을 프론트엔드가
바로 쓸 수 있는 JSON으로 내보내는 코드.**

`agentsociety`/`SupplyChainAgent/enterprise` 쪽 대규모 도시 시뮬레이션과는 별개의,
독립적으로 돌아가는 작은 모듈이다. 외부 의존성이 `requests` 하나뿐이라 가볍게 돌려볼 수 있다.

---

## 1. 사전 준비 (설치)

| 필요한 것 | 비고 |
|---|---|
| Python 3.9+ | 표준 라이브러리 + `requests`만 사용 |
| `pip install requests` | 유일한 외부 패키지 |
| OpenAI 호환 chat 엔드포인트를 서빙하는 로컬/원격 LLM | 아래 참고 |
| `data/` 폴더 (screening과 형제 폴더) | 이 레포에 이미 포함되어 있음 (서비스·통관·인코텀즈·좌표 데이터) |

### LLM 서버

`llm_client.py`가 `POST {LLM_BASE_URL}/chat/completions`를 그대로 호출한다 (OpenAI SDK 없이
`requests`로 직접 호출). 기본값:

```
LLM_BASE_URL = http://127.0.0.1:11500/v1
LLM_MODEL    = qwen2.5-7b-instruct-local
```

이 저장소를 만든 원 환경은 [Ollama](https://ollama.com)로 로컬에 Qwen2.5-7B-Instruct를
띄워서 썼다. 다른 사람이 처음부터 돌리려면:

```bash
# 1) Ollama 설치 후 모델 준비 (HuggingFace safetensors를 갖고 있다면 Modelfile로 import,
#    아니면 그냥 아무 instruct 모델을 pull 해도 됨 — 이름만 맞춰주면 됨)
ollama pull qwen2.5:7b-instruct   # 예시. 실제 쓴 모델명은 위 기본값과 다를 수 있음

# 2) 서버 실행 (기본 포트가 11500이 아니면 3번처럼 환경변수로 맞춰줄 것)
ollama serve
```

포트/모델명이 다르면 코드를 고칠 필요 없이 환경변수로 덮어쓰면 된다:

```bash
export LLM_BASE_URL="http://127.0.0.1:11434/v1"   # 예: ollama 기본 포트
export LLM_MODEL="qwen2.5:7b-instruct"
```

OpenAI API, vLLM, LM Studio 등 `/v1/chat/completions`를 지원하는 아무 서버로 바꿔도 동작한다.

---

## 2. 파일 구성

| 파일 | 역할 |
|---|---|
| `schema.py` | 데이터셋에 관계없이 공통으로 쓰는 `NormalizedService` 레코드 정의 |
| `adapters.py` | 데이터셋별 원본 JSON → `NormalizedService` 변환 (현재는 `ver6`만 사용) |
| `route_search.py` | LLM 없이 순수 그래프 탐색으로 origin→destination 경로 후보를 찾음 |
| `ceu.py` | 차종별 공간환산계수(CEU) 테이블 — SEDAN 기준가를 실제 차종 가격으로 환산 |
| `kb.py` | 통관 규정(`customs_rules.json`)·인코텀즈(`incoterms.json`)·좌표(`coords.json`) 로더 |
| `llm_client.py` | 로컬/원격 LLM에 대한 얇은 OpenAI 호환 wrapper |
| `agents.py` | **핵심.** `CarrierAgent`(운송사 역) + `GlovisAgent`(화주 역) 2자 협상 엔진 |
| `run_frontend_request.py` | **요청 1건 → 결과 1건.** 프론트엔드용 최종 JSON을 만드는 진입점 |

---

## 3. 실행 방법

### 3-1. 요청 1건 → 결과 1건 (프론트엔드가 받는 것)

```bash
cd screening
python3 run_frontend_request.py \
  --origin KRPUS --destination DEHAM \
  --cargo SEDAN --quantity 10 \
  --top_k 3 --priorities COST,TIME \
  --dataset ver6 \
  --out-dir frontend_results
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--origin` / `--destination` | `KRPUS` / `DEHAM` | 출발지/도착지 노드 코드 (`coords.json` 기준) |
| `--cargo` | `SEDAN` | 차종 (`SEDAN`/`SUV`/`PICKUP`/`VAN`/`HIGH_HEAVY` 등, `ceu.py` 참고) |
| `--quantity` | `10` | 요청 대수 |
| `--top_k` | `3` | COST·TIME 각 축에서 뽑아 협상까지 붙일 후보 개수 (중복 경로는 자동 제외) |
| `--priorities` | `COST,TIME` | 후보를 뽑을 정렬 축. 콤마로 구분해 여러 개 지정 가능 (`COST`/`TIME`/`CO2`) |
| `--dataset` | `ver6` | 사용할 데이터셋 (현재는 `ver6`만 실제로 동작함) |
| `--out-dir` | `screening/frontend_results/` | 결과·진행상황 파일을 쓸 폴더 |
| `--max_rounds` | `agents.NEGOTIATION_MAX_ROUNDS_DEFAULT`(5) | leg당 carrier↔buyer 카운터오퍼 최대 라운드 수 |

**주의**: `top_k`나 `priorities` 개수를 늘리면 그만큼 협상해야 할 leg가 늘어나서 LLM 호출
횟수와 실행 시간이 같이 늘어난다. 로컬 CPU Ollama 기준 `top_k=3, priorities=COST,TIME`
정도면 보통 1~3분 안에 끝난다.

---

## 4. 결과 파일 (`{request_id}_result.json`) 상세

`run_frontend_request.py`가 끝나면 `--out-dir` 아래에
`REQ-{origin}-{destination}-{cargo}-{quantity}_result.json` 형태로 딱 한 번 써진다.
예시: `REQ-KRPUS-DEHAM-SEDAN-10_result.json`.

```jsonc
{
  "schema_version": "1.0.0",
  "request_id": "REQ-KRPUS-DEHAM-SEDAN-10",
  "status": "completed",        // "completed" | "failed"
  "partial_result": false,      // 협상 실패로 제외된 후보가 있으면 true

  "request": {                  // 원래 요청 내용을 그대로 echo
    "origin": "KRPUS", "destination": "DEHAM",
    "cargo_type": "FINISHED_VEHICLE", "vehicle_type": "SEDAN",
    "quantity": 10, "cost_display_basis": "shipment"
  },

  "locations": {                // routes[].path에 등장하는 모든 노드 코드의 좌표/이름
    "KRPUS": { "name": "Busan", "country": "KR", "latitude": 35.18, "longitude": 129.08 }
    // ...
  },

  "search_summary": {
    "candidate_routes_found": 13,   // 그래프 탐색으로 찾은 전체 후보 수 (협상 전)
    "routes_returned": 4,           // 그중 실제로 협상까지 붙어 최종 반환된 수
    "source_data_version": "ver6"
  },

  "routes": [ /* 아래 4-1 참고 */ ],

  "customs": {                  // origin/destination 국가 간 통관 규정
    "origin_country": "KR", "destination_country": "DE",
    "required": true, "typical_clearance_days": 1.5, "fta_applicable": "KOREU"
  },

  "incoterm": { "code": "CIP", "version": "Incoterms 2020" },

  "warnings": [
    // 협상 실패로 routes[]에서 제외된 후보가 있으면 여기 한 줄씩 남음
    // 예: "KRPUS→XXX→DEHAM [road+sea] 후보는 일부 구간 협상 실패로 제외되었습니다."
  ]
}
```

**`recommendation_sets`(우선순위별 랭킹)는 의도적으로 넣지 않는다.** LLM이 순위를 매기던
구 로직을 걷어냈고, `routes[].metrics`에 COST/TIME/CO2 판단에 필요한 숫자가 이미 다
있으므로 어떤 기준으로 정렬/추천할지는 **받는 쪽(백엔드)이 직접 계산**하도록 설계했다.

### 4-1. `routes[]` 배열 — 경로 하나당 원소 하나

```jsonc
{
  "route_id": "ROUTE-HYUNDAI_GLOVIS_SEA-DSV_ROAD",  // carrier_id 조합 + 일련번호로 생성, 결정론적
  "label": "Hyundai Glovis-DSV Road 복합운송",         // 사람이 읽는 이름 (carrier_name 기반 템플릿, LLM 아님)
  "path": ["KRPUS", "DEBRV", "DEHAM"],               // 경유 노드 코드 순서
  "modes": ["sea", "road"],                          // leg 순서대로 나열된 운송수단 (중복 제거)
  "feasible": true,                                  // 모든 leg가 협상 성공했는지

  "metrics": {
    "cost_usd_per_vehicle": 481.5,     // 대당 비용 — feasible이면 협상가, 아니면 정가
    "shipment_cost_usd": 4815.0,       // = cost_usd_per_vehicle * quantity.agreed (요청 전체 물량 기준 총액)
    "total_days": 36.7,                // 전체 leg 소요일 합
    "co2_kg_per_vehicle": 308.0,
    "reliability": 0.83,               // leg별 reliability_score의 곱
    "transfers": 1,                    // leg 수 - 1 (환적 횟수)
    "listed_cost_usd_per_vehicle": 496.1  // 정가가 협상가와 다를 때만 존재하는 선택 필드
  },

  "quantity": { "requested": 10, "agreed": 10, "unit": "vehicle" },
  // agreed는 leg별 협상 결과 중 가장 적게 확보된 수량(병목 leg 기준). requested=agreed면 전량 확보.

  "legs": [
    {
      "sequence": 1,
      "carrier_id": "HYUNDAI_GLOVIS_SEA", "carrier_name": "Hyundai Glovis",
      "service_id": "GLV-PCTC-KRPUS-DEBRV-020", "source_dataset": "ver6",
      "mode": "sea", "origin": "KRPUS", "destination": "DEBRV",
      "self_operated": true,   // true면 Glovis 자사선 — 협상 없이 내부 용량 체크만 함
      "listed_cost_usd_per_vehicle": 436.7,
      "agreed_cost_usd_per_vehicle": 436.7,  // 협상 실패 leg면 null
      "days": 35.9, "co2_kg_per_vehicle": 295.3, "reliability": 0.91,
      "negotiation_rounds": 0,  // 0=자사선(협상 없음), 1=1라운드에서 즉시 합의, 2=상대가 카운터오퍼를 냄
      "available_capacity": 6800  // 데이터에 남은 용량 정보가 있을 때만 포함
    }
    // ...
  ]
}
```

**대당 비용 vs 총액**: 원본 운송사 데이터(`data/`)는 전부 **대당(per-vehicle)**
가격으로 들어있다. `cost_usd_per_vehicle`가 그 값이고, `shipment_cost_usd`는 여기에 확보
수량(`quantity.agreed`)을 곱한 **이번 요청 전체 물량 기준 총액**이다. 두 값이 같이 있으니
프론트에서 "대당 $481.5 · 총 10대 $4,815" 식으로 바로 보여줄 수 있다.

**협상 실패 시**: 어떤 leg라도 협상이 끝내 결렬되면(`deal_reached=false`) 그 경로 전체가
`feasible: false`가 되고, `routes[]`에는 아예 안 들어가고 `warnings[]`에 한 줄 남는다 —
불완전한 경로를 프론트에 섞어 보내지 않기 위함.

---

## 5. 진행상황 파일 (`{request_id}_progress.json`) 상세

**결과 파일과는 별도 파일이다.** 협상은 로컬 LLM으로 도는 만큼 몇 분씩 걸릴 수 있어서,
아직 결과 파일이 만들어지기 전에도 지금 어디까지 진행됐는지 폴링할 수 있도록 실행 도중
계속 덮어써진다.

```jsonc
{
  "request_id": "REQ-KRPUS-DEHAM-SEDAN-10",
  "status": "running",           // "running" | "completed" | "failed"
  "current_stage": { "stage": "negotiate_leg", "status": "round1_start", "...": "..." },
  "events": [ /* 지금까지의 모든 체크포인트, 아래 참고 */ ],
  "updated_at": "2026-08-08T12:40:23.060032+00:00"
}
```

`events[]`에 순서대로 쌓이는 체크포인트(`stage` 값 기준):

| stage | 의미 |
|---|---|
| `loading_data` | 데이터셋/지식베이스 로딩 시작 |
| `route_search` | 그래프 탐색 시작(`start`)/완료(`done`, 후보 수 포함)/`no_routes`(경로 없음) |
| `scenarios_selected` | COST/TIME 축으로 뽑은 협상 대상 후보 확정 |
| `scenario_negotiation` | 경로 하나 단위 협상 시작(`start`)/완료(`done`) |
| `negotiate_leg` | leg 하나의 협상 라운드 진행 상황 (`round1_start` → `round1_done` → 필요시 `round2_start` → `done`, 자사선이면 `self_operated`) |
| `complete` | 전체 완료 |

프론트/백엔드에서는 이 파일을 몇 초 간격으로 폴링하다가 `status: "completed"`(또는
`"failed"`)가 되고 결과 파일이 생기면 그때 결과 파일을 읽으면 된다.

---

## 6. 협상 로직 요약

- 경로 탐색 자체(`route_search.py`)는 LLM을 쓰지 않는 순수 그래프 탐색이다.
- 화주 쪽(`GlovisAgent`)이 COST 기준 top_k개 + TIME 기준 top_k개(중복 제외)를 후보로 뽑는다.
- 후보 경로의 각 leg마다: **Glovis 자사선이면** 내부 용량만 확인하고 끝(LLM 호출 없음).
  **파트너 운송사면** 최대 2라운드 협상: 1라운드에서 운송사 역할의 LLM이
  ACCEPT/COUNTER/REJECT를 결정하고, COUNTER가 나오면 2라운드에서 화주 역할의 LLM이
  ACCEPT/WALK_AWAY를 결정한다.
- 같은 leg(`service_id`+수량)가 여러 후보 경로에 겹쳐 등장해도 협상은 한 번만 하고 결과를
  캐시해서 재사용한다 — LLM 호출을 불필요하게 중복하지 않기 위함.
- 협상가가 실제로 근거 데이터(`leg.cost_usd`) 대비 너무 크게 벗어나면 내부적으로
  grounding 체크에 걸리도록 되어 있다(수치를 지어내는지 검증용. 프론트용 결과 파일에는
  포함하지 않음).

---

## 7. 알려진 제약사항

- 로컬 CPU Ollama 기준 협상 1건(leg당 LLM 호출)마다 수 초~수십 초 걸릴 수 있다 —
  `top_k`·`priorities` 개수를 늘릴수록 leg 협상 건수가 늘어 전체 실행 시간이 길어진다.
- 현재 실제로 동작하는 데이터셋은 `ver6`(`data/`) 하나뿐이다. 그 외
  `LOADERS`에 남아있는 항목들은 원본 폴더가 삭제된 과거 데이터셋 참고용으로, 호출하면
  `FileNotFoundError`가 난다.

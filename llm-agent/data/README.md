# 완성차 복합운송 멀티에이전트 데이터셋 v5

**운송사 1곳 = 파일 1개 = 에이전트 1개.**
화주 요청을 받아 해상·철도·도로·항공을 조합한 E2E 경로를 제안하고, 근거를 검증할 수 있게 설계했다.

---

## 왜 이 데이터로 시작하면 되는가

에이전트를 붙일 때 데이터에서 막히는 지점이 보통 다섯 개다. 전부 해결해뒀다.

| 흔한 문제 | 이 데이터에서 |
|---|---|
| **"경로가 안 이어져요"** | 5개 대표 구간 전수 검증 완료. 울산→뮌헨 45개, 부산→프라하 36개 |
| **"에이전트가 숫자를 지어내요"** | 모든 값에 `service_id` 부여. 인용 강제 → 사후 검증 가능 |
| **"플래그랑 설명이 반대예요"** | 자유 텍스트 필드 없음. 모순이 생길 구조 자체가 없음 |
| **"환산을 매번 해야 해요"** | 비용·시간·탄소 모두 **대당 단위로 미리 계산됨** |
| **"뭘 고를지 답이 하나예요"** | **하선항 대안 7~11곳.** 축마다 다른 답이 나옴 |

**즉시 확인**
```bash
python verify5.py
```
```
서비스 850개 / 운송사 8곳
=== 울산 → 뮌헨 : 45개 경로 ===
  하선항 대안 11곳: ['BEANR','BEZEE','DEBRV','DEHAM','ESVLC','FRLEH','ITGOA','NLRTM','PLGDN','SEGOT','SIKOP']
=== 무결성 점검 ===
  이상 없음
```

---

## 규모

| | |
|---|---|
| 서비스 | **754개** (완성차 635 / 부품·일반 119) |
| 운송사 | 9곳 — 해운 1 · 철도 2 · 도로 4 · 항공 2 |
| 수단별 | 해운 112 · 철도 272 · 도로 310 · 항공 60 |
| 티어 | STANDARD 601 · EXPRESS 107 · ECONOMY 46 |
| 노드 | 66곳 (한국 공장·야드 5 · 아시아 출발항 8 · 유럽 항만 12 · 내륙 13 · 공항) |

### 역할 구분

| 역할 | 운송사 | 수단 |
|---|---|---|
| **OWN_FLEET** | **현대글로비스** | **해운 (자사 PCTC 선대)** |
| PARTNER | DB Cargo, Rail Cargo Group | 철도 |
| PARTNER | 한국카라인, 대한운수 | 도로 (국내) |
| PARTNER | EuroTrans Auto, DSV Road | 도로 (유럽) |
| PARTNER | Korean Air Cargo, Lufthansa Cargo | 항공 (부품 긴급) |

**글로비스는 PCTC를 직접 운항하는 선사다.** 해상 구간은 자사 선대로 운항하고,
육상 구간은 파트너 운송사를 이용한다. 이 구조를 `carrier.role` 필드로 명시했다.

→ 해운은 **"어느 배·어느 항차"**를 고르는 문제, 육상은 **"어느 회사"**를 고르는 문제로 성격이 다르다.

---

## 파일

```
sea_hyundai_glovis.json         해운 — 현대글로비스 (자사 PCTC)
rail_db_cargo.json              철도 — DB Cargo
rail_rail_cargo_group.json      철도 — Rail Cargo Group
road_korea_carline.json         도로 — 한국카라인 (국내)
road_daehan_trans.json          도로 — 대한운수 (국내)
road_eurotrans_auto.json        도로 — EuroTrans Auto (유럽)
road_dsv.json                   도로 — DSV Road (유럽)
air_korean_air_cargo.json       항공 — Korean Air Cargo
air_lufthansa_cargo.json        항공 — Lufthansa Cargo

transfer_rules.json    환승 비용·시간 (25종)
customs_rules.json     국가쌍 통관 요건 (306쌍)
incoterms.json         Incoterms 2020 (11개)
coords.json            노드 좌표

verify5.py             경로 검증 + 무결성 점검
```

**지식베이스 3종은 캐리어 서비스와 조인하지 않는다.**
정형 데이터(캐리어)는 필터링 후 주입, 비정형 텍스트(조항)는 코드로 정확 검색해서 해당 텍스트만 주입하는 구조다.

---

## 에이전트 연동

### 1) 캐리어 에이전트 — 파일 하나씩

```python
def carrier_agent(carrier_file, request):
    d = json.load(open(carrier_file, encoding="utf-8"))
    svc = [s for s in d["services"]
           if s["carries_finished_vehicle"]
           and s["origin"]["location_id"] == request["origin"]]
    return llm(f"""너는 {d['carrier']['carrier_name']}이다.
아래 서비스 중 제안 가능한 것을 골라 근거와 함께 제시하라.
반드시 service_id를 인용하라. 숫자를 지어내지 마라.
{json.dumps(svc, ensure_ascii=False)}
요청: {request}""")
```

**`service_id` 인용을 강제하면 환각이 사후 검증된다.**
"$535라고 했는데 그 service_id가 실제로 그 값인가"를 확인할 수 있다.

### 2) 오케스트레이터 — 합산 공식

```python
총비용 = Σ pricing.cost_usd_per_vehicle_all_in + Σ 환승비
총일수 = Σ schedule.total_days_with_wait + Σ 환승시간/24 + 통관일수
총탄소 = Σ environment.co2_kg_per_vehicle
정시율 = Π performance.on_time_rate
p90    = Σ schedule.transit_days_p90        # 꼬리 리스크
```

환승비는 `transfer_rules.json`에서 노드 타입 쌍으로 조회한다.
통관일수는 `customs_rules.json`에서 출발·도착 국가쌍으로 조회한다.

### 3) 필수 필터 두 개

```python
# ① 완성차만
if not s["carries_finished_vehicle"]: continue

# ② 환승 비용 반영 (안 하면 철도가 과대평가된다)
if 이전.mode != 다음.mode:
    비용 += transfer_rules[(이전.node_type, 다음.node_type)]["cost_usd_per_vehicle"]
    시간 += transfer_rules[...]["hours"] / 24
```

---

## 필드

### 서비스 공통

| 경로 | 필드 | 비고 |
|---|---|---|
| `service_id` | | **인용 검증용 키** |
| `service_tier` | | ECONOMY / STANDARD / EXPRESS |
| `origin` / `destination` | `node_id` `location_id` `node_type` `country` | |
| `distance_km` | | 전 수단 통일 |
| `carries_finished_vehicle` | | **완성차 필터** |

### schedule

| 필드 | 의미 |
|---|---|
| `transit_days` | 순수 운송 |
| `average_wait_days` | 배차 대기 |
| `total_days_with_wait` | **합계 — 이걸 쓰면 됨** |
| `transit_days_p90` | **90퍼센타일. 꼬리 리스크** |
| `departure_days` `frequency_per_week` | 배차 스케줄 |
| `booking_lead_days` `cargo_closing_hours` | 부킹 마감 |
| `border_crossings` `gauge_changes` | **국경·궤간 (지연 근거)** |

### pricing

| 필드 | 의미 |
|---|---|
| `cost_usd_per_vehicle` | 기본 대당 |
| `cost_usd_per_vehicle_all_in` | **할증 포함 — 이걸 쓰면 됨** |
| `min_charge_usd` | 최저운임 |
| `rate_validity_type` | **계약 유형** — ANNUAL_CONTRACT / SEMI_ANNUAL / QUARTERLY / MONTHLY / SPOT / PROMOTIONAL |
| `valid_from` `valid_to` | 요율 유효기간 (계약 유형별로 스태거링) |
| `days_until_expiry` | **기준일(2026-08-07) 기준 잔여일. 필터에 바로 사용** |
| `surcharges[]` | BAF·THC·TOLL 등 내역 |

### performance

| 필드 | 의미 |
|---|---|
| `on_time_rate` | 정시율 (구간 곱) |
| `delay_probability` | 지연 확률 |
| `damage_rate` `cancellation_rate` | 손상·취소율 |
| `reliability_source` `on_time_sample_size` | **신뢰도 근거·표본 수** |

### dwell / environment

| 필드 | 의미 |
|---|---|
| `dwell.free_time_days` | 무료 장치 기간 |
| `dwell.demurrage_usd_per_unit_day` | 체화료 |
| `dwell.detention_usd_per_unit_day` | 지체료 |
| `environment.co2_kg_per_vehicle` | **대당 배출량 (계산 완료)** |
| `environment.co2_g_per_tonkm` | GLEC 계수 |
| `environment.cii_grade` | A~E |

---

## 이 데이터가 만드는 판단 상황

### ① 하선항 선택 — 해상과 육상이 반대로 움직인다

울산 → 마드리드 (하선항 7곳)

| 하선항 | 수단 | 일수 | 비용 | CO2 |
|---|---|---|---|---|
| **발렌시아** | sea+road | 32.4 | **$493** | **289kg** |
| 제노바 | sea+road | 34.7 | $680 | 407kg |
| 로테르담 | sea+road | 38+ | $700+ | 420kg+ |

**발렌시아는 해상이 길지만 마드리드까지 육상이 짧아 총비용이 이긴다.**
울산 → 밀라노는 제노바가, 상하이 → 바르샤바는 그단스크가 이긴다.

→ **구간을 따로 보면 절대 안 나오는 답.** 에이전트가 논쟁할 실질적 근거가 된다.

### ② 철도 vs 트럭 — 싸고 저탄소 vs 빠르고 확실

| | 비용 | 일수 | CO2 | 정시율 |
|---|---|---|---|---|
| 철도 | 낮음 | +2~3일 | **-15%** | 0.75~0.78 |
| 트럭 | 높음 | 빠름 | 높음 | **0.84~0.89** |

철도는 환적비($18~38)와 라스트마일 트럭이 붙는다. **단거리에서는 트럭 직송이 이긴다.**

### ③ 티어 — 같은 노선, 다른 서비스

EXPRESS는 대당 22~35% 비싸고 대기가 40% 짧으며 정시율이 5% 높다.
ECONOMY는 12~14% 싸고 대기가 30% 길다.

→ 납기가 급한 화주와 단가가 중요한 화주에게 다른 답이 나온다.

### ④ 요율 만료 — 견적의 유통기한

계약 유형별로 갱신 주기가 다르다. 850건이 **185개의 서로 다른 만료일**을 갖는다.

| 계약 유형 | 주기 | 건수 |
|---|---|---|
| SEMI_ANNUAL | 6개월 | 247 |
| PROMOTIONAL | 1개월 | 230 |
| QUARTERLY | 3개월 | 215 |
| ANNUAL_CONTRACT | 12개월 | 94 |
| MONTHLY | 1개월 | 44 |
| SPOT | 2~5주 | 20 |

수단별 특성을 반영했다. **해운은 연간·반기 계약이 많고, 항공은 월 단위·스팟이 대부분이다.**
그리고 **같은 구간에서 하위 25% 가격대는 PROMOTIONAL로 분류해 1개월 만료**로 뒀다.
현실에서 할인 요율이 먼저 만료되기 때문이다.

**필터가 실제로 작동한다** (울산 → 뮌헨)

| 조건 | 경로 수 | 최저가 |
|---|---|---|
| 필터 없음 | 45개 | $535 |
| 7일 이상 유효 | 42개 | $535 |
| **30일 이상 유효** | **21개** | **$537** |

→ "이 견적은 D-3에 만료됩니다. 30일 이상 유효한 대안은 $2 비쌉니다" 같은 시나리오가 성립한다.

```python
# 만료 임박 경고
if s["pricing"]["days_until_expiry"] <= 7:
    warn(f"{s['service_id']} 요율이 D-{days} 만료 예정")

# 장기 유효 요율만
svc = [s for s in services if s["pricing"]["days_until_expiry"] >= 30]
```

### ⑤ 국내 구간 — 공장에서 항만까지도 선택이 있다

화성공장 → 부산항

| 운송사 | 비용 | 일수 | 정시율 |
|---|---|---|---|
| 대한운수 | **$73.6** | 1.14일 | 0.93 |
| 한국카라인 | $85.2 | **0.93일** | **0.96** |

**싼 곳은 느리고 정시율이 낮다.** 납기가 빠듯하면 $12 더 내는 게 맞다.

전체 경로에서 이 선택이 어떻게 반영되는지:
```
화성공장 → 부산항 → 제노바 → 뮌헨      $622  34.7일
대한운수    현대글로비스    EuroTrans Auto
```

### ⑥ 국경 — 짧은데 오래 걸리는 구간

코페르(SI) → 트리에스테(IT) 16km가 1.44일.
**거리는 30분인데 국경 2회 통과 절차가 지배한다.** `border_crossings` 필드로 설명 가능.

---

## 수치의 근거

### 시간 = 고정 + 비례 + 국경

```
철도 = 16h(조성·터미널) + 거리/34kmh + 국경수×9h + 궤간변경×26h
도로 = 7h(배차·상하차) + 거리/54kmh + 9h초과시 휴식11h + 국경수×1.5h
해운 = 거리/(16.5kt) + 3.5일(기항 여유)
```

**실측 대조**

| 구간 | 계산 | 업계 통용치 |
|---|---|---|
| 함부르크→뮌헨 철도 612km | 1.42일 | 1~2일 |
| 로테르담→뮌헨 철도 798km | 2.02일 | 2~3일 |
| 중국→유럽 철도 11,000km | 15.65일 | 16~20일 |
| 로테르담→뮌헨 트럭 845km | 1.46일 | 1.5~2일 |

### 요금 = 고정비 + 거리비 × 체감

```
taper(km, start, exp) = km                                  (km ≤ start)
                      = start + (km-start)^exp × start^(1-exp)  (km > start)
```

**장거리일수록 km당 단가가 낮아진다.** 고정비(터미널·조성·서류)가 짧은 구간에서 단가를 지배하기 때문.

| 수단 | 거리 | km당 |
|---|---|---|
| 철도 | 16km | $5.100 |
| 철도 | 1,696km | **$0.135** |
| 도로 | 15km | $1.540 |
| 도로 | 2,930km | **$0.148** |

38배 차이. 이래서 **철도 손익분기 거리**가 데이터에 자연스럽게 생긴다.

### 탄소 = GLEC / ISO 14083

```
CO2_kg = 거리 × 중량톤 × co2_g_per_tonkm / 1000
```
해운 8.4 · 철도 11.0 · 도로 63.0 · 항공 540.0 g/톤-km

---

## 무결성

`verify5.py`가 매 실행마다 검사한다.

- 완성차 서비스에 비용 누락 없음
- 소요일 0 이하 없음
- `transit_days_p90` < `total_days_with_wait` 인 모순 없음
- `allowed_vehicle_types`에 EV 있는데 `ev_allowed: false` 인 모순 없음
- 대륙 간 육로 링크 없음
- 요율 유효기간 분포 (계약 유형별·만료일 다양성)

**현재 전부 통과 (이상 0건).**

---

## 알려진 한계

| 한계 | 대응 |
|---|---|
| 날짜 개념 없음 (소요 기간만) | `departure_days`가 있어 요일 계산 함수만 얹으면 됨 |
| 리스크 이벤트(파업·체선) 없음 | 실행 시점에 별도 레이어로 반영 권장 |
| 화물 규격이 단일 (세단 1.7톤 기준) | 필요 시 CEU 환산 계수 추가 |
| 국내 트럭 운송사 2곳은 가상 | 실제 계약 구조 반영을 위한 설정 |
| 모든 수치 합성값 | 상대 관계·분포는 공개 통계와 실측 벤치마크에 정렬 |

---

## 재생성

```
fix.py        → 이상 링크 제거, 거리·단위 통일
supplement.py → 완성차 라스트마일 보완
realistic.py  → 시간·요금 현실화 (고정+비례+국경, 체감 단가)
enrich.py     → 리스크 필드·티어 부여
expand.py     → 유럽 항만-내륙 연결 확장
expand_sea.py → PCTC 항로망 확장
stagger_validity.py → 요율 유효기간 스태거링
restructure.py → 해운 글로비스 단독화, 국내 트럭 신설
verify5.py    → 검증
```

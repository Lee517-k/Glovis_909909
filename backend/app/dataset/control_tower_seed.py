"""Control Tower 더미 시드 데이터.

'운송 추적'/'운송사 배분' 화면은 실제 운송 실적 피드가 없기 때문에, 화면이
동작하는 데 필요한 데이터를 여기서 손으로 정의하고 최초 기동 시 SQLite에
한 번만 적재한다(app/db/control_tower_store.py 의 seed_if_empty).

숫자는 무작위가 아니라 화면 KPI가 의도한 값으로 떨어지도록 맞춰 두었다.
  진행중 18 / 지연 3 / 리스크 감시 5 / 오늘 도착 4 / 환적 대기 2
날짜는 시드를 적재하는 날(today)을 기준으로 상대 오프셋으로 만들어지므로
어느 날에 적재해도 "오늘 도착 4건"이 성립한다.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. 노드(항만/공항/내륙거점) 사전 — 지도 좌표의 원천
#    (node_id, 한글명, 영문명, 경도, 위도, 유형, 국가코드, 지역권 id)
# ---------------------------------------------------------------------------
NODES: list[tuple] = [
    ("KRPUS", "부산항", "Busan", 129.04, 35.10, "PORT", "KR", "RG-EA"),
    ("KRUSN", "울산항", "Ulsan", 129.32, 35.53, "PORT", "KR", "RG-EA"),
    ("KRICN", "인천공항", "Incheon", 126.44, 37.46, "AIRPORT", "KR", "RG-EA"),
    ("KRICH", "이천", "Icheon", 127.44, 37.28, "INLAND", "KR", "RG-EA"),
    ("CNQIN", "칭다오", "Qingdao", 120.38, 36.07, "PORT", "CN", "RG-EA"),
    ("CNSHA", "상하이", "Shanghai", 121.47, 31.23, "PORT", "CN", "RG-EA"),
    ("SIN", "싱가포르", "Singapore", 103.85, 1.29, "PORT", "SG", "RG-EA"),
    ("ALA", "알마티", "Almaty", 76.89, 43.24, "RAIL_HUB", "KZ", "RG-CA"),
    ("AEJEA", "제벨알리", "Jebel Ali", 55.06, 25.00, "PORT", "AE", "RG-CA"),
    ("SUEZ", "수에즈", "Suez", 32.55, 30.00, "WAYPOINT", "EG", "RG-EU"),
    ("NLRTM", "로테르담", "Rotterdam", 4.14, 51.95, "PORT", "NL", "RG-EU"),
    ("BEANR", "안트베르펜", "Antwerp", 4.42, 51.26, "PORT", "BE", "RG-EU"),
    ("GBFXT", "펠릭스토", "Felixstowe", 1.29, 51.95, "PORT", "GB", "RG-EU"),
    ("GBSOU", "사우샘프턴", "Southampton", -1.40, 50.90, "PORT", "GB", "RG-EU"),
    ("DEHAM", "함부르크", "Hamburg", 9.98, 53.54, "PORT", "DE", "RG-EU"),
    ("DEBRV", "브레머하펜", "Bremerhaven", 8.58, 53.54, "PORT", "DE", "RG-EU"),
    ("DEDUI", "뒤스부르크", "Duisburg", 6.76, 51.43, "RAIL_HUB", "DE", "RG-EU"),
    ("DEFRA", "프랑크푸르트", "Frankfurt", 8.56, 50.04, "AIRPORT", "DE", "RG-EU"),
    ("DEMUC", "뮌헨", "Munich", 11.58, 48.14, "INLAND", "DE", "RG-EU"),
    ("ATVIE", "비엔나", "Vienna", 16.37, 48.21, "INLAND", "AT", "RG-EU"),
    ("ITGOA", "제노아", "Genoa", 8.93, 44.41, "PORT", "IT", "RG-EU"),
    ("ESVLC", "발렌시아", "Valencia", -0.33, 39.44, "PORT", "ES", "RG-EU"),
    ("USLAX", "LA", "Los Angeles", -118.25, 33.74, "PORT", "US", "RG-NA"),
]

# ---------------------------------------------------------------------------
# 2. 지역권(탭) — '운송사 배분' 상단 탭과 배분 카드의 그룹 키
#    (region_id, 이름, 정렬순서, 탭 노출 여부)
# ---------------------------------------------------------------------------
REGIONS: list[tuple] = [
    ("RG-EA", "동아시아 내륙", 1, 1),
    ("RG-EU", "서·북유럽", 2, 1),
    ("RG-CA", "중앙아시아 · TCR", 3, 1),
    ("RG-NA", "북미", 4, 1),
    ("RG-AIR", "항공 (전 지역)", 5, 1),
]

# ---------------------------------------------------------------------------
# 3. 운송사 마스터
#    (carrier_id, 이름, 설명, 모드 CSV, 주력 지역권, 등급, 등급종류,
#     정시율%, 계약 잔량%, 상태 tone, 상태 라벨, 대표색)
#    grade_kind: 해상 운송사는 CII, 그 외는 ESG 등급을 표시한다.
# ---------------------------------------------------------------------------
CARRIERS: list[tuple] = [
    ("CR-HMM", "HMM", "아시아–유럽 항로", "sea", "RG-EU", "C", "cii", 82, 62.0, "warn", "의존도 주의", "#0B3C71"),
    ("CR-MSC", "MSC", "로테르담 기항", "sea", "RG-EU", "B", "cii", 85, 44.0, "ok", "정상", "#1668C4"),
    ("CR-CMA", "CMA CGM", "지중해·북미 서안", "sea", "RG-NA", "B", "cii", 83, 51.0, "ok", "정상", "#2E86D9"),
    ("CR-MAE", "Maersk", "북유럽 셔틀", "sea", "RG-EU", "A", "cii", 88, 35.0, "ok", "정상", "#4FA3E8"),
    ("CR-DBC", "DB Cargo", "유럽 내륙 철도", "rail", "RG-EU", "A", "esg", 92, 71.0, "ok", "정상", "#12A47B"),
    ("CR-CRE", "CRE Block Train", "중국–유럽 블록트레인", "rail", "RG-CA", "B", "esg", 78, 88.0, "danger", "단일 의존", "#0A7A57"),
    ("CR-KE", "KE Cargo", "인천 허브", "air", "RG-AIR", "E", "esg", 94, 39.0, "ok", "정상", "#4E32B5"),
    ("CR-FWD", "포워더 콘솔", "혼재 항공 스페이스", "air", "RG-AIR", "E", "esg", 89, 27.0, "ok", "정상", "#7A5AF8"),
    ("CR-DHL", "DHL Express", "특송 문전배송", "express", "RG-AIR", "D", "esg", 97, 18.0, "ok", "정상", "#C3CDDA"),
    ("CR-GLV", "GLOVIS Inland", "국내 내륙 자가", "truck", "RG-EA", "C", "esg", 96, None, "blue", "자가 운송", "#96610A"),
    ("CR-EUT", "EU Trucking", "유럽 라스트마일", "truck", "RG-EU", "C", "esg", 91, 46.0, "ok", "정상", "#E08A00"),
    ("CR-PA", "협력사 A", "국내 위탁 운송", "truck", "RG-EA", "C", "esg", 89, 33.0, "ok", "정상", "#E8A83A"),
    ("CR-PB", "협력사 B", "TCR 연계 위탁", "rail", "RG-CA", "C", "esg", 81, 41.0, "warn", "물량 편중", "#3FBF97"),
    ("CR-NAT", "NA Trucking", "북미 내륙 배송", "truck", "RG-NA", "D", "esg", 87, 29.0, "ok", "정상", "#D9A05B"),
]

# ---------------------------------------------------------------------------
# 4. 지역권 × 운송사 배분 실적 (최근 90일)
#    (region_id, carrier_id, 표시명, 물량, 단위, 집행액(억원), 비중%)
#    비중(share_pct)으로 HHI를 서버에서 계산하므로 여기에 HHI 값은 두지 않는다.
# ---------------------------------------------------------------------------
ALLOCATIONS: list[tuple] = [
    # 서·북유럽 1,284 TEU
    ("RG-EU", "CR-HMM", "HMM", 488.0, "TEU", 1.24, 38.0),
    ("RG-EU", "CR-MSC", "MSC", 308.0, "TEU", 0.81, 24.0),
    ("RG-EU", "CR-DBC", "DB Cargo", 244.0, "TEU", 0.29, 19.0),
    ("RG-EU", "CR-EUT", "EU Trucking", 154.0, "TEU", 0.22, 12.0),
    ("RG-EU", "CR-MAE", "Maersk", 90.0, "TEU", 0.14, 7.0),
    # 동아시아 내륙 862 TEU
    ("RG-EA", "CR-GLV", "GLOVIS Inland", 465.0, "TEU", 0.18, 54.0),
    ("RG-EA", "CR-PA", "협력사 A", 241.0, "TEU", 0.11, 28.0),
    # carrier_id 가 None 인 행은 특정 운송사가 아니라 '기타' 집계 버킷이다.
    ("RG-EA", None, "기타", 156.0, "TEU", 0.07, 18.0),
    # 중앙아시아 · TCR 521 TEU
    ("RG-CA", "CR-CRE", "CRE Block Train", 370.0, "TEU", 0.52, 71.0),
    ("RG-CA", "CR-PB", "협력사 B", 151.0, "TEU", 0.19, 29.0),
    # 항공 (전 지역) 402 t
    ("RG-AIR", "CR-KE", "KE Cargo", 189.0, "t", 0.94, 47.0),
    ("RG-AIR", "CR-FWD", "포워더 콘솔", 125.0, "t", 0.51, 31.0),
    ("RG-AIR", "CR-DHL", "DHL", 88.0, "t", 0.44, 22.0),
    # 북미 186 TEU
    ("RG-NA", "CR-CMA", "CMA CGM", 104.0, "TEU", 0.21, 56.0),
    ("RG-NA", "CR-MAE", "Maersk", 52.0, "TEU", 0.10, 28.0),
    ("RG-NA", "CR-NAT", "NA Trucking", 30.0, "TEU", 0.06, 16.0),
]

# ---------------------------------------------------------------------------
# 5. 거점별 물량 (지도 버블) — (node_id, 물량, 단위, 주력 모드, 라벨, 버블반경)
# ---------------------------------------------------------------------------
HUB_VOLUMES: list[tuple] = [
    ("NLRTM", 1284.0, "TEU", "sea", "서·북유럽 1,284 TEU", 44),
    ("DEHAM", 612.0, "TEU", "sea", "612 TEU", 30),
    ("DEMUC", 388.0, "TEU", "truck", "남독 내륙 388", 22),
    ("DEDUI", 340.0, "TEU", "rail", "340", 20),
    ("KRPUS", 862.0, "TEU", "truck", "동아시아 862", 34),
    ("CNQIN", 214.0, "TEU", "sea", "환적 214", 18),
    ("ALA", 521.0, "TEU", "rail", "중앙아시아 TCR 521", 24),
    ("KRICN", 402.0, "t", "air", "항공 402t", 19),
    ("USLAX", 186.0, "TEU", "sea", "북미 서안 186", 15),
]

# ---------------------------------------------------------------------------
# 6. 화물(운송) 마스터 — 총 22건 (활성 18 / 완료 3 / 계획 1)
#
#  status: IN_TRANSIT(운송중) DELAYED(지연) CUSTOMS_HOLD(통관보류)
#          ARRIVING(도착임박) PLANNED(계획) COMPLETED(완료)
#  eta_offset : 시드 적재일(today) 기준 계획 ETA 오프셋(일)
#  forecast_offset : 예측 ETA 오프셋. None이면 계획대로.
# ---------------------------------------------------------------------------
_S = (
    # id, 화물명, 중량kg, 출발, 도착, 모드CSV, 진행%, 상태,
    # eta_offset, eta_time, forecast_offset, risk, risk_level, esg, cii, co2kg,
    # 운송사CSV, region, 현재노드, 현재위치라벨, 환적대기
    ("SHP-24081", "반도체 웨이퍼", 800, "KRPUS", "DEMUC", "truck,air,truck", 68, "CUSTOMS_HOLD",
     1, "14:20", None, 0.19, "LOW", "E", None, 3479, "CR-GLV,CR-KE,CR-EUT", "RG-AIR", "DEFRA", "프랑크푸르트 통관중", 0),
    ("SHP-24076", "자동차 부품", 8000, "KRPUS", "DEMUC", "sea,truck", 41, "IN_TRANSIT",
     19, "09:00", None, 0.28, "MEDIUM", "B", "B", 1180, "CR-HMM,CR-EUT", "RG-EU", "SUEZ", "수에즈 통과", 0),
    ("SHP-24071", "배터리", 12000, "KRPUS", "DEHAM", "sea,rail", 78, "DELAYED",
     6, "10:30", 8, 0.46, "HIGH", "B", "B", 1420, "CR-MSC,CR-DBC", "RG-EU", "DEHAM", "함부르크 혼잡 대기", 1),
    ("SHP-24068", "의약품", 240, "KRICH", "NLRTM", "express", 92, "ARRIVING",
     0, "11:00", None, 0.08, "LOW", "D", None, 980, "CR-DHL", "RG-AIR", "NLRTM", "최종 배송중", 0),
    ("SHP-24065", "부품", 6000, "CNQIN", "DEDUI", "rail", 33, "DELAYED",
     14, "10:00", 21, 0.61, "CRITICAL", "A", None, 310, "CR-CRE", "RG-CA", "ALA", "국경 통관 보류", 0),
    ("SHP-24062", "완성차 200대", 300000, "KRUSN", "DEBRV", "sea", 52, "IN_TRANSIT",
     21, "08:00", None, 0.24, "LOW", "B", "B", 8600, "CR-HMM", "RG-EU", "SUEZ", "수에즈 대기", 0),
    ("SHP-24059", "완성차 120대", 180000, "KRPUS", "GBSOU", "sea", 44, "IN_TRANSIT",
     24, "07:00", None, 0.21, "LOW", "A", "A", 7300, "CR-MSC", "RG-EU", "SIN", "싱가포르 기항", 0),
    ("SHP-24057", "자동차 부품", 18000, "KRICN", "ATVIE", "air,truck", 81, "IN_TRANSIT",
     0, "18:40", None, 0.17, "LOW", "E", None, 2960, "CR-KE,CR-EUT", "RG-AIR", "DEFRA", "프랑크푸르트 환적", 0),
    ("SHP-24054", "완성차 80대", 120000, "KRUSN", "DEHAM", "sea", 57, "DELAYED",
     12, "09:30", 15, 0.52, "HIGH", "C", "C", 8900, "CR-HMM", "RG-EU", "AEJEA", "제벨알리 환적 대기", 1),
    ("SHP-24051", "일반화물", 30000, "DEHAM", "DEDUI", "truck", 22, "IN_TRANSIT",
     2, "15:00", None, 0.33, "MEDIUM", "C", None, 240, "CR-EUT", "RG-EU", "DEHAM", "함부르크 출고", 0),
    ("SHP-24048", "완성차 60대", 90000, "KRICN", "ITGOA", "sea", 70, "IN_TRANSIT",
     9, "12:00", None, 0.19, "LOW", "B", "B", 5200, "CR-CMA", "RG-EU", "SUEZ", "수에즈 통과", 0),
    ("SHP-24045", "전장부품", 3200, "KRPUS", "NLRTM", "sea,rail", 61, "IN_TRANSIT",
     11, "13:00", None, 0.27, "MEDIUM", "B", "B", 1650, "CR-MSC,CR-DBC", "RG-EU", "NLRTM", "로테르담 접안", 0),
    ("SHP-24042", "정밀기기", 460, "KRICN", "DEFRA", "air", 88, "ARRIVING",
     0, "22:15", None, 0.11, "LOW", "E", None, 1870, "CR-KE", "RG-AIR", "DEFRA", "프랑크푸르트 도착 예정", 0),
    ("SHP-24039", "부품", 9000, "CNQIN", "DEDUI", "rail", 47, "IN_TRANSIT",
     13, "10:00", None, 0.38, "MEDIUM", "A", None, 620, "CR-CRE", "RG-CA", "ALA", "알마티 통과", 0),
    ("SHP-24036", "완성차 150대", 225000, "DEBRV", "DEMUC", "truck", 90, "IN_TRANSIT",
     0, "16:00", None, 0.14, "LOW", "C", None, 380, "CR-EUT", "RG-EU", "DEFRA", "프랑크푸르트 경유", 0),
    ("SHP-24030", "타이어", 24000, "KRPUS", "USLAX", "sea", 36, "IN_TRANSIT",
     16, "08:30", None, 0.29, "MEDIUM", "B", "B", 4100, "CR-CMA", "RG-NA", "CNSHA", "태평양 항해중", 0),
    ("SHP-24027", "부품", 5000, "KRICH", "NLRTM", "truck,air,truck", 25, "IN_TRANSIT",
     4, "19:00", None, 0.22, "LOW", "E", None, 1520, "CR-GLV,CR-FWD,CR-EUT", "RG-AIR", "KRICN", "인천공항 적재", 0),
    ("SHP-24024", "일반화물", 16000, "KRPUS", "BEANR", "sea", 68, "IN_TRANSIT",
     7, "11:30", None, 0.31, "MEDIUM", "C", "C", 3400, "CR-HMM", "RG-EU", "AEJEA", "제벨알리 기항", 0),
    # --- 완료 3건 ---
    ("SHP-24012", "일반화물", 25000, "KRPUS", "ESVLC", "sea", 100, "COMPLETED",
     -3, "09:00", None, 0.12, "LOW", "A", "A", 3050, "CR-MAE", "RG-EU", "ESVLC", "발렌시아 인도 완료", 0),
    ("SHP-24020", "완성차 100대", 150000, "KRUSN", "DEBRV", "sea", 100, "COMPLETED",
     -1, "07:30", None, 0.15, "LOW", "B", "B", 7800, "CR-HMM", "RG-EU", "DEBRV", "브레머하펜 인도 완료", 0),
    ("SHP-24033", "정밀기기", 620, "KRICN", "DEMUC", "air,truck", 100, "COMPLETED",
     0, "06:10", None, 0.09, "LOW", "E", None, 2340, "CR-KE,CR-EUT", "RG-AIR", "DEMUC", "뮌헨 DC 입고 완료", 0),
    # --- 계획 1건 ---
    ("SHP-24090", "완성차 200대", 300000, "KRUSN", "DEBRV", "sea", 0, "PLANNED",
     26, "08:00", None, 0.18, "LOW", "B", "B", 8600, "CR-HMM", "RG-EU", "KRUSN", "울산항 선적 대기", 0),
)
SHIPMENTS: list[tuple] = list(_S)


def _leg(seq, frm, to, mode, carrier, plan_days, actual_days, state, kind="MOVE", title=None, note=""):
    """구간(leg) 1건을 만든다. 거리·비용은 서버가 좌표로 계산하므로 여기선 생략."""
    return (seq, frm, to, mode, carrier, plan_days, actual_days, state, kind, title, note)


# ---------------------------------------------------------------------------
# 7. 화물별 구간 타임라인 — '구간 진행'/'Journey Timeline' 의 원천
#    state: done(완료) / active(진행중) / pending(대기)
# ---------------------------------------------------------------------------
SEGMENTS: dict[str, list[tuple]] = {
    "SHP-24081": [
        _leg(1, "KRPUS", "KRICN", "truck", "CR-GLV", 0.3, 0.3, "done"),
        _leg(2, "KRICN", "DEFRA", "air", "CR-KE", 1.2, 1.1, "done"),
        _leg(3, "DEFRA", "DEFRA", "air", "CR-KE", 0.5, None, "active", "CUSTOMS",
             "프랑크푸르트 통관", "전략물자 EL 검증 · 3시간 경과"),
        _leg(4, "DEFRA", "DEMUC", "truck", "CR-EUT", 0.4, None, "pending", "MOVE", None, "대기"),
        _leg(5, "DEMUC", "DEMUC", "truck", "CR-EUT", 0.2, None, "pending", "HANDOVER",
             "뮌헨 DC 입고", "Zone C · Dock 4 예약 완료"),
    ],
    "SHP-24076": [
        _leg(1, "KRPUS", "NLRTM", "sea", "CR-HMM", 26.0, None, "active"),
        _leg(2, "NLRTM", "DEMUC", "truck", "CR-EUT", 1.4, None, "pending"),
    ],
    "SHP-24071": [
        _leg(1, "KRPUS", "DEHAM", "sea", "CR-MSC", 30.0, 32.0, "done"),
        _leg(2, "DEHAM", "DEHAM", "sea", "CR-MSC", 0.5, None, "active", "HANDOVER",
             "함부르크 환적 대기", "터미널 혼잡 · 슬롯 재배정 대기"),
        _leg(3, "DEHAM", "DEDUI", "rail", "CR-DBC", 0.8, None, "pending"),
    ],
    "SHP-24068": [
        _leg(1, "KRICH", "KRICN", "truck", "CR-DHL", 0.2, 0.2, "done"),
        _leg(2, "KRICN", "NLRTM", "express", "CR-DHL", 2.0, 1.9, "done"),
        _leg(3, "NLRTM", "NLRTM", "express", "CR-DHL", 0.3, None, "active", "MOVE",
             "최종 배송", "문전 배송중"),
    ],
    "SHP-24065": [
        _leg(1, "CNQIN", "ALA", "rail", "CR-CRE", 6.0, 6.4, "done"),
        _leg(2, "ALA", "ALA", "rail", "CR-CRE", 0.5, None, "active", "CUSTOMS",
             "카자흐 국경 통관", "서류 보완 요구 · 보류중"),
        _leg(3, "ALA", "DEDUI", "rail", "CR-CRE", 9.0, None, "pending"),
    ],
    "SHP-24062": [
        _leg(1, "KRUSN", "SUEZ", "sea", "CR-HMM", 18.0, None, "active"),
        _leg(2, "SUEZ", "DEBRV", "sea", "CR-HMM", 12.0, None, "pending"),
    ],
    "SHP-24059": [
        _leg(1, "KRPUS", "SIN", "sea", "CR-MSC", 6.0, 6.0, "done"),
        _leg(2, "SIN", "GBSOU", "sea", "CR-MSC", 24.0, None, "active"),
    ],
    "SHP-24057": [
        _leg(1, "KRICN", "DEFRA", "air", "CR-KE", 1.2, 1.2, "done"),
        _leg(2, "DEFRA", "ATVIE", "truck", "CR-EUT", 0.5, None, "active"),
    ],
    "SHP-24054": [
        _leg(1, "KRUSN", "AEJEA", "sea", "CR-HMM", 14.0, 15.0, "done"),
        _leg(2, "AEJEA", "AEJEA", "sea", "CR-HMM", 1.0, None, "active", "HANDOVER",
             "제벨알리 환적 대기", "모선 스케줄 지연 · 3일 대기"),
        _leg(3, "AEJEA", "DEHAM", "sea", "CR-HMM", 16.0, None, "pending"),
    ],
    "SHP-24051": [
        _leg(1, "DEHAM", "DEDUI", "truck", "CR-EUT", 0.5, None, "active"),
    ],
    "SHP-24048": [
        _leg(1, "KRICN", "SUEZ", "sea", "CR-CMA", 20.0, 20.0, "done"),
        _leg(2, "SUEZ", "ITGOA", "sea", "CR-CMA", 6.0, None, "active"),
    ],
    "SHP-24045": [
        _leg(1, "KRPUS", "NLRTM", "sea", "CR-MSC", 27.0, 27.0, "done"),
        _leg(2, "NLRTM", "NLRTM", "rail", "CR-DBC", 0.4, None, "active", "HANDOVER",
             "로테르담 철도 인계", "블록트레인 적재중"),
        _leg(3, "NLRTM", "DEDUI", "rail", "CR-DBC", 0.6, None, "pending"),
    ],
    "SHP-24042": [
        _leg(1, "KRICN", "DEFRA", "air", "CR-KE", 1.2, None, "active"),
    ],
    "SHP-24039": [
        _leg(1, "CNQIN", "ALA", "rail", "CR-CRE", 6.0, 6.0, "done"),
        _leg(2, "ALA", "DEDUI", "rail", "CR-CRE", 9.0, None, "active"),
    ],
    "SHP-24036": [
        _leg(1, "DEBRV", "DEFRA", "truck", "CR-EUT", 0.6, 0.6, "done"),
        _leg(2, "DEFRA", "DEMUC", "truck", "CR-EUT", 0.4, None, "active"),
    ],
    "SHP-24030": [
        _leg(1, "KRPUS", "CNSHA", "sea", "CR-CMA", 2.0, 2.0, "done"),
        _leg(2, "CNSHA", "USLAX", "sea", "CR-CMA", 16.0, None, "active"),
    ],
    "SHP-24027": [
        _leg(1, "KRICH", "KRICN", "truck", "CR-GLV", 0.2, 0.2, "done"),
        _leg(2, "KRICN", "DEFRA", "air", "CR-FWD", 1.3, None, "active"),
        _leg(3, "DEFRA", "NLRTM", "truck", "CR-EUT", 0.5, None, "pending"),
    ],
    "SHP-24024": [
        _leg(1, "KRPUS", "AEJEA", "sea", "CR-HMM", 13.0, 13.0, "done"),
        _leg(2, "AEJEA", "BEANR", "sea", "CR-HMM", 15.0, None, "active"),
    ],
    "SHP-24012": [
        _leg(1, "KRPUS", "ESVLC", "sea", "CR-MAE", 25.0, 24.6, "done"),
    ],
    "SHP-24020": [
        _leg(1, "KRUSN", "DEBRV", "sea", "CR-HMM", 30.0, 30.2, "done"),
    ],
    "SHP-24033": [
        _leg(1, "KRICN", "DEFRA", "air", "CR-KE", 1.2, 1.1, "done"),
        _leg(2, "DEFRA", "DEMUC", "truck", "CR-EUT", 0.4, 0.4, "done"),
    ],
    "SHP-24090": [
        _leg(1, "KRUSN", "DEBRV", "sea", "CR-HMM", 30.0, None, "pending"),
    ],
}

# ---------------------------------------------------------------------------
# 8. 화물별 AI 알림 — '리스크 감시' KPI와 상세 카드의 AI 알림 박스 원천.
#    미해결(resolved=0) WARNING/CRITICAL 알림을 가진 활성 화물 = 5건이 되도록 구성.
#    (shipment_id, severity, category, 제목, 본문, hours_ago, resolved, 액션 라벨)
# ---------------------------------------------------------------------------
SHIPMENT_ALERTS: list[tuple] = [
    ("SHP-24081", "CRITICAL", "CUSTOMS", "프랑크푸르트 전략물자 심사",
     "프랑크푸르트 통관에서 전략물자 EL 검증이 3시간째 진행중입니다. 6시간을 넘기면 뮌헨 배송이 다음 날로 밀립니다.",
     3, 0, "통관 담당 연결"),
    ("SHP-24071", "WARNING", "CONGESTION", "함부르크 터미널 혼잡",
     "노무 인력 부족으로 접안이 48시간 지연되고 있습니다. 철도 접속 슬롯 재예약이 필요합니다.",
     5, 0, "대안 분석"),
    ("SHP-24065", "CRITICAL", "CUSTOMS", "카자흐 국경 통관 보류",
     "원산지 증명 보완 요구로 통관이 보류되었습니다. ETA를 산정할 수 없어 대체 경로 검토가 필요합니다.",
     11, 0, "대안 경로 분석"),
    ("SHP-24054", "WARNING", "WEATHER", "아라비아해 기상 악화",
     "제벨알리 환적 대기중 모선 스케줄이 3일 밀렸습니다. 함부르크 도착이 15일 후로 재산정되었습니다.",
     8, 0, "시나리오 보기"),
    ("SHP-24039", "WARNING", "CONTRACT", "TCR 단일 운송사 의존",
     "중앙아시아 물량의 71%가 CRE Block Train에 집중돼 있습니다. 대체 운송사 계약 검토를 권고합니다.",
     20, 0, "배분 현황 보기"),
    # 이미 해소된 이력(타임라인 표시용)
    ("SHP-24076", "INFO", "OPTIMIZATION", "철도 접속 통합 기회",
     "로테르담 하역 후 블록트레인 통합으로 4,200,000원 절감이 가능합니다.", 30, 1, "권고 적용"),
    ("SHP-24045", "INFO", "OPTIMIZATION", "크로스도킹 적용",
     "뒤스부르크 크로스도킹으로 보관일수 2일을 단축했습니다.", 26, 1, "확인"),
]

# ---------------------------------------------------------------------------
# 9. 컨트롤타워 전역 알림 (대시보드 우측 알림 패널)
#    (alert_id, level, 라벨, 제목, 본문, hours_ago, 액션 라벨, 이동 페이지)
# ---------------------------------------------------------------------------
OPS_ALERTS: list[tuple] = [
    ("ALT-1001", "critical", "PORT CONGESTION", "로테르담 터미널 B",
     "노무 인력 부족으로 입항 선박에 48시간 지연이 예상됩니다. 3개 화물이 영향권입니다.", 0.2, "대안 분석", "scenario"),
    ("ALT-1002", "warning", "WEATHER RISK", "남중국해 태풍 접근",
     "예상 경로에 자사 선박 3척이 위치합니다. ETA 유지를 위한 우회를 권고합니다.", 1, "시나리오 보기", "scenario"),
    ("ALT-1003", "info", "OPTIMIZATION", "철도 화물 통합 기회",
     "대기중 화물 3건을 DB Cargo 블록트레인으로 통합하면 4,200,000원을 절감합니다.", 3, "권고 적용", "network"),
    ("ALT-1004", "warning", "CUSTOMS", "프랑크푸르트 전략물자 심사",
     "SHP-24081의 EL 검증이 3시간째 진행중입니다. 6시간 초과 시 뮌헨 배송이 하루 밀립니다.", 4, "통관 담당 연결", "tracking"),
    ("ALT-1005", "critical", "CONTRACT", "CRE 블록트레인 의존도 71%",
     "중앙아시아 TCR 물량이 단일 운송사에 집중돼 있습니다. 대체 운송사 계약 검토가 필요합니다.", 6, "배분 현황 보기", "network"),
]

# ---------------------------------------------------------------------------
# 10. 제안서 보관함 초기 1건 (프론트 navSavedCnt = 1)
# ---------------------------------------------------------------------------
SAVED_PROPOSALS: list[tuple] = [
    ("SCEN-8790", "광양 → 안트베르펜 · 해상+철도", 4120000, "KRW", 26.4, "B",
     "blue", "승인 대기", '["sea","rail"]'),
]

# ---------------------------------------------------------------------------
# 11. 업로드 컬럼 매핑 사전 — 업로드된 CSV 헤더를 내부 필드로 자동 매핑할 때 사용.
#     (원본 컬럼 후보, 내부 필드, 변환 메모, 신뢰도 tone, 상태 라벨)
# ---------------------------------------------------------------------------
COLUMN_DICTIONARY: list[tuple] = [
    ("POL", "from_node", "", "ok", "자동 확정"),
    ("POD", "to_node", "", "ok", "자동 확정"),
    ("POL / POD", "from_node / to_node", "", "ok", "자동 확정"),
    ("OFR_20DC", "krw_per_kg", "환산 ÷ 24,000kg", "ok", "자동 확정"),
    ("OFR_40HC", "krw_per_kg", "환산 ÷ 26,000kg", "ok", "자동 확정"),
    ("T/TIME", "days", "", "ok", "자동 확정"),
    ("TRANSIT_TIME", "days", "", "ok", "자동 확정"),
    ("VESSEL_NAME", "vessel_imo", "→ CII 조회 키", "warn", "확인 필요"),
    ("IMO", "vessel_imo", "", "ok", "자동 확정"),
    ("CARRIER", "carrier_id", "운송사 사전 대조", "ok", "자동 확정"),
    ("SURCHARGE_BAF", "—", "미지정", "gray", "건너뜀"),
    ("REMARK", "note", "", "ok", "자동 확정"),
    ("VALID_FROM", "valid_from", "", "ok", "자동 확정"),
    ("VALID_TO", "valid_to", "", "ok", "자동 확정"),
]

# 업로드 검증 결과가 기존 상담(시나리오) 추천에 주는 영향 데모
UPLOAD_IMPACT: list[tuple] = [
    ("CNS-3312", "항공 직결", "해상+철도 연합", "ok", "−12.4%"),
    ("CNS-3308", "해상+트럭 연합", "해상+트럭 연합", "gray", "유지"),
    ("CNS-3301", "특송 문전", "특송 문전", "danger", "+2.1%"),
]

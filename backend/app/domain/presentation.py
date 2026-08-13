"""화면 표기 규칙(색·라벨·아이콘) 상수.

프론트엔드 CSS 변수/칩 색과 1:1로 맞춰 두어, 백엔드가 내려준 값을 그대로
style/className 에 넣을 수 있게 한다. (glovis-ai-control-tower.html 의
MODE_KO / MODE_HEX / GRADE_HEX 와 동일)
"""

from __future__ import annotations

MODE_KO = {"sea": "해상", "air": "항공", "rail": "철도", "truck": "육상", "express": "특송"}
MODE_HEX = {"sea": "#1E6FBF", "air": "#7A5AF8", "rail": "#12A47B", "truck": "#E08A00", "express": "#D8443C"}
GRADE_HEX = {"A": "#0E9E62", "B": "#7CB342", "C": "#E0A21B", "D": "#F07B26", "E": "#D8443C"}

# 구간 아이콘: 구간 종류(kind)가 우선, 없으면 운송 모드로 결정한다.
KIND_ICON = {"CUSTOMS": "ti-file-check", "HANDOVER": "ti-building-warehouse"}
MODE_ICON = {
    "sea": "ti-anchor",
    "air": "ti-plane",
    "rail": "ti-train",
    "truck": "ti-truck",
    "express": "ti-rocket",
}

# 상태 색(진행바 tone) — 위험도가 색을 지배하고, 그다음이 진척도, 마지막이 모드색
TONE_DANGER = "#D8443C"
TONE_WARN = "#D08700"
TONE_OK = "#0E9E62"

STATUS_KO = {
    "IN_TRANSIT": "운송중",
    "DELAYED": "지연",
    "CUSTOMS_HOLD": "통관 보류",
    "ARRIVING": "도착 임박",
    "PLANNED": "계획",
    "COMPLETED": "완료",
}


def segment_icon(kind: str | None, mode: str | None) -> str:
    if kind and kind in KIND_ICON:
        return KIND_ICON[kind]
    return MODE_ICON.get(mode or "", "ti-point")


def split_csv(value: str | None) -> list[str]:
    return [x for x in (value or "").split(",") if x]

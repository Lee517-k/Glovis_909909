export type PageId =
  | "dashboard"
  | "scenario"
  | "saved"
  | "tracking"
  | "network"
  | "upload"
  | "yp_data_reliability";

export interface NavigationItem {
  id: PageId;
  label: string;
  description: string;
  icon: "grid" | "route" | "location" | "network" | "bookmark";
}

export const NAV_ITEMS: NavigationItem[] = [
  {
    id: "dashboard",
    label: "대시보드",
    description: "주요 운송 지표와 운영 현황을 확인하는 화면입니다.",
    icon: "grid",
  },
  {
    id: "scenario",
    label: "운송 시나리오",
    description: "복합운송 조건을 입력하고 후보 경로를 비교하는 화면입니다.",
    icon: "route",
  },
  {
    id: "tracking",
    label: "운송 추적",
    description: "진행 중인 운송 건과 구간별 상태를 확인하는 화면입니다.",
    icon: "location",
  },
  {
    id: "network",
    label: "운송사 배분",
    description: "거점과 운송 연결망을 조회하는 화면입니다.",
    icon: "network",
  },
  {
    id: "saved",
    label: "제안서 보관함",
    description: "저장한 운송 시나리오와 비교 결과를 모아보는 화면입니다.",
    icon: "bookmark",
  },
  {
    id: "upload",
    label: "데이터",
    description: "운송 계획에 필요한 기준 데이터를 관리하는 화면입니다.",
    icon: "grid",
  },
  {
    id: "yp_data_reliability",
    label: "데이터 신뢰도",
    description: "등록된 물류 데이터의 품질과 신뢰도를 확인하는 화면입니다.",
    icon: "location",
  },
];

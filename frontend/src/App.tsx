import { useEffect, useRef, useState } from "react";

import { AppHeader } from "./components/AppHeader";
import { Sidebar } from "./components/Sidebar";
import { Drawer, type DrawerContent } from "./components/Drawer";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { ScenarioPage } from "./pages/ScenarioPage";
import { SavedPage, type SavedProposal } from "./pages/SavedPage";
import { UploadPage } from "./pages/YP_DataUploadPage";
import { YpDataReliabilityPage } from "./pages/YP_DataReliabilityPage";
import { listSavedScenarios, toggleFavoriteScenario } from "./api/negotiationApi";
import type { SavedScenario } from "./types/negotiation";
import type { BadgeTone } from "./lib/YP_ui";
import { YPDashboardPage } from "./pages/YP_DashboardPage";
import { TrackingPage } from "./pages/HS_TrackingPage";
import { NetworkPage } from "./pages/HS_NetworkPage";
import { NAV_ITEMS, type PageId } from "./types/navigation";

const DEFAULT_PAGE: PageId = "dashboard";

const STATUS_TONE: Record<SavedScenario["status"], BadgeTone> = {
  DRAFT: "gray",
  CONFIRMED: "blue",
  ACTIVE: "ok",
  CANCELLED: "danger",
  CLOSED: "purple",
};

function toSavedProposal(sc: SavedScenario): SavedProposal {
  return {
    id: sc.scenario_id,
    title: sc.scenario_name,
    cost: `$${Math.round(sc.metrics.shipment_cost_usd).toLocaleString()}`,
    days: `${sc.metrics.total_days}일`,
    grade: `정시 ${Math.round(sc.metrics.reliability * 100)}%`,
    when: sc.created_at ? `${sc.created_at.slice(5, 10)} 저장` : "",
    tag: STATUS_TONE[sc.status] ?? "gray",
    tagLabel: sc.status,
    isFavorite: sc.is_favorite,
  };
}

function getPageFromHash(): PageId {
  const candidate = window.location.hash.replace("#/", "") as PageId;
  return NAV_ITEMS.some((item) => item.id === candidate) ? candidate : DEFAULT_PAGE;
}

function App() {
  const [page, setPage] = useState<PageId>(getPageFromHash);
  const dashboardShipmentRef = useRef<string | null>(null);
  const [drawerContent, setDrawerContent] = useState<DrawerContent | null>(null);
  const [allScenarios, setAllScenarios] = useState<SavedScenario[]>([]);
  const [savedRefreshKey, setSavedRefreshKey] = useState(0);

  useEffect(() => {
    const handleHashChange = () => setPage(getPageFromHash());
    const handleDashboardShipment = (event: MouseEvent) => {
      if ((event.target as HTMLElement).closest(".yp-dashboard-kpis .kpi")) {
        dashboardShipmentRef.current = null;
        window.dispatchEvent(new CustomEvent("dashboard:shipment-selected", { detail: { shipmentId: null } }));
        return;
      }
      const row = (event.target as HTMLElement).closest(".yp-dashboard-table tbody tr");
      if (!row) return;
      const shipmentId = row.querySelector(".mono")?.textContent?.trim();
      if (!shipmentId) return;
      const isSameShipment = dashboardShipmentRef.current === shipmentId;
      if (isSameShipment) {
        dashboardShipmentRef.current = null;
        document.querySelectorAll<HTMLElement>(".yp-dashboard-kpis .kpi").forEach((card) => card.classList.add("active"));
        window.dispatchEvent(new CustomEvent("dashboard:shipment-selected", { detail: { shipmentId: null } }));
      } else {
        dashboardShipmentRef.current = shipmentId;
        document.querySelectorAll<HTMLElement>(".yp-dashboard-kpis .kpi").forEach((card) => card.classList.remove("active"));
        window.dispatchEvent(new CustomEvent("dashboard:shipment-selected", { detail: { shipmentId } }));
      }
    };
    window.addEventListener("hashchange", handleHashChange);
    document.addEventListener("click", handleDashboardShipment);
    return () => {
      window.removeEventListener("hashchange", handleHashChange);
      document.removeEventListener("click", handleDashboardShipment);
    };
  }, []);

  // 진짜 SQLite(scenarios) 조회 — 로컬 state가 아니다. 한 번에 전부 불러온
  // 다음 화면에서 즐겨찾기 여부로 나눠 쓴다: "제안서 보관함" 목록엔
  // is_favorite=true만, "보관함에 추가" 팝업엔 false만.
  useEffect(() => {
    let cancelled = false;
    listSavedScenarios()
      .then((data) => {
        if (!cancelled) setAllScenarios(data);
      })
      .catch(() => {
        // 백엔드가 아직 없거나 조회에 실패해도 조용히 빈 목록으로 둔다.
      });
    return () => {
      cancelled = true;
    };
  }, [savedRefreshKey]);

  const favorites = allScenarios.filter((s) => s.is_favorite).map(toSavedProposal);
  const unsaved = allScenarios.filter((s) => !s.is_favorite);

  const activeItem = NAV_ITEMS.find((item) => item.id === page) ?? NAV_ITEMS[0];

  const navigate = (nextPage: PageId) => {
    window.location.hash = `/${nextPage}`;
    setPage(nextPage);
  };

  const refreshSaved = () => setSavedRefreshKey((key) => key + 1);

  // 제안서 보관함의 휴지통 = 즐겨찾기 OFF일 뿐, 시나리오 자체를 지우지 않는다.
  async function toggleFavorite(scenarioId: string) {
    await toggleFavoriteScenario(scenarioId);
    refreshSaved();
  }

  // 제안서 보관함 "열기" → 그 시나리오를 운송 추적에서 바로 띄운다.
  // DRAFT(순수 북마크, 한 번도 "이 경로 선택" 안 한 것)는 운송 추적에
  // 애초에 안 뜨는 시나리오라 대신 알려준다.
  function openInTracking(scenarioId: string, status: string) {
    if (status === "DRAFT" || status === "CANCELLED") {
      window.alert("아직 실행 확정(경로 선택)되지 않은 시나리오라 운송 추적에는 없습니다.\n운송 시나리오에서 '이 경로 선택'을 먼저 눌러주세요.");
      return;
    }
    void scenarioId;
    navigate("tracking");
  }

  const renderPage = () => {
    if (page === "dashboard") {
      return <YPDashboardPage onJump={navigate} />;
    }
    if (page === "tracking") return <TrackingPage active />;
    if (page === "network") return <NetworkPage active />;
    if (page === "yp_data") {
      return <UploadPage active />;
    }

    if (page === "yp_data_reliability") {
      return <YpDataReliabilityPage active />;
    }

    if (page === "scenario") {
      return (
        <ScenarioPage
          active
          onOpenDrawer={setDrawerContent}
          onSave={refreshSaved}
          onNavigateToTracking={() => navigate("tracking")}
        />
      );
    }

    if (page === "saved") {
      return (
        <SavedPage
          active
          items={favorites}
          unsaved={unsaved}
          onUnbookmark={toggleFavorite}
          onAddToBookmark={toggleFavorite}
          onOpen={openInTracking}
        />
      );
    }

    return <PlaceholderPage page={activeItem} />;
  };

  return (
    <div className="app-layout">
      <Sidebar
        page={page}
        onNavigate={navigate}
        savedCount={favorites.length}
        trackingCount={0}
      />

      <div className="app-main">
        <AppHeader />
        {renderPage()}
      </div>
      <Drawer content={drawerContent} onClose={() => setDrawerContent(null)} />
    </div>
  );
}

export default App;

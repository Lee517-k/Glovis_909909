import { useEffect, useState } from "react";

import { AppHeader } from "./components/AppHeader";
import { Sidebar } from "./components/Sidebar";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { UploadPage } from "./pages/YP_DataUploadPage";
import { YpDataReliabilityPage } from "./pages/YP_DataReliabilityPage";
import { YPDashboardPage } from "./pages/YP_DashboardPage";
import { TrackingPage } from "./pages/HS_TrackingPage";
import { NetworkPage } from "./pages/HS_NetworkPage";
import { NAV_ITEMS, type PageId } from "./types/navigation";

const DEFAULT_PAGE: PageId = "dashboard";

function getPageFromHash(): PageId {
  const candidate = window.location.hash.replace("#/", "") as PageId;
  return NAV_ITEMS.some((item) => item.id === candidate) ? candidate : DEFAULT_PAGE;
}

function App() {
  const [page, setPage] = useState<PageId>(getPageFromHash);

  useEffect(() => {
    const handleHashChange = () => setPage(getPageFromHash());
    const handleDashboardShipment = (event: MouseEvent) => {
      if ((event.target as HTMLElement).closest(".yp-dashboard-kpis .kpi")) {
        window.dispatchEvent(new CustomEvent("dashboard:shipment-selected", { detail: { shipmentId: null } }));
        return;
      }
      const row = (event.target as HTMLElement).closest(".yp-dashboard-table tbody tr");
      if (!row) return;
      const shipmentId = row.querySelector(".mono")?.textContent?.trim();
      if (!shipmentId) return;
      document.querySelectorAll<HTMLElement>(".yp-dashboard-kpis .kpi:not(.active)").forEach((card) => card.click());
      window.dispatchEvent(new CustomEvent("dashboard:shipment-selected", { detail: { shipmentId } }));
    };
    window.addEventListener("hashchange", handleHashChange);
    document.addEventListener("click", handleDashboardShipment);
    return () => {
      window.removeEventListener("hashchange", handleHashChange);
      document.removeEventListener("click", handleDashboardShipment);
    };
  }, []);

  const activeItem = NAV_ITEMS.find((item) => item.id === page) ?? NAV_ITEMS[0];

  const navigate = (nextPage: PageId) => {
    window.location.hash = `/${nextPage}`;
    setPage(nextPage);
  };

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

    return <PlaceholderPage page={activeItem} />;
  };

  return (
    <div className="app-layout">
      <Sidebar
        page={page}
        onNavigate={navigate}
        savedCount={0}
        trackingCount={0}
      />

      <div className="app-main">
        <AppHeader />
        {renderPage()}
      </div>
    </div>
  );
}

export default App;

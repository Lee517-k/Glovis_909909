import { useEffect, useState } from "react";

import { AppHeader } from "./components/AppHeader";
import { Sidebar } from "./components/Sidebar";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { YP_DataUploadPage } from "./pages/YP_DataUploadPage";
import { YP_DataReliabilityPage } from "./pages/YP_DataReliabilityPage";
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
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const activeItem = NAV_ITEMS.find((item) => item.id === page) ?? NAV_ITEMS[0];

  const navigate = (nextPage: PageId) => {
    window.location.hash = `/${nextPage}`;
    setPage(nextPage);
  };

  const renderPage = () => {
    if (page === "yp_data") {
      return <YP_DataUploadPage />;
    }

    if (page === "yp_data_reliability") {
      return <YP_DataReliabilityPage />;
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
        <AppHeader pageTitle={activeItem.label} />
        {renderPage()}
      </div>
    </div>
  );
}

export default App;

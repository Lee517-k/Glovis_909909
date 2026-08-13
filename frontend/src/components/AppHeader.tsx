import { useState } from "react";

export function AppHeader() {
  const [searchText, setSearchText] = useState("");

  return (
    <header className="topbar">
      <h2>Control Tower</h2>
      <div className="searchwrap">
        <i className="ti ti-search" />
        <input
          className="search"
          value={searchText}
          onChange={(event) => setSearchText(event.target.value)}
          placeholder={searchText ? "" : "운송번호, 항만, 시나리오 검색"}
        />
        {searchText && (
          <button className="search-clear" type="button" aria-label="검색어 지우기" onClick={() => setSearchText("") }>
            <i className="ti ti-x" />
          </button>
        )}
      </div>
      <div className="topbar-spacer" />
      <div className="toppill">
        <span className="pulse topbar-pulse" />
        진행중 화물 0건
      </div>
      <button className="icobtn" type="button" aria-label="알림">
        <i className="ti ti-bell" />
        <span className="dot" />
      </button>
      <button className="icobtn" type="button" aria-label="앱 메뉴">
        <i className="ti ti-apps" />
      </button>
      <div className="avatar">KR</div>
    </header>
  );
}


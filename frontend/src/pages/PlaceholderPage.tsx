import { Icon } from "../components/Icon";
import type { NavigationItem } from "../types/navigation";

export function PlaceholderPage({ page }: { page: NavigationItem }) {
  return (
    <main className="page-content">
      <section className="page-heading">
        <div>
          <span className="page-kicker">CONTROL TOWER</span>
          <h1>{page.label}</h1>
          <p>{page.description}</p>
        </div>
        <button className="outline-button" type="button" disabled>
          기능 준비 중
        </button>
      </section>

      <section className="summary-grid" aria-label="요약 영역 예시">
        {["운영 현황", "주요 지표", "알림 및 이슈"].map((title) => (
          <article className="summary-card" key={title}>
            <span className="skeleton skeleton-label" />
            <strong>{title}</strong>
            <span className="skeleton skeleton-value" />
          </article>
        ))}
      </section>

      <section className="empty-panel">
        <div className="empty-icon">
          <Icon name={page.icon} />
        </div>
        <h2>{page.label} 화면 준비 중</h2>
        <p>레이아웃과 메뉴 이동만 구성된 초기 UI입니다. 세부 기능은 다음 개발 단계에서 추가합니다.</p>
        <div className="empty-lines" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </section>
    </main>
  );
}


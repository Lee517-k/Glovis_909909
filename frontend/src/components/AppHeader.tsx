interface AppHeaderProps {
  pageTitle: string;
}

export function AppHeader({ pageTitle }: AppHeaderProps) {
  return (
    <header className="app-header">
      <div className="header-title">
        <div>
          <span className="header-eyebrow">MULTIMODAL LOGISTICS</span>
          <strong>{pageTitle}</strong>
        </div>
      </div>

      <div className="header-actions">
        <button className="notification-button" type="button" aria-label="알림">
          <span className="notification-icon">○</span>
        </button>
        <div className="profile">
          <span className="profile-avatar">CT</span>
          <div>
            <strong>Control Tower</strong>
            <span>Project Team</span>
          </div>
        </div>
      </div>
    </header>
  );
}

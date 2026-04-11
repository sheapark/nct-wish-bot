import { useState } from "react";
import DashboardPage from "./pages/DashboardPage";
import LogsPage from "./pages/LogsPage";
import SettingsPage from "./pages/SettingsPage";

type Tab = "dashboard" | "logs" | "settings";

const NAV: { id: Tab; label: string; icon: string }[] = [
  { id: "dashboard", label: "대시보드", icon: "🌸" },
  { id: "logs", label: "로그", icon: "📋" },
  { id: "settings", label: "설정", icon: "⚙️" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="header-brand">
            <span className="brand-dot" />
            <span className="brand-name">✨ NCT WISH BOT</span>
            <span className="brand-tag">ADMIN</span>
          </div>
          <nav className="header-nav">
            {NAV.map((n) => (
              <button
                key={n.id}
                className={`nav-btn ${tab === n.id ? "active" : ""}`}
                onClick={() => setTab(n.id)}
              >
                <span className="nav-icon">{n.icon}</span>
                <span className="nav-label">{n.label}</span>
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="main">
        {tab === "dashboard" && <DashboardPage />}
        {tab === "logs" && <LogsPage />}
        {tab === "settings" && <SettingsPage />}
      </main>

      <nav className="bottom-nav">
        {NAV.map((n) => (
          <button
            key={n.id}
            className={`bottom-nav-btn ${tab === n.id ? "active" : ""}`}
            onClick={() => setTab(n.id)}
          >
            <span className="nav-icon">{n.icon}</span>
            <span>{n.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}

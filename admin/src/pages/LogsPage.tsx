import { useState } from "react";
import { useLogs } from "../hooks/useData";
import { format, parseISO } from "date-fns";

export default function LogsPage() {
  const { data: logs, loading, reload } = useLogs();
  const [expanded, setExpanded] = useState<number | null>(null);

  const successCount = logs.filter((l) => l.success).length;
  const failCount = logs.length - successCount;

  if (loading)
    return (
      <div className="loading-screen">
        <div className="spinner" />
        <p>📋 로그 불러오는 중…</p>
      </div>
    );

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">📋 트윗 로그</h1>
        <button className="btn-ghost" onClick={reload}>
          🔄 새로고침
        </button>
      </div>

      {/* 요약 배지 */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <span
          style={{
            background: "var(--mint-soft)",
            color: "var(--mint-deep)",
            border: "1.5px solid rgba(52,184,137,0.3)",
            borderRadius: "999px",
            padding: "5px 14px",
            fontSize: 12,
            fontWeight: 800,
          }}
        >
          ✅ 성공 {successCount}건
        </span>
        <span
          style={{
            background: "var(--pink-soft)",
            color: "var(--pink-deep)",
            border: "1.5px solid rgba(232,87,154,0.3)",
            borderRadius: "999px",
            padding: "5px 14px",
            fontSize: 12,
            fontWeight: 800,
          }}
        >
          ❌ 실패 {failCount}건
        </span>
        <span
          style={{
            background: "var(--lavender-soft)",
            color: "var(--lavender-deep)",
            border: "1.5px solid rgba(196,168,255,0.3)",
            borderRadius: "999px",
            padding: "5px 14px",
            fontSize: 12,
            fontWeight: 800,
          }}
        >
          🕐 전체 {logs.length}건
        </span>
      </div>

      <div className="log-list">
        {logs.map((log) => (
          <div
            key={log.id}
            className={`log-item ${log.success ? "log-ok" : "log-err"}`}
            onClick={() => setExpanded(expanded === log.id ? null : log.id)}
          >
            <div className="log-row">
              <span className={`log-status ${log.success ? "ok" : "err"}`}>
                {log.success ? "✓" : "✗"}
              </span>
              <span className="log-time">🕐 {format(parseISO(log.posted_at), "MM/dd HH:mm")}</span>
              {log.youtube_views != null && (
                <span className="log-views">🎬 {log.youtube_views.toLocaleString()}</span>
              )}
              {!log.success && log.error_msg && (
                <span className="log-errmsg">⚠️ {log.error_msg}</span>
              )}
              <span className="log-chevron">{expanded === log.id ? "▲" : "▼"}</span>
            </div>
            {expanded === log.id && <pre className="log-body">{log.tweet_text}</pre>}
          </div>
        ))}
      </div>
    </div>
  );
}

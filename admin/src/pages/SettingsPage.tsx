import { useState, useEffect } from "react";
import { useConfig } from "../hooks/useData";

const RENDER_WEBHOOK = import.meta.env.VITE_RENDER_WEBHOOK_URL || "";

export default function SettingsPage() {
  const { data: config, loading, updateBulk } = useConfig();
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [trigResult, setTrigResult] = useState<string | null>(null);

  useEffect(() => {
    const map: Record<string, string> = {};
    for (const c of config) map[c.key] = c.value;
    setForm(map);
  }, [config]);

  // ── 전체 한 번에 저장 ──────────────────────────
  async function handleSave() {
    setSaving(true);
    await updateBulk(form); // DB 요청 1번으로 끝!
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  async function handleManualRun() {
    if (!RENDER_WEBHOOK) {
      setTrigResult("⚠️ VITE_RENDER_WEBHOOK_URL 환경변수가 없어요!");
      return;
    }
    setTriggering(true);
    setTrigResult(null);
    try {
      const res = await fetch(RENDER_WEBHOOK, { method: "POST" });
      setTrigResult(res.ok ? "🎉 트윗 발행 요청 완료!" : `❌ 실패 (${res.status})`);
    } catch {
      setTrigResult("❌ 네트워크 오류가 발생했어요");
    }
    setTriggering(false);
  }

  if (loading)
    return (
      <div className="loading-screen">
        <div className="spinner" />
        <p>⚙️ 설정 불러오는 중…</p>
      </div>
    );

  const cookieValue = form["guyseom_cookie"] ?? "";

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">⚙️ 봇 설정</h1>
      </div>

      {/* 타깃 곡 설정 */}
      <section className="card">
        <h2 className="card-title">🎵 타깃 곡 설정</h2>
        <div className="form-grid">
          {[
            { key: "target_title", label: "🎶 곡 제목", placeholder: "COLOR" },
            { key: "target_artist", label: "🌟 아티스트", placeholder: "NCT WISH" },
            { key: "yt_video_id", label: "🎬 YouTube Video ID", placeholder: "28dAfmIAlCo" },
          ].map(({ key, label, placeholder }) => (
            <label key={key} className="form-field">
              <span className="form-label">{label}</span>
              <input
                className="form-input"
                value={form[key] ?? ""}
                placeholder={placeholder}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              />
            </label>
          ))}

          <label className="form-field">
            <span className="form-label">🔔 봇 상태</span>
            <div className="toggle-wrap">
              <button
                className={`toggle-btn ${form["paused"] === "true" ? "on" : "off"}`}
                onClick={() =>
                  setForm({ ...form, paused: form["paused"] === "true" ? "false" : "true" })
                }
              >
                <span className="toggle-knob" />
              </button>
              <span className="toggle-label">
                {form["paused"] === "true" ? "😴 일시정지 중" : "🟢 실행 중"}
              </span>
            </div>
          </label>
        </div>

        <div className="form-actions">
          <button
            className={`btn-primary ${saved ? "btn-success" : ""}`}
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? "💾 저장 중…" : saved ? "✨ 저장됐어요!" : "💾 설정 저장"}
          </button>
        </div>
      </section>

      {/* 가이섬 쿠키 */}
      <section className="card">
        <h2 className="card-title">🍪 가이섬 쿠키 갱신</h2>
        <p className="card-desc" style={{ marginBottom: 16 }}>
          🔄 가이섬 세션 쿠키는 주기적으로 만료돼요. 멜론 실시간 차트가 ❌로 뜨면 여기서
          갱신해주세요!
        </p>

        <div
          style={{
            background: "var(--yellow-soft)",
            border: "1.5px solid rgba(232,201,122,0.5)",
            borderRadius: "var(--radius-sm)",
            padding: "14px 16px",
            marginBottom: 16,
            fontSize: 12,
            lineHeight: 1.9,
            fontWeight: 600,
            color: "var(--text-muted)",
          }}
        >
          <p style={{ fontWeight: 800, color: "var(--text)", marginBottom: 4 }}>
            📖 쿠키 가져오는 방법
          </p>
          <p>
            1️⃣ 브라우저에서 <strong>가이섬(xn--o39an51b2re.com)</strong> 로그인
          </p>
          <p>2️⃣ F12 → Application 탭 → Cookies → 해당 사이트 선택</p>
          <p>
            3️⃣{" "}
            <code
              style={{
                background: "rgba(0,0,0,0.07)",
                padding: "1px 6px",
                borderRadius: 4,
                fontFamily: "var(--mono)",
              }}
            >
              __Secure-next-auth.session-token
            </code>{" "}
            값 복사
          </p>
          <p>4️⃣ 아래 입력칸에 붙여넣고 저장 🎉</p>
        </div>

        <label className="form-field">
          <span className="form-label">🔐 세션 토큰</span>
          <textarea
            className="form-input"
            style={{
              resize: "vertical",
              minHeight: 90,
              fontFamily: "var(--mono)",
              fontSize: 11,
              lineHeight: 1.7,
              wordBreak: "break-all",
            }}
            value={cookieValue}
            placeholder="eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..."
            onChange={(e) => setForm({ ...form, guyseom_cookie: e.target.value })}
          />
        </label>

        <div
          style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}
        >
          <span
            style={{
              background: cookieValue ? "var(--mint-soft)" : "var(--pink-soft)",
              color: cookieValue ? "var(--mint-deep)" : "var(--pink-deep)",
              border: `1.5px solid ${cookieValue ? "rgba(52,184,137,0.3)" : "rgba(232,87,154,0.3)"}`,
              borderRadius: "999px",
              padding: "4px 12px",
              fontSize: 11,
              fontWeight: 800,
            }}
          >
            {cookieValue ? "✅ 쿠키 설정됨" : "⚠️ 쿠키 없음 — 멜론 실시간 ❌"}
          </span>
          {cookieValue && (
            <span
              style={{
                fontSize: 11,
                color: "var(--text-dim)",
                fontWeight: 600,
                fontFamily: "var(--mono)",
              }}
            >
              {cookieValue.slice(0, 24)}…
            </span>
          )}
        </div>

        <div className="form-actions">
          <button
            className={`btn-primary ${saved ? "btn-success" : ""}`}
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? "💾 저장 중…" : saved ? "✨ 저장됐어요!" : "🍪 쿠키 저장"}
          </button>
        </div>
      </section>

      {/* 수동 트윗 발행 */}
      <section className="card">
        <h2 className="card-title">🚀 수동 트윗 발행</h2>
        <p className="card-desc">
          💡 크론잡 스케줄과 별개로 지금 즉시 트윗을 발행할 수 있어요.
          <br />
          Render의 Deploy Hook URL이 필요해요.
        </p>
        <button className="btn-neon" onClick={handleManualRun} disabled={triggering}>
          {triggering ? "🌀 발행 중…" : "🐦 지금 트윗 발행하기 ✨"}
        </button>
        {trigResult && <p className="trig-result">{trigResult}</p>}
      </section>

      {/* 환경변수 가이드 */}
      <section className="card">
        <h2 className="card-title">🔑 환경변수 설정 가이드</h2>
        <div className="env-block">
          <p className="env-comment"># admin/.env.local</p>
          <p>
            <span className="env-key">VITE_SUPABASE_URL</span>=https://xxxx.supabase.co
          </p>
          <p>
            <span className="env-key">VITE_SUPABASE_ANON_KEY</span>=eyJ...
          </p>
          <p>
            <span className="env-key">VITE_RENDER_WEBHOOK_URL</span>
            =https://api.render.com/deploy/...
          </p>
        </div>
        <p className="card-desc" style={{ marginTop: 12 }}>
          📦 Render Static Site 배포 시 Environment Variables에 동일하게 입력하면 돼요!
        </p>
      </section>
    </div>
  );
}

import { useMemo } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { useRanks, useLogs } from "../hooks/useData";
import { SITE_LABELS, SITE_COLORS, type SiteKey } from "../types";

const SITES = Object.keys(SITE_LABELS) as SiteKey[];

function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string | number | null | undefined;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ color: accent }}>
        {value ?? "—"}
      </div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

function RankBadge({ rank, delta }: { rank: number | null; delta: number | null }) {
  if (rank == null) return <span className="rank-null">❌</span>;
  const arrow =
    delta == null ? "" : delta > 0 ? `🔺${delta}` : delta < 0 ? `🔻${Math.abs(delta)}` : "➖";
  return (
    <span className="rank-badge">
      <strong>{rank}</strong>
      {arrow && <small>{arrow}</small>}
    </span>
  );
}

// UTC → KST 변환 헬퍼
function toKST(dateStr: string): Date {
  return new Date(new Date(dateStr).getTime() + 9 * 3600_000);
}

export default function DashboardPage() {
  const { data: ranks, loading: rl } = useRanks(336);
  const { data: logs, loading: ll } = useLogs();

  const latestRanks = useMemo(() => {
    const map: Partial<Record<SiteKey, { rank: number | null; delta: number | null }>> = {};
    for (const row of ranks) map[row.site as SiteKey] = { rank: row.rank, delta: row.delta };
    return map;
  }, [ranks]);

  const latestViews = logs[0]?.youtube_views ?? null;

  const successRate = useMemo(() => {
    if (!logs.length) return 0;
    return Math.round((logs.filter((l) => l.success).length / logs.length) * 100);
  }, [logs]);

  // 차트 데이터 — KST 기준
  const chartData = useMemo(() => {
    const last24 = ranks.filter(
      (r) => new Date(r.checked_at).getTime() > Date.now() - 24 * 3600_000,
    );
    const grouped: Record<string, Record<string, number | string | null>> = {};
    for (const row of last24) {
      const kst = toKST(row.checked_at);
      const key = kst.toISOString().slice(0, 13); // "2026-04-11T19"
      if (!grouped[key]) grouped[key] = { time: key };
      grouped[key][row.site] = row.rank;
    }
    return Object.values(grouped).sort((a, b) => (String(a.time) < String(b.time) ? -1 : 1));
  }, [ranks]);

  // 조회수 차트 — KST 기준
  const viewsChart = useMemo(() => {
    return logs
      .slice(0, 48)
      .reverse()
      .map((l) => {
        const kst = toKST(l.posted_at);
        const hh = String(kst.getUTCHours()).padStart(2, "0");
        const mm = String(kst.getUTCMinutes()).padStart(2, "0");
        return {
          time: `${hh}:${mm}`,
          views: l.youtube_views,
        };
      });
  }, [logs]);

  if (rl || ll)
    return (
      <div className="loading-screen">
        <div className="spinner" />
        <p>🌸 데이터 불러오는 중…</p>
      </div>
    );

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">🌟 대시보드</h1>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        <StatCard
          label="🎬 유튜브 조회수"
          value={latestViews != null ? latestViews.toLocaleString() : "—"}
          sub="최근 트윗 기준"
          accent="var(--lavender-deep)"
        />
        <StatCard
          label="💌 트윗 성공률"
          value={`${successRate}%`}
          sub={`최근 ${logs.length}건`}
          accent={successRate >= 95 ? "var(--mint-deep)" : "var(--peach)"}
        />
        <StatCard
          label="🍀 멜론 TOP100"
          value={latestRanks.melon_top100?.rank ?? "—"}
          sub={
            latestRanks.melon_top100?.delta != null
              ? latestRanks.melon_top100.delta > 0
                ? `🔺${latestRanks.melon_top100.delta}`
                : latestRanks.melon_top100.delta < 0
                  ? `🔻${Math.abs(latestRanks.melon_top100.delta)}`
                  : "➖ 유지"
              : ""
          }
          accent="var(--mint-deep)"
        />
        <StatCard
          label="💜 지니"
          value={latestRanks.genie?.rank ?? "—"}
          sub=""
          accent="var(--lavender-deep)"
        />
      </div>

      {/* 현재 순위 */}
      <section className="card">
        <h2 className="card-title">🏆 현재 순위</h2>
        <div className="rank-grid">
          {SITES.map((site) => (
            <div key={site} className="rank-row">
              <span className="site-dot" style={{ background: SITE_COLORS[site] }} />
              <span className="site-name">{SITE_LABELS[site]}</span>
              <RankBadge
                rank={latestRanks[site]?.rank ?? null}
                delta={latestRanks[site]?.delta ?? null}
              />
            </div>
          ))}
        </div>
      </section>

      {/* 순위 추이 차트 */}
      <section className="card">
        <h2 className="card-title">📈 순위 추이 (최근 24시간 · KST)</h2>
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: -20 }}>
              <XAxis
                dataKey="time"
                tick={{
                  fill: "var(--text-muted)",
                  fontSize: 11,
                  fontFamily: "Nunito",
                  fontWeight: 600,
                }}
                tickFormatter={(v) => `${String(v).slice(11, 13)}시`}
                interval="preserveStartEnd"
              />
              <YAxis
                reversed
                tick={{
                  fill: "var(--text-muted)",
                  fontSize: 11,
                  fontFamily: "Nunito",
                  fontWeight: 600,
                }}
                domain={["dataMin - 1", "dataMax + 1"]}
              />
              <Tooltip
                contentStyle={{
                  background: "white",
                  border: "1.5px solid var(--border)",
                  borderRadius: 14,
                  fontSize: 12,
                  fontFamily: "Nunito",
                  fontWeight: 700,
                  boxShadow: "0 4px 20px rgba(180,130,210,0.15)",
                }}
                labelFormatter={(v) =>
                  `🕐 ${String(v).slice(0, 10)} ${String(v).slice(11, 13)}시 (KST)`
                }
              />
              <Legend
                wrapperStyle={{
                  fontSize: 12,
                  paddingTop: 12,
                  fontFamily: "Nunito",
                  fontWeight: 700,
                }}
                formatter={(v) => SITE_LABELS[v as SiteKey] ?? v}
              />
              {SITES.map((site) => (
                <Line
                  key={site}
                  type="monotone"
                  dataKey={site}
                  stroke={SITE_COLORS[site]}
                  strokeWidth={2.5}
                  dot={false}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* 유튜브 조회수 차트 */}
      <section className="card">
        <h2 className="card-title">🎬 유튜브 조회수 추이 (최근 48시간 · KST)</h2>
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={viewsChart} margin={{ top: 4, right: 8, bottom: 4, left: 10 }}>
              <XAxis
                dataKey="time"
                tick={{
                  fill: "var(--text-muted)",
                  fontSize: 11,
                  fontFamily: "Nunito",
                  fontWeight: 600,
                }}
                interval={5}
              />
              <YAxis
                tick={{
                  fill: "var(--text-muted)",
                  fontSize: 11,
                  fontFamily: "Nunito",
                  fontWeight: 600,
                }}
                tickFormatter={(v) => `${(v / 10000).toFixed(0)}만`}
              />
              <Tooltip
                contentStyle={{
                  background: "white",
                  border: "1.5px solid var(--border)",
                  borderRadius: 14,
                  fontSize: 12,
                  fontFamily: "Nunito",
                  fontWeight: 700,
                  boxShadow: "0 4px 20px rgba(180,130,210,0.15)",
                }}
                formatter={(v: unknown) => [(v as number).toLocaleString(), "👁️ 조회수"]}
              />
              <Line
                type="monotone"
                dataKey="views"
                stroke="var(--lavender)"
                strokeWidth={2.5}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}

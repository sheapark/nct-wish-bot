import { createClient } from "@supabase/supabase-js";
import type { TweetLog, RankHistory, BotConfig } from "../types";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || "";
const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY || "";

export const supabase =
  supabaseUrl && supabaseKey ? createClient(supabaseUrl, supabaseKey) : null;

// ── Mock data for development ──────────────────────────────────────────────
function generateMockRanks(): RankHistory[] {
  const sites = [
    "melon_top100",
    "melon_hot100",
    "guyseom",
    "genie",
    "flo",
    "bugs",
    "vibe_top300",
  ];
  const rows: RankHistory[] = [];
  const now = new Date();
  for (let h = 335; h >= 0; h--) {
    const checked_at = new Date(now.getTime() - h * 3600_000).toISOString();
    for (const site of sites) {
      const base = site.includes("melon")
        ? 3
        : site === "genie"
        ? 5
        : site === "flo"
        ? 7
        : 4;
      const rank = Math.max(
        1,
        base + Math.round((Math.random() - 0.48) * 3 + (h / 335) * 6)
      );
      rows.push({
        id: rows.length,
        checked_at,
        site,
        rank,
        delta: Math.round((Math.random() - 0.5) * 4),
      });
    }
  }
  return rows;
}

function generateMockLogs(): TweetLog[] {
  const logs: TweetLog[] = [];
  const now = new Date();
  for (let i = 335; i >= 0; i--) {
    const posted_at = new Date(
      now.getTime() - i * 3600_000 + 10 * 60_000
    ).toISOString();
    const success = Math.random() > 0.04;
    logs.push({
      id: i,
      posted_at,
      tweet_text: `🎨COLOR  | ${posted_at.slice(0, 16).replace("T", " ")}\n\n•멜론 TOP100 3 (🔺1)\n•멜론 HOT100 4 (-)\n•멜론 실시간 2 (🔺2)\n•지니 5 (-)\n•플로 7 (🔻1)\n•벅스 4 (🔺1)\n•바이브 6 (-)\n\n🎬 ${(2400000 + i * 3000).toLocaleString()}\n\n#NCTWISH #COLOR`,
      success,
      error_msg: success ? null : "Twitter API rate limit exceeded",
      youtube_views: 2400000 + i * 3000,
    });
  }
  return logs.reverse();
}

function generateMockConfig(): BotConfig[] {
  return [
    { key: "target_title", value: "COLOR" },
    { key: "target_artist", value: "NCT WISH" },
    { key: "yt_video_id", value: "28dAfmIAlCo" },
    { key: "paused", value: "false" },
  ];
}

export const mockData = {
  ranks: generateMockRanks(),
  logs: generateMockLogs(),
  config: generateMockConfig(),
};

// ── DB helpers ─────────────────────────────────────────────────────────────
export async function fetchRecentRanks(hours = 336): Promise<RankHistory[]> {
  if (!supabase) return mockData.ranks;
  const since = new Date(Date.now() - hours * 3600_000).toISOString();
  const { data } = await supabase
    .from("rank_history")
    .select("*")
    .gte("checked_at", since)
    .order("checked_at", { ascending: true });
  return data ?? [];
}

export async function fetchRecentLogs(limit = 336): Promise<TweetLog[]> {
  if (!supabase) return mockData.logs;
  const { data } = await supabase
    .from("tweet_logs")
    .select("*")
    .order("posted_at", { ascending: false })
    .limit(limit);
  return data ?? [];
}

export async function fetchConfig(): Promise<BotConfig[]> {
  if (!supabase) return mockData.config;
  const { data } = await supabase.from("bot_config").select("*");
  return data ?? [];
}

export async function upsertConfig(key: string, value: string): Promise<void> {
  if (!supabase) return;
  await supabase.from("bot_config").upsert({ key, value });
}
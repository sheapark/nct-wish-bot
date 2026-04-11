export interface TweetLog {
  id: number;
  posted_at: string;
  tweet_text: string;
  success: boolean;
  error_msg: string | null;
  youtube_views: number | null;
}

export interface RankHistory {
  id: number;
  checked_at: string;
  site: string;
  rank: number | null;
  delta: number | null;
}

export interface BotConfig {
  key: string;
  value: string;
}

export type SiteKey =
  | "melon_top100"
  | "melon_hot100"
  | "guyseom"
  | "genie"
  | "flo"
  | "bugs"
  | "vibe_top300";

export const SITE_LABELS: Record<SiteKey, string> = {
  melon_top100: "멜론 TOP100",
  melon_hot100: "멜론 HOT100",
  guyseom: "멜론 실시간",
  genie: "지니",
  flo: "플로",
  bugs: "벅스",
  vibe_top300: "바이브",
};

export const SITE_COLORS: Record<SiteKey, string> = {
  melon_top100: "#00d084",
  melon_hot100: "#00a86b",
  guyseom: "#00ff99",
  genie: "#a855f7",
  flo: "#3b82f6",
  bugs: "#f59e0b",
  vibe_top300: "#ec4899",
};
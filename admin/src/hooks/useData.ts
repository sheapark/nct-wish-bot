import { useState, useEffect, useCallback } from "react";
import {
  fetchRecentRanks,
  fetchRecentLogs,
  fetchConfig,
  upsertConfigBulk,
} from "../lib/supabase";
import type { TweetLog, RankHistory, BotConfig } from "../types";

export function useRanks(hours = 336) {
  const [data, setData]       = useState<RankHistory[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setData(await fetchRecentRanks(hours));
    setLoading(false);
  }, [hours]);

  useEffect(() => {
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, [load]);

  return { data, loading, reload: load };
}

export function useLogs() {
  const [data, setData]       = useState<TweetLog[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setData(await fetchRecentLogs());
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, [load]);

  return { data, loading, reload: load };
}

export function useConfig() {
  const [data, setData]       = useState<BotConfig[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setData(await fetchConfig());
    setLoading(false);
  }, []);

  // 전체 form을 한 번에 저장 (기존처럼 하나씩 X)
  const updateBulk = useCallback(
    async (configs: Record<string, string>) => {
      await upsertConfigBulk(configs);
      await load();
    },
    [load]
  );

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, updateBulk };
}
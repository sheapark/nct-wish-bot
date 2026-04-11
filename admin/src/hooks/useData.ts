import { useState, useEffect, useCallback } from "react";
import {
  fetchRecentRanks,
  fetchRecentLogs,
  fetchConfig,
  upsertConfig,
} from "../lib/supabase";
import type { TweetLog, RankHistory, BotConfig } from "../types";

export function useRanks(hours = 336) {
  const [data, setData] = useState<RankHistory[]>([]);
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
  const [data, setData] = useState<TweetLog[]>([]);
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
  const [data, setData] = useState<BotConfig[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setData(await fetchConfig());
    setLoading(false);
  }, []);

  const update = useCallback(
    async (key: string, value: string) => {
      await upsertConfig(key, value);
      await load();
    },
    [load]
  );

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, update };
}
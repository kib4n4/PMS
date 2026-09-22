"use client";

import { useEffect, useState } from "react";

type DashboardDataState<T> = {
  data: T | null;
  isLoading: boolean;
  error: string | null;
};

/**
 * Fetches a dashboard's data from one of this app's own /api/dashboard/*
 * proxy routes (never Django directly — see lib/backend.ts) on mount.
 * Before this hook existed, every dashboard page rendered hardcoded mock
 * data with no loading/error/empty state handling at all.
 */
export function useDashboardData<T>(path: string): DashboardDataState<T> {
  const [state, setState] = useState<DashboardDataState<T>>({
    data: null,
    isLoading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await fetch(path, { cache: "no-store" });
        if (!response.ok) {
          if (!cancelled) {
            setState({ data: null, isLoading: false, error: `Failed to load (${response.status}).` });
          }
          return;
        }
        const data = (await response.json()) as T;
        if (!cancelled) {
          setState({ data, isLoading: false, error: null });
        }
      } catch {
        if (!cancelled) {
          setState({ data: null, isLoading: false, error: "Failed to load." });
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [path]);

  return state;
}

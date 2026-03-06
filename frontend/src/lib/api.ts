import type { Article, Market } from "@/types";

const BASE_URL = "/api/v1";

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  articles: {
    list: (params?: { category?: string; limit?: number; offset?: number }) => {
      const qs = new URLSearchParams(
        Object.entries(params ?? {}).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])
      ).toString();
      return fetchJSON<Article[]>(`/articles${qs ? `?${qs}` : ""}`);
    },
    get: (id: number) => fetchJSON<Article>(`/articles/${id}`),
  },
  markets: {
    list: (params?: { category?: string }) => {
      const qs = new URLSearchParams(
        Object.entries(params ?? {}).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])
      ).toString();
      return fetchJSON<Market[]>(`/markets${qs ? `?${qs}` : ""}`);
    },
    get: (id: number) => fetchJSON<Market>(`/markets/${id}`),
  },
};

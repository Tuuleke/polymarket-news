import type { Article, GenerateUpdatesResult, Market } from "@/types";

function getBaseURL() {
  if (typeof window === "undefined") {
    // Server-side: use internal Docker network name
    return `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/v1`;
  }
  // Client-side: go directly to backend, bypassing the Next.js proxy (which times out on slow LLM calls)
  return `${process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"}/api/v1`;
}

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${getBaseURL()}${path}`, { cache: "no-store", ...options });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json() as Promise<T>;
}

function postJSON<T>(path: string): Promise<T> {
  return fetchJSON<T>(path, { method: "POST" });
}

function buildQS(params: Record<string, string | number | undefined>): string {
  const qs = new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => [k, String(v)])
  ).toString();
  return qs ? `?${qs}` : "";
}

export const api = {
  articles: {
    list: (params?: { article_type?: string; limit?: number; offset?: number }) =>
      fetchJSON<Article[]>(`/articles${buildQS(params ?? {})}`),
    get: (id: number) => fetchJSON<Article>(`/articles/${id}`),
  },
  markets: {
    list: (params?: { category?: string }) =>
      fetchJSON<Market[]>(`/markets${buildQS(params ?? {})}`),
    get: (id: number) => fetchJSON<Market>(`/markets/${id}`),
    generateExplanation: (id: number) => postJSON<Article>(`/markets/${id}/explain`),
    generateUpdates: (id: number) =>
      postJSON<GenerateUpdatesResult>(`/markets/${id}/generate-updates`),
  },
};

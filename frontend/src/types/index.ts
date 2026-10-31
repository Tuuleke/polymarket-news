export interface Article {
  id: number;
  market_id: number;
  title: string;
  body: string;
  llm_model: string;
  probability_at_generation: number;
  created_at: string;
  article_type: "explanation" | "update";
  probability_change: number | null;
  snapshot_date: string | null;
}

export interface MarketSnapshot {
  id: number;
  market_id: number;
  date: string;
  probability: number;
}

export interface Market {
  id: number;
  polymarket_id: string;
  question: string;
  category: string;
  probability: number;
  volume: number;
  end_date: string | null;
  fetched_at: string;
  articles: Article[];
  snapshots: MarketSnapshot[];
}

export interface GenerateUpdatesResult {
  generated: number;
  dates: string[];
}

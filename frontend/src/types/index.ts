export interface Market {
  id: number;
  polymarket_id: string;
  question: string;
  category: string;
  probability: number;
  volume: number;
  end_date: string | null;
  fetched_at: string;
}

export interface Article {
  id: number;
  market_id: number;
  title: string;
  body: string;
  llm_model: string;
  probability_at_generation: number;
  created_at: string;
}
